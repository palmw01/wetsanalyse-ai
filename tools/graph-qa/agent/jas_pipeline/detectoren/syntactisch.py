"""Syntactische detectoren (ADR-001): kandidaten uit de taalanalyse.

Een parse van wetstekst is minder betrouwbaar dan van krantentekst (lange zinnen, opsommingen,
labels als "c." die als onderwerp worden gelezen). Daarom:

- **Rechtsbetrekking** herkent de uitdrukkingswijze (H2:46) lexicaal op tokens – een modaal
  hulpwerkwoord of een normatief predicaat – en werkt dus óók op een gedegradeerde analyse. De span
  is het normsegment tussen de leestekens (. ; :); de hele zin is een optie.
- Een **rechtsgevolg als eigen hoofdzin** ('De eerste termijn vervalt …', '… vindt het eerste lid
  toepassing') herkent de gevolgdetector op de parse: het predicaat moet in de hoofdzin staan, niet
  in een bijzin, en de span is de eigen clause (`taal.clausebereik`).
- De overige detectoren hebben dependencies nodig. Zonder parse slaan ze zich **zichtbaar** over
  (`DetectorResult.overgeslagen` + reden), ze vallen niet stil terug.

Grammatica levert hier kandidaten, geen klassen: een onderwerp is geen rechtssubject omdat het een
onderwerp is (profiel Rechtssubject, negative_patterns). `possible_classes` zegt wat mogelijk is;
de volgorde is voorkeur, geen besluit.
"""
from __future__ import annotations

import json
import re
from functools import cache

from ..kandidaten import BronSpan, Candidate, DetectorResult, Evidence, SpanOption
from ..taal import LinguisticAnalysis, Token
from ..taal.afgeleid import _BIJZIN, _KERN, clausebereik, predicaten
from ..taal.grenzen import analyseer_grenzen
from ..taal.verwijzingen import VERSIE as VERWIJZING_VERSIE
from . import BronTekst, resultaat
from .ontleding import bereik, in_verwijzing, parse_of_reden, zonder_randfunctie
from .regels import maskers, woordenlijsten

SUBJ, OBJ, BETR, FEIT, VW, VAR, PAR, OP, AR = (
    "Rechtssubject", "Rechtsobject", "Rechtsbetrekking", "Rechtsfeit", "Voorwaarde",
    "Variabele en variabelewaarde", "Parameter en parameterwaarde", "Operator", "Afleidingsregel")

_ONDERWERP = {"nsubj", "nsubj:pass", "obl:agent", "csubj"}


@cache
def _lijst(naam: str) -> re.Pattern:
    return re.compile(rf"^(?:{woordenlijsten()[naam]})$", re.IGNORECASE)


# Gedeelde ontledingshulp staat in `ontleding`; de korte namen blijven voor de detectoren hier.
_parse_of_reden, _in_verwijzing, _bereik, _zonder_randfunctie = (
    parse_of_reden, in_verwijzing, bereik, zonder_randfunctie)


def _optie(bron: BronTekst, grens: tuple[int, int], soort: str) -> SpanOption:
    return SpanOption(soort=soort, span=BronSpan.van(bron.span(*grens)))


def _kandidaat(bron: BronTekst, grenzen: list[tuple[tuple[int, int], str]], klassen, bewijs) -> Candidate:
    """De eerste grens is de kandidaat, de rest (ontdubbeld) zijn spanopties."""
    eerste = grenzen[0][0]
    gezien, opties = {eerste}, []
    for g, soort in grenzen[1:]:
        if g not in gezien:
            gezien.add(g)
            opties.append(_optie(bron, g, soort))
    return Candidate.maak(bron.span(*eerste), klassen, bewijs, opties)


# --- Rechtsbetrekking: lexicaal, werkt ook zonder parse --------------------------------------

def _norm_in(stuk: str) -> re.Match | None:
    """Modaal hulpwerkwoord of normatief predicaat (H2:46); gedeeld door norm- en NP-detectie."""
    return (re.search(rf"\b(?:{woordenlijsten()['MODAAL']})\b", stuk, re.IGNORECASE)
            or re.search(rf"\b(?:{woordenlijsten()['NORMATIEF']})\b", stuk, re.IGNORECASE))


def _normsegmenten(tekst: str) -> list[tuple[int, int]]:
    """Beschermde segmenten met een normatief predicaat; zelfde grenzen als NormDetector."""
    return [(g.start, g.eind) for g in analyseer_grenzen(tekst).segmenten(tekst) if _norm_in(tekst[g.start:g.eind])]


_ONDERGESCHIKT = {"acl", "acl:relcl", "advcl"}


def _modaal_alleen_in_bijzin(a: LinguisticAnalysis, s: int, e: int) -> bool:
    """Staat elk modaal werkwoord in dit segment in een bijzin? 'de termijn waarbinnen de betaling moet
    plaatsvinden' noemt een termijn, geen plicht: de norm zit in de relatieve bijzin van een naamwoordgroep.
    Een bijzin is een `acl`, `acl:relcl` of `advcl` ergens boven het werkwoord in de boom."""
    modalen = [t for t in a.tokens if s <= t.start < e and _lijst("MODAAL").match(t.tekst)]

    def in_bijzin(i: int) -> bool:
        gezien = set()
        while i >= 0 and i not in gezien:
            gezien.add(i)
            if a.tokens[i].deprel in _ONDERGESCHIKT:
                return True
            i = a.tokens[i].head
        return False
    return bool(modalen) and all(in_bijzin(t.i) for t in modalen)


def _normsignaal(tekst: str, s: int, e: int, a: LinguisticAnalysis | None) -> tuple[re.Match | None, re.Match | None]:
    """(modaal, normatief) in het segment `s:e`. Met een parse telt een modaal werkwoord alleen in de hoofdzin;
    zonder parse lexicaal, zoals altijd. Gedeeld door de norm- en de tegenwoordige-tijddetector, zodat een
    modaal werkwoord in een bijzin de norm in de hoofdzin niet verbergt."""
    stuk = tekst[s:e]
    modaal = re.search(rf"\b(?:{woordenlijsten()['MODAAL']})\b", stuk, re.IGNORECASE)
    if modaal and a is not None and _modaal_alleen_in_bijzin(a, s, e):
        modaal = None
    normatief = None if modaal else re.search(rf"\b(?:{woordenlijsten()['NORMATIEF']})\b", stuk, re.IGNORECASE)
    return modaal, normatief


