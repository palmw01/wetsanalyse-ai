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

SUBJ, OBJ, BETR, FEIT, VW, VAR, PAR, OP = (
    "Rechtssubject", "Rechtsobject", "Rechtsbetrekking", "Rechtsfeit", "Voorwaarde",
    "Variabele en variabelewaarde", "Parameter en parameterwaarde", "Operator")

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


class NormDetector:
    REGELS: tuple[str, ...] = ("jas.betrekking.modaal_predicaat", "jas.betrekking.vaste_uitdrukking",
                               "jas.betrekking.normatief_adjectief", "jas.feit.rechtsgevolg_in_norm")
    naam = "norm"
    versie = "3"  # D03: Rechtsfeit alleen met een rechtsgevolg in het segment

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        tekst = bron.tekst
        structuur = analyseer_grenzen(tekst)
        zinnen = structuur.zinnen(tekst)
        kandidaten = []
        for segment in structuur.segmenten(tekst):
            s, e = segment.start, segment.eind
            stuk = tekst[s:e]
            modaal = re.search(rf"\b(?:{woordenlijsten()['MODAAL']})\b", stuk, re.IGNORECASE)
            normatief = None if modaal else _norm_in(stuk)
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


class NaamwoordgroepDetector:
    REGELS: tuple[str, ...] = (
        "jas.parameter.beschrijving", "jas.variabele.uitvoer_van_afleiding", "jas.variabele.eigenschap_np",
        "jas.subject.voornaamwoord", "jas.subject.rollexicon", "jas.subject.np_bij_normatief_predicaat",
        "jas.subject.np", "jas.object.opsommingsonderdeel", "jas.object.np_bij_normatief_predicaat", "jas.object.np")
    naam = "naamwoordgroep"
    # Grammaticale rol zonder juridische functie: blokkeert sterk patroonbewijs niet (audit D05).
    BEWIJS = {"SUBJECT_NP": ("generiek", ""), "OBJECT_NP": ("generiek", ""), "ENUMERATED_NP": ("generiek", "")}
    versie = f"2+verwijzing.{VERWIJZING_VERSIE}"  # D01: normcontext getoetst, niet verondersteld

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        kandidaten = []
        normen = _normsegmenten(bron.tekst)
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
            norm = any(s <= t.start < e for s, e in normen)
            bewijs, klassen = self._classificeer_signaal(a, t, lemma, norm)
            kandidaten.append(_kandidaat(bron, grenzen, klassen, bewijs))
        return resultaat(self, bron, kandidaten)

    def _classificeer_signaal(self, a: LinguisticAnalysis, t: Token, lemma: str, norm: bool = True):
        """Welke klassen mogelijk zijn en waarom – signalen uit het profiel, geen besluit.

        Generieke onderwerp- en objectsignalen heten alleen 'bij normatief predicaat' als dat predicaat
        in hetzelfde beschermde segment staat (audit D01). Zonder normcontext is een lijdend onderwerp
        of een object geen dragende partij: Rechtssubject vervalt daar als hypothese.
        """
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

class BijzinDetector:
    REGELS: tuple[str, ...] = ("jas.voorwaarde.als_bijzin", "jas.voorwaarde.beperkende_bijzin")
    naam = "bijzin"
    versie = f"2+verwijzing.{VERWIJZING_VERSIE}"  # als-clause met eigen predicatie; T4 C037

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        kandidaten = []
        for t in a.tokens:
            kinderen = a.kinderen(t.i)
            # Ook vergelijkend 'als dat van …' en 'als bestuurder' kunnen mark + advcl krijgen.
            # Een nominale groep zonder werkwoordelijke predicatie is nog geen conditionele bijzin.
            als = next((a.tokens[k] for k in kinderen if a.tokens[k].deprel == "mark"
                        and a.tokens[k].tekst.lower() == "als"), None)
            eigen_predicaat = any(a.tokens[i].upos in {"VERB", "AUX"} for i in a.subboom(t.i)) if als else False
            if t.deprel in _BIJZIN and als is not None and eigen_predicaat \
                    and not _in_verwijzing(bron, als.start, als.eind):
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
        return resultaat(self, bron, kandidaten)


# --- Rechtsfeit: nominalisatie ('het indienen van …', 'de dagtekening van …') -------------------

