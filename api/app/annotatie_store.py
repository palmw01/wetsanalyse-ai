"""
AnnotatieStore – persistentie voor het annotatie-domein (los van de analyse-`JobStore`).

Zelfde SQLAlchemy-Core-stijl als `postgres_store.py` op dezelfde engine (`db.get_engine()`), maar een
eigen, verse tabelset. Het document draagt de HUIDIGE elementen-staat (JSON); `annotatie_audit` is de
append-only geschiedenis (alleen inserts). Tijd komt uit Python (`db.utcnow`) zodat de queries portable
blijven (SQLite-tests).
"""
from __future__ import annotations

import uuid
from typing import Callable

from sqlalchemy import delete, exists, insert, select, update
from sqlalchemy.exc import IntegrityError

from . import db
from .annotatie_contracts import AgentRun, AnnotatieDocument, AnnotatieElement, AuditRecord, LidStand

# Sentinel: het document bestaat (en is van de client) maar het gevraagde element niet.
GEEN_ELEMENT = object()
# Sentinel: de meegegeven `If-Match` komt niet overeen met de huidige staat (→ 412).
CONFLICT = object()


def etag_van(doc: AnnotatieDocument) -> str:
    """Zwakke ETag uit `updated`. Bewust geen aparte versiekolom: `updated` wordt binnen dezelfde
    transactie gezet als de elementen, dus het is even betrouwbaar en kost geen migratie."""
    return f'W/"{doc.updated.isoformat() if doc.updated else "0"}"'


def laag_sleutel(bwb_id: str, artikel: str) -> str:
    """De sleutel van de gedeelde laag van één artikel: `"{BWBID}:{artikel}"`.

    Genormaliseerd op wat een aanroeper onschuldig anders kan schrijven – hoofdletters in het
    BWB-id, witruimte rond of in het artikelnummer. Méér niet: "3a" en "3A" zijn in de wet
    verschillende artikelen en dat mag de sleutel niet gelijkmaken.
    """
    return f"{bwb_id.strip().upper()}:{''.join(artikel.split())}"


def mag_zien(doc: AnnotatieDocument, user_id: str) -> bool:
    """Een laag is van iedereen; een per-gebruiker-document alleen van zijn eigenaar."""
    return bool(doc.laag_sleutel) or doc.user_id == user_id


def _naar_document(row) -> AnnotatieDocument:
    d = row._mapping
    return AnnotatieDocument(
        slug=d["slug"],
        user_id=d["user_id"] or "",   # legacy-rijen (vóór de migratie) hebben NULL → ""
        client_id=d["client_id"],
        citeertitel=d["citeertitel"] or "",
        werkgebied=d["werkgebied"],
        bwbId=d["bwbId"],
        artikel=d["artikel"],
        lid=d["lid"],
        status=d["status"],
        elementen=[AnnotatieElement.model_validate(e) for e in (d["elementen"] or [])],
        runs=[AgentRun.model_validate(r) for r in (d["runs"] or [])],
        laag_sleutel=d["laag_sleutel"] or "",
        # NULL op rijen van vóór de kolom: `reconcile_schema` voegt hem toe zonder waarde.
        leden={k: LidStand.model_validate(w) for k, w in (d["leden"] or {}).items()},
        created=db.aware(d["created"]),
        updated=db.aware(d["updated"]),
    )