class NormDetector:
    REGELS: tuple[str, ...] = ("jas.betrekking.modaal_predicaat", "jas.betrekking.vaste_uitdrukking",
                               "jas.betrekking.normatief_adjectief", "jas.feit.rechtsgevolg_in_norm")
    naam = "norm"
    # 3: D03: Rechtsfeit alleen met een rechtsgevolg in het segment
    # 4: met een parse telt een modaal werkwoord alleen in de hoofdzin, niet in een bijzin
    versie = "4"

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        tekst = bron.tekst
        structuur = analyseer_grenzen(tekst)
        zinnen = structuur.zinnen(tekst)
        a, _ = _parse_of_reden(bron)
        kandidaten = []
        for segment in structuur.segmenten(tekst):
            s, e = segment.start, segment.eind
            stuk = tekst[s:e]
            modaal, normatief = _normsignaal(tekst, s, e, a)
            if not (modaal or normatief):
                continue
            # Delegatieformule ('kunnen … regels worden gesteld') is Delegatiebevoegdheid (H2:127).
            if re.search(r"\bregels\b.*\bgesteld\b", stuk, re.IGNORECASE):
                continue
            s2, e2 = _trim(tekst, s, e)
            if s2 >= e2:
                continue
            treffer = modaal or normatief
            regel = ("jas.betrekking.modaal_predicaat" if modaal else
                     "jas.betrekking.vaste_uitdrukking" if " " in treffer.group() else
                     "jas.betrekking.normatief_adjectief")
            zin = next(((z.start, z.eind) for z in zinnen if z.start <= s2 and e2 <= z.eind), (s2, e2))
            grenzen = [((s2, e2), "segment"), (_trim(tekst, *zin), "zin")]
            bewijs = [Evidence(detector=self.naam, code="NORMATIVE_PREDICATE", regel=regel, detail=treffer.group())]
            # Een normsignaal bewijst op zichzelf geen rechtsfeit: dat vraagt een rechtsgevolg (H2:53).
            gevolg = re.search(rf"\b(?:{woordenlijsten()['RECHTSGEVOLG']})\b", stuk, re.IGNORECASE)
            if gevolg:
                bewijs.append(Evidence(detector=self.naam, code="LEGAL_EFFECT_PREDICATE",
                                       regel="jas.feit.rechtsgevolg_in_norm", detail=gevolg.group()))
            kandidaten.append(_kandidaat(bron, grenzen, [BETR, FEIT] if gevolg else [BETR], bewijs))
        return resultaat(self, bron, kandidaten)


def _trim(tekst: str, s: int, e: int) -> tuple[int, int]:
    """Witruimte, een label ('a.', '1°.') en een term met dubbele punt aan het begin weg."""
    while s < e and tekst[s] in " \t\n":
        s += 1
    label = re.match(r"[a-z0-9]{1,3}°?\.\s+", tekst[s:e])
    if label:
        s += label.end()
    while e > s and tekst[e - 1] in " \t\n:,":
        e -= 1
    return s, e


# --- naamwoordgroepen: subject, object, variabele, parameter ------------------------------------

def _naamwoordelijk_gezegde(a: LinguisticAnalysis, t: Token) -> bool:
    """`is invorderbaar`, `is bevoegd`: het naamwoordelijk deel van het gezegde, geen naamwoordgroep.

    Herkenbaar aan een koppelwerkwoord (`cop`) als kind en géén lidwoord. De tagger noemt zo'n woord
    soms een NOUN – bij art. 9 lid 1 IW 1990 ("Een belastingaanslag is invorderbaar …") wordt
    "invorderbaar" daardoor een OBJECT_NP-kandidaat met de hele zin als grens, en kiest het model
    Variabele. Het gezegde draagt de normatieve relatie; die vindt de
    NormDetector. Met lidwoord ("is de ontvanger") blijft het wél een naamwoordgroep."""
    kinderen = [a.tokens[k] for k in a.kinderen(t.i)]
    return any(k.deprel == "cop" for k in kinderen) and not any(k.deprel == "det" for k in kinderen)


def _nominaal(a: LinguisticAnalysis, t: Token) -> bool:
    if _naamwoordelijk_gezegde(a, t):
        return False
    if t.upos in {"NOUN", "PROPN"}:
        return True
    if t.upos == "PRON":
        return bool(_lijst("ROL").match(t.tekst))
    if t.upos in {"VERB", "ADJ"}:        # 'de verzekerde', 'een bestuurder die …': genominaliseerd
        return any(a.tokens[k].deprel == "det" and a.tokens[k].tekst.lower() != "het" for k in a.kinderen(t.i))
    return False


PERSOON, PARTIJ, ZAAK, HANDELING, ONBEKEND = "persoon", "partij", "zaak", "handeling", "onbekend"
_REGELINGSNAAM = ("wet", "wetboek", "besluit", "regeling")


def _is_zaak(t: Token) -> bool:
    return (t.lemma or t.tekst).lower().endswith(tuple(woordenlijsten()["ZAAK"].split("|")))


def _is_partij(t: Token) -> bool:
    """Kan dit een partij zijn zonder in de rollenlijst te staan? Een woord voor een partij, een eigennaam die geen
    regeling noemt, of het handelend voorwerp ('door de ontvanger'). Alleen een hypothese: het model kiest."""
    lemma = (t.lemma or t.tekst).lower()
    return (lemma.endswith(tuple(woordenlijsten()["PARTIJ"].split("|"))) or t.deprel == "obl:agent"
            or (t.upos == "PROPN" and not lemma.endswith(_REGELINGSNAAM)))


def referent(a: LinguisticAnalysis, t: Token, uitgesloten: list[tuple[int, int]]) -> str:
    """Wat de kop van een naamwoordgroep aanduidt: een persoon, een zaak, een handeling of onbekend.

    Een rol of persoonlijk voornaamwoord gaat voor (ROL is disjunct met ZAAK). Een document of
    rechtshandeling als ding ('het aanslagbiljet', 'een belastingaanslag') is een zaak; een
    genominaliseerde handeling ('de toepassing van …') een handeling. Geen van beide kan drager van
    een recht of plicht zijn, dus geen Rechtssubject (profiel Rechtssubject, negative_patterns).
    """
    lemma = (t.lemma or t.tekst).lower()
    if t.upos == "PRON" or _lijst("ROL").match(lemma) or _lijst("ROL").match(t.tekst):
        return PERSOON
    if _is_zaak(t):
        return ZAAK
    if _is_partij(t):
        return PARTIJ
    if _nominalisatie(a, t, uitgesloten):
        return HANDELING
    return ONBEKEND


