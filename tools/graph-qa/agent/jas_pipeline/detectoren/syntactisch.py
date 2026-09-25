"""Syntactische detectoren (ADR-001 PR 7): kandidaten uit de taalanalyse.

Een parse van wetstekst is minder betrouwbaar dan van krantentekst (lange zinnen, opsommingen,
labels als "c." die als onderwerp worden gelezen). Daarom:

- **Rechtsbetrekking** herkent de uitdrukkingswijze (H2:46) lexicaal op tokens – een modaal
  hulpwerkwoord of een normatief predicaat – en werkt dus óók op een gedegradeerde analyse. De span
  is het normsegment tussen de leestekens (. ; :); de hele zin is een optie.
- De overige detectoren hebben dependencies nodig. Zonder parse slaan ze zich **zichtbaar** over
  (`DetectorResult.overgeslagen` + reden), ze vallen niet stil terug.

Grammatica levert hier kandidaten, geen klassen: een onderwerp is geen rechtssubject omdat het een
onderwerp is (profiel Rechtssubject, negative_patterns). `possible_classes` zegt wat mogelijk is;
de volgorde is voorkeur, geen besluit.
"""
from __future__ import annotations

import re
from functools import cache

from ..kandidaten import BronSpan, Candidate, DetectorResult, Evidence, SpanOption
from ..taal import LinguisticAnalysis, Token
from ..taal.afgeleid import _BIJZIN, _KERN
from . import BronTekst
from .regels import maskers, woordenlijsten

SUBJ, OBJ, BETR, FEIT, VW, VAR, PAR, OP = (
    "Rechtssubject", "Rechtsobject", "Rechtsbetrekking", "Rechtsfeit", "Voorwaarde",
    "Variabele en variabelewaarde", "Parameter en parameterwaarde", "Operator")

_SEGMENTGRENS = re.compile(r"[.;:]")
_ONDERWERP = {"nsubj", "nsubj:pass", "obl:agent", "csubj"}


@cache
def _lijst(naam: str) -> re.Pattern:
    return re.compile(rf"^(?:{woordenlijsten()[naam]})$", re.IGNORECASE)


def _overgeslagen(naam: str, bron: BronTekst, reden: str) -> DetectorResult:
    return DetectorResult(detector=naam, versie="1", bron_iri=bron.bron_iri, overgeslagen=True, reden=reden)


def _parse_of_reden(bron: BronTekst) -> tuple[LinguisticAnalysis | None, str]:
    if bron.analyse is None:
        return None, "geen taalanalyse aangeleverd"
    if bron.analyse.gedegradeerd:
        return None, f"geen parse: {bron.analyse.fout}"
    return bron.analyse, ""


def _in_verwijzing(bron: BronTekst, s: int, e: int) -> bool:
    return any(ms <= s and e <= me for ms, me in maskers(bron.tekst).get("verwijzing", []))


def _bereik(a: LinguisticAnalysis, tokens) -> tuple[int, int] | None:
    tokens = [i for i in tokens if a.tokens[i].upos != "PUNCT"]
    if not tokens or not a.aaneengesloten(tuple(tokens)):
        return None
    return a.bereik(tokens)


_RANDFUNCTIE = {"case", "cc", "mark", "punct"}


def _zonder_randfunctie(a: LinguisticAnalysis, tokens, kop: int) -> list[int]:
    """Een voorzetsel, voegwoord of leesteken vóór de groep hoort er niet bij ('Voor een partner')."""
    tokens = sorted(tokens)
    while tokens and tokens[0] != kop and a.tokens[tokens[0]].deprel in _RANDFUNCTIE:
        tokens.pop(0)
    return tokens


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