class AnnotatieStore:
    async def maak_document(self, doc: AnnotatieDocument) -> None:
        now = db.utcnow()
        async with db.get_engine().begin() as conn:
            await conn.execute(insert(db.annotatie_documenten).values(
                slug=doc.slug,
                user_id=doc.user_id,
                client_id=doc.client_id,
                citeertitel=doc.citeertitel,
                werkgebied=doc.werkgebied,
                bwbId=doc.bwbId,
                artikel=doc.artikel,
                lid=doc.lid or "",
                status=doc.status.value,
                elementen=[e.model_dump(mode="json") for e in doc.elementen],
                runs=[r.model_dump(mode="json") for r in doc.runs],
                laag_sleutel=doc.laag_sleutel,
                leden={k: w.model_dump(mode="json") for k, w in doc.leden.items()},
                created=now,
                updated=now,
            ))

    async def laad_laag(self, sleutel: str) -> AnnotatieDocument | None:
        async with db.get_engine().connect() as conn:
            row = (await conn.execute(
                select(db.annotatie_documenten).where(db.annotatie_documenten.c.laag_sleutel == sleutel)
            )).first()
        return _naar_document(row) if row else None

    async def haal_of_maak_laag(
        self, bwb_id: str, artikel: str, citeertitel: str, client_id: str,
    ) -> tuple[AnnotatieDocument, bool]:
        """De gedeelde laag van dit artikel, en of hij net is aangemaakt.

        Insert-dan-herlaad in plaats van check-dan-insert: twee Lex-runs op hetzelfde artikel
        tegelijk mogen er geen twee lagen van maken, en dat dwingt de unieke index af – niet deze
        code. Verliest deze aanroep de race, dan leest hij de laag van de winnaar.
        """
        sleutel = laag_sleutel(bwb_id, artikel)
        if (bestaand := await self.laad_laag(sleutel)) is not None:
            return bestaand, False
        doc = AnnotatieDocument(
            slug=uuid.uuid4().hex[:16], client_id=client_id, citeertitel=citeertitel,
            bwbId=bwb_id.strip().upper(), artikel="".join(artikel.split()), laag_sleutel=sleutel,
        )
        try:
            await self.maak_document(doc)
        except IntegrityError:
            winnaar = await self.laad_laag(sleutel)
            if winnaar is None:
                raise
            return winnaar, False
        return await self.laad_laag(sleutel), True  # type: ignore[return-value]

    async def lijst_lagen(
        self, mijn_user_id: str | None = None, bwb_id: str | None = None,
        limit: int = 50, offset: int = 0,
    ) -> list[AnnotatieDocument]:
        """De gedeelde lagen, meest recent eerst. `mijn_user_id` beperkt tot lagen waar die gebruiker
        iets aan deed – dat staat in de audit, want een laag heeft geen eigenaar."""
        t = db.annotatie_documenten
        q = select(t).where(t.c.laag_sleutel != "")
        if bwb_id:
            q = q.where(t.c.bwbId == bwb_id.strip().upper())
        if mijn_user_id:
            a = db.annotatie_audit
            q = q.where(exists().where(a.c.document_slug == t.c.slug, a.c.actor == mijn_user_id))
        async with db.get_engine().connect() as conn:
            rows = (await conn.execute(q.order_by(t.c.updated.desc()).limit(limit).offset(offset))).all()
        return [_naar_document(r) for r in rows]

    async def laad_document(self, slug: str) -> AnnotatieDocument | None:
        async with db.get_engine().connect() as conn:
            row = (await conn.execute(
                select(db.annotatie_documenten).where(db.annotatie_documenten.c.slug == slug)
            )).first()
        return _naar_document(row) if row else None

    async def lijst_documenten(self, user_id: str, limit: int = 50, offset: int = 0) -> list[AnnotatieDocument]:
        async with db.get_engine().connect() as conn:
            rows = (await conn.execute(
                select(db.annotatie_documenten)
                .where(db.annotatie_documenten.c.user_id == user_id)
                .order_by(db.annotatie_documenten.c.updated.desc())
                .limit(limit).offset(offset)
            )).all()
        return [_naar_document(r) for r in rows]

    async def alle_documenten(self, limit: int = 1000) -> list[AnnotatieDocument]:
        """Álle documenten, over gebruikers heen — uitsluitend voor de admin-statistiek.

        Bewust een aparte methode en niet een `user_id=None` op `lijst_documenten`: die functie is de
        per-gebruiker gescopete lijst en dat is een garantie van dit domein. Een optionele parameter
        die de scoping uitzet is precies het soort ding dat later per ongeluk wordt meegegeven.
        """
        async with db.get_engine().connect() as conn:
            rows = (await conn.execute(
                select(db.annotatie_documenten)
                .order_by(db.annotatie_documenten.c.updated.desc())
                .limit(limit)
            )).all()
        return [_naar_document(r) for r in rows]

    async def muteer_document(
        self,
        slug: str,
        user_id: str,
        muteer: Callable[[AnnotatieDocument], object | None],
        if_match: str | None = None,
    ) -> AnnotatieDocument | None | object:
        """Het ENIGE schrijfpad naar `elementen`, `runs` en `status`. Laadt met een row-lock, toetst
        eigenaarschap en `If-Match`, laat `muteer` het document herschikken en schrijft in DEZELFDE
        transactie weg.

        Eén pad met één slot, want twee gelijktijdige schrijvers op dezelfde JSON-kolom overschrijven
        elkaar anders volledig (lost update). Er stond hier eerder ook een `vervang_elementen` zónder
        lock; die is weg – een destructief pad dat blijft rondslingeren wordt vroeg of laat gebruikt.

        `muteer` mag een sentinel teruggeven (bv. `GEEN_ELEMENT`) om de mutatie af te breken; die komt
        dan ongewijzigd terug en er wordt niets geschreven. Retourneert verder het bijgewerkte
        document, `None` (onbekend of niet-eigenaar → 404) of `CONFLICT` (ETag-mismatch → 412).
        Op SQLite is `with_for_update` een no-op, maar serialiseert de transactie de schrijfactie.
        """
        now = db.utcnow()
        async with db.get_engine().begin() as conn:
            row = (await conn.execute(
                select(db.annotatie_documenten)
                .where(db.annotatie_documenten.c.slug == slug)
                .with_for_update()
            )).first()
            if row is None:
                return None
            doc = _naar_document(row)
            if not mag_zien(doc, user_id):
                return None
            if if_match is not None and if_match != etag_van(doc):
                return CONFLICT
            uitkomst = muteer(doc)
            if uitkomst is not None:
                return uitkomst
            await conn.execute(
                update(db.annotatie_documenten)
                .where(db.annotatie_documenten.c.slug == slug)
                .values(
                    elementen=[e.model_dump(mode="json") for e in doc.elementen],
                    runs=[r.model_dump(mode="json") for r in doc.runs],
                    leden={k: w.model_dump(mode="json") for k, w in doc.leden.items()},
                    status=doc.status.value,
                    updated=now,
                )
            )
        doc.updated = now
        return doc

    async def beslis_op_element(
        self,
        slug: str,
        user_id: str,
        element_id: str,
        toepassen: Callable[[AnnotatieDocument, AnnotatieElement], object | None],
    ) -> AnnotatieDocument | None | object:
        """Pas een human-decision atomair toe op één element. Dunne wrapper om `muteer_document`.

        `toepassen` krijgt het hele document mee – de vraag óf er beslist mag worden hangt niet
        alleen van het element af maar ook van de documentstatus, en die toets hoort binnen dezelfde
        row-lock als de mutatie. Geeft het een sentinel terug (bv. `CONFLICT`), dan wordt er niets
        geschreven en komt die sentinel ongewijzigd terug.
        """

        def muteer(doc: AnnotatieDocument):
            el = next((x for x in doc.elementen if x.id == element_id), None)
            if el is None:
                return GEEN_ELEMENT
            return toepassen(doc, el)

        return await self.muteer_document(slug, user_id, muteer)

    async def verwijder_document(self, slug: str) -> None:
        async with db.get_engine().begin() as conn:
            await conn.execute(delete(db.annotatie_audit).where(db.annotatie_audit.c.document_slug == slug))
            await conn.execute(delete(db.annotatie_documenten).where(db.annotatie_documenten.c.slug == slug))

    async def schrijf_audit(
        self, slug: str, client_id: str, actor: str, actie: str,
        element_id: str | None = None, detail: dict | None = None,
    ) -> None:
        """Append-only: voegt één auditregel toe (nooit update/delete)."""
        async with db.get_engine().begin() as conn:
            await conn.execute(insert(db.annotatie_audit).values(
                document_slug=slug, client_id=client_id, actor=actor, actie=actie,
                element_id=element_id, detail=detail or {}, tijdstip=db.utcnow(),
            ))

    async def schrijf_auditregels(self, slug: str, client_id: str, actor: str, regels: list[tuple]) -> None:
        """Meerdere auditregels in één insert: `[(actie, element_id, detail), …]`.

        Een agent-ronde raakt tientallen elementen; per regel een aparte transactie openen zou de
        schrijfactie onnodig oprekken en het log kunnen laten scheuren als er halverwege iets misgaat.
        """
        if not regels:
            return
        nu = db.utcnow()
        async with db.get_engine().begin() as conn:
            await conn.execute(insert(db.annotatie_audit), [
                {
                    "document_slug": slug, "client_id": client_id, "actor": actor,
                    "actie": actie, "element_id": element_id, "detail": detail or {}, "tijdstip": nu,
                }
                for actie, element_id, detail in regels
            ])

    async def lees_audit(self, slug: str, limit: int = 200, offset: int = 0) -> list[AuditRecord]:
        async with db.get_engine().connect() as conn:
            rows = (await conn.execute(
                select(db.annotatie_audit)
                .where(db.annotatie_audit.c.document_slug == slug)
                .order_by(db.annotatie_audit.c.id)
                .limit(limit).offset(offset)
            )).all()
        return [
            AuditRecord(
                id=r._mapping["id"], actor=r._mapping["actor"], actie=r._mapping["actie"],
                element_id=r._mapping["element_id"], detail=r._mapping["detail"] or {},
                tijdstip=db.aware(r._mapping["tijdstip"]),
            )
            for r in rows
        ]
