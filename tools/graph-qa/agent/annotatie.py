"""
Annotatie-grounding-helpers: parse de JAS-JSON van het model en verifieer elk element **brongetrouw**
(het fragment moet letterlijk in de opgehaalde artikeltekst voorkomen). Niet-onderbouwde of
ongeldig-geclassificeerde voorstellen worden verworpen (nooit stil doorgelaten). Gebruikt door de
annoteer-stap in `orchestrator.py` (`_parse_elementen`/`_verwerk`).
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Iterator
from typing import Any, NamedTuple

from .jas_klassen import GELDIGE_JAS_KLASSEN, REGELS, RegelType
from .models import (
    Anker, AnnotatieAlternatief, AnnotatieVoorstel, CriticOordeel, OntbrekendItem, VerworpenFragment,
)

logger = logging.getLogger("graph_qa.annotatie")

_AANDACHT = {"groen", "geel", "rood"}
_ACTIES = {"behoud", "vervang", "verwijder"}

_WS = re.compile(r"\s+")
# Het lidnummer waarmee `artikel._leden_en_corpus` elk lid in het corpus voorafgaat ("1. ", "9a. ").
#
# Ook de decimale vorm van een beleidsregel ("25.1. ", "73.3a.2. "), want bij de Leidraad zijn de
# corpussegmenten subdivisies in plaats van leden. Zonder dat kreeg elk segment lid "" terug, viel
# de lid-scoping van `_lokaliseer` terug op het hele corpus, en liepen lid en anker uit elkaar –
# precies wat "het lid en het anker zijn één beslissing" moet voorkomen. Het achterste `\.` blijft
# gevolgd door een spatie, zodat "25.1" in "25.1.1. tekst" niet als heel nummer wordt gelezen.
_LIDPREFIX = re.compile(r"^(\d+[a-z]*(?:\.(?:\d+[a-z]*|[a-z]+))*)\. ")
# Een woordteken: waar een fragment niet middenin mag landen. Inclusief accenten, want een match
# vlak vóór de "ë" van "beëindiging" is net zo goed een half woord.
_WOORDTEKEN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]")

# --- Anker-helpers ---------------------------------------------------------------
#
# De offsets slaan op de *originele* brontekst (vóór normalisatie), zodat de UI
# exact het juiste teken kan markeren. De hash is FNV-1a 32-bit – identiek aan
# `bronHash()` in `frontend/lib/selectie.ts`, zodat de UI kan detecteren of de
# brontekst verschoven is na een herimport.

_CONTEXT_LENGTE = 48   # tekens context vóór/na het fragment – gelijk aan frontend CONTEXT_LENGTE
_FNV_PRIME = 0x01000193
_FNV_OFFSET = 0x811C9DC5


def _fnv1a_32(tekst: str) -> str:
    """FNV-1a 32-bit hash als hex-string. Identiek aan bronHash() in selectie.ts."""
    h = _FNV_OFFSET
    for ch in tekst:
        for byte in ch.encode("utf-8"):
            h ^= byte
            h = (h * _FNV_PRIME) & 0xFFFFFFFF
    return format(h, "08x")


def _maak_anker(corpus: str, start: int, eind: int, lid: str = "") -> Anker:
    """Bouw het Anker voor een fragment op positie [start, eind) in `corpus`.

    De offsets zijn op de originele (niet-genormaliseerde) brontekst. De context
    (voor/na) bewaart 48 tekens zodat de UI het juiste voorkomen van een herhaald
    fragment kan kiezen als de offsets na een herimport zijn verschoven.
    """
    return Anker(
        lid=lid,
        start=start,
        eind=eind,
        voor=corpus[max(0, start - _CONTEXT_LENGTE): start],
        na=corpus[eind: eind + _CONTEXT_LENGTE],
        bron_hash=_fnv1a_32(corpus),
    )


def _lid_segmenten(corpus: str) -> list[tuple[str, int, int]]:
    """Splits het corpus terug in (lidnummer, start, eind) per lid.

    Dit is exact en geen heuristiek: `artikel._leden_en_corpus` bouwt het corpus door de leden
    samen te voegen met "\\n\\n" en er `"{lid}. "` voor te zetten, terwijl de onderdelen binnen
    een lid met een enkele "\\n" aan elkaar hangen. Splitsen op "\\n\\n" levert dus precies de
    leden op, en het lidnummer staat vooraan het segment.

    Heeft een segment geen lidprefix (een bepaling, of een artikel zonder genummerde leden), dan
    krijgt het lid `""`. Een corpus van één zo'n segment maakt de lid-scoping vanzelf een no-op.
    """
    segmenten: list[tuple[str, int, int]] = []
    positie = 0
    for stuk in corpus.split("\n\n"):
        m = _LIDPREFIX.match(stuk)
        segmenten.append((m.group(1) if m else "", positie, positie + len(stuk)))
        positie += len(stuk) + 2
    return segmenten


def _segment_van(segmenten: list[tuple[str, int, int]], lid: str) -> tuple[int, int] | None:
    """Het (start, eind)-venster van `lid`, of None als het corpus dat lid niet draagt."""
    for nummer, start, eind in segmenten:
        if nummer == lid:
            return (start, eind)
    return None


def _onderdeel_nummer(waarde: str) -> str:
    """Normaliseer een onderdeelnummer zodat "c", "c." en "onderdeel c" hetzelfde zijn.

    De afsluitende punt gaat eraf, de `°` blijft staan: zonder dat vallen een hypothetisch "1." en
    het geneste "1°." samen, en dan wijst het anker naar het verkeerde niveau.
    """
    kop = waarde.strip().lower().removeprefix("onderdeel").strip()
    return kop.rstrip(".")


def _onderdeel_segmenten(corpus: str, venster: tuple[int, int]) -> list[tuple[str, int, int]]:
    """Splits één lidsegment in (onderdeelnummer, start, eind) per regel.

    Net zo exact als `_lid_segmenten`: `artikel._vouw_onderdelen_in` zet elk onderdeel op een eigen
    regel achter zijn nummer ("a. rijksbelastingen: …"), met de lidtekst als eerste regel. Die
    eerste regel is de aanhef en krijgt nummer `""`.
    """
    vanaf, tot = venster
    rijen: list[tuple[str, int, int]] = []
    positie = vanaf
    for i, regel in enumerate(corpus[vanaf:tot].split("\n")):
        nummer = "" if i == 0 else _onderdeel_nummer(regel.split(" ", 1)[0])
        rijen.append((nummer, positie, positie + len(regel)))
        positie += len(regel) + 1
    return rijen


def _lid_op(segmenten: list[tuple[str, int, int]], offset: int) -> str:
    """Het lidnummer waarin `offset` valt ("" als het corpus geen genummerde leden heeft)."""
    for nummer, start, eind in segmenten:
        if start <= offset < eind:
            return nummer
    return ""


def _op_woordgrenzen(tekst: str, start: int, lengte: int) -> bool:
    """Staat `tekst[start:start+lengte]` op woordgrenzen?

    De eis geldt per zijde en alleen waar het fragment zélf een woordteken heeft: een fragment dat
    met een leesteken begint ("– de gevraagde gegevens…") heeft aan die kant niets te bewijzen.

    Waarom dit nodig is: de Operator "en" komt 59x voor in lid 2 van artikel 6 Uitvoeringsregeling
    Awir, en het eerste voorkomen zit in "Als gevallen als bedoeld" — een lettergreep, geen
    voegwoord. Het anker wees daar op 1 sep 2026 live naar.

    Genormaliseerde en originele tekst mogen door elkaar: `_normaliseer` collapst witruimte maar
    verwijdert nooit letters, dus of twee woordtekens aan elkaar grenzen is in beide gelijk.
    """
    eind = start + lengte
    if _WOORDTEKEN.match(tekst[start]) and start > 0 and _WOORDTEKEN.match(tekst[start - 1]):
        return False
    if _WOORDTEKEN.match(tekst[eind - 1]) and eind < len(tekst) and _WOORDTEKEN.match(tekst[eind]):
        return False
    return True


def _lokaliseer(
    corpus: str, norm_corpus: str, norm_frag: str, lid: str = "", onderdeel: str = "",
) -> tuple[int, int, str]:
    """Waar staat dit fragment? Geeft (start, eind, lid) — of (-1, -1, lid) als het er niet staat.

    De ladder is **onderdeel → lid → hele corpus**, elke trede met de woordgrens-voorkeur uit
    `_zoek_in_origineel`. Het onderdeel is de fijnste aanwijzing die het model geeft; hij wordt niet
    opgeslagen, want de offsets pinnen de plek daarna exact.

    Staat het fragment niet in het geclaimde lid, dan klopt die claim niet en wint het anker: het
    teruggegeven lid is dat van de plek waar het fragment werkelijk landt. Een element met een lid
    en een anker die elkaar tegenspreken mag er niet uit komen.

    Deze functie is bewust de **enige** plek die dit uitrekent. Zij bedient `_verwerk` (verse
    voorstellen) én `pas_critic_toe` (een door de Critic vervangen fragment). Die tweede kreeg zijn
    anker eerder helemaal niet bijgewerkt: op 1 sep 2026 stond in een live annotatie een Operator
    "en" met een anker van 83 tekens eromheen, omdat de patcher alleen `tekst` verving.
    """
    segmenten = _lid_segmenten(corpus)
    genummerd = any(nummer for nummer, _, _ in segmenten)
    venster = _segment_van(segmenten, lid) if (lid and genummerd) else None

    start, eind = (-1, -1)
    if venster and (nummer := _onderdeel_nummer(onderdeel)):
        fijner = _segment_van(_onderdeel_segmenten(corpus, venster), nummer)
        if fijner:
            start, eind = _zoek_in_origineel(corpus, norm_corpus, norm_frag, fijner)
    if start < 0 and venster:
        # Geen (bruikbaar) onderdeel: terug naar het lid. Een fout onderdeel mag nooit het lid
        # corrigeren – dat is een grovere claim en kan best kloppen.
        start, eind = _zoek_in_origineel(corpus, norm_corpus, norm_frag, venster)
    if start >= 0:
        return (start, eind, lid)

    start, eind = _zoek_in_origineel(corpus, norm_corpus, norm_frag)
    if start >= 0 and lid and genummerd:
        gevonden = _lid_op(segmenten, start)
        if gevonden != lid:
            logger.info(
                "annotatie: lid gecorrigeerd naar de plek van het anker",
                extra={"beweerd_lid": lid[:8], "anker_lid": gevonden[:8]},
            )
        return (start, eind, gevonden)
    return (start, eind, lid)


def _zoek_in_origineel(
    corpus: str, norm_corpus: str, norm_frag: str, binnen: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """Geef (start, eind) in de originele `corpus` voor een genormaliseerd fragment.

    `_normaliseer` collapst witruimte. Daardoor wijken de tekenposities in `norm_corpus`
    af van die in `corpus`. We zoeken het fragment in de genormaliseerde tekst, mappen
    de start-positie terug naar de originele tekst door te tellen hoeveel originele tekens
    overeenkomen vóór elk genormaliseerd teken.

    Algoritme: bouw een mapping van norm-index → orig-index. Dat is O(n) en eenvoudig
    aantoonbaar correct. Bij een niet-gevonden fragment geeft de aanroeper (-1, -1).

    Met `binnen` (start, eind) in *originele* coördinaten telt alleen een voorkomen dat daar
    begint. Zo blijft een kort fragment binnen het lid waar het element over gaat: "derde" komt
    negen keer voor in artikel 6 Uitvoeringsregeling Awir, en zonder venster wint altijd het
    eerste — het rangtelwoord in "artikel 25, derde lid" in lid 1, niet het rechtssubject in lid 2.
    Zonder `binnen` is het gedrag ongewijzigd, op de woordgrens-voorkeur na (`_op_woordgrenzen`):
    die geldt altijd, maar als geen enkel voorkomen eraan voldoet wint alsnog het eerste. Een
    brongetrouw fragment kwijtraken omdat de plaatsbepaling niet lukt is erger dan een minder
    scherpe plaatsbepaling — dezelfde afweging als bij het lid.
    """
    # Snelle mapping: norm_idx -> orig_idx voor elk niet-witruimte karakter
    mapping: list[int] = []
    in_ws = False
    for orig_idx, ch in enumerate(corpus):
        if ch in (" ", "\t", "\n", "\r"):
            if not in_ws:
                # De genormaliseerde tekst heeft hier één spatie
                mapping.append(orig_idx)
                in_ws = True
        else:
            mapping.append(orig_idx)
            in_ws = False

    # Loop de voorkomens langs en kies de beste. Twee criteria, in deze volgorde:
    #   1. het voorkomen begint in `binnen` (harde eis wanneer een venster is meegegeven);
    #   2. het staat op woordgrenzen (voorkeur — zie hieronder).
    # Wie het venster op norm-coördinaten zou omrekenen, dupliceert de mapping; die hebben we al.
    vanaf, tot = binnen if binnen is not None else (0, len(corpus))
    norm_start, keus = norm_corpus.find(norm_frag), -1
    while 0 <= norm_start < len(mapping):
        if vanaf <= mapping[norm_start] < tot:
            if _op_woordgrenzen(norm_corpus, norm_start, len(norm_frag)):
                keus = norm_start
                break
            if keus < 0:
                keus = norm_start  # onthoud het eerste, als terugval
        norm_start = norm_corpus.find(norm_frag, norm_start + 1)
    if keus < 0:
        return (-1, -1)

    orig_start = mapping[keus]
    norm_start = keus
    # Eind: orig_start + lengte van het fragment in de originele tekst.
    # We lopen over de originele tekst vanaf orig_start en tellen totdat we
    # len(norm_frag) genormaliseerde tekens hebben gezien.
    norm_len = len(norm_frag)
    gezien = 0
    orig_eind = orig_start
    in_ws2 = False
    for orig_idx in range(orig_start, len(corpus)):
        ch = corpus[orig_idx]
        if ch in (" ", "\t", "\n", "\r"):
            if not in_ws2:
                gezien += 1
                in_ws2 = True
        else:
            gezien += 1
            in_ws2 = False
        if gezien >= norm_len:
            orig_eind = orig_idx + 1
            break
    else:
        orig_eind = len(corpus)

    return (orig_start, orig_eind)


def _normaliseer(s: str) -> str:
    """Collapse witruimte, zodat een fragment ondanks layout-verschillen matcht."""
    return _WS.sub(" ", s or "").strip()


# --- Prioriteitsvalidator ---------------------------------------------------
#
# Deterministisch: geen LLM-call. Controleert of de toegewezen klasse al dan
# niet de hoogste prioriteit heeft volgens REGELS. Bij een lagere-prioriteits-
# klasse wordt de klasse gecorrigeerd en de verplaatste klasse als alternatief
# bewaard. Eén bron van waarheid (REGELS in jas_klassen.py) voedt zowel de
# prompt (_prioriteitsregels_tekst) als deze code.

def _prioriteitsrang(klasse: str) -> dict[str, int]:
    """Geef een dict {klasse: rang} voor alle PRIORITEIT-regels waarbij `klasse` betrokken is."""
    rang: dict[str, int] = {}
    for regel in REGELS:
        if regel.type != RegelType.PRIORITEIT:
            continue
        if klasse not in regel.applies_to:
            continue
        prio = dict(regel.priority)
        for k, r in prio.items():
            if k not in rang or rang[k] < r:
                rang[k] = r
    return rang


def _pas_prioriteitsregels_toe(
    klasse: str, alternatieven: list[Any], als_dict: bool = False
) -> tuple[str, list[Any]]:
    """Corrigeer `klasse` als een alternatief hogere prioriteit heeft.

    Geeft (definitieve_klasse, bijgewerkte_alternatieven) terug. Als de klasse al de
    hoogste prioriteit heeft, of als er geen prioriteitsregel van toepassing is, blijft
    alles ongewijzigd.

    Voorbeeld: klasse=Variabele, alternatief=[Tijdsaanduiding]
    → Tijdsaanduiding wint (rang 100 > 50)
    → klasse=Tijdsaanduiding, alternatieven=[...Variabele...]

    `als_dict` bepaalt de vorm van een NIEUW alternatief. Het annoteerderpad (`_verwerk`) werkt met
    `AnnotatieAlternatief`, de patcher (`pas_critic_toe`) met kale dicts; een dataclass tussen de
    dicts schuiven levert daar verderop een TypeError op.
    """
    rang = _prioriteitsrang(klasse)
    if not rang:
        return klasse, alternatieven

    eigen_rang = rang.get(klasse, 0)
    winnaar_klasse = klasse
    winnaar_rang = eigen_rang

    for alt in (alternatieven or []):
        alt_klasse = str(alt.klasse if hasattr(alt, "klasse") else alt.get("klasse", "")).strip()
        alt_rang = rang.get(alt_klasse, 0)
        if alt_rang > winnaar_rang:
            winnaar_rang = alt_rang
            winnaar_klasse = alt_klasse

    if winnaar_klasse == klasse:
        return klasse, alternatieven

    # Wissel: voeg de oude klasse toe als alternatief (als die er nog niet in zit)
    nieuwe_alts = list(alternatieven or [])
    oud_als_alt_klassen = {
        str(a.klasse if hasattr(a, "klasse") else a.get("klasse", "")).strip()
        for a in nieuwe_alts
    }
    if klasse not in oud_als_alt_klassen:
        motivatie = f"Lagere prioriteit dan {winnaar_klasse} (JAS-prioriteitsregel)."
        if als_dict:
            nieuwe_alts.insert(0, {"klasse": klasse, "motivatie": motivatie})
        else:
            from .models import AnnotatieAlternatief as _AA
            nieuwe_alts.insert(0, _AA(klasse=klasse, motivatie=motivatie))
    # Verwijder de winnaar uit de alternatieven (hij wordt de hoofdklasse)
    nieuwe_alts = [
        a for a in nieuwe_alts
        if str(a.klasse if hasattr(a, "klasse") else a.get("klasse", "")).strip() != winnaar_klasse
    ]
    return winnaar_klasse, nieuwe_alts


def komt_letterlijk_voor(corpus: str, fragment: str) -> bool:
    """Staat dit fragment letterlijk in de opgehaalde tekst?

    Dezelfde eis (en dezelfde normalisatie) waarmee `_verwerk` de voorstellen van het model afkeurt,
    maar los bruikbaar – bijvoorbeeld voor de markeringen die de jurist meestuurt. Ook die moeten in
    de bepaling staan die is opgehaald: een Critic-oordeel over een fragment dat hij niet voor zich
    heeft is geen oordeel.
    """
    norm = _normaliseer(fragment)
    return bool(norm) and _normaliseer(corpus).find(norm) >= 0


# ---------------------------------------------------------------------------
# Fase 2A – kandidaat-parsing en filtering
# ---------------------------------------------------------------------------

def parse_kandidaten(llm_text: str) -> list[dict]:
    """Parse de JSON-output van de kandidaat-generator.

    Verwacht {"kandidaten": [{"span": "...", "lid": "...", "reden": "..."}]}.
    Robuust tegen proza/afkapping: fast-path hele JSON, fallback op
    gebalanceerde {}-objecten die `span` of `tekst` bevatten.
    """
    raw = (llm_text or "").strip().strip("`")
    if raw.lower().startswith("json"):
        raw = raw[4:]
    s, e = raw.find("{"), raw.rfind("}")
    if s != -1 and e > s:
        try:
            data = json.loads(raw[s: e + 1])
            if isinstance(data, dict) and isinstance(data.get("kandidaten"), list):
                return [
                    k for k in data["kandidaten"]
                    if isinstance(k, dict) and (k.get("span") or k.get("tekst"))
                ]
        except json.JSONDecodeError:
            pass
    # Fallback: gebalanceerde objecten die span of tekst bevatten
    gered = []
    for obj in _balanced_objecten(raw):
        try:
            d = json.loads(obj)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and (d.get("span") or d.get("tekst")):
            gered.append(d)
    return gered


_MIN_KANDIDAAT_LENGTE = 2   # tekens – te korte spans zijn bijna nooit een JAS-element


def filter_kandidaten(kandidaten: list[dict], corpus: str) -> list[dict]:
    """Filter de kandidatenlijst deterministisch (geen LLM).

    Stappen:
    1. Verwijder spans korter dan _MIN_KANDIDAAT_LENGTE tekens.
    2. Verwijder spans die niet letterlijk in de corpus staan.
    3. Normaliseer het span-veld (strip witruimte).
    4. Dedupliceer op genormaliseerde span + lid (eerste wins).
    5. Overlappende spans: behoud beide als ze inhoudelijk verschillen.
       Alleen identieke deelverzamelingen (contained + zelfde reden) worden
       samengevoegd – de classificator beslist over grensgevallen.

    De juridische keuze (welke overlappende span is het element?) blijft bij
    de classificator, niet bij deze filter. Zie plan V3 §2A.
    """
    norm_corpus = _normaliseer(corpus)
    gezien: dict[tuple[str, str], dict] = {}
    resultaat = []
    for k in kandidaten:
        span = _normaliseer(k.get("span") or k.get("tekst") or "")
        if len(span) < _MIN_KANDIDAAT_LENGTE:
            continue
        if norm_corpus.find(span) < 0:
            continue
        lid = (k.get("lid") or "").strip()
        sleutel = (span.lower(), lid)
        if sleutel in gezien:
            continue
        gezien[sleutel] = k
        resultaat.append({**k, "span": span, "lid": lid})
    return resultaat


def sleutel_van(tekst: str, lid: str) -> tuple[str, str]:
    """Identiteit van een markering los van zijn id: fragment + lid.

    Twee elementen met dezelfde sleutel zijn dezelfde markering, ook al dragen ze een ander id. Dat
    gebeurt als een herziening een bestaand fragment opnieuw voorstelt zonder het id mee te sturen —
    en dan krijgt de jurist twee identieke kaartjes te reviewen.

    **Bewust ZONDER klasse**, gelijk aan de terugval in de api-merge (`routers/annotatie.py:_sleutel`)
    en aan `mergeVoorstellen` in de werkplek: een herziening mág juist de klasse veranderen en moet
    dan hetzelfde element treffen. Stond de klasse er wél in, dan werd een herclassificatie zonder
    id een tweede element – en zag de jurist dezelfde tekstspan twee keer met tegenstrijdige
    klassen. Dit is de canonieke regel; wie hem elders nabouwt, bouwt hem hiernaar.
    """
    return (_normaliseer(tekst).lower(), (lid or "").strip())


class PatchTelling(NamedTuple):
    """Wat de patcher deed: hoeveel uitgevoerd, en hoeveel als twijfel doorgegeven."""

    toegepast: int
    alternatief: int

    def __bool__(self) -> bool:
        return bool(self.toegepast or self.alternatief)


def _anker_voor(corpus: str, fragment: str, lid: str = "") -> dict[str, Any] | None:
    """Het anker voor een fragment, als dict (de voorstellen in de state zijn gedumpt).

    Geen `onderdeel`: dat veld wordt bewust niet opgeslagen, dus die trede van de ladder valt hier
    weg. Lukt het lokaliseren niet, dan is het antwoord `None` — een ontbrekend anker is zichtbaar
    in de werkplek, een fout anker niet.
    """
    start, eind, _ = _lokaliseer(corpus, _normaliseer(corpus), _normaliseer(fragment), lid)
    return _maak_anker(corpus, start, eind, lid).model_dump() if start >= 0 else None


def pas_critic_toe(
    voorstellen: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    corpus: str,
) -> tuple[list[dict[str, Any]], PatchTelling, list[dict[str, Any]]]:
    """Voer de correcties van de Critic uit.

    Geeft terug: (nieuwe voorstellen, telling, **onafgehandelde instructies**). Dat laatste is wat de
    herziener nog te doen heeft. Zonder die scheiding kreeg hij de volledige feedback opnieuw – ook
    de correcties die hier net waren uitgevoerd, en ook de gele voorkeuren die hier bewust NIET zijn
    uitgevoerd. Dan voert een taalmodel alsnog uit wat we juist aan de jurist wilden voorleggen, en
    dat was op dev meteen zichtbaar: "2 aanwijzingen toegepast" gevolgd door "4 aangepast".

    De Critic leverde altijd al een uitvoerbare instructie – `actie` met `voorstel_klasse` en/of
    `voorstel_tekst`. Die ging vervolgens naar een tweede LLM (de herziener) die hem moest lezen,
    uitvoeren, en alle ongemoeide elementen ongewijzigd terugtypen. Dat is werk dat code exact doet
    en een taalmodel bij benadering: het kostte een call met het volle corpus, en het maakte van de
    keten een onderhandeling tussen twee modellen – met vier guards nodig om te laten stoppen.

    Wat hier NIET gebeurt, gebeurt nog steeds door het model: een bijna-goed citaat repareren en een
    gemeld ontbrekend element toevoegen. Dat vraagt de brontekst lezen, geen instructie uitvoeren.

    **Het aandacht-niveau bepaalt hoe hard een `vervang` landt.** Bij ROOD is de Critic er zeker van
    dat er iets mis is en wordt de correctie uitgevoerd. Bij GEEL twijfelt hij, en dan wordt een
    voorgestelde klasse een **alternatief** op het element: de werkplek toont die als aanklikbare chip
    ("Twijfel – klik om te wisselen"), zodat de jurist hem met één klik overneemt en het als zijn eigen
    beslissing in het auditspoor landt. Zo hoeft de Critic zijn voorkeur niet in te slikken en wordt
    er ook niets op een vermoeden veranderd.

    Drie grenzen, en ze zijn geen van drieën nieuw:
    - **Een markering van de jurist blijft ongemoeid.** Een oordeel daarover is een suggestie; dat
      staat zo in de api (`critic_suggestie`: "puur advies, wordt nooit toegepast") en het hoort hier
      niet alsnog stilletjes te worden doorgevoerd.
    - **Een voorgesteld fragment moet letterlijk in het corpus staan.** Dezelfde eis als bij een vers
      voorstel (`_verwerk`); een Critic die parafraseert corrigeert niets, hij verzint.
    - **Verwijderen alleen bij rood.** `_verwerk_critic` normaliseert dat al; hier vertrouwen we daar
      niet blind op – het is de enige onomkeerbare handeling in deze functie.
    """
    op_id = {str(f.get("id", "")): f for f in feedback if f.get("id")}
    uit: list[dict[str, Any]] = []
    rest: list[dict[str, Any]] = []
    toegepast = 0
    alternatief = 0

    for v in voorstellen:
        f = op_id.get(str(v.get("id", "")))
        actie = str((f or {}).get("actie", "behoud"))
        if f is None or actie == "behoud" or v.get("van_jurist"):
            uit.append(v)
            continue

        rood = str(f.get("aandacht", "")) == "rood"
        klasse = str(f.get("voorstel_klasse", "")).strip()

        if actie == "verwijder" and rood:
            toegepast += 1
            _markeer_toegepast(v)
            continue

        nieuw = dict(v)

        # GEEL VERANDERT NOOIT IETS. Een voorgestelde klasse wordt een alternatief – de werkplek
        # maakt er een aanklikbare chip van, dus de jurist neemt hem over met één klik en dan staat
        # het als zíjn beslissing in het spoor. Een voorgesteld frágment kent die tussenvorm niet en
        # blijft dus alleen in de motivatie staan; de jurist kan het fragment zelf herselecteren.
        #
        # In beide gevallen is de instructie hier AFGEHANDELD en gaat hij niet door naar de
        # herziener. Deed hij dat wel, dan voerde een taalmodel alsnog uit wat we juist ter
        # beoordeling wilden voorleggen – op dev kortte hij zo twee fragmenten in op een geel advies.
        if actie in ("vervang", "verwijder") and not rood:
            if klasse in GELDIGE_JAS_KLASSEN and klasse != nieuw.get("klasse"):
                alts = list(nieuw.get("alternatieven") or [])
                if not any(str(a.get("klasse")) == klasse for a in alts):
                    alts.append({"klasse": klasse, "motivatie": str(f.get("motivatie", "")).strip()})
                    nieuw["alternatieven"] = alts
                    alternatief += 1
            uit.append(nieuw)
            continue

        gewijzigd = False
        # Gaat een voorgestelde klasse tegen een PRIORITEITSREGEL van de methode in, dan wint de
        # regel. Rood is de tak die DIRECT wordt uitgevoerd – er staat geen tweede beoordelaar meer
        # achter – en de Critic kende deze regels tot 1 sep 2026 niet eens uit zijn prompt. De toets
        # vraagt de validator zélf wat er van dit paar overblijft: één bron van waarheid in
        # `jas_klassen.REGELS`, geen tweede vergelijking die daarvan kan gaan driften.
        prio_weigert = False
        if actie == "vervang" and rood and klasse in GELDIGE_JAS_KLASSEN and klasse != nieuw.get("klasse"):
            gekozen, _ = _pas_prioriteitsregels_toe(
                klasse, [{"klasse": str(nieuw.get("klasse", ""))}], als_dict=True
            )
            prio_weigert = gekozen != klasse

        if prio_weigert:
            # De klasse blijft staan, maar de lezing van de Critic gaat niet verloren: hij komt als
            # alternatief naast de kaart, net als bij geel. De jurist ziet beide en beslist. De
            # instructie is hiermee AFGEHANDELD – doorsturen naar de herziener zou een taalmodel
            # alsnog laten uitvoeren wat de methode net afwees.
            alts = list(nieuw.get("alternatieven") or [])
            if not any(str(a.get("klasse")) == klasse for a in alts):
                alts.append({"klasse": klasse, "motivatie": str(f.get("motivatie", "")).strip()})
                nieuw["alternatieven"] = alts
                alternatief += 1
        elif actie == "vervang" and rood and klasse in GELDIGE_JAS_KLASSEN and klasse != nieuw.get("klasse"):
            nieuw["klasse"] = klasse
            # Stond die klasse al als alternatief op het element (bijv. omdat hetzelfde fragment in
            # twee klassen was voorgesteld en `_voeg_alternatief_toe` er een alternatief van maakte),
            # dan is hij nu de hoofdklasse. Hem laten staan levert de jurist een chip op die naar de
            # keuze wijst die er al staat – op dev kregen twee elementen zo een alternatief dat gelijk
            # was aan hun eigen klasse. Dezelfde invariant die `_voeg_alternatief_toe` bewaakt.
            alts = [a for a in (nieuw.get("alternatieven") or []) if str(a.get("klasse")) != klasse]
            if alts != (nieuw.get("alternatieven") or []):
                nieuw["alternatieven"] = alts
            gewijzigd = True
        tekst = str(f.get("voorstel_tekst", "")).strip()
        if (
            actie == "vervang"
            and rood
            and tekst
            and tekst != nieuw.get("tekst")
            and komt_letterlijk_voor(corpus, tekst)
        ):
            nieuw["tekst"] = tekst
            # Het anker moet mee. Zonder dit bleef het op de vórige, langere span staan: op
            # 1 sep 2026 stond er live een Operator "en" met een anker van 83 tekens eromheen,
            # en omdat `bron_hash` klopt gebruikt de werkplek die offsets rechtstreeks.
            nieuw["anker"] = _anker_voor(corpus, tekst, str(nieuw.get("lid") or ""))
            gewijzigd = True

        if gewijzigd:
            toegepast += 1
            _markeer_toegepast(nieuw)
            # Het oordeel ging over de vórige versie. Leeg laten zou hem uit de aandacht-filters
            # laten vallen zonder dat iemand er iets van vindt; daarom volgt er een tweede
            # Critic-pas over het gecorrigeerde resultaat (zie `route_na_patch`).
            nieuw["aandacht"] = ""
            nieuw["critic"] = ""
        elif not prio_weigert:
            # Rood, maar niets uitvoerbaars: het voorgestelde fragment staat niet letterlijk in de
            # bron, of de klasse was al zo. Dít is wat de herziener nog kan oplossen – hij mag de
            # brontekst lezen en het bedoelde fragment opzoeken.
            #
            # Een door de PRIORITEITSREGEL geweigerde klasse hoort hier NIET bij: die is afgehandeld,
            # en doorsturen zou de herziener alsnog laten uitvoeren wat de methode net afwees.
            rest.append(f)
        uit.append(nieuw)

    # De prioriteitsregels van de METHODE gelden ook hier, niet alleen op de annoteerder-uitkomst
    # (`_verwerk`). Zonder deze pas verloor JAS-PRIORITY-001 van een Critic die de regel niet in zijn
    # prompt had: een correct toegewezen Tijdsaanduiding kon met rood+vervang direct naar Variabele
    # worden gezet, en daar staat geen tweede beoordelaar meer achter.
    #
    # Dit is geen schending van "GEEL VERANDERT NOOIT IETS" hierboven. Dat principe houdt een tweede
    # TAALMODEL tegen dat stil uitvoert wat aan de jurist voorgelegd moest worden. Dit is methode, geen
    # oordeel: de regel is deterministisch, hij kijkt alleen naar klasse + alternatieven en niet naar
    # wie ze aandroeg, en de weggedrukte klasse blijft als alternatief op de kaart staan. Zou hij hier
    # niet draaien, dan kreeg hetzelfde eindresultaat twee verschillende uitkomsten al naar gelang de
    # annoteerder of de Critic het alternatief had aangebracht.
    for v in uit:
        # Wat de jurist zelf markeerde blijft ongemoeid – dezelfde grens als hierboven.
        if v.get("van_jurist"):
            continue
        klasse, alts = _pas_prioriteitsregels_toe(
            str(v.get("klasse", "")), list(v.get("alternatieven") or []), als_dict=True
        )
        if klasse != v.get("klasse"):
            v["klasse"] = klasse
            v["alternatieven"] = alts
    # De telling blijft ongemoeid: PatchTelling rapporteert wat de CRITIC deed, en een methode-regel
    # is geen Critic-actie. Op het annoteerderpad is dezelfde validator net zo stil.
    return uit, PatchTelling(toegepast=toegepast, alternatief=alternatief), rest


def demp_zelfweerspreking(voorstellen: list[dict[str, Any]]) -> int:
    """Zwak een eindoordeel af dat de eigen uitgevoerde correctie terugdraait. Geeft het aantal terug.

    De eindbeoordeling gaat rechtstreeks naar de jurist – daar zit geen patcher meer achter die hem
    kan wegen. Komt de Critic daar terug op een klasse die hij zélf in de vorige ronde liet
    aanbrengen, dan levert dat een rode kaart op waarin de agent zichzelf tegenspreekt. Op dev stond
    er zo "dit is een Rechtsobject, geen Rechtsbetrekking" op een element dat hij één ronde eerder
    van Rechtsobject náár Rechtsbetrekking had gebracht.

    Dat is geen zekerheid maar twijfel: hetzelfde fragment, twee keer gewogen, twee uitkomsten. Dus
    behandelen we het als twijfel – de klasse blijft staan, het niveau zakt naar geel en de andere
    lezing komt als alternatief naast de kaart te liggen. De jurist ziet beide en kiest.

    Een eindoordeel over iets ánders (het fragment, overlap, een klasse die de Critic niet zelf heeft
    aangebracht) blijft onaangeroerd: dat is wél een nieuw bezwaar.
    """
    gedempt = 0
    for v in voorstellen:
        rondes = v.get("critic_rondes") or []
        if len(rondes) < 2 or str(rondes[-1].get("aandacht", "")) != "rood":
            continue
        klasse = str(rondes[-1].get("voorstel_klasse", "")).strip()
        huidig = str(v.get("klasse", ""))
        if not klasse or klasse == huidig:
            continue
        if not any(r.get("toegepast") and str(r.get("voorstel_klasse", "")) == huidig
                   for r in rondes[:-1]):
            continue

        alts = list(v.get("alternatieven") or [])
        if not any(str(a.get("klasse")) == klasse for a in alts):
            alts.append({"klasse": klasse, "motivatie": str(rondes[-1].get("motivatie", "")).strip()})
            v["alternatieven"] = alts
        v["aandacht"] = "geel"
        rondes[-1]["aandacht"] = "geel"
        gedempt += 1
    return gedempt


# De spaties eromheen blijven van de motivatie, niet van de match – anders plakken de woorden
# aan weerszijden van een vervangen id aan elkaar.
_ELEMENT_ID = re.compile(r"(?:\[|\()?(?:id\s*=\s*)?\b([0-9a-f]{12})\b(?:\]|\))?")


def vervang_ids_door_citaat(motivatie: str, voorstellen: list[dict[str, Any]]) -> str:
    """Zet interne element-ids in een Critic-motivatie om naar het fragment waar ze op slaan.

    De Critic krijgt de ids in zijn prompt omdat hij zijn oordeel eraan moet hangen, en verwijst
    vervolgens naar buurelementen met diezelfde id – "de Voorwaarde zit eigenlijk in [635074d49a74]".
    Die motivatie staat één-op-één op de reviewkaart, dus de jurist las een hexcode. Dat gebeurde op
    dev in drie van de zestien kaarten.

    Een id dat bij geen enkel voorstel hoort (de Critic verzint er soms een) wordt neutraal
    weggeschreven in plaats van blijven staan; anders ruilt de kaart een hexcode in voor een
    verkeerde verwijzing.
    """
    if not motivatie:
        return motivatie
    op_id = {str(v.get("id", "")): str(v.get("tekst", "")) for v in voorstellen}

    def _vervang(m: re.Match[str]) -> str:
        tekst = op_id.get(m.group(1), "")
        if not tekst:
            return "een ander element"
        kort = tekst if len(tekst) <= 45 else tekst[:44].rstrip() + "…"
        # Zette de Critic er zelf al aanhalingstekens omheen ("element '[<id>]'"), dan zouden die van
        # ons erbij komen: element ''zo'n fragment''. De zijne winnen.
        omsloten = motivatie[m.start() - 1: m.start()] in "'\u2018\u201c" and (
            motivatie[m.end(): m.end() + 1] in "'\u2019\u201d")
        return kort if omsloten else f"'{kort}'"

    return _ELEMENT_ID.sub(_vervang, motivatie).strip()


def openstaand_voorstel(voorstel: dict[str, Any], corpus: str) -> tuple[str, str, str]:
    """Wat de EINDbeoordeling voorstelt maar niemand meer uitvoert: (klasse, fragment, reden).

    De patcher draait vóór de eindbeoordeling; wat de Critic dáár nog voorstelt, komt door geen enkele
    stap meer heen. Op dev gebeurde dat twee keer in één run: "overweeg het fragment te beperken tot
    'is aansprakelijk'", met het exacte fragment in de data, terwijl de jurist het met de hand moest
    naselecteren. Hetzelfde geldt voor een voorgestelde klasse: bij een eerdere ronde maakt de patcher
    daar een alternatief van, maar in de eindronde draait die niet meer.

    Uitvoeren doen we het niet – het oordeel ís het sluitstuk, en er komt geen ronde meer overheen die
    er iets van kan vinden. Maar het als aanklikbare suggestie naast de kaart leggen kan wel; dan
    landt het als een beslissing van de jurist. Dezelfde eis als overal: letterlijk in de bron.
    """
    leeg = ("", "", "")
    rondes = voorstel.get("critic_rondes") or []
    if not rondes:
        return leeg
    laatste = rondes[-1]
    if str(laatste.get("actie", "")) != "vervang" or laatste.get("toegepast"):
        return leeg

    klasse = str(laatste.get("voorstel_klasse", "")).strip()
    if klasse not in GELDIGE_JAS_KLASSEN or klasse == str(voorstel.get("klasse", "")):
        klasse = ""

    tekst = str(laatste.get("voorstel_tekst", "")).strip()
    if tekst == str(voorstel.get("tekst", "")) or not komt_letterlijk_voor(corpus, tekst):
        tekst = ""

    if not klasse and not tekst:
        return leeg
    return klasse, tekst, str(laatste.get("motivatie", "")).strip()


def _markeer_toegepast(voorstel: dict[str, Any]) -> None:
    """Zet `toegepast` op de laatste Critic-ronde van dit element.

    Zonder dit verschilt "de Critic vroeg erom" niet van "het is ook gebeurd" – en juist dat verschil
    moet een auditspoor kunnen laten zien.
    """
    rondes = voorstel.get("critic_rondes") or []
    if rondes:
        rondes[-1]["toegepast"] = True


def _balanced_objecten(text: str) -> Iterator[str]:
    """Yield elke gebalanceerde {…}-substring op élk niveau (string-/escape-bewust).

    Elementen zitten genest in de wrapper `{"elementen": [ {…}, {…} ]}`, dus we moeten ook geneste
    objecten opleveren. Een afgekapt (nooit-gesloten) object levert niets op – precies wat we willen.
    """
    stack: list[int] = []
    in_str = False
    escape = False
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            stack.append(i)
        elif ch == "}":
            if stack:
                yield text[stack.pop() : i + 1]


def _parse_elementen(text: str) -> list[dict[str, Any]]:
    """Haal de element-objecten uit de LLM-respons.

    Fast-path: de hele respons als één JSON-object met `elementen`. Faalt dat (proza eromheen,
    afgekapt op max_tokens, code-fences), dan **salvagen** we de losse gebalanceerde {…}-objecten die
    op een element lijken (met `klasse` én `tekst`) – zo overleeft een afgekapt of omlijst antwoord
    (het onvolledige laatste object valt weg, de complete blijven) i.p.v. dat álles wegvalt.
    """
    raw = (text or "").strip()
    kandidaat = raw
    if kandidaat.startswith("```"):
        kandidaat = kandidaat.strip("`")
        if kandidaat.lower().startswith("json"):
            kandidaat = kandidaat[4:]
    s, e = kandidaat.find("{"), kandidaat.rfind("}")
    if s != -1 and e > s:
        try:
            data = json.loads(kandidaat[s : e + 1])
            if isinstance(data, dict) and isinstance(data.get("elementen"), list):
                return [x for x in data["elementen"] if isinstance(x, dict)]
        except json.JSONDecodeError:
            pass
    gered: list[dict[str, Any]] = []
    for obj in _balanced_objecten(raw):
        try:
            d = json.loads(obj)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "klasse" in d and "tekst" in d:
            gered.append(d)
    return gered


def _voeg_alternatief_toe(voorstel: AnnotatieVoorstel, klasse: str, motivatie: str) -> None:
    """Neem een tweede lezing van dezelfde span op als alternatief bij het eerste voorstel.

    Doet niets als het dezelfde klasse is (dan is het een echte herhaling) of als de klasse al als
    alternatief staat – anders groeit de lijst met dubbelen bij elke ronde.
    """
    if klasse == voorstel.klasse or any(a.klasse == klasse for a in voorstel.alternatieven):
        return
    voorstel.alternatieven.append(AnnotatieAlternatief(klasse=klasse, motivatie=motivatie))


def aanduiding_in_woorden(aanduiding: str, lid: str = "", soort: str = "") -> str:
    """"art. 9 lid 1" of "bepaling 25.1" – hoe je deze vindplaats in proza noemt.

    Een `Divisie` van een beleidsregel is geen artikel en heeft geen leden: "art. 25.1 lid 2" is een
    vindplaats die niet bestaat. De Leidraad labelt haar top-divisies zelf wél "Artikel 25", maar de
    subdivisies eronder niet, en "bepaling" dekt beide zonder iets te beweren wat niet klopt. Het is
    ook de term die de code al gebruikt (`get_bepaling`, `_bepaling_fallback`, `OngeldigeVindplaats`).

    Onbekend soort valt terug op "art.": dat is wat er stond, en bij de zes wet-achtige regelingen –
    veruit het meeste verkeer – is het gewoon juist.
    """
    nummer = str(aanduiding).strip()
    scope = str(lid or "").strip()
    if soort == "Divisie":
        return f"bepaling {nummer}" + (f", {scope}" if scope else "")
    return f"art. {nummer}" + (f" lid {scope}" if scope else "")


def _verwerk(
    llm_text: str, corpus: str, bwb_id: str, artikel: str, scope_lid: str | None = None,
    geldige_ids: set[str] | None = None, soort: str = "",
) -> tuple[list[AnnotatieVoorstel], list[VerworpenFragment]]:
    """Parse de LLM-JSON, valideer klasse + brongetrouwheid, bereken vindplaats.

    Is een `scope_lid` gezet (annotatie tot één lid), dan wint dat voor de vindplaats – elke markering
    verwijst dan naar dat lid, ook als het model het lid-veld leeg laat.

    `geldige_ids` begrenst welke id's het model mag hergebruiken, en wordt door de **herziening**
    meegegeven: daar krijgt het model bestaande voorstellen te zien, en een verwisseld id zou dan
    element A overschrijven met de inhoud van B – inclusief de beslissingen van de jurist en het
    auditspoor die eraan hangen. Een id buiten de set wordt genegeerd; het voorstel krijgt een vers
    id en komt er dus naast te staan in plaats van iets stuk te maken.

    De eerste ronde geeft het bewust niet mee: daar bestaat binnen de beurt nog geen element om te
    overschrijven, dus een id uit het model is hooguit een raar id.

    Dezelfde strengheid die `_verwerk_critic` al hanteerde: die valideert oordelen ook tegen de
    aangeboden id's. Dat de twee parsers daarin verschilden was een gat, geen keuze.

    Geeft naast de gegronde voorstellen de VERWORPEN fragmenten terug. Die gingen eerder als kale
    teller verloren, terwijl ze de bruikbaarste feedback voor een herzieningsronde zijn: een bijna
    goed citaat is met de aanwijzing "dit staat niet letterlijk in de tekst" prima te repareren.
    """
    norm_corpus = _normaliseer(corpus)
    segmenten = _lid_segmenten(corpus)
    genummerd = any(nummer for nummer, _, _ in segmenten)
    voorstellen: list[AnnotatieVoorstel] = []
    verworpen: list[VerworpenFragment] = []
    rauw = _parse_elementen(llm_text)
    if not rauw and llm_text.strip():
        logger.warning("annotatie: geen element-objecten uit de respons gehaald")

    gezien: dict[tuple[str, str], AnnotatieVoorstel] = {}
    for e in rauw:
        klasse = str(e.get("klasse", "")).strip()
        fragment = str(e.get("tekst", "")).strip()
        norm_frag = _normaliseer(fragment)
        idx = norm_corpus.find(norm_frag) if norm_frag else -1
        # Verwerp ongeldige klasse of niet-onderbouwd fragment: nooit stil doorlaten.
        if klasse not in GELDIGE_JAS_KLASSEN or idx < 0:
            verworpen.append(VerworpenFragment(
                klasse=klasse, tekst=fragment,
                reden="ongeldige_klasse" if klasse not in GELDIGE_JAS_KLASSEN else "niet_letterlijk",
            ))
            continue
        lid = str(scope_lid).strip() if scope_lid and str(scope_lid).strip() else str(e.get("lid", "")).strip()
        alts = [
            AnnotatieAlternatief(klasse=str(a.get("klasse", "")).strip(), motivatie=str(a.get("motivatie", "")).strip())
            for a in e.get("alternatieven", [])
            if isinstance(a, dict) and str(a.get("klasse", "")).strip() in GELDIGE_JAS_KLASSEN
        ]
        # Prioriteitsvalidatie (deterministisch, geen LLM): corrigeer de klasse als een
        # alternatief hogere JAS-prioriteit heeft (bv. Tijdsaanduiding > Variabele).
        # Eén bron van waarheid: REGELS in jas_klassen.py – geen aparte prompt-proza nodig.
        klasse, alts = _pas_prioriteitsregels_toe(klasse, alts)
        # Twee keer hetzelfde fragment in één ronde: het model herhaalt zich. De eerste telt —
        # die draagt eventueel het id uit een eerdere ronde, en daaraan hangen de beslissingen.
        # Gaat het om dezelfde span met een ANDERE klasse, dan is dat geen herhaling maar twijfel:
        # de tweede lezing wordt een alternatief op het eerste voorstel in plaats van een tweede
        # element. Eén klasse per element, de andere lezing zichtbaar – stil weggooien zou precies
        # de twijfel verbergen die de jurist moet zien.
        sleutel = sleutel_van(fragment, lid)
        if (eerste := gezien.get(sleutel)) is not None:
            _voeg_alternatief_toe(eerste, klasse, str(e.get("toelichting", "")).strip())
            continue
        # Bereken de anker-offsets op de originele brontekst. De genormaliseerde positie is al
        # bekend (idx in norm_corpus); we mappen die terug naar de originele tekst zodat de UI
        # exact de juiste tekens kan markeren – ook als de brontekst meerdere witruimte-varianten
        # bevat die _normaliseer samentrekt.
        #
        # Zoek binnen het lid waar het element zelf over gaat. Het lid en de positie gaan over
        # hetzelfde ding; ze los van elkaar bepalen laat ze uit elkaar lopen, en dan wijst de
        # werkplek een ander stuk wet aan dan de vindplaats belooft. Live gebeurd op artikel 6
        # Uitvoeringsregeling Awir: "derde" (lid 2) landde op het rangtelwoord in lid 1.
        orig_start, orig_eind, gevonden_lid = _lokaliseer(
            corpus, norm_corpus, norm_frag, lid, str(e.get("onderdeel", "")),
        )
        if gevonden_lid != lid:
            # Het lid is gecorrigeerd naar de plek van het anker; de ontdubbelsleutel verandert mee.
            lid = gevonden_lid
            sleutel = sleutel_van(fragment, lid)
            if (eerste := gezien.get(sleutel)) is not None:
                _voeg_alternatief_toe(eerste, klasse, str(e.get("toelichting", "")).strip())
                continue
        anker = _maak_anker(corpus, orig_start, orig_eind, lid) if orig_start >= 0 else None
        vindplaats = f"{bwb_id} {aanduiding_in_woorden(artikel, lid, soort)}"
        # Een id uit een eerdere ronde behouden (herziening van een bestaand element); anders een
        # nieuw id. Zo blijft de koppeling met de Critic én met de api-elementen intact – maar
        # alléén voor een id dat het model ook echt is aangeboden.
        bestaand_id = str(e.get("id", "")).strip()
        if geldige_ids is not None and bestaand_id and bestaand_id not in geldige_ids:
            logger.info("annotatie: onbekend element-id genegeerd", extra={"element_id": bestaand_id[:40]})
            bestaand_id = ""
        voorstel = AnnotatieVoorstel(
            id=bestaand_id or uuid.uuid4().hex[:12],
            klasse=klasse,
            tekst=fragment,
            lid=lid,
            toelichting=str(e.get("toelichting", "")).strip(),
            alternatieven=alts,
            grounded=True,
            vindplaats=vindplaats,
            anker=anker,
        )
        gezien[sleutel] = voorstel
        voorstellen.append(voorstel)
    return voorstellen, verworpen


def _verwerk_critic(
    llm_text: str, ids: list[str]
) -> tuple[dict[str, CriticOordeel], list[OntbrekendItem], list[str]]:
    """Parse het Critic-JSON: per element-id een oordeel + een ontbrekend-lijst.

    Koppelt op `id`, met `index` (positie in `ids`) als terugval – een model dat het id-veld vergeet
    verliest zo niet stilzwijgend álles. Op positie alleen koppelen kan niet meer: zodra een
    herzieningsronde een element toevoegt of weglaat, schuiven de indices en landt een oordeel op het
    verkeerde element.

    Robuust tegen proza/afkapping (fast-path hele-JSON, anders de gebalanceerde {…}-objecten).
    Onbekende id's en indices buiten bereik worden genegeerd. Een oordeel met een ONLEESBAAR
    niveau wordt ook overgeslagen, maar niet meer stil: de derde retourwaarde geeft die waarden
    terug zodat de tijdlijn ze kan melden. Nooit exceptions naar de caller – de Critic mag de
    annotatie niet breken.
    """
    oordelen: dict[str, CriticOordeel] = {}
    ontbrekend: list[OntbrekendItem] = []
    geldige_ids = set(ids)
    #: Aandacht-waarden die we niet konden lezen. Zie de plek waar hij gevuld wordt: dit scheidt
    #: "de Critic sloeg het element over" van "wij gooiden zijn oordeel weg".
    onleesbaar: list[str] = []

    data: dict[str, Any] | None = None
    raw = (llm_text or "").strip()
    kandidaat = raw.strip("`")
    if kandidaat.lower().startswith("json"):
        kandidaat = kandidaat[4:]
    s, e = kandidaat.find("{"), kandidaat.rfind("}")
    if s != -1 and e > s:
        try:
            parsed = json.loads(kandidaat[s : e + 1])
            if isinstance(parsed, dict):
                data = parsed
        except json.JSONDecodeError:
            data = None
    # Fallback: los de gebalanceerde objecten op en herken oordeel-/ontbrekend-objecten.
    oordeel_objs: list[dict[str, Any]] = []
    ontbrekend_objs: list[dict[str, Any]] = []
    if isinstance(data, dict):
        oordeel_objs = [o for o in data.get("oordelen", []) if isinstance(o, dict)]
        ontbrekend_objs = [o for o in data.get("ontbrekend", []) if isinstance(o, dict)]
    else:
        for obj in _balanced_objecten(raw):
            try:
                d = json.loads(obj)
            except json.JSONDecodeError:
                continue
            if not isinstance(d, dict):
                continue
            if ("id" in d or "index" in d) and "aandacht" in d:
                oordeel_objs.append(d)
            elif "klasse" in d and "reden" in d:
                ontbrekend_objs.append(d)

    for o in oordeel_objs:
        element_id = str(o.get("id", "")).strip()
        if element_id not in geldige_ids:
            # Terugval: positie in de aangeboden lijst.
            try:
                idx = int(o.get("index"))
            except (TypeError, ValueError):
                continue
            if not (0 <= idx < len(ids)):
                continue
            element_id = ids[idx]

        aandacht = str(o.get("aandacht", "")).strip().lower()
        motivatie = str(o.get("motivatie", "")).strip()
        if aandacht not in _AANDACHT and motivatie:
            # EEN OORDEEL ZONDER NIVEAU, MAAR MÉT EEN OPMERKING. Gemeten op 2 sep 2026 in ronde 1
            # van een annotatie op art. 2 lid 1 IW 1990: één oordeel kwam binnen met een leeg
            # `aandacht`-veld en een gevulde motivatie. Dat gooiden we in zijn geheel weg, waarna het
            # element bij de jurist stond alsof de Critic er nooit naar had gekeken — terwijl hij er
            # wel degelijk iets over te zeggen had.
            #
            # Het niveau wordt NIET aangevuld met een gok: een verzonnen "geel" is een oordeel dat
            # het model niet gaf, en dat is precies de schijnzekerheid die dit platform vermijdt.
            # Het blijft dus leeg — `_critic_melding` telt dat als "geen oordeel", de api houdt het
            # element op `voorgesteld` en de kaart toont *Niet beoordeeld* — maar de motivatie komt
            # nu wél bij de jurist terecht. Een meegegeven `actie` valt zonder rood niveau in de
            # gele tak van `pas_critic_toe`: voorgelegd, niet uitgevoerd. Dat is de veilige kant.
            onleesbaar.append(str(o.get("aandacht", "")).strip() or "(leeg)")
            logger.info("critic: oordeel zonder niveau, motivatie behouden",
                        extra={"element_id": element_id[:40]})
            oordelen[element_id] = CriticOordeel(aandacht="", motivatie=motivatie)
            continue
        if aandacht not in _AANDACHT:
            # HIER GING EEN OORDEEL STIL VERLOREN. Een oordeel zonder leesbaar niveau werd
            # weggegooid — inclusief de motivatie en de instructie — en het element kwam bij de
            # jurist alsof de Critic er nooit naar had gekeken. Dat zijn twee verschillende dingen:
            # "niet beoordeeld" is modelgedrag waar niets aan te doen valt, "wij konden zijn oordeel
            # niet lezen" is onze fout. Op 2 sep 2026 viel er in twee opeenvolgende runs op art. 2
            # lid 1 IW 1990 telkens precies één element buiten de boot; welke van de twee het was,
            # viel nergens af te lezen.
            #
            # Het niveau NIET aanvullen met een gok: een verzonnen "geel" is een oordeel dat het
            # model niet gaf, en dat is precies de schijnzekerheid die dit platform vermijdt. Wel de
            # motivatie bewaren — die is inhoud — en meetellen zodat het zichtbaar wordt.
            onleesbaar.append(str(o.get("aandacht", "")).strip() or "(leeg)")
            logger.info("critic: oordeel zonder leesbaar niveau",
                        extra={"aandacht": str(o.get("aandacht", ""))[:20],
                               "element_id": element_id[:40]})
            continue

        actie = str(o.get("actie", "behoud")).strip().lower()
        if actie not in _ACTIES:
            actie = "behoud"
        voorstel_klasse = str(o.get("voorstel_klasse", "")).strip()
        if voorstel_klasse and voorstel_klasse not in GELDIGE_JAS_KLASSEN:
            voorstel_klasse = ""
        voorstel_tekst = str(o.get("voorstel_tekst", "")).strip()

        # Weggooien is de zwaarste ingreep: alleen bij een expliciet rood oordeel. En vervangen
        # zonder te zeggen wát het moet worden is geen instructie maar een klacht.
        if actie == "verwijder" and aandacht != "rood":
            actie = "vervang"
        if actie == "vervang" and not (voorstel_klasse or voorstel_tekst):
            actie = "behoud"

        oordelen[element_id] = CriticOordeel(
            aandacht=aandacht,
            motivatie=motivatie,
            actie=actie,
            voorstel_klasse=voorstel_klasse,
            voorstel_tekst=voorstel_tekst,
        )

    for o in ontbrekend_objs:
        klasse = str(o.get("klasse", "")).strip()
        if klasse in GELDIGE_JAS_KLASSEN:
            ontbrekend.append(OntbrekendItem(
                klasse=klasse,
                reden=str(o.get("reden", "")).strip(),
                tekst=str(o.get("tekst", "")).strip(),
            ))

    return oordelen, ontbrekend, onleesbaar