@cache
def _duur() -> re.Pattern:
    """Een kale duur: telwoord + periode ('zes weken', 'één maand')."""
    return re.compile(rf"(?:{woordenlijsten()['TELWOORD']})\s+(?:{woordenlijsten()['PERIODE']})", re.IGNORECASE)


class NaamwoordgroepDetector:
    REGELS: tuple[str, ...] = (
        "jas.parameter.beschrijving", "jas.variabele.uitvoer_van_afleiding", "jas.variabele.eigenschap_np",
        "jas.variabele.duur_np",
        "jas.subject.voornaamwoord", "jas.subject.rollexicon", "jas.subject.partij", "jas.object.zaak_als_kern",
        "jas.object.handeling_als_kern", "jas.subject.np_bij_normatief_predicaat",
        "jas.subject.np", "jas.object.opsommingsonderdeel", "jas.object.np_bij_normatief_predicaat", "jas.object.np")
    naam = "naamwoordgroep"
    # Grammaticale rol zonder juridische functie: blokkeert sterk patroonbewijs niet (audit D05). Een
    # getypeerde zaak of handeling is net zo generiek: het zegt wat de groep níét is, geen functie.
    BEWIJS = {"SUBJECT_NP": ("generiek", ""), "OBJECT_NP": ("generiek", ""), "ENUMERATED_NP": ("generiek", ""),
              "THING_NP": ("generiek", ""), "ACTION_NP": ("generiek", ""), "PARTY_NP": ("generiek", ""),
              "DURATION_NP": ("generiek", "")}
    # 3: een zaak of handeling als kop krijgt geen Rechtssubject (art. 9 lid 5 IW 1990)
    # 4: een onderdeel onder een aanhef heeft normcontext
    # 5: een partij buiten de rollenlijst krijgt Rechtssubject als hypothese
    # 6: geen kale kern van een nominalisatie, niets binnen een vaste uitdrukking
    # 7: een aantalsgrens valt buiten de groep
    # 8: een grootheid ('de betalingstermijn') is een eigenschap; een duur ('zes weken') geen subject of object
    versie = f"8+verwijzing.{VERWIJZING_VERSIE}"

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        kandidaten = []
        normen = _normsegmenten(bron.tekst)
        # Een onderdeel van een opsomming draagt zijn norm in de aanhef van de ouder, niet in de eigen tekst.
        onder_aanhef = bron.context.rstrip().endswith(":")
        uitgesloten = _vaste_uitdrukkingen(bron.tekst)
        # Een aantalsgrens hoort niet bij de groep: "niet meer dan één woning" is een Operator, een waarde en een zaak.
        grenzen_aantal = [m.span() for m in re.finditer(
            rf"\b(?:{woordenlijsten()['AANTALSVERGELIJKING']})\s+(?:{woordenlijsten()['TELWOORD']})\b", bron.tekst, re.IGNORECASE)]
        in_aantal = {x.i for x in a.tokens if _in_vaste_uitdrukking(x, grenzen_aantal)}
        for t in a.tokens:
            aantal = in_aantal - {t.i}
            if not _nominaal(a, t) or t.deprel in {"fixed", "flat", "flat:name", "compound", "nmod:poss"}:
                continue
            # Een handeling met een eigen voorwerp is de kandidaat; haar kale kern is geen object of kenmerk.
            if _in_vaste_uitdrukking(t, uitgesloten) or (_nominalisatie(a, t, uitgesloten) and _heeft_voorwerp(a, t)):
                continue
            kern = {t.i} | {i for k in a.kinderen(t.i) if a.tokens[k].deprel in _KERN for i in a.subboom(k)}
            zonder_bijzin = set(a.subboom(t.i)) - {i for k in a.kinderen(t.i)
                                                    if a.tokens[k].deprel in {*_BIJZIN, "conj", "parataxis", "punct", "cc"}
                                                    for i in a.subboom(k)}
            geheel = set(a.subboom(t.i)) - {i for k in a.kinderen(t.i)
                                            if a.tokens[k].deprel in {"conj", "parataxis", "cc", "punct"}
                                            for i in a.subboom(k)}
            grenzen = [(g, soort) for g, soort in (
                (_bereik(a, _zonder_randfunctie(a, kern - aantal, t.i)), "np_kern"),
                (_bereik(a, _zonder_randfunctie(a, zonder_bijzin - aantal, t.i)), "np"),
                (_bereik(a, _zonder_randfunctie(a, geheel - aantal, t.i)), "np_met_bijzin")) if g]
            if not grenzen or _in_verwijzing(bron, *grenzen[0][0]):
                continue
            lemma = (t.lemma or t.tekst).lower()
            norm = onder_aanhef or any(s <= t.start < e for s, e in normen)
            if _duur().fullmatch(bron.tekst[slice(*grenzen[0][0])]):
                # Een duur is geen drager en geen voorwerp van een recht (H2:26, H2:35): alleen een waarde, en de
                # tijdsaanduiding eromheen gaat daar weer voor (JAS-PRIORITY-001).
                bewijs, klassen = [Evidence(detector=self.naam, code="DURATION_NP", regel="jas.variabele.duur_np",
                                            relatie=t.deprel, detail=t.tekst)], [VAR]
            else:
                bewijs, klassen = self._classificeer_signaal(a, t, lemma, norm, referent(a, t, uitgesloten))
            kandidaten.append(_kandidaat(bron, grenzen, klassen, bewijs))
        return resultaat(self, bron, kandidaten)

    def _classificeer_signaal(self, a: LinguisticAnalysis, t: Token, lemma: str, norm: bool = True,
                              soort: str = ONBEKEND):
        """Welke klassen mogelijk zijn en waarom – signalen uit het profiel, geen besluit.

        Generieke onderwerp- en objectsignalen heten alleen 'bij normatief predicaat' als dat predicaat
        in hetzelfde beschermde segment staat (audit D01). Zonder normcontext is een lijdend onderwerp
        of een object geen dragende partij: Rechtssubject vervalt daar als hypothese. Hetzelfde geldt,
        in elke zinsrol, voor een zaak of handeling als kop (`referent`).
        """
        rel = t.deprel
        if _lijst("PARAMETERWOORD").match(lemma) or _lijst("PARAMETERWOORD").match(t.tekst):
            return [Evidence(detector=self.naam, code="PARAMETER_NOUN", regel="jas.parameter.beschrijving",
                             relatie=rel, detail=t.tekst)], [PAR, VAR]
        # Een grootheid ('de betalingstermijn', 'de vervaldag') is net zo goed een kenmerk: één lijst, twee lezers.
        if any(lemma.endswith(w) for naam in ("EIGENSCHAP", "GROOTHEID") for w in woordenlijsten()[naam].split("|")):
            regel = ("jas.variabele.uitvoer_van_afleiding"
                     if rel in _ONDERWERP and (a.tokens[t.head].lemma or "") in {"bedragen"}
                     else "jas.variabele.eigenschap_np")
            return [Evidence(detector=self.naam, code="PROPERTY_NOUN", regel=regel, relatie=rel,
                             detail=t.tekst)], [VAR, OBJ]
        if t.upos == "PRON":
            return [Evidence(detector=self.naam, code="PERSON_PRONOUN", regel="jas.subject.voornaamwoord",
                             relatie=rel, detail=t.tekst)], [SUBJ]
        if _lijst("ROL").match(lemma) or _lijst("ROL").match(t.tekst):
            return [Evidence(detector=self.naam, code="ROLE_NOUN", regel="jas.subject.rollexicon",
                             relatie=rel, detail=t.tekst)], [SUBJ, OBJ]
        if soort == PARTIJ:
            return [Evidence(detector=self.naam, code="PARTY_NP", regel="jas.subject.partij",
                             relatie=rel, detail=t.tekst)], [SUBJ, OBJ]
        if soort == ZAAK:
            return [Evidence(detector=self.naam, code="THING_NP", regel="jas.object.zaak_als_kern",
                             relatie=rel, detail=t.tekst)], [OBJ, VAR]
        if soort == HANDELING:
            return [Evidence(detector=self.naam, code="ACTION_NP", regel="jas.object.handeling_als_kern",
                             relatie=rel, detail=t.tekst)], [OBJ, VAR]
        if rel in _ONDERWERP:
            regel = "jas.subject.np_bij_normatief_predicaat" if norm else "jas.subject.np"
            klassen = [OBJ, VAR] if (not norm and rel == "nsubj:pass") else [SUBJ, OBJ, VAR]
            return [Evidence(detector=self.naam, code="SUBJECT_NP", regel=regel,
                             relatie=rel, detail=t.tekst)], klassen
        if rel == "conj":
            return [Evidence(detector=self.naam, code="ENUMERATED_NP", regel="jas.object.opsommingsonderdeel",
                             relatie=rel, detail=t.tekst)], [OBJ, SUBJ, VAR]
        if not norm:
            return [Evidence(detector=self.naam, code="OBJECT_NP", regel="jas.object.np",
                             relatie=rel, detail=t.tekst)], [OBJ, VAR]
        return [Evidence(detector=self.naam, code="OBJECT_NP", regel="jas.object.np_bij_normatief_predicaat",
                         relatie=rel, detail=t.tekst)], [OBJ, VAR, SUBJ]


