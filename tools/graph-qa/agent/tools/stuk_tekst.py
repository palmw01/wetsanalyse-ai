"""Wat elke leestool van een bronconnector deelt over de tekst van een stuk (ADR-013): de inhoud met offsets voor de
eerste pagina, de kop alleen waar hij verandert, en de pagina zelf (`tekstpagina`). Eén plek, zodat een tweede connector
haar niet kopieert en het bronvenster overal dezelfde vorm ziet."""
from __future__ import annotations

import json
from typing import Any, Sequence

from ..resultaat import BUDGET, per_eenheid

#: Zo veel koppen staan hoogstens in `inhoud` op de eerste pagina: het diepste niveau dat past (`inhoud_van`).
MAX_INHOUD = 40
#: Een kop op het bovenste niveau draagt het begin van zijn eerste alinea mee, tot hoogstens zo veel tekens: de aanhef
#: van een wijzigingsartikel ("De Invorderingswet 1990 wordt als volgt gewijzigd:"). Zonder die regel opende het model
#: elk artikel van een verzamelwet om te zien welke regeling het wijzigt (meting bekendmakingen B16: negen pagina's,
#: 338k tokens). Een langere alinea wordt afgekapt op een woordgrens, met `begint_afgekapt` (hermeting 11 nov 2026: met
#: alleen alinea's tot deze lengte vielen acht artikelen van Stb. 2009, 610 weg, en de regeling staat vooraan).
MAX_BEGIN = 160


def begin_van(tekst: str) -> tuple[str, bool]:
    """Het begin van een alinea tot `MAX_BEGIN` tekens, afgekapt op een woordgrens, en of er is afgekapt. Geen
    weglatingsteken: het begin is letterlijk de bron, en dat het niet de hele alinea is, zegt de vlag."""
    tekst = " ".join(tekst.split())
    if len(tekst) <= MAX_BEGIN:
        return tekst, False
    knip = tekst[:MAX_BEGIN + 1].rsplit(" ", 1)[0] if " " in tekst[:MAX_BEGIN + 1] else tekst[:MAX_BEGIN]
    return knip.rstrip(" ,;:"), True

#: Velden die een rij alleen draagt als ze anders zijn dan op de rij ervoor op dezelfde pagina. De kop staat anders op
#: elke alinea van een sectie: bij ECLI:NL:HR:2022:50 ~900 van de ~8500 tekens, en dan past de uitspraak niet op één
#: pagina en haalt het model het vervolg op (derde meting 10 nov 2026: 72k tokens in plaats van 47k).
HERHAALD = ("kop",)


#: Het argument van elke leestool waarmee Lex alleen de inhoud van een stuk leest, met alle koppen (`inhoudpagina`). Eén
#: schema, zodat de drie leestools het gelijk beschrijven.
INHOUD_ARG = {"type": "boolean", "description": "true: alleen de inhoud van het stuk: de koppen op het bovenste niveau met "
                                                 "hun offset en het begin van hun eerste alinea, en de diepere koppen met hun "
                                                 "naam en 'diepte' zo ver als in één antwoord past, per pagina. Gebruik het als "
                                                 "de eerste pagina 'inhoud_openen' noemt (de inhoud is ingekort, zonder het begin "
                                                 "van de delen, of er zijn diepere koppen), of om te zien waar een deel staat."}


def koppen(rijen: Sequence[dict[str, Any]], diepte: int | None = None, *, met_begin: bool = True) -> list[dict[str, Any]]:
    """De koppen van een stuk tot `diepte` niveaus (alles bij None), elk één keer, met de offset van hun eerste rij. Een kop
    op het bovenste niveau draagt het begin van zijn eerste alinea (`begint`, `begin_van`), behalve zonder `met_begin`."""
    uit: list[dict[str, Any]] = []
    gezien: set[str] = set()
    for i, r in enumerate(rijen):
        delen = str(r.get("kop") or "").split(" › ")
        kop = " › ".join(delen[:diepte] if diepte else delen)
        if kop and kop not in gezien:
            gezien.add(kop)
            begin: dict[str, Any] = {}
            if (met_begin and " › " not in kop and r.get("kop") == kop
                    and (tekst := str(r.get("tekst") or "").strip())):
                stuk, afgekapt = begin_van(tekst)
                begin = {"begint": stuk, **({"begint_afgekapt": True} if afgekapt else {})}
            uit.append({"kop": kop, "offset": i, **begin})
    return uit


