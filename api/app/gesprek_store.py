"""
GesprekStore – persistentie voor het gesprekken-domein (chatgeschiedenis van de werkplek).

Zelfde SQLAlchemy-Core-stijl als de andere stores, op dezelfde engine (`db.get_engine()`), met een
eigen tabelset (`gesprekken` + `gesprek_berichten`). Per-gebruiker gescopet (`user_id`). De berichten
staan als aparte, geordende rijen; de heterogene beurt-payload zit in de JSON-kolom `inhoud`. Tijd komt
uit Python (`db.utcnow`) zodat de queries portable blijven (SQLite-tests).
"""
from __future__ import annotations

import logging

from pydantic import ValidationError
from sqlalchemy import and_, delete, exists, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from . import db
from .gesprek_contracts import (
    Bericht, BerichtContext, BerichtInvoer, Contextopbouw, Gesprek, GesprekGroep, GesprekSamenvatting, GesprekTelling,
    KindContext,
)

logger = logging.getLogger(__name__)


#: De gestructureerde velden van een bericht: wat de agent erbij legde. Klopt zo'n veld niet meer met het
#: contract van nu – een kaartje met een stap die intussen anders heet, een artefact van een vervallen
#: soort –, dan valt alleen dat veld weg. Anders weigerde de api het hele gesprek (500), en daarmee ook
#: laden én verwijderen: een gesprek is een verslag en moet altijd te openen en weg te halen zijn.
_OPTIONEEL = ("hergebruik", "dekking", "overzicht", "antwoord", "annotatie_doel", "tool_executions", "reeks", "artefact",
              "bevestiging", "bevestiging_antwoord", "vraagkaart", "intake_antwoord", "uitkomst", "contextopbouw")


#: Hoeveel deelgesprekken de boom van de contextopbouw hooguit leest: ruim boven een regie (hoogstens tientallen).
MAX_KINDEREN = 200


def _bericht_uit_row(row) -> Bericht:
    d = row._mapping
    inhoud = d["inhoud"] or {}
    velden = dict(
        id=d["id"],
        rol=d["rol"],
        tekst=inhoud.get("tekst", ""),
        denk=inhoud.get("denk", ""),
        bronnen=inhoud.get("bronnen", []) or [],
        annotatie_slug=inhoud.get("annotatie_slug", ""),
        annotatie_titel=inhoud.get("annotatie_titel", ""),
        run_id=inhoud.get("run_id", ""),
        hergebruik=inhoud.get("hergebruik", {}) or {},
        dekking=inhoud.get("dekking", {}) or {},
        overzicht=inhoud.get("overzicht", {}) or {},
        antwoord=inhoud.get("antwoord") or None,
        annotatie_doel=inhoud.get("annotatie_doel") or None,
        tool_executions=inhoud.get("tool_executions", []) or [],
        reeks=inhoud.get("reeks") or None,
        artefact=inhoud.get("artefact") or None,
        bevestiging=inhoud.get("bevestiging") or None,
        bevestiging_antwoord=inhoud.get("bevestiging_antwoord") or None,
        vraagkaart=inhoud.get("vraagkaart") or None,
        intake_antwoord=inhoud.get("intake_antwoord") or None,
        uitkomst=inhoud.get("uitkomst") or None,
        grounding=inhoud.get("grounding", {}) or {},
        contextopbouw=inhoud.get("contextopbouw") or None,
        created=db.aware(d["created"]),
    )
    try:
        return Bericht(**velden)
    except ValidationError as fout:
        weg = sorted({str(e["loc"][0]) for e in fout.errors() if e["loc"] and e["loc"][0] in _OPTIONEEL})
        if not weg:
            raise
        logger.warning("bericht: veraald veld weggelaten",
                       extra={"categorie": "functioneel", "bericht_id": d["id"], "velden": weg})
        return Bericht(**{**velden, **{k: Bericht.model_fields[k].get_default(call_default_factory=True)
                                       for k in weg}})