# --- bijzinnen: 'als'-voorwaarde en beperkende relatieve bijzin --------------------------------

# Voegwoorden van een voorwaardelijke bijzin (H2:64). De grens komt hier uit de parse, dus een komma in een
# verwijzing of opsomming knipt de bijzin niet, zoals in de regel `jas.voorwaarde.voorwaardelijke_bijzin`.
_VOORWAARDELIJK = {"als", "indien", "mits", "tenzij", "wanneer", "ingeval", "voorzover", "zolang"}


def _voegwoord_van(a: LinguisticAnalysis, t: Token) -> Token | None:
    """Het voorwaardelijke voegwoord van bijzin `t`. De parser hangt het soms aan een woord in de bijzin
    ('Indien op grond van artikel 25 …' aan 'artikel'), dus ook een voegwoord direct vóór de bijzin telt."""
    van = (a.tokens[i] for i in a.subboom(t.i) if a.tokens[i].deprel == "mark")
    return next((m for m in van if m.tekst.lower() in _VOORWAARDELIJK), None)


def _bijzinbereik(a: LinguisticAnalysis, tokens: set[int]) -> tuple[int, int] | None:
    """Een bijzin mag komma's bevatten; alleen die aan de rand vallen weg."""
    geordend = sorted(tokens)
    if not a.aaneengesloten(tuple(geordend)):
        return None
    while geordend and a.tokens[geordend[-1]].upos == "PUNCT":
        geordend.pop()
    return (a.tokens[geordend[0]].start, a.tokens[geordend[-1]].eind) if geordend else None


class BijzinDetector:
    REGELS: tuple[str, ...] = ("jas.voorwaarde.als_bijzin", "jas.voorwaarde.beperkende_bijzin",
                               "jas.voorwaarde.beperkende_bijzin_bij_zaak")
    naam = "bijzin"
    # 3: een beperkende bijzin bij een zaak of handeling biedt geen Rechtssubject aan
    # 4: elk voorwaardelijk voegwoord, en de bijzin zelf als spanoptie
    versie = f"4+verwijzing.{VERWIJZING_VERSIE}"

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        kandidaten = []
        uitgesloten = _vaste_uitdrukkingen(bron.tekst)
        for t in a.tokens:
            kinderen = a.kinderen(t.i)
            # Ook vergelijkend 'als dat van …' en 'als bestuurder' kunnen mark + advcl krijgen.
            # Een nominale groep zonder werkwoordelijke predicatie is nog geen conditionele bijzin.
            als = _voegwoord_van(a, t)
            eigen_predicaat = any(a.tokens[i].upos in {"VERB", "AUX"} for i in a.subboom(t.i)) if als else False
            if t.deprel in _BIJZIN and als is not None and eigen_predicaat \
                    and not _in_verwijzing(bron, als.start, als.eind):
                g = _bijzinbereik(a, {als.i, *a.subboom(t.i)})
                if g:
                    kandidaten.append(_kandidaat(bron, [(g, "bijzin")], [VW], [Evidence(
                        detector=self.naam, code="CONDITIONAL_CLAUSE", regel="jas.voorwaarde.als_bijzin",
                        relatie=t.deprel, detail=als.tekst.lower())]))
            # 'een partner die geen verzekerde is': de bijzin stelt een eis aan de referent.
            if _nominaal(a, t) and any(a.tokens[k].deprel == "acl:relcl" for k in kinderen):
                geheel = set(a.subboom(t.i)) - {i for k in kinderen if a.tokens[k].deprel in {"conj", "parataxis"}
                                                for i in a.subboom(k)}
                g = _bereik(a, _zonder_randfunctie(a, geheel, t.i))
                if g:
                    persoonloos = referent(a, t, uitgesloten) in {ZAAK, HANDELING}
                    bijzinnen = [(b, "bijzin") for k in kinderen if a.tokens[k].deprel == "acl:relcl"
                                 if (b := _bereik(a, a.subboom(k)))]
                    kandidaten.append(_kandidaat(bron, [(g, "np_met_bijzin"), *bijzinnen],
                                                 [VW, OBJ] if persoonloos else [VW, SUBJ, OBJ], [Evidence(
                        detector=self.naam, code="RESTRICTIVE_RELATIVE",
                        regel="jas.voorwaarde.beperkende_bijzin_bij_zaak" if persoonloos
                        else "jas.voorwaarde.beperkende_bijzin", relatie="acl:relcl", detail=t.tekst)]))
        return resultaat(self, bron, kandidaten)


