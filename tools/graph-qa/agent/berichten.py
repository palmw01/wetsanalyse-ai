"""Het berichtenvenster naar de LLM: parsen, snoeien en schoonmaken.

Deze helpers bewaken één harde eis van de Anthropic-API: een `tool_result` mag nooit zonder zijn
`tool_use` in het venster staan. Ze zitten in een eigen module zodat zowel de orchestrator als de
node-modules ze kunnen gebruiken.
"""
from __future__ import annotations

from typing import Any

def _parse_final(final: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Splits een Anthropic-response in (tool_uses, text_parts)."""
    tool_uses: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for block in final.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_uses.append({"id": block.id, "name": block.name, "input": block.input})
    return tool_uses, text_parts


def _msg_lengte(m: dict[str, Any]) -> int:
    c = m.get("content")
    if isinstance(c, str):
        return len(c)
    if isinstance(c, list):
        return sum(len(str(b)) for b in c)
    return 0


def _is_tool_result_user(m: dict[str, Any]) -> bool:
    """Een user-message dat (alleen) tool_result-blokken draagt – orphan als z'n tool_use is weggevallen."""
    c = m.get("content")
    return (
        m.get("role") == "user"
        and isinstance(c, list)
        and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c)
    )


def _is_plain_user(m: dict[str, Any]) -> bool:
    """Een 'platte' user-beurt (de vraag/correctie) – géén tool_result-drager. Zo'n bericht is een
    geldig venster-begin: alles erna is een compleet assistant→tool_result-verloop."""
    return m.get("role") == "user" and not _is_tool_result_user(m)


#: Waarmee een correctiebericht van de brongetrouwheidscontrole begint (`correct_node`). Het staat als
#: user-bericht in de historie, maar is geen vraag van de jurist.
CORRECTIE = "Let op: "


def beurt_start(messages: list[dict[str, Any]], vraag: str = "") -> int:
    """Index waar de huidige beurt begint: de laatste platte user-beurt met deze vraag.

    De checkpointer bewaart de hele thread, dus `messages` loopt over alle beurten heen. Wat over
    DEZE beurt gaat – welke bepaling de agent net ophaalde, welk resultaat hij nu leest – hoort
    alleen hier gezocht te worden. Met `vraag` telt een correctiebericht ("Let op: …") van
    `correct_node` niet als begin: dat is een platte user-beurt midden in dezelfde beurt.
    Zonder geschikte kandidaat: 0 (alles is deze beurt)."""
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if _is_plain_user(m) and (not vraag or m.get("content") == vraag):
            return i
    return 0