class NormDetector:
    REGELS: tuple[str, ...] = ("jas.betrekking.modaal_predicaat", "jas.betrekking.vaste_uitdrukking",
                               "jas.betrekking.normatief_adjectief")
    naam = "norm"
    versie = "1"

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        tekst = bron.tekst
        segmenten = []
        begin = 0
        for m in [*_SEGMENTGRENS.finditer(tekst), None]:
            eind = m.end() if m else len(tekst)
            segmenten.append((begin, eind))
            begin = eind
        zinnen = _zinnen(tekst)
        kandidaten = []
        for s, e in segmenten:
            stuk = tekst[s:e]
            modaal = re.search(rf"\b(?:{woordenlijsten()['MODAAL']})\b", stuk, re.IGNORECASE)
            normatief = re.search(rf"\b(?:{woordenlijsten()['NORMATIEF']})\b", stuk, re.IGNORECASE)
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
            zin = next(((zs, ze) for zs, ze in zinnen if zs <= s2 and e2 <= ze), (s2, e2))
            grenzen = [((s2, e2), "segment"), (_trim(tekst, *zin), "zin")]
            bewijs = [Evidence(detector=self.naam, code="NORMATIVE_PREDICATE", regel=regel, detail=treffer.group())]
            kandidaten.append(_kandidaat(bron, grenzen, [BETR, FEIT], bewijs))
        return DetectorResult(detector=self.naam, versie=self.versie, bron_iri=bron.bron_iri,
                              kandidaten=tuple(kandidaten))


def _zinnen(tekst: str) -> list[tuple[int, int]]:
    uit, begin = [], 0
    for m in re.finditer(r"(?<=[.])\s+(?=[A-Z])|\n", tekst):
        uit.append((begin, m.start()))
        begin = m.end()
    uit.append((begin, len(tekst)))
    return uit


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

def _nominaal(a: LinguisticAnalysis, t: Token) -> bool:
    if t.upos in {"NOUN", "PROPN"}:
        return True
    if t.upos == "PRON":
        return bool(_lijst("ROL").match(t.tekst))
    if t.upos in {"VERB", "ADJ"}:        # 'de verzekerde', 'een bestuurder die …': genominaliseerd
        return any(a.tokens[k].deprel == "det" and a.tokens[k].tekst.lower() != "het" for k in a.kinderen(t.i))
    return False


class NaamwoordgroepDetector:
    REGELS: tuple[str, ...] = (
        "jas.parameter.beschrijving", "jas.variabele.uitvoer_van_afleiding", "jas.variabele.eigenschap_np",
        "jas.subject.voornaamwoord", "jas.subject.rollexicon", "jas.subject.np_bij_normatief_predicaat",
        "jas.object.opsommingsonderdeel", "jas.object.np_bij_normatief_predicaat")
    naam = "naamwoordgroep"
    versie = "1"

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return _overgeslagen(self.naam, bron, reden)
        kandidaten = []
        for t in a.tokens:
            if not _nominaal(a, t) or t.deprel in {"fixed", "flat", "flat:name", "compound", "nmod:poss"}:
                continue
            kern = {t.i} | {i for k in a.kinderen(t.i) if a.tokens[k].deprel in _KERN for i in a.subboom(k)}
            zonder_bijzin = set(a.subboom(t.i)) - {i for k in a.kinderen(t.i)
                                                    if a.tokens[k].deprel in {*_BIJZIN, "conj", "parataxis", "punct", "cc"}
                                                    for i in a.subboom(k)}
            geheel = set(a.subboom(t.i)) - {i for k in a.kinderen(t.i)
                                            if a.tokens[k].deprel in {"conj", "parataxis", "cc", "punct"}
                                            for i in a.subboom(k)}
            grenzen = [(g, soort) for g, soort in (
                (_bereik(a, _zonder_randfunctie(a, kern, t.i)), "np_kern"),
                (_bereik(a, _zonder_randfunctie(a, zonder_bijzin, t.i)), "np"),
                (_bereik(a, _zonder_randfunctie(a, geheel, t.i)), "np_met_bijzin")) if g]
            if not grenzen or _in_verwijzing(bron, *grenzen[0][0]):
                continue
            lemma = (t.lemma or t.tekst).lower()
            bewijs, klassen = self._classificeer_signaal(a, t, lemma)
            kandidaten.append(_kandidaat(bron, grenzen, klassen, bewijs))
        return DetectorResult(detector=self.naam, versie=self.versie, bron_iri=bron.bron_iri,
                              kandidaten=tuple(kandidaten))

    def _classificeer_signaal(self, a: LinguisticAnalysis, t: Token, lemma: str):
        """Welke klassen mogelijk zijn en waarom – signalen uit het profiel, geen besluit."""
        rel = t.deprel
        if _lijst("PARAMETERWOORD").match(lemma) or _lijst("PARAMETERWOORD").match(t.tekst):
            return [Evidence(detector=self.naam, code="PARAMETER_NOUN", regel="jas.parameter.beschrijving",
                             relatie=rel, detail=t.tekst)], [PAR, VAR]
        if any(lemma.endswith(w) for w in woordenlijsten()["EIGENSCHAP"].split("|")):
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
        if rel in _ONDERWERP:
            return [Evidence(detector=self.naam, code="SUBJECT_NP", regel="jas.subject.np_bij_normatief_predicaat",
                             relatie=rel, detail=t.tekst)], [SUBJ, OBJ, VAR]
        if rel == "conj":
            return [Evidence(detector=self.naam, code="ENUMERATED_NP", regel="jas.object.opsommingsonderdeel",
                             relatie=rel, detail=t.tekst)], [OBJ, SUBJ, VAR]
        return [Evidence(detector=self.naam, code="OBJECT_NP", regel="jas.object.np_bij_normatief_predicaat",
                         relatie=rel, detail=t.tekst)], [OBJ, VAR, SUBJ]