# --- Rechtsfeit: nominalisatie ('het indienen van …', 'de dagtekening van …') -------------------

_BEPALING = {"van", "door"}


def _vaste_uitdrukkingen(tekst: str) -> list[tuple[int, int]]:
    """Vaste voorzetseluitdrukkingen en regelingsvormen: daarin is een -ing-woord geen handeling."""
    return [m.span() for naam in ("VOORZETSELUITDRUKKING", "REGELINGSVORM")
            for m in re.finditer(rf"\b(?:{woordenlijsten()[naam]})\b", tekst, re.IGNORECASE)]


def _heeft_voorwerp(a: LinguisticAnalysis, t: Token) -> bool:
    """Een 'van'-bepaling. Een 'door'-bepaling noemt de handelende partij: daarmee blijft het woord een zaak mogelijk."""
    return any(a.tokens[k].deprel == "nmod" and any(a.tokens[c].deprel == "case" and a.tokens[c].tekst.lower() == "van"
                                                    for c in a.kinderen(k)) for k in a.kinderen(t.i))


def _in_vaste_uitdrukking(t: Token, uitgesloten: list[tuple[int, int]]) -> bool:
    return any(s <= t.start and t.eind <= e for s, e in uitgesloten)


def _nominalisatie(a: LinguisticAnalysis, t: Token, uitgesloten: list[tuple[int, int]]) -> bool:
    """Is `t` de kop van een genominaliseerde handeling ('het indienen van', 'de toepassing van')?

    Gedeeld door de nominalisatiedetector (Rechtsfeit-hypothese) en de typering van de referent van
    een naamwoordgroep (een handeling is geen persoon).
    """
    kinderen = a.kinderen(t.i)

    def bepaling(k: int) -> bool:
        return a.tokens[k].deprel == "nmod" and any(
            a.tokens[c].deprel == "case" and a.tokens[c].tekst.lower() in _BEPALING for c in a.kinderen(k))

    infinitief = t.upos == "VERB" and t.feat("VerbForm") == "Inf" and any(
        a.tokens[k].deprel == "det" and a.tokens[k].tekst.lower() == "het" for k in kinderen)
    handeling = (t.upos == "NOUN" and t.tekst.lower().endswith("ing") and not _is_zaak(t)
                 and any(bepaling(k) for k in (
                     *kinderen, *(j for c in kinderen if a.tokens[c].deprel == "conj"
                                  and a.tokens[c].tekst.lower().endswith("ing") for j in a.kinderen(c))))
                 and not _in_vaste_uitdrukking(t, uitgesloten))
    return infinitief or handeling


class NominalisatieDetector:
    """Handeling of gebeurtenis als naamwoord: 'het indienen van …', 'de dagtekening van …' (H2:55).

    Een -ing-woord telt alleen met een 'van'- of 'door'-bepaling, niet in een vaste
    voorzetseluitdrukking ('in afwijking van') of regelingsvorm ('regeling van Onze Minister'):
    daar noemt het een verhouding of een regeling, geen handeling (audit D04). Een nevengeschikte
    tak met eigen predicaat, eigen onderwerp of distributieve kwantor is een eigen functie en
    valt buiten de span.

    Welke klassen mogelijk zijn hangt af van de plek in de zin (`_context`). Een nominalisatie is
    alleen géén eigen Voorwaarde waar de zin haar al een andere rol geeft:

    - **referentiemoment** – achter een tijdvoorzetsel ('één maand na de dagtekening van …'): het
      moment waarvan een termijn loopt; de tijdsaanduiding eromheen draagt de functie. Het tijdstip van zo'n
      rechtsfeit is wel een gegeven waarmee gerekend wordt, dus ook een Variabele (H2:80);
    - **in een voorwaarde** – onderwerp of lijdend voorwerp van het gezegde van een voorwaardelijke
      bijzin ('Indien de toepassing van … niet leidt tot …'): de bijzin is de voorwaarde, niet het
      naamwoord erin.

    Elders blijft Voorwaarde een hypothese ('gericht op het voorkomen van herhaling').

    Met een 'van'-bepaling heeft de handeling haar eigen voorwerp ('het indienen van een bezwaarschrift'): dat
    bezwaarschrift is het Rechtsobject, de nominalisatie zelf niet (H2:35, H2:55). Of er een rechtsgevolg aan hangt,
    blijft aan het model (H2:53).
    """
    REGELS: tuple[str, ...] = ("jas.feit.nominalisatie_van", "jas.feit.nominalisatie_met_voorwerp",
                               "jas.feit.nominalisatie_referentiemoment", "jas.feit.nominalisatie_in_voorwaarde")
    naam = "nominalisatie"
    # 5: de context bepaalt of Voorwaarde een hypothese is (art. 9 lid 5 IW 1990)
    # 6: een zaak op -ing is geen handeling
    # 7: met een eigen voorwerp geen Rechtsobject; de grens begint na een vaste uitdrukking
    # 8: het tijdstip van een referentiemoment is ook een Variabele ('na de dagtekening van …')
    versie = f"8+verwijzing.{VERWIJZING_VERSIE}"
    _AAN_DE_RAND = {"case", "cc", "advmod", "mark", "punct"}

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        uitgesloten = _vaste_uitdrukkingen(bron.tekst)
        kandidaten = []
        for t in a.tokens:
            kinderen = a.kinderen(t.i)
            if not _nominalisatie(a, t, uitgesloten):
                continue
            weg = {i for k in kinderen if a.tokens[k].deprel in {"parataxis", *_BIJZIN} for i in a.subboom(k)}
            for i in a.subboom(t.i):
                n = a.tokens[i]
                if n.deprel == "conj" and (
                    n.feat("VerbForm") == "Fin"
                    or any(a.tokens[j].deprel in _ONDERWERP for j in a.kinderen(i))
                    or _lijst("DISTRIBUTIEF").match(n.tekst)
                    or any(a.tokens[j].deprel == "det" and _lijst("DISTRIBUTIEF").match(a.tokens[j].tekst)
                           for j in a.kinderen(i))
                ):
                    weg.update(a.subboom(i))
            tokens = sorted(set(a.subboom(t.i)) - weg)
            while tokens and tokens[0] != t.i and (a.tokens[tokens[0]].deprel in self._AAN_DE_RAND
                                                   or _in_vaste_uitdrukking(a.tokens[tokens[0]], uitgesloten)):
                tokens.pop(0)
            g = _bereik(a, tokens)
            if not g or _in_verwijzing(bron, *g):
                continue
            regel, klassen = self._context(a, t)
            kandidaten.append(_kandidaat(bron, [(g, "np")], klassen, [Evidence(
                detector=self.naam, code="NOMINALIZED_ACTION", regel=regel, relatie=t.deprel, detail=t.tekst)]))
        return resultaat(self, bron, kandidaten)

    @staticmethod
    def _context(a: LinguisticAnalysis, t: Token) -> tuple[str, list[str]]:
        from .functies import VOORWAARDE_VOEGWOORDEN
        if any(a.tokens[k].deprel == "case" and _lijst("TIJDVOORZETSEL").match(a.tokens[k].tekst)
               for k in a.kinderen(t.i)):
            return "jas.feit.nominalisatie_referentiemoment", [FEIT, VAR]
        gezegde = a.tokens[t.head] if t.head >= 0 else None
        if (t.deprel in {"nsubj", "nsubj:pass", "obj"} and gezegde is not None and gezegde.deprel == "advcl"
                and any(a.tokens[m].deprel == "mark" and (a.tokens[m].lemma or a.tokens[m].tekst).lower()
                        in VOORWAARDE_VOEGWOORDEN for m in a.kinderen(gezegde.i))):
            return "jas.feit.nominalisatie_in_voorwaarde", [FEIT, OBJ]
        if _heeft_voorwerp(a, t):
            return "jas.feit.nominalisatie_met_voorwerp", [FEIT, VW]
        return "jas.feit.nominalisatie_van", [FEIT, VW, OBJ]


