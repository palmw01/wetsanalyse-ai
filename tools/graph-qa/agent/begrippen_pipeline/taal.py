"""De taalstap van de begrippenketen (ADR-004): kern, term, samenstelling en terugverwijzing.

Bouwt op de taallaag van de JAS-keten (`jas_pipeline/taal`, ADR-002): één `LinguisticAnalysis` per
bronnode, met offsets in die bron. Een formulering wordt daarbinnen opgezocht; er wordt niets
opnieuw getokeniseerd en niets aan de brontekst veranderd.

- **Kern**: het syntactische hoofd van de span (het hoofd ligt erbuiten), met voorrang voor een
  zelfstandig naamwoord, dan een voornaamwoord of bijvoeglijk naamwoord ("degene die …";
  "belastingschuldige" heet bij spaCy een bijvoeglijk naamwoord).
- **Term**: de kern met haar vaste modificeerders (bijvoeglijk naamwoord, samenstelling), zonder
  lidwoord of aanwijzend woord, in kleine letters, met de kern als lemma. "Een voorlopige
  aanslag" → "voorlopige aanslag".
- **Beperkt**: de span draagt een bijzin of voorzetselgroep aan de kern ("een belastingaanslag
  die een uit te betalen bedrag behelst"). Dat wijst op een soort, niet op een synoniem. Een
  nevenschikking ("beschikking of uitspraak"), een verwijzing ("bedoeld in onderdeel c") en een
  van-complement ("partner van de belanghebbende", "Minister van Financiën") beperken niet.
- **Kop van de samenstelling**: corpusgebonden. Is een andere kern in het manifest een staart van
  deze kern ("navorderingsaanslag" eindigt op "aanslag"), dan is dat de kop. Een algemeen
  woordenboek komt pas als de meting erom vraagt; zo kan deze stap geen kop verzinnen die in het
  werkgebied niet voorkomt.
- **Zin**: draagt de span een persoonsvorm ("De eerste termijn vervalt …", "Indien … leidt …"),
  dan is het een zin en geen term. De kern is dan het onderwerp, en dat met een losse naamwoordgroep
  vergelijken als "zelfde term" geeft vragen die nergens over gaan. Zonder parse onbekend (`False`).
- **Aanwijzend**: begint de formulering met "die", "deze", "dat" of "dit", dan wijst ze terug naar
  de dichtstbijzijnde voorafgaande naamwoordgroep met dezelfde kern in dezelfde bron. Losse
  voornaamwoorden ("hij", "deze" zonder naamwoord) blijven buiten beschouwing.

Zonder parser (gedegradeerd) volgen kern en term uit de tekst zelf: het laatste woord, zonder
lidwoord. Er is dan geen kop-, beperkings- of antecedentbepaling, en de analyse zegt dat.
"""
from __future__ import annotations

import re

from ..jas_pipeline.taal.afgeleid import _KERN, naamwoordgroepen
from ..jas_pipeline.taal.model import LinguisticAnalysis
from ..jas_pipeline.taal.provider import TaalProvider
from .model import Formulering, Manifest, Taalanalyse

VERSIE = "3"
_NAAMWOORD = ("NOUN", "PROPN")
_AANWIJZEND = {"die", "deze", "dat", "dit"}
_LIDWOORD = {"de", "het", "een", "'t"}
_MIN_KOP = 4          # een kop van minder tekens is eerder een achtervoegsel dan een woord


def _tokens_in(a: LinguisticAnalysis, f: Formulering) -> list[int]:
    return [t.i for t in a.tokens if t.start >= f.start and t.eind <= f.eind]


def _kern(a: LinguisticAnalysis, binnen: list[int]) -> int | None:
    """Het syntactische hoofd: een token in de span waarvan het hoofd erbuiten ligt.

    Voorrang: een zelfstandig naamwoord, dan een voornaamwoord of bijvoeglijk naamwoord
    ("degene die …", "belastingschuldige"). Pas als geen hoofd nominaal is, het eerste
    zelfstandig naamwoord in de span.
    """
    span = set(binnen)
    buiten = [i for i in binnen if a.tokens[i].head not in span and a.tokens[i].upos != "PUNCT"]
    for soorten in (_NAAMWOORD, ("PRON", "ADJ")):
        for i in buiten:
            if a.tokens[i].upos in soorten:
                return i
    naamwoorden = [i for i in binnen if a.tokens[i].upos in _NAAMWOORD]
    if naamwoorden:
        return naamwoorden[0]
    return buiten[0] if buiten else None


def _nevengeschikt(a: LinguisticAnalysis, kern: int, binnen: list[int]) -> set[int]:
    """Naamwoorden die met "of"/"en" naast de kern staan, plus het voegwoord.

    Lineair bepaald, niet via de parse: spaCy hangt "de uitspraak" in "de kennisgeving van de
    beschikking of de uitspraak" aan "kennisgeving". De partner van een nevengeschikt naamwoord
    is het laatste naamwoord vóór het voegwoord; alleen als dat de kern is, hoort het erbij.
    """
    erbij: set[int] = set()
    for j, i in enumerate(binnen):
        if a.tokens[i].upos != "CCONJ":
            continue
        voor = [k for k in binnen[:j] if a.tokens[k].upos in _NAAMWOORD]
        na = [k for k in binnen[j + 1:] if a.tokens[k].upos in _NAAMWOORD]
        if voor and na and voor[-1] in ({kern} | erbij) and all(
                a.tokens[k].upos == "DET" for k in binnen[j + 1:binnen.index(na[0])]):
            erbij.update({i, na[0]})
    return erbij