# --- bijzinnen: 'als'-voorwaarde en beperkende relatieve bijzin --------------------------------

class BijzinDetector:
    REGELS: tuple[str, ...] = ("jas.voorwaarde.als_bijzin", "jas.voorwaarde.beperkende_bijzin")
    naam = "bijzin"
    versie = "1"

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return _overgeslagen(self.naam, bron, reden)
        kandidaten = []
        for t in a.tokens:
            kinderen = a.kinderen(t.i)
            # 'als' als inleider van een bijzin; 'als bedoeld in' en 'als bestuurder' hebben geen mark.
            als = next((a.tokens[k] for k in kinderen if a.tokens[k].deprel == "mark"
                        and a.tokens[k].tekst.lower() == "als"), None)
            if t.deprel in _BIJZIN and als is not None and not _in_verwijzing(bron, als.start, als.eind):
                g = _bereik(a, a.subboom(t.i))
                if g:
                    kandidaten.append(_kandidaat(bron, [(g, "bijzin")], [VW], [Evidence(
                        detector=self.naam, code="CONDITIONAL_CLAUSE", regel="jas.voorwaarde.als_bijzin",
                        relatie=t.deprel, detail="als")]))
            # 'een partner die geen verzekerde is': de bijzin stelt een eis aan de referent.
            if _nominaal(a, t) and any(a.tokens[k].deprel == "acl:relcl" for k in kinderen):
                geheel = set(a.subboom(t.i)) - {i for k in kinderen if a.tokens[k].deprel in {"conj", "parataxis"}
                                                for i in a.subboom(k)}
                g = _bereik(a, _zonder_randfunctie(a, geheel, t.i))
                if g:
                    kandidaten.append(_kandidaat(bron, [(g, "np_met_bijzin")], [VW, SUBJ, OBJ], [Evidence(
                        detector=self.naam, code="RESTRICTIVE_RELATIVE", regel="jas.voorwaarde.beperkende_bijzin",
                        relatie="acl:relcl", detail=t.tekst)]))
        return DetectorResult(detector=self.naam, versie=self.versie, bron_iri=bron.bron_iri,
                              kandidaten=tuple(kandidaten))


# --- Rechtsfeit: nominalisatie ('het indienen van …', 'de dagtekening van …') -------------------