# --- Rechtsbetrekking: een rechtsgevolg als eigen hoofdzin ------------------------------------

def _in_hoofdzin(a: LinguisticAnalysis, i: int) -> bool:
    """Staat predicaat `i` in de hoofdzin: de root, of nevengeschakeld aan de root – niet in een bijzin."""
    gezien = set()
    while a.tokens[i].deprel in {"conj", "parataxis"} and i not in gezien:
        gezien.add(i)
        i = a.tokens[i].head
    return a.tokens[i].deprel == "root"


def _norm_in_tegenwoordige_tijd(a: LinguisticAnalysis, i: int, tekst: str, segmenten) -> bool:
    """'De ontvanger betaalt …', 'vindt … plaats', 'wordt melding gemaakt': de wet gebiedt meestal zonder modaal
    werkwoord. Een eindig werkwoord als gezegde, in een segment zonder ander normsignaal of delegatieformule."""
    t = a.tokens[i]
    if t.upos != "VERB" or any(a.tokens[k].deprel == "mark" for k in a.kinderen(i)) or not (
            t.feat("VerbForm") == "Fin" or any(a.tokens[k].deprel == "aux:pass"
                                               and a.tokens[k].feat("VerbForm") == "Fin" for k in a.kinderen(i))):
        return False
    g = next((g for g in segmenten if g.start <= t.start < g.eind), None)
    seg = tekst[g.start:g.eind] if g else ""
    return (not (g and any(_normsignaal(tekst, g.start, g.eind, a)))
            and not re.search(r"\bregels\b.*\bgesteld\b", seg, re.IGNORECASE))


def _predicaatvorm(a: LinguisticAnalysis, i: int) -> str:
    """Het lemma met een scheidbaar partikel ervoor ('gaat … over' → 'overgaan') en 'in werking treden'."""
    lemma = (a.tokens[i].lemma or a.tokens[i].tekst).lower()
    prt = [a.tokens[k].tekst.lower() for k in a.kinderen(i) if a.tokens[k].deprel == "compound:prt"]
    if lemma == "treden" and any((a.tokens[k].lemma or "").lower() == "werking" and any(
            a.tokens[c].tekst.lower() == "in" for c in a.kinderen(k)) for k in a.kinderen(i)):
        return "in werking treden"
    return "".join(prt) + lemma