class NominalisatieDetector:
    """Handeling of gebeurtenis als naamwoord: 'het indienen van …', 'de dagtekening van …' (H2:55).

    Een -ing-woord telt alleen met een 'van'- of 'door'-bepaling, niet in een vaste
    voorzetseluitdrukking ('in afwijking van') of regelingsvorm ('regeling van Onze Minister'):
    daar noemt het een verhouding of een regeling, geen handeling (audit D04). Een nevengeschikte
    tak met eigen predicaat, eigen onderwerp of distributieve kwantor is een eigen functie en
    valt buiten de span.
    """
    REGELS: tuple[str, ...] = ("jas.feit.nominalisatie_van",)
    naam = "nominalisatie"
    versie = f"4+verwijzing.{VERWIJZING_VERSIE}"  # D04: van/door-bepaling, vaste uitdrukkingen, distributief
    _AAN_DE_RAND = {"case", "cc", "advmod", "mark", "punct"}
    _BEPALING = {"van", "door"}

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        uitgesloten = [m.span() for naam in ("VOORZETSELUITDRUKKING", "REGELINGSVORM")
                       for m in re.finditer(rf"\b(?:{woordenlijsten()[naam]})\b", bron.tekst, re.IGNORECASE)]

        def bepaling(k: int) -> bool:
            return a.tokens[k].deprel == "nmod" and any(
                a.tokens[c].deprel == "case" and a.tokens[c].tekst.lower() in self._BEPALING for c in a.kinderen(k))

        kandidaten = []
        for t in a.tokens:
            kinderen = a.kinderen(t.i)
            infinitief = t.upos == "VERB" and t.feat("VerbForm") == "Inf" and any(a.tokens[k].deprel == "det" and a.tokens[k].tekst.lower() == "het"
                                                  for k in kinderen)
            handeling = (t.upos == "NOUN" and t.tekst.lower().endswith("ing")
                         and any(bepaling(k) for k in (
                             *kinderen, *(j for c in kinderen if a.tokens[c].deprel == "conj"
                                          and a.tokens[c].tekst.lower().endswith("ing") for j in a.kinderen(c))))
                         and not any(s <= t.start and t.eind <= e for s, e in uitgesloten))
            if not (infinitief or handeling):
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
            while tokens and a.tokens[tokens[0]].deprel in self._AAN_DE_RAND and tokens[0] != t.i:
                tokens.pop(0)
            g = _bereik(a, tokens)
            if not g or _in_verwijzing(bron, *g):
                continue
            kandidaten.append(_kandidaat(bron, [(g, "np")], [FEIT, VW, OBJ], [Evidence(
                detector=self.naam, code="NOMINALIZED_ACTION", regel="jas.feit.nominalisatie_van",
                relatie=t.deprel, detail=t.tekst)]))
        return resultaat(self, bron, kandidaten)


# --- Rechtsbetrekking: een rechtsgevolg als eigen hoofdzin ------------------------------------

def _in_hoofdzin(a: LinguisticAnalysis, i: int) -> bool:
    """Staat predicaat `i` in de hoofdzin: de root, of nevengeschakeld aan de root – niet in een bijzin."""
    gezien = set()
    while a.tokens[i].deprel in {"conj", "parataxis"} and i not in gezien:
        gezien.add(i)
        i = a.tokens[i].head
    return a.tokens[i].deprel == "root"


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
    REGELS: tuple[str, ...] = ("jas.betrekking.rechtsgevolg_hoofdzin", "jas.betrekking.toepassingsgevolg")
    CODES = ("LEGAL_EFFECT_CLAUSE", "APPLICABILITY_CONSEQUENCE")
    naam = "gevolg"
    versie = "1"

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        from .functies import toepassingskeuze
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        segmenten = analyseer_grenzen(bron.tekst).segmenten(bron.tekst)
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
            kandidaten.append(_kandidaat(bron, grenzen, klassen, [Evidence(
                detector=self.naam, code=code, regel=regel, relatie=t.deprel,
                detail=json.dumps(detail, ensure_ascii=False, sort_keys=True))]))
        return resultaat(self, bron, kandidaten)


# --- Operator: nevenschikking tussen clauses en negatie ----------------------------------------

class LogischeOperatorDetector:
    REGELS: tuple[str, ...] = ("jas.operator.nevenschikking", "jas.operator.negatie")
    naam = "logisch"
    versie = "2"                         # 2: geen nevenschikking binnen een naamwoordgroep

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
        return resultaat(self, bron, kandidaten)


def syntactische_detectoren() -> list:
    return [NormDetector(), GevolgDetector(), NaamwoordgroepDetector(), BijzinDetector(), NominalisatieDetector(),
            LogischeOperatorDetector()]