class NominalisatieDetector:
    REGELS: tuple[str, ...] = ("jas.feit.nominalisatie_van",)
    naam = "nominalisatie"
    versie = "1"
    _AAN_DE_RAND = {"case", "cc", "advmod", "mark", "punct"}

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return _overgeslagen(self.naam, bron, reden)
        kandidaten = []
        for t in a.tokens:
            kinderen = a.kinderen(t.i)
            infinitief = t.upos == "VERB" and any(a.tokens[k].deprel == "det" and a.tokens[k].tekst.lower() == "het"
                                                  for k in kinderen)
            handeling = (t.upos == "NOUN" and t.tekst.lower().endswith("ing")
                         and any(a.tokens[k].deprel == "nmod" for k in kinderen))
            if not (infinitief or handeling):
                continue
            weg = {i for k in kinderen if a.tokens[k].deprel in {"parataxis", *_BIJZIN} for i in a.subboom(k)}
            tokens = sorted(set(a.subboom(t.i)) - weg)
            while tokens and a.tokens[tokens[0]].deprel in self._AAN_DE_RAND and tokens[0] != t.i:
                tokens.pop(0)
            g = _bereik(a, tokens)
            if not g or _in_verwijzing(bron, *g):
                continue
            kandidaten.append(_kandidaat(bron, [(g, "np")], [FEIT, VW, OBJ], [Evidence(
                detector=self.naam, code="NOMINALIZED_ACTION", regel="jas.feit.nominalisatie_van",
                relatie=t.deprel, detail=t.tekst)]))
        return DetectorResult(detector=self.naam, versie=self.versie, bron_iri=bron.bron_iri,
                              kandidaten=tuple(kandidaten))


# --- Operator: nevenschikking tussen clauses en negatie ----------------------------------------

class LogischeOperatorDetector:
    REGELS: tuple[str, ...] = ("jas.operator.nevenschikking", "jas.operator.negatie")
    naam = "logisch"
    versie = "2"                         # 2: geen nevenschikking binnen een naamwoordgroep (PR 17)

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return _overgeslagen(self.naam, bron, reden)
        kandidaten = []
        for t in a.tokens:
            laag = t.tekst.lower()
            kop = a.tokens[t.head] if t.head >= 0 else None
            # 'en'/'of' tussen (bij)zinnen of predicaten – niet tussen woorden in één naamwoordgroep.
            # Een logische operator verbindt zinsdelen (voorwaarden, normen), geen woorden binnen één
            # naamwoordgroep ("een verplichting of onthouden aanspraak"; profiel Operator,
            # negative_patterns). Het tweede conjunct moet dus een eigen zin zijn – met een eigen
            # onderwerp of als persoonsvorm – én het eerste conjunct moet zelf werkwoordelijk zijn.
            clause = False
            if kop is not None and kop.head >= 0:
                eerste = a.tokens[kop.head]
                eigen_zin = (any(a.tokens[k].deprel in _ONDERWERP for k in a.kinderen(kop.i))
                             or kop.feat("VerbForm") == "Fin")
                clause = kop.deprel == "conj" and eerste.upos in {"VERB", "AUX", "ADJ"} and eigen_zin
            if t.deprel == "cc" and laag in {"en", "of"} and clause:
                regel, code = "jas.operator.nevenschikking", "CLAUSE_COORDINATION"
            elif laag in {"niet", "geen"} and t.deprel in {"advmod", "det"} and kop is not None \
                    and any(a.tokens[k].deprel == "mark" for k in a.kinderen(kop.i)):
                regel, code = "jas.operator.negatie", "NEGATION_IN_CONDITION"
            else:
                continue
            kandidaten.append(_kandidaat(bron, [((t.start, t.eind), "kern")], [OP], [Evidence(
                detector=self.naam, code=code, regel=regel, relatie=t.deprel, detail=t.tekst)]))
        return DetectorResult(detector=self.naam, versie=self.versie, bron_iri=bron.bron_iri,
                              kandidaten=tuple(kandidaten))


def syntactische_detectoren() -> list:
    return [NormDetector(), NaamwoordgroepDetector(), BijzinDetector(), NominalisatieDetector(),
            LogischeOperatorDetector()]