def inhoud_van(rijen: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool, bool]:
    """De inhoud voor de eerste pagina: (koppen, ingekort, zonder het begin). Het diepste niveau dat helemaal past
    (hoogstens `MAX_INHOUD` koppen en een kwart van de begroting: de inhoud wijst de weg, de alinea's zijn de inhoud), op
    elk niveau eerst met `begint` en dan zonder – meer koppen gaan voor het begin, want het bronvenster en de sprong naar
    een deel hebben de koppen nodig, en het begin staat op de inhoudpagina. Past zelfs het bovenste niveau zonder begin
    niet, dan het begin van die lijst. Leeg bij één kop."""
    def past(lijst: list[dict[str, Any]]) -> bool:
        return len(lijst) <= MAX_INHOUD and len(json.dumps(lijst, ensure_ascii=False)) <= BUDGET // 4

    # Elke diepte, van diep naar ondiep: eerst stond hier (alles, 2, 1), en dan kreeg een begroting met vijf niveaus de
    # zeven koppen van niveau 2 terwijl de 32 van niveau 3 pasten. Het model zocht "Artikel 1 Belastingen" toen met vijf
    # offsets (ronde 2 Kamerstukken, 11 nov 2026, K15: kst-36200-IX-2).
    diepst = max((len(str(r.get("kop") or "").split(" › ")) for r in rijen if r.get("kop")), default=1)
    for diepte in (None, *range(diepst - 1, 0, -1)):
        for met in (True, False):
            if past(lijst := koppen(rijen, diepte, met_begin=met)):
                if len(lijst) <= 1:
                    return [], False, False
                return lijst, False, not met and any("begint" in k for k in koppen(rijen, 1))
    lijst = koppen(rijen, 1, met_begin=False)
    while lijst and not past(lijst):
        lijst = lijst[:-1]
    return lijst, True, True