class GevolgDetector:
    """Een rechtsgevolg dat de bepaling zelf uitspreekt, als hoofdzin (H2:46, H2:53).

    'De eerste termijn vervalt één maand na …' en '… vindt het eerste lid toepassing' zijn geen
    modale normen, maar wel de uitspraak waar de bepaling om draait. De NormDetector ziet ze niet
    (hij zoekt een modaal of normatief gezegde) en een lexicale treffer op 'vervalt' zou het hele
    segment pakken, ook als het werkwoord in een bijzin staat. Hier dus op de parse:

    - het predicaat staat in de hoofdzin (`_in_hoofdzin`), nooit in een voorwaarde of bijzin;
    - de span is de eigen clause; het segment en het predicaat zelf zijn opties;
    - de toepassingskeuze wordt herkend met dezelfde helper als in de functiedetector.

    Zonder parse slaat hij zich zichtbaar over.
    """
    REGELS: tuple[str, ...] = ("jas.betrekking.rechtsgevolg_hoofdzin", "jas.betrekking.toepassingsgevolg",
                               "jas.afleiding.datumtoewijzing")
    CODES = ("LEGAL_EFFECT_CLAUSE", "APPLICABILITY_CONSEQUENCE", "DATE_ASSIGNMENT")
    naam = "gevolg"
    # 2: een rechtsgevolg dat een moment vastlegt is ook een afleiding (H2:71), met het ALS→DAN-segment als
    #    eigen kandidaat
    versie = "2"

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        from .functies import toepassingskeuze
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        segmenten = analyseer_grenzen(bron.tekst).segmenten(bron.tekst)
        momenten = _momenten(bron)
        kandidaten, gezien = [], set()
        for p in predicaten(a):
            if not _in_hoofdzin(a, p.kop):
                continue
            vorm = _predicaatvorm(a, p.kop)
            keuze = toepassingskeuze(a, p.kop)
            if keuze and not (keuze["ontkend"] or keuze["overeenkomstig"]):
                code, regel, klassen = self.CODES[1], self.REGELS[1], [BETR]
            elif _lijst("GEVOLGPREDICAAT").match(vorm):
                code, regel, klassen = self.CODES[0], self.REGELS[0], [BETR, FEIT]
            else:
                continue
            t = a.tokens[p.kop]
            seg = next(((g.start, g.eind) for g in segmenten if g.start <= t.start < g.eind), None)
            clause = clausebereik(a, p.kop)
            span = clause or (seg and _trim(bron.tekst, *seg))
            if not span or span[0] >= span[1] or _in_verwijzing(bron, *span) or span in gezien:
                continue
            gezien.add(span)
            grenzen = [(span, "clause" if clause else "segment")]
            if seg:
                grenzen.append((_trim(bron.tekst, *seg), "segment"))
            if a.aaneengesloten(p.tokens):
                grenzen.append(((p.start, p.eind), "predicaat"))
            detail = {"predicaat": vorm, **({} if clause else {"clause_onderbroken": True})}
            bewijs = [Evidence(detector=self.naam, code=code, regel=regel, relatie=t.deprel,
                               detail=json.dumps(detail, ensure_ascii=False, sort_keys=True))]
            # Een rechtsgevolg dat een moment vastlegt ('vervalt één maand na de dagtekening', 'vervalt op 15 april')
            # leidt een datum af uit bestaande gegevens (H2:71): Afleidingsregel als hypothese, het model kiest.
            moment = code == self.CODES[0] and next(
                ((ms, me) for ms, me in momenten if span[0] <= ms < span[1]), None)
            if moment:
                klassen = [*klassen, AR]
                bewijs.append(Evidence(detector=self.naam, code=self.CODES[2], regel=self.REGELS[2], relatie=t.deprel,
                                       detail=bron.tekst[moment[0]:moment[1]]))
            kandidaten.append(_kandidaat(bron, grenzen, klassen, bewijs))
            # Staat er een voorwaarde vóór het gevolg in hetzelfde segment ('Indien …, vervalt …', 'Is …, dan vervalt
            # …'), dan is de hele ALS→DAN-zin de regel: een eigen kandidaat op het segment, de clause als optie.
            segspan = _trim(bron.tekst, *seg) if seg else None
            if moment and segspan and span[0] > segspan[0] and _voorwaarde_voor(a, p.kop, segspan):
                if segspan not in gezien:
                    gezien.add(segspan)
                    kandidaten.append(_kandidaat(bron, [(segspan, "segment"), (span, "clause")], [AR, BETR], [Evidence(
                        detector=self.naam, code=self.CODES[2], regel=self.REGELS[2], relatie=t.deprel,
                        detail=json.dumps({"predicaat": vorm, "voorwaarde": True}, ensure_ascii=False,
                                          sort_keys=True))]))
        return resultaat(self, bron, kandidaten)


# Tijdtreffers die een moment aanwijzen, niet alleen een tijdsduur: een datum, een maand, een tijdstip, een
# herhaling ('telkens een maand later'), of een duur met een startmoment ('één maand na de dagtekening').
# 'na vijf jaar' alleen is een tijdsverloop, geen toegekend moment.
_MOMENTCODES = frozenset({"TEMPORAL_DATE", "TEMPORAL_MONTH", "TEMPORAL_MOMENT", "TEMPORAL_RECURRENCE"})


def _momenten(bron: BronTekst) -> list[tuple[int, int]]:
    """De bereiken van de tijdregels (regels/tijd.yaml) die een moment aanwijzen; buiten een verwijzing."""
    from .regels import alle_regels
    weg = maskers(bron.tekst).get("verwijzing", [])
    uit = []
    for r in alle_regels():
        if r.detector != "tijd" or r.code not in _MOMENTCODES | {"TEMPORAL_DURATION"}:
            continue
        for grenzen in r.vind(bron.tekst, bron.analyse):
            kern = grenzen[0]
            if any(ms <= kern[0] and kern[1] <= me for ms, me in weg):
                continue
            if r.code == "TEMPORAL_DURATION":
                met_start = [g for g in grenzen if g[1] > kern[1]]
                if met_start:
                    uit.append(max(met_start, key=lambda g: g[1] - g[0]))
            else:
                uit.append(grenzen[-1])
    return sorted(uit)


def _voorwaarde_voor(a: LinguisticAnalysis, kop: int, seg: tuple[int, int]) -> bool:
    """Hangt er een voorwaarde vóór predicaat `kop` in segment `seg`: een voorwaardelijke bijzin (`advcl` met een
    voorwaardelijk voegwoord), of een inversie ('Is de termijn zes weken, (dan) vervalt …': het segment begint met
    een persoonsvorm vóór het predicaat)."""
    t = a.tokens[kop]
    for k in a.kinderen(kop):
        if a.tokens[k].deprel == "advcl" and a.tokens[k].start < t.start and any(
                a.tokens[m].deprel == "mark" and a.tokens[m].tekst.lower() in _VOORWAARDELIJK for m in a.subboom(k)):
            return True
    eerste = next((x for x in a.tokens if x.start >= seg[0] and x.upos != "PUNCT"), None)
    return (eerste is not None and eerste.i != kop and eerste.start < t.start
            and eerste.upos in {"AUX", "VERB"} and eerste.feat("VerbForm") == "Fin")