def eerdere_beurten(messages: list[dict[str, Any]], vraag: str = "", *, aantal: int = 3,
                    per_bericht: int = 400) -> list[tuple[str, str]]:
    """De laatste `aantal` afgeronde beurten vóór deze, als (vraag, antwoord) in platte tekst.

    Voor wie het gesprek moet kennen zonder de tool-ruis: de supervisor. Per beurt de platte
    user-vraag en de láátste assistent-tekst erna (het antwoord, of de geheugenregel van een
    annotatie); tool-blokken en correctieberichten tellen niet."""
    beurten: list[tuple[str, str]] = []
    huidig: list[str] | None = None
    for m in messages[:beurt_start(messages, vraag)]:
        if _is_plain_user(m) and isinstance(m.get("content"), str) and not m["content"].startswith(CORRECTIE):
            huidig = [m["content"], ""]
            beurten.append(huidig)  # type: ignore[arg-type]
        elif m.get("role") == "assistant" and huidig is not None:
            c = m.get("content")
            tekst = c if isinstance(c, str) else " ".join(
                b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text")
            if tekst.strip():
                huidig[1] = tekst.strip()
    kort = lambda t: t if len(t) <= per_bericht else t[:per_bericht] + "…"  # noqa: E731
    return [(kort(v), kort(a)) for v, a in beurten[-aantal:]]


def beurt_berichten(messages: list[dict[str, Any]], vraag: str = "") -> list[dict[str, Any]]:
    """De berichten van de huidige beurt (zie `beurt_start`)."""
    return messages[beurt_start(messages, vraag):]


# Wat er van een oud tool-resultaat overblijft als het budget knelt. Ruim genoeg om te zien wát er
# gevonden is (de eerste treffers, de kop van een SELECT), te krap om het venster te domineren.
_TOOLRESULT_KRIMP = 800
_KRIMP_NOOT = "\n[… ingekort: ouder tool-resultaat, vraag het opnieuw op als je het nodig hebt]"


def _krimp(messages: list[dict[str, Any]], tot: int) -> list[dict[str, Any]]:
    """Kort de tool-resultaten in de berichten vóór index `tot` in tot `_TOOLRESULT_KRIMP` tekens.

    De blokken zélf blijven staan; alleen hun tekst wordt afgekapt. Weggooien zou een `tool_use` zonder
    `tool_result` achterlaten en dat weigert Anthropic."""
    uit: list[dict[str, Any]] = []
    for i, m in enumerate(messages):
        c = m.get("content")
        if i >= tot or not isinstance(c, list):
            uit.append(m)
            continue
        nieuw_blokken = []
        for blok in c:
            if (isinstance(blok, dict) and blok.get("type") == "tool_result"
                    and isinstance(blok.get("content"), str)
                    and len(blok["content"]) > _TOOLRESULT_KRIMP):
                blok = {**blok, "content": blok["content"][:_TOOLRESULT_KRIMP] + _KRIMP_NOOT}
            nieuw_blokken.append(blok)
        uit.append({**m, "content": nieuw_blokken})
    return uit


def _knippunten(historie: list[dict[str, Any]], stap: int) -> list[int]:
    """Een vast raster van plekken waar het venster mag beginnen of de krimp mag ophouden.

    Een knippunt is de eerste platte user-beurt op of na elk veelvoud van `stap` tekens, geteld vanaf het begin van
    het gesprek. Omdat de historie alleen aangroeit, verschuift een bestaand knippunt nooit: er komen er alleen
    achteraan bij. Daardoor blijft het venster een paar beurten lang byte-gelijk, en kan de prompt-cache de historie
    van de vorige beurt hergebruiken (nulmeting context 12 nov 2026: per beurt werd de hele historie opnieuw
    geschreven, omdat het venster bij elke beurt een stukje verschoof)."""
    punten: list[int] = []
    totaal, vak = 0, -1
    for i, m in enumerate(historie):
        if _is_plain_user(m) and totaal // stap > vak:
            punten.append(i)
            vak = totaal // stap
        totaal += _msg_lengte(m)
    return punten


def _historievenster(historie: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    """De historie vóór de lopende beurt, binnen `max_chars`. Gebouwd om over beurten heen byte-gelijk te blijven.

    1. Past de hele historie, dan gebeurt er niets.
    2. Anders krimpen de tool-resultaten van alle beurten behalve de laatste, zodat het gesprek zelf langer meegaat:
       zonder dit weegt één SPARQL-dump van 8000 tekens even zwaar als twintig beurten proza. De laatste beurt van
       de historie blijft heel; daar gaat een vervolgvraag meestal over. Omdat de historie alleen aangroeit, blijft
       een gekrompen beurt gekrompen: per nieuwe beurt verandert alleen de vorige beurt. Eerder beschermde de krimp
       een halve begroting die bij elke beurt opschoof, en verschoof het venster bij elke beurt een stukje. Dan kon
       de prompt-cache de historie nooit hergebruiken (nulmeting context 12 nov 2026: per beurt opnieuw geschreven).
    3. De voorkant valt weg op een knippunt van `_knippunten`, een vast raster over de gekrompen historie: het eerste
       knippunt waarvandaan het gekrompen oude deel, zonder de laatste beurt, binnen een halve begroting past. Dat deel
       groeit alleen aan, dus het knippunt schuift alleen naar voren, in sprongen van een halve begroting. De laatste
       beurt komt er heel bij. Is het geheel dan nog te groot (een beurt met een groot resultaat), dan krimpt ook de
       laatste beurt.

    Gesimuleerd met de echte cachepunten (`met_beurtcontext`): per beurt ~16k tekens opnieuw geschreven (de vorige
    beurt gekrompen plus de nieuwe), tegen 34–36k met het oude venster. Het minimum is de nieuwe beurt zelf."""
    if sum(_msg_lengte(m) for m in historie) <= max_chars:
        return historie
    laatste = next((i for i in range(len(historie) - 1, -1, -1) if _is_plain_user(historie[i])), 0)
    alles = _krimp(historie, len(historie))
    # Het knippunt hangt alleen af van het gekrompen oude deel (alles vóór de laatste beurt). Dat groeit alleen aan, dus
    # het knippunt schuift alleen naar voren. Hing het ook af van de laatste beurt (heel nu, gekrompen de beurt erna), dan
    # liep de voorkant heen en weer en was de cache telkens weg (nameting G4-3/G4-4).
    oud = lambda p: sum(_msg_lengte(m) for m in alles[p:laatste])  # noqa: E731
    punten = sorted(set(_knippunten(alles, max(1, max_chars // 2))) | {laatste})
    begin = next(p for p in punten if p >= laatste or oud(p) <= max_chars // 2)
    venster = _krimp(historie, laatste)[begin:]
    return venster if sum(_msg_lengte(m) for m in venster) <= max_chars else alles[begin:]


def _trim_messages(messages: list[dict[str, Any]], max_chars: int, vraag: str = "") -> list[dict[str, Any]]:
    """Beperk de historie die naar de LLM gaat tot een char-budget, met behoud van de
    tool_use/tool_result-integriteit (Anthropic weigert een orphan tool_result).

    Het budget geldt voor de historie vóór de lopende beurt (`_historievenster`). **De lopende beurt krimpt nooit en
    telt niet mee**: anders las het model zijn verse resultaat als "ingekort, vraag opnieuw op" en zocht het in een
    lus. Dat de beurt buiten het budget valt, heeft twee gevolgen. Het venster op de historie blijft tijdens de hele
    beurt gelijk, zodat elke ronde haar uit de cache leest. En een lange beurt laat de historie niet meer in één keer
    vallen: eerder viel bij 51k tekens in de lopende beurt het hele gesprek weg en werd de beurt opnieuw geschreven
    (nameting context 12 nov 2026). De prompt is daarmee hoogstens `max_chars` plus de lopende beurt.

    Het venster begint altijd op een platte user-beurt, dus elk tool_result houdt zijn tool_use. `vraag` wijst de
    lopende beurt aan (`beurt_start`). Zonder telt een correctiebericht als begin van de beurt, en dan valt de
    brontekst die het model moet herstellen in de historie. `max_chars<=0` → ongewijzigd.
    """
    if max_chars <= 0 or not messages:
        return messages
    b = beurt_start(messages, vraag)
    return _historievenster(messages[:b], max_chars) + messages[b:]


def _is_vraag(m: dict[str, Any]) -> bool:
    """Een platte user-beurt die geen correctiebericht is: een vraag van de jurist."""
    c = m.get("content")
    return _is_plain_user(m) and not (isinstance(c, str) and c.startswith(CORRECTIE))


def venster_telling(origineel: list[dict[str, Any]], venster: list[dict[str, Any]]) -> dict[str, int]:
    """Wat `_trim_messages` van de historie overliet, als tellingen zonder inhoud (E6-C1).

    `origineel` is de historie vóór het trimmen, `venster` wat naar het model gaat. Een beurt is een
    vraag van de jurist (geen correctie); `ingekort` telt de tool-resultaten met de krimpnoot. Vallen er
    beurten weg, dan is `beurten_venster < beurten_historie`."""
    ingekort = sum(
        1
        for m in venster
        if isinstance(m.get("content"), list)
        for b in m["content"]
        if isinstance(b, dict) and b.get("type") == "tool_result"
        and isinstance(b.get("content"), str) and b["content"].endswith(_KRIMP_NOOT)
    )
    return {
        "historie_tekens": sum(_msg_lengte(m) for m in origineel),
        "venster_tekens": sum(_msg_lengte(m) for m in venster),
        "beurten_historie": sum(_is_vraag(m) for m in origineel),
        "beurten_venster": sum(_is_vraag(m) for m in venster),
        "ingekort": ingekort,
    }


# Bovengrens op wat er in de CHECKPOINTER blijft staan. `max_history_chars` begrenst alleen wat er
# per beurt naar het model gaat; de opgeslagen historie groeide onbeperkt door, inclusief elk
# tool-resultaat van 8000 tekens. Bij een lang gesprek betekent dat een steeds tragere en dikkere
# checkpoint-write bij élke stap van de graaf.
#
# Ruim boven het prompt-budget gekozen (een veelvoud), zodat het snoeien nooit het venster raakt dat
# de LLM tóch al krijgt: dit is een opslagrem, geen tweede contextrem.
# Vaste grens, want een LangGraph-reducer is een pure functie zonder toegang tot `Settings`. Ruim
# vier keer het default prompt-budget (`max_history_chars`, 40k). Zet iemand dat budget hoger dan de
# helft hiervan, dan waarschuwt `Settings.controleer_historie_grens()` bij boot – dan zou de
# opslagrem binnen het promptvenster gaan knippen, en dat is precies wat hij niet moet doen.
MAX_HISTORIE_CHARS = 160_000


def _snoei_historie(messages: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    """Houd de bewaarde historie onder een bovengrens, en knip alleen op een veilige grens.

    "Veilig" is een plátte user-beurt (`_is_plain_user`): begint de historie met een los
    tool_result, dan mist dat blok zijn tool_use en weigert Anthropic de hele request. Vinden we geen
    veilige grens binnen het budget, dan snoeien we níét – een te grote historie is hinderlijk, een
    kapotte is fataal.
    """
    if max_chars <= 0 or not messages:
        return messages
    totaal = sum(_msg_lengte(m) for m in messages)
    if totaal <= max_chars:
        return messages
    # Zoek van achter naar voren de eerste platte user-beurt die het geheel binnen budget brengt.
    opgeteld = 0
    for i in range(len(messages) - 1, -1, -1):
        opgeteld += _msg_lengte(messages[i])
        if opgeteld >= max_chars:
            for j in range(i, len(messages)):
                if _is_plain_user(messages[j]):
                    return messages[j:]
            return messages
    return messages


def _voeg_toe_en_snoei(
    bestaand: list[dict[str, Any]], nieuw: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """State-reducer voor `messages`: append (zoals `operator.add`) plus een opslagrem."""
    return _snoei_historie(list(bestaand) + list(nieuw), MAX_HISTORIE_CHARS)


def _beantwoord(messages: list[dict[str, Any]], i: int) -> set[str]:
    """De id's van de tool-aanroepen die in het bericht ná `i` een resultaat hebben."""
    volgend = messages[i + 1].get("content") if i + 1 < len(messages) else None
    if not isinstance(volgend, list):
        return set()
    return {b.get("tool_use_id", "") for b in volgend if isinstance(b, dict) and b.get("type") == "tool_result"}


def _schoon_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Maak de bewaarde historie geldig voor de provider, in de kopie die naar het model gaat.

    - Lege tekstblokken weg: Anthropic weigert {"type":"text","text":""}, Claude stuurt die soms mee
      náást een tool_use, en via het gespreksgeheugen komen ze terug.
    - Een `tool_use` zonder `tool_result` direct erna weg. De checkpointer bewaart de aanroep vóór
      `tools_node` draait, dus stoppen, een crash of de stappenlimiet laat hem open staan, en dan
      weigert Anthropic elke volgende beurt in dat gesprek. Geen verzonnen resultaat: de aanroep is
      niet uitgevoerd. Omdat dit bij elke beurt gebeurt, herstelt het ook bestaande gesprekken.

    Berichten waarvan de content daardoor leeg wordt, slaan we over; twee user-berichten op rij
    zijn toegestaan."""
    schoon: list[dict[str, Any]] = []
    for i, m in enumerate(messages):
        c = m.get("content")
        if isinstance(c, list):
            nieuw = [
                b
                for b in c
                if not (isinstance(b, dict) and b.get("type") == "text" and not str(b.get("text", "")).strip())
                and not (isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id") not in _beantwoord(messages, i))
            ]
            if nieuw:
                schoon.append({**m, "content": nieuw})
        else:
            schoon.append(m)
    return schoon


#: De kop boven de context van de beurt in het bericht van de jurist (`met_beurtcontext`). Hij zegt van wie de tekst is:
#: van de werkplek, niet van de jurist. Wat erin staat, gold eerder als het variabele deel van de systeemprompt.
BEURTCONTEXT_KOP = ("CONTEXT VAN DEZE BEURT – van de werkplek, niet geschreven door de jurist. Het plan, de "
                    "gesprekscontext en de bronnen hieronder gelden voor de vraag die erna komt.\n\n")


def met_beurtcontext(venster: list[dict[str, Any]], vraag: str, context: str) -> tuple[list[dict[str, Any]], tuple[int, ...]]:
    """Zet de context van de lopende beurt vóór de vraag, en wijs de cachepunten op de historie aan.

    Het plan, de gesprekscontext, het werkgebied, het onderwerp en BRONNEN IN DEZE BEURT verschillen per beurt. Als
    variabel deel van de systeemprompt stonden ze vóór de berichten, dus elke beurt was de hele historie nieuw voor de
    prompt-cache (nulmeting context 12 nov 2026: 11–18k tokens per beurt opnieuw geschreven). Als eerste blok van het
    bericht van de jurist staan ze ná de historie. Binnen de beurt staan ze elke ronde op dezelfde plek, dus de cache
    blijft geldig.

    Het blok gaat alleen naar het model, niet de checkpoint in: de historie bewaart de vraag zoals de jurist hem stelde.
    Daardoor is dat bericht in de volgende beurt anders, en de cache kan pas tot het eind van de historie van deze
    beurt worden hergebruikt. Daarvoor dienen de twee cachepunten (indexen in het venster):
    - het eind van de historie van deze beurt (schrijven);
    - het eind van de historie van de vorige beurt (lezen: dat punt schreef de vorige beurt).
    De provider zoekt een eerdere hit maar een beperkt aantal blokken terug, dus het tweede punt is nodig om de vorige
    beurt te overbruggen. Zonder context ongewijzigd, maar wel met de punten."""
    b = beurt_start(venster, vraag)
    eerdere = [i for i in range(b) if _is_vraag(venster[i])]
    punten = tuple(sorted({i for i in (eerdere[-1] - 1 if eerdere else -1, b - 1) if i >= 0}))
    if not context or b >= len(venster):
        return venster, punten
    m = venster[b]
    blok = {"type": "text", "text": BEURTCONTEXT_KOP + context}
    c = m.get("content")
    inhoud = [blok, {"type": "text", "text": c}] if isinstance(c, str) else [blok, *(c or [])]
    return [*venster[:b], {**m, "content": inhoud}, *venster[b + 1:]], punten