def inhoud(rijen: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """De koppen van het stuk met de offset waar ze beginnen, voor de eerste pagina, en of dat alle koppen zijn
    (`inhoud_van`). Zo springt Lex naar het deel dat de vraag raakt in plaats van het stuk pagina voor pagina te lezen
    (acceptatie 8 nov 2026: twee pagina's gelezen, de artikelsgewijze toelichting niet)."""
    lijst, ingekort, _ = inhoud_van(rijen)
    return lijst, not ingekort


def _zonder_gaten(rijen: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    """De velden uit `HERHAALD` die na hun eerste voorkomen op elke rij staan. Alleen die mogen wegvallen bij een
    herhaling: een rij zonder kop midden in het stuk zou bij het aanvullen anders de kop van de rij ervoor krijgen."""
    uit = []
    for veld in HERHAALD:
        gezien = False
        for r in rijen:
            if r.get(veld):
                gezien = True
            elif gezien:
                break
        else:
            uit.append(veld)
    return tuple(uit)


def aangevuld(data: dict[str, Any]) -> list[dict[str, Any]]:
    """De rijen van één pagina met elk veld dat de pagina bij een herhaling weglaat (`zonder_herhaling`) weer op elke
    rij: de lezer van een pagina (het blok `extern`) krijgt de kop van een passage ook als die alinea midden in een
    sectie staat."""
    rijen = [r for r in data.get("resultaten") or [] if isinstance(r, dict)]
    velden = [v for v in data.get("zonder_herhaling") or [] if isinstance(v, str)]
    uit: list[dict[str, Any]] = []
    vorige: dict[str, Any] = {}
    for r in rijen:
        r = dict(r)
        for veld in velden:
            if r.get(veld):
                vorige[veld] = r[veld]
            elif veld in vorige:
                r[veld] = vorige[veld]
        uit.append(r)
    return uit


def _met_inhoud(rijen: list[dict[str, Any]], tool: str, args: dict[str, Any], *, sleutel: str) -> dict[str, Any]:
    """De inhoud van `rijen` onder `sleutel`. Ontbreken er koppen (`inhoud_ingekort`) of het begin van de delen
    (`inhoud_zonder_begin`), dan `inhoud_openen`: de aanroep die de hele inhoud met het begin geeft (`inhoudpagina`).
    Zonder dat wist het model niet hoe het verder kwam, en bladerde het de tekst door (hermeting bekendmakingen 11 nov
    2026, B16: 11 van de 30 artikelen van Stb. 2009, 610, zonder de regeling die ze wijzigen)."""
    inh, ingekort, zonder_begin = inhoud_van(rijen)
    openen = {"inhoud_openen": {"tool": tool, "args": {"id": args["id"], "inhoud": True}}}
    # Staan er diepere koppen in het stuk dan in deze inhoud, en toont de inhoudpagina ze, dan zegt de pagina dat
    # (`inhoud_dieper`): bij kst-36200-IX-2 stonden zeven koppen van niveau 2 als hele inhoud, en zocht het model
    # "Artikel 1 Belastingen" met vijf offsets (ronde 2 Kamerstukken, K15).
    dieper = bool(inh) and not ingekort and _diepte_inhoudpagina(rijen) > max(_diepte(k["kop"]) for k in inh)
    return {**({sleutel: inh} if inh else {}), **({"inhoud_ingekort": True} if ingekort else {}),
            **({"inhoud_zonder_begin": True} if zonder_begin and not ingekort else {}),
            **({"inhoud_dieper": True} if dieper else {}),
            **(openen if ingekort or zonder_begin or dieper else {})}


def _diepte(kop: str) -> int:
    return len(str(kop or "").split(" › "))


def _bovenste(rijen: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """De koppen op het bovenste niveau voor de inhoudpagina, met hun eerste alinea als rij als die kort genoeg is."""
    lijst = []
    for k in koppen(rijen, 1):
        r = rijen[k["offset"]]
        tekst = str(r.get("tekst") or "")
        if "begint" in k and isinstance(r.get("nr"), int) and len(tekst) <= MAX_AANHEF:
            k = {"nr": r["nr"], "kop": k["kop"], "offset": k["offset"], "tekst": tekst}
        lijst.append(k)
    return lijst


def _inhoudpagina_koppen(rijen: Sequence[dict[str, Any]], diepte: int) -> list[dict[str, Any]]:
    """De koppen van de inhoudpagina tot `diepte`: het bovenste niveau als nu, en een diepere kop met alleen zijn eigen
    naam en zijn `diepte` (het pad zou elke kop een veelvoud zo lang maken), in documentvolgorde."""
    lijst = _bovenste(rijen)
    if diepte > 1:
        # Per niveau apart: een kop van niveau 2 zonder eigen alinea's staat anders niet boven zijn kinderen.
        lijst += [{"kop": k["kop"].split(" › ")[-1], "diepte": niveau, "offset": k["offset"]}
                  for niveau in range(2, diepte + 1)
                  for k in koppen(rijen, niveau, met_begin=False) if _diepte(k["kop"]) == niveau]
        lijst.sort(key=lambda k: (k["offset"], k.get("diepte", 1)))
    return lijst


def _diepte_inhoudpagina(rijen: Sequence[dict[str, Any]]) -> int:
    """Het diepste niveau waarop de inhoudpagina in één antwoord past, hoogstens het diepste van het stuk; het bovenste
    niveau als zelfs het tweede niet past (een verzamelwet: de artikelen met hun aanhef, zoals eerst)."""
    diepst = max((_diepte(r.get("kop")) for r in rijen if r.get("kop")), default=1)
    for d in range(diepst, 1, -1):
        if len(json.dumps(_inhoudpagina_koppen(rijen, d), ensure_ascii=False)) <= BUDGET * 3 // 4:
            return d
    return 1


#: Zo lang mag de eerste alinea van een deel zijn om op de inhoudpagina helemaal te staan, als rij met haar `nr`: dan is
#: ze citeerbaar in het blok `extern` (controle 11 nov 2026, B16: de aanhef per artikel stond alleen als begin in de inhoud,
#: en het model citeerde de hele eerste pagina). Een langere alinea staat er als begin (`begint`), en Lex leest haar vanaf
#: de offset.
MAX_AANHEF = BUDGET // 8


def inhoudpagina(rijen: list[dict[str, Any]], *, tool: str, args: dict[str, Any], offset: int,
                 stuk: dict[str, Any]) -> str:
    """Alleen de inhoud van een stuk: de koppen op het bovenste niveau (`koppen`) met hun offset, en daaronder zo diep als in
    één antwoord past (`_diepte_inhoudpagina`, een diepere kop met alleen zijn naam en `diepte`; ronde 3 Kamerstukken), per pagina – het niveau
    waarop een ingekorte inhoud stopt (`inhoud`), en bij een verzamelwet de artikelen met de regeling die ze wijzigen.
    Per kop de eerste alinea als rij (`nr`, `tekst`, letterlijk en dus te citeren) als die hoogstens `MAX_AANHEF` tekens
    telt, anders haar begin (`begint`, `begint_afgekapt`). De offsets wijzen in de tekst (een aanroep zonder `inhoud`), de
    paginering van deze aanroep loopt over de koppen. Een dieper deel staat in de tekst vanaf de offset van zijn kop.

    Een stuk zonder koppen (een oud Kamerstuk, een korte brief) zegt dat met `zonder_koppen` en het aantal alinea's, met
    de lezing vanaf het begin in `lezen`. Eerst was het resultaat leeg en las de statusregel "geen tekst"; het model bladerde
    dan pagina voor pagina, of gaf het stuk op (ronde 1 Kamerstukken, 11 nov 2026: K07 en K16). Een stuk zonder tekst zegt
    `leesbaar: false`, zoals bij `tekstpagina`."""
    if not rijen:
        stuk = {**stuk, "leesbaar": False}
    diepte = _diepte_inhoudpagina(rijen) if rijen else 1
    lijst = _inhoudpagina_koppen(rijen, diepte)
    if rijen and not lijst:
        alineas = sum(1 for r in rijen if r.get("soort") != "voetnoot")
        lezen = {"tool": tool, "args": {"id": args["id"], "offset": 0}}
        return per_eenheid([], tool=tool, args={"id": args["id"], "inhoud": True}, offset=offset,
                           extra={"stuk": stuk, "totaal": 0, "zonder_koppen": True, "alineas": alineas, "lezen": lezen},
                           toelichting=f"Dit stuk heeft geen koppen; de tekst telt {alineas} "
                                       f"{'alinea' if alineas == 1 else 'alinea’s'}. Lees de tekst vanaf het begin "
                                       f"met {{\"id\": \"{args['id']}\", \"offset\": 0}}.")
    return per_eenheid(lijst, tool=tool, args={"id": args["id"], "inhoud": True}, offset=offset,
                       extra={"stuk": stuk, "totaal": len(lijst)},
                       toelichting="De koppen van het stuk met hun eerste alinea; 'offset' is de plek in de tekst: lees "
                                   f"vanaf daar met {{\"id\": \"{args['id']}\", \"offset\": <offset>}}. Een rij met nr "
                                   "en tekst kun je citeren."
                                   + (f" Een kop met 'diepte' (tot niveau {diepte}) draagt alleen zijn eigen naam en hoort "
                                      "bij de kop met een lagere diepte erboven." if diepte > 1 else ""))


def tekstpagina(rijen: list[dict[str, Any]], *, tool: str, args: dict[str, Any], offset: int, stuk: dict[str, Any],
                extra: dict[str, Any] | None = None, toelichting: str = "",
                publicatie: list[dict[str, Any]] | None = None) -> str:
    """Een pagina van de tekst van een stuk, voor elke leestool dezelfde vorm.

    - De kop alleen waar hij verandert (`HERHAALD`); de eerste rij van een pagina draagt hem altijd.
    - Op de eerste pagina `inhoud`, behalve als het hele stuk zonder past en met niet: dan staan de koppen al in de rijen,
      en één pagina scheelt het model een ronde.
    - Is de lezing gefilterd (een artikel, een regeling), dan geeft de aanroeper de rijen van het hele stuk mee als
      `publicatie`, en draagt de pagina `inhoud_publicatie`: de koppen van het hele stuk met hun offset in een lezing
      zonder filter. Zo leest Lex gericht door (de inwerkingtreding, de toelichting bij het onderdeel) in plaats van het
      hele stuk (hermeting 11 nov 2026, B08: 86k tegen 24k).
    - Een stuk zonder tekst zegt `leesbaar: false` in `stuk`, zoals een stuk dat de bron niet als tekst heeft."""
    if not rijen and not publicatie:
        stuk = {**stuk, "leesbaar": False}
    velden = _zonder_gaten(rijen)
    # De pagina zegt welke velden bij een herhaling wegvallen, zodat een lezer alleen dan aanvult (een tabelpagina doet
    # het niet: haar rijen hebben geen kop).
    basis = {"stuk": stuk, **(extra or {}), "totaal": len(rijen), **({"zonder_herhaling": list(velden)} if velden else {})}

    def maak(met: dict[str, Any]) -> str:
        return per_eenheid(rijen, tool=tool, args=args, offset=offset, extra=met, toelichting=toelichting,
                           zonder_herhaling=velden)

    if offset != 0:
        return maak(basis)
    if publicatie is not None:
        return maak({**basis, **_met_inhoud(publicatie, tool, args, sleutel="inhoud_publicatie")})
    met = {**basis, **_met_inhoud(rijen, tool, args, sleutel="inhoud")}
    tekst = maak(met)
    if met.get("inhoud") and not json.loads(tekst).get("volledig"):
        zonder = maak(basis)
        if json.loads(zonder).get("volledig"):
            return zonder
    return tekst