def _inhoud(inv: BerichtInvoer | Bericht) -> dict:
    """De heterogene beurt-payload → de JSON-kolom (weglaten wat leeg is houdt de rij compact)."""
    inhoud: dict = {"tekst": inv.tekst}
    if inv.denk:
        inhoud["denk"] = inv.denk
    if inv.bronnen:
        inhoud["bronnen"] = inv.bronnen
    if inv.annotatie_slug:
        inhoud["annotatie_slug"] = inv.annotatie_slug
    if inv.annotatie_titel:
        inhoud["annotatie_titel"] = inv.annotatie_titel
    if inv.hergebruik:
        inhoud["hergebruik"] = inv.hergebruik
    if inv.dekking:
        inhoud["dekking"] = inv.dekking
    if inv.overzicht:
        inhoud["overzicht"] = inv.overzicht
    if inv.antwoord:
        inhoud["antwoord"] = inv.antwoord.model_dump()
    if inv.annotatie_doel:
        inhoud["annotatie_doel"] = inv.annotatie_doel.model_dump()
    if inv.tool_executions:
        inhoud["tool_executions"] = inv.tool_executions
    if inv.run_id:
        inhoud["run_id"] = inv.run_id
    if inv.reeks:
        inhoud["reeks"] = inv.reeks.model_dump()
    if inv.artefact:
        inhoud["artefact"] = inv.artefact.model_dump()
    if inv.bevestiging:
        inhoud["bevestiging"] = inv.bevestiging.model_dump()
    if inv.bevestiging_antwoord:
        inhoud["bevestiging_antwoord"] = inv.bevestiging_antwoord.model_dump()
    if inv.vraagkaart:
        inhoud["vraagkaart"] = inv.vraagkaart.model_dump()
    if inv.intake_antwoord:
        inhoud["intake_antwoord"] = inv.intake_antwoord.model_dump()
    if inv.uitkomst:
        inhoud["uitkomst"] = inv.uitkomst.model_dump()
    if inv.grounding:
        inhoud["grounding"] = inv.grounding
    if inv.contextopbouw:
        inhoud["contextopbouw"] = inv.contextopbouw.model_dump()
    return inhoud