class TegenwoordigeTijdDetector:
    """De wet gebiedt meestal zonder modaal werkwoord: 'De ontvanger betaalt …', '… vindt … plaats' (H2:46, H2:55).

    Dat kan een plicht zijn of een gebeurtenis, en dat bepaalt de tekst niet: dus Rechtsbetrekking of Rechtsfeit als
    hypothese, het model kiest. Alleen in de hoofdzin, en niet naast een ander normsignaal. Zonder parse slaat hij
    zich zichtbaar over.
    """
    REGELS: tuple[str, ...] = ("jas.betrekking.tegenwoordige_tijd",)
    naam = "tegenwoordige_tijd"
    versie = "2"                         # 2: een modaal werkwoord in een bijzin is geen ander normsignaal

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        segmenten = analyseer_grenzen(bron.tekst).segmenten(bron.tekst)
        kandidaten, gezien = [], set()
        for p in predicaten(a):
            if not _in_hoofdzin(a, p.kop) or not _norm_in_tegenwoordige_tijd(a, p.kop, bron.tekst, segmenten):
                continue
            t = a.tokens[p.kop]
            seg = next(((g.start, g.eind) for g in segmenten if g.start <= t.start < g.eind), None)
            span = clausebereik(a, p.kop) or (seg and _trim(bron.tekst, *seg))
            if not span or span[0] >= span[1] or _in_verwijzing(bron, *span) or span in gezien:
                continue
            gezien.add(span)
            grenzen = [(span, "clause")]
            if seg:
                grenzen.append((_trim(bron.tekst, *seg), "segment"))
            if span[0] < t.start < span[1]:
                grenzen.append(((t.start, span[1]), "vanaf_gezegde"))
            kandidaten.append(_kandidaat(bron, grenzen, [BETR, FEIT], [Evidence(
                detector=self.naam, code="NORM_IN_PRESENT_TENSE", regel=self.REGELS[0], relatie=t.deprel,
                detail=t.tekst)]))
        return resultaat(self, bron, kandidaten)


# --- Operator: nevenschikking tussen clauses en negatie ----------------------------------------

_NAAMWOORD = {"NOUN", "PROPN"}
# Een nevenschikking van structuurnummers is een verwijzing ('artikel 3 en artikel 4'), geen operator.
_STRUCTUURWOORD = {"artikel", "lid", "onderdeel", "hoofdstuk", "afdeling", "paragraaf", "titel", "bijlage",
                   "volzin"}


class LogischeOperatorDetector:
    REGELS: tuple[str, ...] = ("jas.operator.nevenschikking", "jas.operator.negatie", "jas.operator.woordgroep")
    CODES = ("CLAUSE_COORDINATION", "NEGATION_IN_CONDITION", "PHRASE_COORDINATION")
    naam = "logisch"
    # 2: geen nevenschikking binnen een naamwoordgroep
    # 3: een persoonsvorm als hulp- of koppelwerkwoord maakt het conjunct een eigen zin ('of is gesteld op')
    # 4: 'en'/'of' tussen naamwoordgroepen is een eigen, zwakkere regel (H2:98: EN/OF tussen operanden)
    versie = "4"

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        kandidaten = []
        for t in a.tokens:
            laag = t.tekst.lower()
            kop = a.tokens[t.head] if t.head >= 0 else None
            # 'en'/'of' tussen (bij)zinnen of predicaten – niet tussen woorden in één naamwoordgroep.
            # Een logische operator verbindt zinsdelen (voorwaarden, normen), geen woorden binnen één
            # naamwoordgroep ("een verplichting of onthouden aanspraak"; profiel Operator,
            # negative_patterns). Het tweede conjunct moet dus een eigen zin zijn – met een eigen
            # onderwerp of een persoonsvorm, ook als die persoonsvorm een hulp- of koppelwerkwoord is
            # ('… of is gesteld op …': de kop is dan een deelwoord) – én het eerste conjunct moet zelf
            # werkwoordelijk zijn.
            clause = False
            if kop is not None and kop.head >= 0:
                eerste = a.tokens[kop.head]
                eigen_zin = (any(a.tokens[k].deprel in _ONDERWERP for k in a.kinderen(kop.i))
                             or kop.feat("VerbForm") == "Fin"
                             or any(a.tokens[k].deprel in {"aux", "aux:pass", "cop"}
                                    and a.tokens[k].feat("VerbForm") == "Fin" for k in a.kinderen(kop.i)))
                clause = kop.deprel == "conj" and eerste.upos in {"VERB", "AUX", "ADJ"} and eigen_zin
            # 'en'/'of' tussen twee naamwoordgroepen ('de aanslag of de beschikking'): een operator
            # binnen een voorwaarde, berekening of opsomming (H2:98: EN/OF verbindt operanden). Zwakker
            # dan tussen zinnen, want het kan ook een gewone opsomming van objecten zijn; dat oordeel
            # is aan de classifier. Niet tussen een naamwoord en een bijvoeglijk of werkwoordelijk
            # conjunct ('in november of eerder' heeft een eigen regel, 'verplichting of onthouden
            # aanspraak' verbindt woorden), niet tussen structuurnummers en niet in een verwijzing. Ook
            # niet in 'tussen X en Y': dat noemt de twee kanten van een relatie, geen EN. Het voorzetsel
            # hangt aan het eerste conjunct of staat tussen dat conjunct en het voegwoord (de parse hangt
            # 'tussen de Dienst en die houder' soms aan het woord ervoor).
            woordgroep = (kop is not None and kop.deprel == "conj" and kop.head >= 0
                          and kop.upos in _NAAMWOORD and a.tokens[kop.head].upos in _NAAMWOORD
                          and not {kop.lemma.lower(), a.tokens[kop.head].lemma.lower()} & _STRUCTUURWOORD
                          and not any(a.tokens[k].deprel == "case" and a.tokens[k].tekst.lower() == "tussen"
                                      for k in (*a.kinderen(kop.head), *range(kop.head + 1, t.i))))
            if t.deprel == "cc" and laag in {"en", "of"} and clause:
                regel, code = self.REGELS[0], self.CODES[0]
            elif laag in {"niet", "geen"} and t.deprel in {"advmod", "det"} and kop is not None \
                    and any(a.tokens[k].deprel == "mark" for k in a.kinderen(kop.i)):
                regel, code = self.REGELS[1], self.CODES[1]
            elif t.deprel == "cc" and laag in {"en", "of"} and woordgroep \
                    and not _in_verwijzing(bron, a.tokens[kop.head].start, kop.eind):
                regel, code = self.REGELS[2], self.CODES[2]
            else:
                continue
            kandidaten.append(_kandidaat(bron, [((t.start, t.eind), "kern")], [OP], [Evidence(
                detector=self.naam, code=code, regel=regel, relatie=t.deprel, detail=t.tekst)]))
        return resultaat(self, bron, kandidaten)


def syntactische_detectoren() -> list:
    return [NormDetector(), GevolgDetector(), TegenwoordigeTijdDetector(), NaamwoordgroepDetector(), BijzinDetector(), NominalisatieDetector(),
            LogischeOperatorDetector()]
