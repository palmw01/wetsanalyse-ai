"""Herkenning van verwijzingen tussen wetsartikelen.

Primair worden de gestructureerde ``<intref>``/``<extref>``-elementen uit de
toestand-XML gebruikt (met ``bwb-id``, ``doc`` en ``bwb-ng-variabel-deel``).
Als fallback detecteert een regex losse tekstverwijzingen zoals ``artikel 4``,
``artikel 6:162 BW`` of ``artikel 3:2 Awb`` die niet getagd zijn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lxml import etree

from app.afkortingen import zoek_bwb_id
from app.models import Verwijzing, VerwijzingSoort

# Verwijzingen mogen niet uit meta-data-subtrees komen.
_REF_XPATH = ".//*[self::intref or self::extref][not(ancestor::meta-data)]"

# Losse tekstverwijzingen: "artikel 4", "12a", "10.1", "3:2 Awb", "6:162 BW".
# Vangt het artikelnummer (cijfers met optionele letter/punt/dubbelepunt) plus
# een optionele wetafkorting (hoofdletter-initiaal, bv. BW, Awb, Sr).
# Geen IGNORECASE: de wetafkorting (bv. BW, Awb, Sr) begint met een hoofdletter,
# zodat losse woorden als "en"/"van" niet als afkorting worden aangezien.
_TEXT_REF = re.compile(
    r"\b[Aa]rtikel(?:en)?\s+"
    r"(?P<nummer>\d+[a-z]?(?:[.:]\d+[a-z]?)*)"
    r"(?:\s+(?P<wet>[A-Z][A-Za-z]{0,6}))?"
)

# Onderdelen van een jci-verwijzing (bv. "jci1.3:c:BWBR0005537&artikel=3:40").
_JCI_BWB = re.compile(r":c:(BWBR\d+)")
_JCI_ARTIKEL = re.compile(r"[&?]artikel=([^&]+)")
_JCI_LID = re.compile(r"[&?]lid=([^&]+)")
_JCI_ONDERDEEL = re.compile(r"[&?]o=([^&]+)")
_JCI_STRUCTUUR = re.compile(r"[&?](hoofdstuk|titeldeel|afdeling|paragraaf)=([^&]+)")


def jci_doel(doc: str | None) -> tuple[str | None, str | None, str | None]:
    """Ontleed een jci-``doc`` tot ``(bwb_id, artikelnummer, lidnummer)``.

    Versieparameters (``&z=``/``&g=``) worden genegeerd. Elk veld is ``None``
    als het niet in de verwijzing voorkomt (bv. een verwijzing naar een heel
    hoofdstuk levert geen artikel/lid).
    """
    if not doc:
        return (None, None, None)
    bwb = _JCI_BWB.search(doc)
    # Geneste circulaire-divisies dragen het volledige pad als herhaalde
    # ``&artikel=``-segmenten (bv. ``&artikel=79&artikel=79.5a``); het laatste is
    # het meest specifieke doel. Voor gewone wetten is er precies één segment.
    artikelen = _JCI_ARTIKEL.findall(doc)
    lidnrs = _JCI_LID.findall(doc)
    return (
        bwb.group(1) if bwb else None,
        artikelen[-1] if artikelen else None,
        lidnrs[-1] if lidnrs else None,
    )


def jci_to_ref_key(doc: str | None) -> str | None:
    """Vorm een stabiele artikelsleutel ``{bwb}#artikel={nr}`` uit een jci-doc.

    Versieparameters (``&z=``/``&g=``) worden genegeerd. Geeft ``None`` als de
    verwijzing geen concreet artikel aanduidt (bv. naar een heel hoofdstuk),
    zodat er geen onterechte VERWIJST_NAAR ontstaat.
    """
    bwb, artikel, _ = jci_doel(doc)
    if not bwb or not artikel:
        return None
    return f"{bwb}#artikel={artikel}"


def jci_structuurpad(doc: str | None) -> list[tuple[str, str]]:
    """Alle structuursegmenten van een jci, in volgorde: ``[("hoofdstuk","VIII"),("afdeling","2")]``."""
    return list(_JCI_STRUCTUUR.findall(doc)) if doc else []


def jci_node_ref_key(doc: str | None) -> tuple[str | None, str | None]:
    """De identiteitssleutel van een STRUCTUURNODE – met het volledige pad.

    Verschil met :func:`jci_doel_ref_key`, en waarom dat verschil er moet zijn.

    Die functie houdt van een structuurdoel alleen het **laatste** segment aan, dus
    ``&hoofdstuk=VIII&afdeling=1`` wordt ``{bwb}#afdeling=1``. Voor een *verwijzing* is dat
    verdedigbaar — je verwijst naar "afdeling 1" en niet naar het pad ernaartoe — maar als
    **identiteit** van een node is het fout: elke "Afdeling 1" van elke regeling landt dan op
    dezelfde IRI.

    Met alleen het laatste segment hebben 16 van de 93 afdelingen en 5 van de 27 paragrafen meer dan
    één ouder. ``urn:bwb:BWBR0002320:afdeling:1`` draagt dan vier afdelingen ineen — *Bezwaar*,
    *Overtredingen*, *Strafbare feiten* en *Vertegenwoordiging buiten rechte* — met vier titels, vier
    ouders en de artikelen van alle vier op één hoop. Bij de Invorderingswet is ``afdeling:1`` dan
    tegelijk *Aansprakelijkheid* (hoofdstuk VI) en *Verhaalsrechten* (hoofdstuk IV).

    Gevolg voor de lezer van de graaf: een verkeerde inhoudsopgave, artikelen die aan de verkeerde
    afdeling hangen, en een artikel dat in twee hoofdstukken tegelijk lijkt te zitten.

    Het pad is altijd beschikbaar: alle 93 afdelingsnodes dragen een jci die het meevoert. Regelingen
    met hiërarchische nummering (de Awb: ``afdeling=10.2.1``) hebben géén hoofdstuk-segment en houden
    dus precies dezelfde sleutel als met alleen het laatste segment — daar is ook geen collisie.

    Artikel-, lid- en onderdeelsleutels blijven ongemoeid: die zijn binnen een regeling al uniek.
    """
    if not doc:
        return (None, None)
    bwb_match = _JCI_BWB.search(doc)
    if not bwb_match:
        return (None, None)
    bwb = bwb_match.group(1)
    if _JCI_ARTIKEL.search(doc):
        # Een artikel (of lid/onderdeel) heeft zijn eigen unieke sleutel; het structuurpad
        # ernaartoe hoort daar niet in, anders verandert elke artikel-IRI in de graaf.
        return jci_doel_ref_key(doc)
    segmenten = jci_structuurpad(doc)
    if not segmenten:
        return (bwb, "wet")
    pad = "".join(f"#{naam}={waarde}" for naam, waarde in segmenten)
    return (f"{bwb}{pad}", segmenten[-1][0])


def jci_doel_ref_key(doc: str | None) -> tuple[str | None, str | None]:
    """Ontleed een jci-doc tot ``(ref_key, doel_soort)`` op élk niveau.

    Anders dan :func:`jci_to_ref_key` (alleen artikel-niveau) resolveert deze
    ook hele-structuur-, lid- en onderdeel-doelen:

    - ``&artikel=…``                     -> ``{bwb}#artikel={nr}`` ("artikel")
    - ``… &lid=…``                       -> ``…#lid={l}`` ("lid")
    - ``… &o=…[&o=…]``                   -> ``…#o={o1}[#o={o2}]`` ("onderdeel")
    - alleen ``&hoofdstuk=``/…           -> ``{bwb}#hoofdstuk={nr}`` (soortnaam)
    - alleen ``:c:BWBR…``                -> ``{bwb}`` ("wet")

    Versieparameters (``&z=``/``&g=``) worden genegeerd; van herhaalde
    ``&artikel=``-/structuursegmenten telt het laatste (meest specifieke).
    """
    if not doc:
        return (None, None)
    bwb_match = _JCI_BWB.search(doc)
    if not bwb_match:
        return (None, None)
    bwb = bwb_match.group(1)

    artikelen = _JCI_ARTIKEL.findall(doc)
    if artikelen:
        ref_key, soort = f"{bwb}#artikel={artikelen[-1]}", "artikel"
        lidnrs = _JCI_LID.findall(doc)
        if lidnrs:
            ref_key, soort = f"{ref_key}#lid={lidnrs[-1]}", "lid"
        onderdelen = _JCI_ONDERDEEL.findall(doc)
        if onderdelen:
            # Geneste onderdelen dragen het pad als herhaalde &o=-segmenten.
            ref_key = ref_key + "".join(f"#o={o}" for o in onderdelen)
            soort = "onderdeel"
        return (ref_key, soort)

    structuren = _JCI_STRUCTUUR.findall(doc)
    if structuren:
        naam, waarde = structuren[-1]
        return (f"{bwb}#{naam}={waarde}", naam)

    return (bwb, "wet")


def _normaliseer(tekst: str | None) -> str:
    return re.sub(r"\s+", " ", tekst or "").strip()


# --------------------------------------------------------------- lid en onderdeel uit de ankertekst
#
# De bron wijst met `doc` altijd een heel artikel aan: `&lid=` en `&o=` komen in geen enkele `<intref>`
# of `<extref>` voor (gemeten over Awb, AWR, IW 1990, Awir, Leidraad). Het lid en het onderdeel staan
# alleen in de tekst van de verwijzing zelf: "artikel 25, derde lid". Daarom wordt die tekst hier
# gelezen, met dezelfde nuchterheid als de rest: alleen wat er letterlijk staat, en bij twijfel niets.

_RANGTELWOORDEN = (
    "eerste tweede derde vierde vijfde zesde zevende achtste negende tiende elfde twaalfde "
    "dertiende veertiende vijftiende zestiende zeventiende achttiende negentiende twintigste "
    "eenentwintigste tweeëntwintigste drieëntwintigste vierentwintigste vijfentwintigste"
).split()
_RANG = {woord: nummer for nummer, woord in enumerate(_RANGTELWOORDEN, start=1)}
_WOORD = "|".join(sorted(_RANG, key=len, reverse=True))
_LIDNR = r"\d+[a-z]?"
_EN = r"(?:,\s*|\s+en\s+|\s+of\s+|\s+tot en met\s+)"
# "derde lid", "eerste en tweede lid", "eerste lid en derde tot en met zevende lid".
_LEDEN_WOORD = re.compile(
    rf"\b(?:{_WOORD})(?:(?:\s+lid)?{_EN}(?:{_WOORD}))*\s+(?:lid|leden)\b", re.IGNORECASE
)
# "lid 3", "leden 1 en 2", "lid 1 tot en met 3".
_LEDEN_CIJFER = re.compile(rf"\b(?:lid|leden)\s+{_LIDNR}(?:{_EN}{_LIDNR})*\b", re.IGNORECASE)
_NR = r"(?:[a-z]{1,2}|\d+[a-z]?°?)"
_EINDE = r"(?=$|[,;.]|\s+(?:en|of|van|in|bij)\b)"
# "onderdeel b", "onderdelen a en b", "onder a", "sub 2°"; "aanhef en" ervoor maakt niet uit.
_ONDERDELEN = re.compile(
    rf"\b(?:onderdelen|onderdeel|onder|sub)\s+(?P<lijst>{_NR}(?:{_EN}{_NR})*){_EINDE}"
)
# Een niveau dieper, direct erachter: "onderdeel e, onder 1°".
_DIEPER = re.compile(rf"^,?\s*(?:onder|sub|subonderdeel)\s+(?P<nr>{_NR}){_EINDE}")
# Woorden die op een nummer lijken: "onder de voorwaarde".
_GEEN_NUMMER = {"de", "en", "of", "in", "op", "te", "is", "na", "om", "al", "er", "ze"}
_ARTIKELNUMMER = re.compile(r"\d+[a-z]*(?:[.:]\d+[a-z]*)*")
# Waar het aanwijzen ophoudt en de naam van de regeling begint: "…, van de Awb".
_REGELINGSNAAM = re.compile(r"\s+(?:van|in|bij)\s+(?:de|het|die|deze|dat|dit|Boek)\b")


def _reeks(fragment: str, nummer: str, waarde=str) -> list[str]:
    """De nummers uit een opsomming; een "tot en met" vult aan wat ertussen ligt."""
    uit: list[str] = []
    tot = False
    for match in re.finditer(rf"tot en met|\b(?:en|of)\b|{nummer}", fragment):
        tekst = match.group()
        if tekst == "tot en met":
            tot = True
        elif tekst not in ("en", "of"):
            if tot and uit:
                uit.extend(_tussenliggend(uit[-1], waarde(tekst)))
            uit.append(waarde(tekst))
            tot = False
    return uit


def _tussenliggend(van: str, tot: str) -> list[str]:
    if van.isdigit() and tot.isdigit():
        return [str(n) for n in range(int(van) + 1, int(tot))]
    if len(van) == len(tot) == 1 and van.isalpha() and tot.isalpha():
        return [chr(n) for n in range(ord(van) + 1, ord(tot))]
    return []


def _leden(tekst: str) -> tuple[list[str], tuple[int, int] | None]:
    """De lidnummers in de tekst, en waar ze staan."""
    match = _LEDEN_WOORD.search(tekst)
    if match:
        return _reeks(match.group().lower(), rf"\b(?:{_WOORD})\b", lambda w: str(_RANG[w])), match.span()
    match = _LEDEN_CIJFER.search(tekst)
    if match:
        return _reeks(match.group(), rf"\b{_LIDNR}\b"), match.span()
    return [], None


def _kaal_nummer(nummer: str) -> str:
    """Het nummer zoals de jci het schrijft: "1°" → "1"."""
    return nummer.rstrip("°").lower()


@dataclass(frozen=True)
class Deeldoel:
    """Eén plek binnen een artikel: een lid, een pad van onderdelen, of beide."""

    lid: str | None = None
    onderdelen: tuple[str, ...] = ()

    def sleutel(self, artikel_sleutel: str) -> str:
        lid = f"#lid={self.lid}" if self.lid else ""
        return artikel_sleutel + lid + "".join(f"#o={o}" for o in self.onderdelen)


def deeldoelen(anker: str | None, artikel: str | None) -> list[Deeldoel]:
    """Wat de tekst van een verwijzing naar `artikel` binnen dat artikel aanwijst.

    "artikel 2, derde lid, onderdeel b, van de AWR" → lid 3, onderdeel b. "eerste en tweede lid" →
    twee doelen. Leeg als de tekst geen lid of onderdeel noemt, of als hij niet eenduidig over dit ene
    artikel gaat ("artikelen 3 en 4, eerste lid"): dan blijft de verwijzing op het artikel staan.

    "eerste en tweede lid, onderdeel a" zegt niet van welk lid: dat wordt beide leden, zonder onderdeel.
    Een volzin heeft geen eigen node en telt niet mee.
    """
    tekst = _normaliseer(anker)
    if not tekst or not artikel:
        return []
    naam = _REGELINGSNAAM.search(tekst)
    deel = tekst[: naam.start()] if naam else tekst

    leden, lid_plek = _leden(deel)
    match = _ONDERDELEN.search(deel, lid_plek[1] if lid_plek else 0)
    onderdelen: list[str] = []
    plekken = [lid_plek] if lid_plek else []
    dieper: str | None = None
    if match and match["lijst"].split()[0].rstrip(",") not in _GEEN_NUMMER:
        onderdelen = _reeks(match["lijst"], _NR, _kaal_nummer)
        eind = match.end()
        if diep := _DIEPER.match(deel[eind:]):
            dieper, eind = _kaal_nummer(diep["nr"]), eind + diep.end()
        plekken.append((match.start(), eind))
    if not plekken:
        return []

    # Blijft er precies één artikelnummer over, en is dat het artikel uit de jci? Anders is niet te
    # zeggen waar de leden bij horen.
    rest, begin = "", 0
    for van, tot in plekken:
        rest += deel[begin:van]
        begin = tot
    rest += deel[begin:]
    nummers = _ARTIKELNUMMER.findall(rest)
    if len(nummers) != 1 or not artikel.lower().endswith(nummers[0].lower()):
        return []

    if len(leden) > 1 or not onderdelen:
        return [Deeldoel(lid=lid) for lid in leden]
    lid = leden[0] if leden else None
    if len(onderdelen) == 1 and dieper:
        return [Deeldoel(lid=lid, onderdelen=(onderdelen[0], dieper))]
    return [Deeldoel(lid=lid, onderdelen=(o,)) for o in onderdelen]


def extract_references(element: etree._Element, *, eigen_bwb_id: str) -> list[Verwijzing]:
    """Haal gestructureerde verwijzingen uit een element (artikel of lid).

    De ``soort`` wordt bepaald door het tag-type (``intref``/``extref``); een
    ``extref`` naar de eigen wet wordt alsnog als intern beschouwd.
    """
    verwijzingen: list[Verwijzing] = []
    for ref in element.xpath(_REF_XPATH):
        doel_bwb = ref.get("bwb-id")
        is_intern = ref.tag == "intref" or (doel_bwb == eigen_bwb_id)
        verwijzingen.append(
            Verwijzing(
                soort=VerwijzingSoort.INTERN if is_intern else VerwijzingSoort.EXTERN,
                tekst=_normaliseer("".join(ref.itertext())),
                doel_bwb_id=doel_bwb,
                doel_pad=ref.get("bwb-ng-variabel-deel"),
                doc=ref.get("doc"),
                verwijzing_id=ref.get("verwijzing-id"),
            )
        )
    return verwijzingen


def detect_textual_references(tekst: str, *, eigen_bwb_id: str) -> list[Verwijzing]:
    """Detecteer losse (ongetagde) tekstverwijzingen naar artikelen (fallback).

    Een herkende wetafkorting wordt via :mod:`app.afkortingen` naar een BWB-id
    vertaald; zonder afkorting geldt de verwijzing als intern (eigen wet).
    Matches met een onbekende afkorting worden overgeslagen (te onzeker).
    """
    treffers: list[Verwijzing] = []
    for match in _TEXT_REF.finditer(tekst):
        nummer = match.group("nummer")
        wet = match.group("wet")
        if wet:
            doel_bwb = zoek_bwb_id(wet, nummer)
            if doel_bwb is None:
                continue
            anker = f"artikel {nummer} {wet}"
        else:
            doel_bwb = eigen_bwb_id
            anker = f"artikel {nummer}"
        treffers.append(
            Verwijzing(
                soort=VerwijzingSoort.TEKSTUEEL,
                tekst=anker,
                doel_bwb_id=doel_bwb,
                doel_artikel=nummer,
            )
        )
    return treffers