class GesprekStore:
    async def maak_gesprek(self, gesprek: Gesprek) -> None:
        now = db.utcnow()
        async with db.get_engine().begin() as conn:
            await conn.execute(insert(db.gesprekken).values(
                id=gesprek.id,
                user_id=gesprek.user_id,
                titel=gesprek.titel,
                werkgebied_id=gesprek.werkgebied_id,
                ouder_id=gesprek.ouder_id,
                delegatie_id=gesprek.delegatie_id,
                profiel=gesprek.profiel,
                created=now,
                updated=now,
            ))

    async def eigenaar_van(self, gesprek_id: str) -> str | None:
        """De eigenaar zonder de berichten: een schrijfroute hoeft het hele gesprek niet te laden."""
        async with db.get_engine().connect() as conn:
            return (await conn.execute(
                select(db.gesprekken.c.user_id).where(db.gesprekken.c.id == gesprek_id)
            )).scalar_one_or_none()

    async def laad_gesprek(self, gesprek_id: str) -> Gesprek | None:
        async with db.get_engine().connect() as conn:
            row = (await conn.execute(
                select(db.gesprekken).where(db.gesprekken.c.id == gesprek_id)
            )).first()
            if row is None:
                return None
            berichten = (await conn.execute(
                select(db.gesprek_berichten)
                .where(db.gesprek_berichten.c.gesprek_id == gesprek_id)
                .order_by(db.gesprek_berichten.c.id)
            )).all()
        d = row._mapping
        return Gesprek(
            id=d["id"],
            user_id=d["user_id"],
            titel=d["titel"],
            werkgebied_id=d["werkgebied_id"] or "",
            ouder_id=d["ouder_id"] or "",
            delegatie_id=d["delegatie_id"] or "",
            profiel=d["profiel"] or "",
            gearchiveerd=db.aware(d["gearchiveerd"]),
            connectors=d["connectors"],
            berichten=[_bericht_uit_row(b) for b in berichten],
            created=db.aware(d["created"]),
            updated=db.aware(d["updated"]),
        )

    async def lijst_samenvattingen(
        self, user_id: str, limit: int = 100, offset: int = 0,
        werkgebied_id: str | None = None, gearchiveerd: bool | None = None, zoek: str = "",
        ouder_id: str | None = None,
    ) -> list[GesprekSamenvatting]:
        """Eigen gesprekken, nieuwste eerst. `werkgebied_id=""` geeft alleen de losse gesprekken;
        `gearchiveerd=None` geeft actief én gearchiveerd. `zoek` zoekt (hoofdletterongevoelig) in de titel
        en in de tekst van de berichten; `%` en `_` tellen daarbij als gewone tekens."""
        g, b, w = db.gesprekken, db.gesprek_berichten, db.werkgebieden
        aantal = func.count(b.c.id).label("aantal")
        q = (
            select(g, aantal, w.c.naam.label("werkgebied_naam"))
            .select_from(g.outerjoin(b, g.c.id == b.c.gesprek_id).outerjoin(w, g.c.werkgebied_id == w.c.id))
            .where(g.c.user_id == user_id)
        )
        if werkgebied_id is not None:
            q = q.where(g.c.werkgebied_id == werkgebied_id)
        if ouder_id is not None:
            q = q.where(g.c.ouder_id == ouder_id)
        if gearchiveerd is not None:
            q = q.where(g.c.gearchiveerd.is_not(None) if gearchiveerd else g.c.gearchiveerd.is_(None))
        if zoek.strip():
            # De tekst staat in de JSON van het bericht; `as_string()` is `->>` op Postgres en
            # `json_extract` op SQLite. Een subquery en geen filter op de join: die join telt ook
            # de berichten, en een filter erop zou `aantal_berichten` laten krimpen.
            patroon = "%" + zoek.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            zb = db.gesprek_berichten.alias("zb")
            q = q.where(or_(
                g.c.titel.ilike(patroon, escape="\\"),
                exists().where(zb.c.gesprek_id == g.c.id,
                               zb.c.inhoud["tekst"].as_string().ilike(patroon, escape="\\")),
            ))
        q = q.group_by(g.c.id, w.c.naam).order_by(g.c.updated.desc(), g.c.id).limit(limit).offset(offset)
        async with db.get_engine().connect() as conn:
            rows = (await conn.execute(q)).all()
        return [
            GesprekSamenvatting(
                id=r._mapping["id"],
                titel=r._mapping["titel"],
                aantal_berichten=r._mapping["aantal"],
                updated=db.aware(r._mapping["updated"]),
                werkgebied_id=r._mapping["werkgebied_id"] or "",
                werkgebied_naam=r._mapping["werkgebied_naam"] or "",
                ouder_id=r._mapping["ouder_id"] or "",
                delegatie_id=r._mapping["delegatie_id"] or "",
                profiel=r._mapping["profiel"] or "",
                gearchiveerd=db.aware(r._mapping["gearchiveerd"]),
            )
            for r in rows
        ]

    async def contextopbouw_van_kinderen(self, ouder_id: str, user_id: str) -> list[KindContext]:
        """De deelgesprekken van `ouder_id` (alleen die van deze gebruiker) met de contextopbouw van hun
        assistentberichten, oudste gesprek eerst. Een kind zonder meting staat erin met een lege lijst: de werkplek
        zegt dan "loopt nog" of "niet gemeten". Een veld dat niet meer bij het contract past, valt weg zoals bij het
        laden van een gesprek; het breekt de boom niet."""
        g, b = db.gesprekken, db.gesprek_berichten
        async with db.get_engine().connect() as conn:
            kinderen = (await conn.execute(
                select(g.c.id, g.c.titel, g.c.updated)
                .where(g.c.ouder_id == ouder_id, g.c.user_id == user_id)
                .order_by(g.c.created, g.c.id).limit(MAX_KINDEREN)
            )).all()
            ids = [k.id for k in kinderen]
            rijen = (await conn.execute(
                select(b.c.id, b.c.gesprek_id, b.c.inhoud, b.c.created)
                .where(b.c.gesprek_id.in_(ids), b.c.rol == "assistant").order_by(b.c.id)
            )).all() if ids else []
        per_kind: dict[str, list[BerichtContext]] = {i: [] for i in ids}
        for r in rijen:
            inhoud = r.inhoud or {}
            if not inhoud.get("contextopbouw"):
                continue
            try:
                opbouw = Contextopbouw(**inhoud["contextopbouw"])
            except (ValidationError, TypeError):
                logger.warning("bericht: veraald veld weggelaten",
                               extra={"categorie": "functioneel", "bericht_id": r.id, "velden": ["contextopbouw"]})
                continue
            per_kind[r.gesprek_id].append(BerichtContext(
                bericht_id=r.id, run_id=inhoud.get("run_id", ""), created=db.aware(r.created), contextopbouw=opbouw))
        return [KindContext(gesprek_id=k.id, titel=k.titel or "", updated=db.aware(k.updated), berichten=per_kind[k.id])
                for k in kinderen]

    @staticmethod
    async def _bericht_van_run(conn, gesprek_id: str, run_id: str) -> Bericht | None:
        """Staat de uitkomst van deze run er al? Kijkt alleen naar de staart van het gesprek: een
        run schrijft aan het eind van zijn eigen beurt, dus verder terug zoeken heeft geen zin."""
        rows = (await conn.execute(
            select(db.gesprek_berichten)
            .where(db.gesprek_berichten.c.gesprek_id == gesprek_id)
            .order_by(db.gesprek_berichten.c.id.desc())
            .limit(20)
        )).fetchall()
        for row in rows:
            if (row._mapping["inhoud"] or {}).get("run_id") == run_id:
                return _bericht_uit_row(row)
        return None

    async def voeg_bericht_toe(self, gesprek_id: str, inv: BerichtInvoer) -> Bericht:
        """Voeg één beurt toe. Append-only, behalve dat een `run_id` maar één keer mag landen.

        Die uitzondering is er omdat een agent-run niet meer aan één browserverbinding hangt: er
        kunnen meerdere tabbladen op dezelfde run meekijken, en die zouden anders elk hun eigen kopie
        van hetzelfde antwoord wegschrijven. De controle staat bewust ín dezelfde transactie als de
        insert. Er is géén unieke index: `reconcile_schema` voegt op bestaande tabellen alleen
        kolommen toe, en de index op (gesprek_id, id) maakt deze check goedkoop.

        De check blijft staan omdat hij het normale geval goedkoop afhandelt (en het bestaande
        bericht kan teruggeven), maar hij is niet meer de enige bescherming: `run_id` is een eigen
        kolom met een partiële unieke index. Verliest een tweede schrijver de race, dan botst hij op
        de database en lezen we alsnog het bericht dat er inmiddels staat.
        """
        now = db.utcnow()
        async with db.get_engine().begin() as conn:
            if inv.run_id:
                bestaand = await self._bericht_van_run(conn, gesprek_id, inv.run_id)
                if bestaand is not None:
                    return bestaand
            try:
                # In een SAVEPOINT: op Postgres aborteert een IntegrityError de hele transactie,
                # waarna de herstelquery hieronder óók zou falen ("current transaction is aborted").
                # Op SQLite valt dat niet op — precies het soort verschil dat pas in productie
                # opduikt.
                async with conn.begin_nested():
                    result = await conn.execute(insert(db.gesprek_berichten).values(
                        gesprek_id=gesprek_id,
                        rol=inv.rol.value,
                        inhoud=_inhoud(inv),
                        run_id=inv.run_id or "",
                        created=now,
                    ))
            except IntegrityError:
                # De unieke index sloeg toe: een andere schrijver was ons net voor met dezelfde run.
                # Dat is precies de race die de check hierboven niet kan dichten; het antwoord is
                # hetzelfde als daar — geef terug wat er staat.
                bestaand = await self._bericht_van_run(conn, gesprek_id, inv.run_id)
                if bestaand is not None:
                    return bestaand
                raise
            # Bump het gesprek zodat de sidebar-sortering (updated desc) meeloopt.
            await conn.execute(
                update(db.gesprekken)
                .where(db.gesprekken.c.id == gesprek_id)
                .values(updated=now)
            )
            nieuw_id = result.inserted_primary_key[0] if result.inserted_primary_key else None
        # Het hele bericht terug, niet een deel: wie het antwoord gebruikt, krijgt wat er staat.
        return Bericht(id=nieuw_id, created=db.aware(now), **inv.model_dump())

    async def wijzig_gesprek(
        self, gesprek_id: str, *, titel: str | None = None,
        werkgebied_id: str | None = None, gearchiveerd: bool | None = None,
        connectors: list[str] | None = None, connectors_zetten: bool = False,
    ) -> None:
        """Titel, werkgebied of archief. Alleen een nieuwe titel telt als bijwerken (`updated`):
        verplaatsen of archiveren mag een gesprek niet bovenaan de lijst zetten."""
        waarden: dict = {}
        if titel is not None:
            waarden.update(titel=titel, updated=db.utcnow())
        if werkgebied_id is not None:
            # Een ander werkgebied maakt een deelgesprek los: de ouder hoort bij het oude.
            waarden.update(werkgebied_id=werkgebied_id, ouder_id="", delegatie_id="")
        if gearchiveerd is not None:
            waarden["gearchiveerd"] = db.utcnow() if gearchiveerd else None
        if connectors_zetten:
            # Geen `updated`: het menu omzetten zet een gesprek niet bovenaan de lijst.
            waarden["connectors"] = list(dict.fromkeys(connectors)) if connectors is not None else None
        if not waarden:
            return
        async with db.get_engine().begin() as conn:
            await conn.execute(update(db.gesprekken).where(db.gesprekken.c.id == gesprek_id).values(**waarden))

    async def verwijder_gesprek(self, gesprek_id: str) -> None:
        async with db.get_engine().begin() as conn:
            await self._wis(conn, [gesprek_id])

    @staticmethod
    async def _wis(conn, ids: list[str]) -> None:
        """Berichten en gesprekken weg, in de transactie van de aanroeper. De deelgesprekken blijven: het zijn
        verslagen. Ze worden los, zoals bij een gewist werkgebied."""
        g, b = db.gesprekken, db.gesprek_berichten
        for stuk in _stukken(ids):
            await conn.execute(delete(b).where(b.c.gesprek_id.in_(stuk)))
            await conn.execute(delete(g).where(g.c.id.in_(stuk)))
            await conn.execute(update(g).where(g.c.ouder_id.in_(stuk)).values(ouder_id="", delegatie_id=""))

    # ── Opruimen per groep (instellingen → Gesprekken) ────────────────────────────────────────────

    async def telling(self, user_id: str) -> GesprekTelling:
        g = db.gesprekken
        async with db.get_engine().connect() as conn:
            aantallen = {
                groep: (await conn.execute(
                    select(func.count()).select_from(g).where(g.c.user_id == user_id, _groep_filter(groep))
                )).scalar_one()
                for groep in ("recent", "archief")
            }
        return GesprekTelling(**aantallen)

    async def ids_in_groep(self, user_id: str, groep: GesprekGroep) -> list[str]:
        g = db.gesprekken
        async with db.get_engine().connect() as conn:
            return list((await conn.execute(
                select(g.c.id).where(g.c.user_id == user_id, _groep_filter(groep)).order_by(g.c.id)
            )).scalars())

    async def _doorsnede(self, conn, user_id: str, groep: GesprekGroep, ids: list[str]) -> list[str]:
        """De ids uit de lijst die van deze gebruiker zijn en nú in de groep staan. Andermans id of een gesprek
        dat intussen verhuisde, valt eruit zonder fout: opruimen is geen plek om te raden."""
        g = db.gesprekken
        gevonden: list[str] = []
        for stuk in _stukken(list(dict.fromkeys(ids))):
            gevonden += (await conn.execute(
                select(g.c.id).where(g.c.id.in_(stuk), g.c.user_id == user_id, _groep_filter(groep))
            )).scalars()
        return sorted(gevonden)

    async def verwijder_gesprekken(self, user_id: str, groep: GesprekGroep, ids: list[str]) -> list[str]:
        """Wis in één transactie de eigen gesprekken uit `ids` die in de groep staan; geeft terug wat wegging."""
        async with db.get_engine().begin() as conn:
            weg = await self._doorsnede(conn, user_id, groep, ids)
            await self._wis(conn, weg)
        return weg

    async def archiveer_gesprekken(self, user_id: str, groep: GesprekGroep, ids: list[str]) -> list[str]:
        """Archiveer in één keer; `updated` blijft staan, net als bij één gesprek (de volgorde verschuift niet)."""
        g = db.gesprekken
        nu = db.utcnow()
        async with db.get_engine().begin() as conn:
            doel = await self._doorsnede(conn, user_id, groep, ids)
            for stuk in _stukken(doel):
                await conn.execute(update(g).where(g.c.id.in_(stuk)).values(gearchiveerd=nu))
        return doel


def _groep_filter(groep: GesprekGroep):
    """De afbakening van een groep, op één plek: telling, ids en wissen gebruiken dezelfde."""
    g = db.gesprekken
    if groep == "recent":
        return and_(g.c.gearchiveerd.is_(None), g.c.werkgebied_id == "")
    return g.c.gearchiveerd.is_not(None)


def _stukken(ids: list[str], grootte: int = 500):
    """Per 500: een `IN` met duizenden parameters loopt op SQLite tegen zijn limiet aan."""
    for i in range(0, len(ids), grootte):
        yield ids[i:i + grootte]