def _beperkt(a: LinguisticAnalysis, kern: int, binnen: list[int]) -> bool:
    """Draagt de span een bijzin of voorzetselgroep aan de kern? "Bedoeld in" is een verwijzing."""
    span = set(binnen)
    for k in a.kinderen(kern):
        t = a.tokens[k]
        if k not in span:
            continue
        if t.deprel == "nmod" and _relatum(a, k):
            continue
        if t.deprel in ("acl:relcl", "nmod") or (t.deprel == "acl" and t.lemma != "bedoelen"):
            return True
    return False


def _relatum(a: LinguisticAnalysis, k: int) -> bool:
    """"Partner van de belanghebbende", "Minister van Financiën": een van-complement noemt bij
    wie of wat de kern hoort, en maakt er geen soort van."""
    return any(a.tokens[c].deprel == "case" and a.tokens[c].lemma == "van" for c in a.kinderen(k))


def _term(a: LinguisticAnalysis, kern: int, binnen: list[int]) -> str:
    span = set(binnen)
    vast = {kern} | _nevengeschikt(a, kern, binnen)
    for k in a.kinderen(kern):
        if a.tokens[k].deprel in _KERN and k in span:
            vast.update(i for i in a.subboom(k) if i in span)
    woorden = []
    for i in sorted(vast):
        t = a.tokens[i]
        if t.upos in ("DET", "ADP") or t.tekst.lower() in _LIDWOORD | _AANWIJZEND:
            continue
        woorden.append((t.lemma or t.tekst) if i == kern else t.tekst)
    return " ".join(woorden).lower()


def _antecedent(a: LinguisticAnalysis, kernlemma: str, voor: int) -> tuple[int, int] | None:
    """De dichtstbijzijnde naamwoordgroep vóór `voor` met dezelfde kern (volledige groep)."""
    beste = None
    for c in naamwoordgroepen(a):
        if c.soort != "np" or c.eind > voor:
            continue
        if (a.tokens[c.kop].lemma or a.tokens[c.kop].tekst).lower() != kernlemma:
            continue
        tokens = [i for i in c.tokens if not (i == c.tokens[0] and a.tokens[i].upos == "ADP")]
        start, eind = a.bereik(tokens)
        if beste is None or start > beste[0]:
            beste = (start, eind)
    return beste


def _gedegradeerd(f: Formulering) -> Taalanalyse:
    woorden = [w for w in re.findall(r"\w[\w-]*", f.tekst.lower()) if w not in _LIDWOORD]
    aanwijzend = bool(woorden) and woorden[0] in _AANWIJZEND
    woorden = [w for w in woorden if w not in _AANWIJZEND] or [f.tekst.lower()]
    return Taalanalyse(element_id=f.element_id, kern=woorden[-1], kernvorm=woorden[-1],
                       term=" ".join(woorden), aanwijzend=aanwijzend, gedegradeerd=True)


def _koppen(analyses: dict[str, Taalanalyse]) -> dict[str, str]:
    kernen = {t.kern for t in analyses.values() if not t.gedegradeerd}
    koppen = {}
    for eid, t in analyses.items():
        staarten = [k for k in kernen if k != t.kern and len(k) >= _MIN_KOP
                    and t.kern.endswith(k) and len(t.kern) - len(k) >= 3]
        if staarten:
            koppen[eid] = max(staarten, key=len)
    return koppen


def analyseer(manifest: Manifest, provider: TaalProvider) -> dict[str, Taalanalyse]:
    """Per formulering haar taalanalyse; één parse per bronnode, deterministisch."""
    per_bron = {b.bron_iri: provider.analyseer(b.tekst) for b in manifest.bronnen}
    uit: dict[str, Taalanalyse] = {}
    for f in manifest.formuleringen:
        a = per_bron[f.bron_iri]
        binnen = _tokens_in(a, f)
        kern = _kern(a, binnen) if not a.gedegradeerd and binnen else None
        if kern is None:
            uit[f.element_id] = _gedegradeerd(f)
            continue
        kt = a.tokens[kern]
        lemma = (kt.lemma or kt.tekst).lower()
        term, beperkt = _term(a, kern, binnen), _beperkt(a, kern, binnen)
        aanwijzend = a.tokens[binnen[0]].tekst.lower() in _AANWIJZEND
        zin = any(a.tokens[i].upos in ("VERB", "AUX") and a.tokens[i].feat("VerbForm") == "Fin" for i in binnen)
        ante = _antecedent(a, lemma, f.start) if aanwijzend else None
        uit[f.element_id] = Taalanalyse(
            element_id=f.element_id, kern=lemma, kernvorm=kt.tekst, term=term, beperkt=beperkt,
            aanwijzend=aanwijzend, zin=zin, antecedent_start=ante[0] if ante else None,
            antecedent_eind=ante[1] if ante else None)
    for eid, kop in _koppen(uit).items():
        uit[eid] = uit[eid].model_copy(update={"kop": kop})
    return uit
