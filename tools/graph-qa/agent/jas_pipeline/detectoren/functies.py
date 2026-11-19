"""Functiehypothesen met benoemde uitkomst/invoer; geen berekening of juridische beslissing.

Toewijzing en toepassingskeuze worden op dependencies getoetst, niet op woordvolgorde: een passief
'stellen op' telt alleen met een grootheid als lijdend onderwerp, een toepassingskeuze alleen onder
een voorwaarde en niet ontkend of als schakelbepaling ('overeenkomstige toepassing'). Rekenkundige
constructies gebruiken beschermde segmenten; de parse is vereist en wordt niet aangepast.

De span is de constructie zelf, niet het segment eromheen: een afleiding 'zoveel … als …' loopt
van 'zoveel' tot het einde van de invoer, een toepassingskeuze is de eigen clause van 'vindt'
(`taal.clausebereik`). Het segment blijft beschikbaar als spanoptie `segment`. Anders valt een
functie samen met de norm die hetzelfde segment draagt, en krijgen ze samen één besluit.
"""
import json
import re
from functools import cache

from ..kandidaten import BronSpan, Candidate, Evidence, SpanOption
from ..taal.afgeleid import clausebereik
from ..taal.grenzen import VERSIE as GRENS_VERSIE, analyseer_grenzen
from ..taal.verwijzingen import VERSIE as VERWIJZING_VERSIE
from . import resultaat
from .ontleding import bereik, in_verwijzing, parse_of_reden, zonder_randfunctie
from .regels import woordenlijsten

AR, T, VW, VAR = "Afleidingsregel", "Tijdsaanduiding", "Voorwaarde", "Variabele en variabelewaarde"
# 'zoveel <telbare uitkomst> als (er) <telbare invoer> <werkwoord>': de uitkomst tot 'als'; de invoer is de bijzin die
# 'als' inleidt, tot het eind van zijn werkwoord (de parse beslist, `_aantal`). 'overblijven' of 'resteren' is geen eis:
# 'als er maanden van het jaar zijn' telt net zo goed (art. 9 lid 7 IW, Termijnen 19 nov 2026).
_AANTAL = re.compile(r"\bzoveel\s+(?P<uitkomst>[^.;:]+?)\s+als\s+", re.I)
# Voegwoorden van een voorwaardelijke bijzin; gedeeld met de nominalisatiedetector.
VOORWAARDE_VOEGWOORDEN = frozenset({"indien", "als", "wanneer", "zodra"})
_ONTKENNING = {"geen", "niet"}


@cache
def _lijst(naam: str) -> re.Pattern:
    return re.compile(rf"^(?:{woordenlijsten()[naam]})$", re.IGNORECASE)


@cache
def _elliptisch() -> re.Pattern:
    return re.compile(rf"\bBij\s+(?:{woordenlijsten()['ELLIPTISCH']})\s+", re.IGNORECASE)


def _lem(a, i) -> str:
    return (a.tokens[i].lemma or a.tokens[i].tekst).lower()


def _telbaar(a, start: int, eind: int) -> bool:
    """Draagt het bereik een telbare grootheid: een zelfstandig naamwoord in het meervoud ('termijnen', 'maanden')."""
    return any(t.upos == "NOUN" and t.feat("Number") == "Plur" and start <= t.start and t.eind <= eind
               for t in a.tokens)


def _aantal(a, tekst: str, s: int, e: int):
    """'zoveel X als … <werkwoord>' in segment [s, e): (uitkomst, invoer) als bereiken, of None.

    De invoer is de bijzin van 'als': van na 'als' tot en met het eerste werkwoord dat niet in een betrekkelijke bijzin
    staat ('… na de maand, die in de dagtekening is vermeld, nog maanden van het jaar overblijven'). Niet de subboom van
    'als': de parser hangt 'als' in zo'n zin soms aan een naamwoord (art. 9 lid 5 IW). Uitkomst en invoer moeten allebei
    een telbare grootheid dragen; 'zoveel mogelijk' of 'zoveel als nodig' telt niet, want dat is geen aantal dat de
    regel afleidt."""
    m = _AANTAL.search(tekst, s, e)
    if not m:
        return None
    begin = m.end()
    na = [t for t in a.tokens if begin <= t.start and t.eind <= e]
    bijzin = {j for t in na if t.deprel == "acl:relcl" for j in a.subboom(t.i)}
    werkwoord = next((t for t in na if t.upos in {"VERB", "AUX"} and t.i not in bijzin), None)
    if werkwoord is None:
        return None
    invoer = (begin, werkwoord.eind)
    uitkomst = (m.start("uitkomst"), m.end("uitkomst"))
    if invoer[0] >= invoer[1] or not (_telbaar(a, *uitkomst) and _telbaar(a, *invoer)):
        return None
    return m.start(), uitkomst, invoer


def toepassingskeuze(a, i: int) -> dict | None:
    """'<regel> vindt (geen / overeenkomstige) toepassing' rond predicaat `i`, of None.

    Gedeeld door de functiedetector (Afleidingsregel: welke regel geldt) en de gevolgdetector
    (Rechtsbetrekking: dát hij geldt), zodat ze dezelfde constructie herkennen. Geeft de token-
    indices van 'toepassing' en de regel, en of het ontkend, een schakelbepaling of voorwaardelijk is.
    """
    if _lem(a, i) != "vinden":
        return None
    toep = [j for j in a.subboom(i) if _lem(a, j) == "toepassing"
            and not any(a.tokens[k].deprel == "advcl" and j in a.subboom(k) for k in a.kinderen(i))]
    regel = [k for k in a.kinderen(i) if a.tokens[k].deprel == "nsubj"]
    if not toep or not regel:
        return None
    t0 = toep[0]
    return {
        "toepassing": t0, "regel": regel[0],
        "ontkend": any(_lem(a, c) in _ONTKENNING for c in (*a.kinderen(t0), *a.kinderen(i))),
        "overeenkomstig": any(_lem(a, c).startswith("overeenkomstig") for c in a.kinderen(t0)),
        "voorwaardelijk": any(_lem(a, m) in VOORWAARDE_VOEGWOORDEN for c in a.kinderen(i) if a.tokens[c].deprel == "advcl"
                              for m in a.kinderen(c) if a.tokens[m].deprel == "mark")
        or any(_lem(a, c) == "geval" for c in a.kinderen(i) if a.tokens[c].deprel == "obl"),
    }


class FunctieDetector:
    naam = "functie"
    # 3: afleiding en toepassingskeuze op hun eigen span, het segment als optie
    # 4: 'zoveel … als' met elke telbare bijzin (de parse), en een tijdstip als waarde (L-2-1, L-2-5)
    versie = f"4+grenzen.{GRENS_VERSIE}+verwijzing.{VERWIJZING_VERSIE}"
    CODES = ("CALCULATION_ASSIGNMENT", "CALCULATION_QUANTITY", "CALCULATION_CALENDAR_POSITION",
             "TEMPORAL_DESCRIPTION", "CONDITIONAL_ELLIPSIS", "CALCULATION_APPLICABILITY", "TEMPORAL_VALUE")
    REGELS = ("jas.afleiding.passieve_toewijzing", "jas.afleiding.aantal_zoveel_als",
              "jas.afleiding.kalenderpositie", "jas.tijd.datumomschrijving",
              "jas.voorwaarde.elliptisch", "jas.afleiding.toepassingskeuze", "jas.variabele.tijdstip_als_waarde")

    def detecteer(self, bron):
        a, reden = parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        ks, gezien = [], set()

        def voeg(s, e, klasse, code, regel, segment=None, **bewijs):
            if code not in self.CODES:
                raise ValueError(f"onbekende functiecode {code}")
            if (s, e, code) in gezien:          # twee predicaten in één segment: één hypothese
                return
            gezien.add((s, e, code))
            opties = [SpanOption(soort="segment", span=BronSpan.van(bron.span(*segment)))] \
                if segment and segment != (s, e) else []
            klassen = list(klasse) if isinstance(klasse, tuple) else [klasse]
            ks.append(Candidate.maak(bron.span(s, e), klassen, [Evidence(
                detector=self.naam, code=code, regel=regel,
                detail=json.dumps(bewijs, ensure_ascii=False, sort_keys=True))], opties))

        def lemma(i):
            return (a.tokens[i].lemma or a.tokens[i].tekst).lower()

        def kind(i, *rels):
            return [k for k in a.kinderen(i) if a.tokens[k].deprel in rels]

        def segment_van(i):
            t = a.tokens[i]
            return next(((g.start, g.eind) for g in segmenten if g.start <= t.start < g.eind), None)

        segmenten = analyseer_grenzen(bron.tekst).segmenten(bron.tekst)
        for t in a.tokens:
            # Passieve toewijzing: '<grootheid> wordt (op X) (vast)gesteld (op X)'.
            if lemma(t.i) in {"stellen", "vaststellen"} and any(lemma(x) == "worden" for x in kind(t.i, "aux:pass")):
                onderwerp = [o for o in kind(t.i, "nsubj:pass") if _lijst("GROOTHEID").match(lemma(o))]
                op = [o for o in kind(t.i, "obl") if any(lemma(c) == "op" for c in kind(o, "case"))]
                seg = segment_van(t.i)
                if onderwerp and op and seg:
                    voeg(*seg, AR, "CALCULATION_ASSIGNMENT", self.REGELS[0],
                         predicaat="stellen op", uitkomst=a.tokens[onderwerp[0]].tekst)
            # Toepassingskeuze: '(Indien …,) vindt <regel> toepassing', niet ontkend of overeenkomstig.
            keuze = toepassingskeuze(a, t.i)
            if keuze and keuze["voorwaardelijk"] and not (keuze["ontkend"] or keuze["overeenkomstig"]):
                seg = segment_van(t.i)
                if seg:
                    ids = set(a.subboom(keuze["regel"])) - set(a.subboom(keuze["toepassing"]))
                    g = bereik(a, ids)
                    clause = clausebereik(a, t.i)
                    # Geen aaneengesloten clause: zichtbaar het segment, nooit een gegokte grens.
                    extra = {} if clause else {"clause_onderbroken": True}
                    voeg(*(clause or seg), AR, "CALCULATION_APPLICABILITY", self.REGELS[5], segment=seg,
                         toepasselijke_regel={"start": g[0], "eind": g[1], "tekst": bron.tekst[g[0]:g[1]]}
                         if g else None, **extra)

        for segment in segmenten:
            s, e = segment.start, segment.eind
            tekst = bron.tekst[s:e]
            if gevonden := _aantal(a, bron.tekst, s, e):
                begin, uitkomst, invoer = gevonden
                voeg(begin, invoer[1], AR, "CALCULATION_QUANTITY", self.REGELS[1], segment=(s, e),
                     **{naam: {"start": g[0], "eind": g[1], "tekst": bron.tekst[g[0]:g[1]]}
                        for naam, g in (("uitkomst", uitkomst), ("invoer", invoer))})
            # Een ordinaliteitsvergelijking bij het bepalen van een vervaldatum, geen losse 'als'.
            if (re.search(r"\bvervalt\b", tekst, re.I)
                    and re.search(r"\bdag\s+die\s+hetzelfde\s+nummer\s+heeft\s+als\b", tekst, re.I)):
                voeg(s, e, AR, "CALCULATION_CALENDAR_POSITION", self.REGELS[2],
                     bewerking="gelijke kalenderpositie", uitkomst="vervaldag")

        for t in a.tokens:
            # Een tijdstip als waarde: '<lidwoord> dagtekening van <iets>', zonder eigen werkwoord en zonder bijzin
            # (die is TEMPORAL_DESCRIPTION). Een gegeven dat een regel leest of afleidt, geen handeling (L-2-5).
            van = [n for n in kind(t.i, "nmod") if any(lemma(c) == "van" for c in kind(n, "case"))]
            if (_lijst("TIJDSTIP").match(lemma(t.i)) and t.feat("Number") != "Plur" and not kind(t.i, "acl:relcl")
                    and van):
                # Het tijdstip met lidwoord en bijvoeglijk naamwoord en zijn van-bepaling; niet de duur ervoor
                # ('zes weken na …') en niet het voorzetsel van de zin.
                ids = {t.i, *kind(t.i, "det"), *(k for k in kind(t.i, "amod") if a.tokens[k].upos == "ADJ"),
                       *(i for n in van for i in a.subboom(n))}
                # Een nevenschikking hoort er niet bij ('… van het aanslagbiljet en een naheffingsaanslag').
                ids -= {j for i in list(ids) if a.tokens[i].deprel in {"conj", "cc"} and a.tokens[i].head in ids
                        for j in a.subboom(i)}
                g = bereik(a, ids)
                if (g and not in_verwijzing(bron, *g)
                        and not any(a.tokens[i].upos in {"VERB", "AUX"} for i in ids)):
                    voeg(*g, (VAR, T), "TEMPORAL_VALUE", self.REGELS[6], hoofd=t.tekst)
            if lemma(t.i) in {"dag", "datum", "tijdstip", "vervaldag"}:
                if kind(t.i, "acl:relcl"):
                    ids = set(a.subboom(t.i))
                    ids -= {i for k in kind(t.i, "conj", "parataxis", "cc") for i in a.subboom(k)}
                    g = bereik(a, zonder_randfunctie(a, ids, t.i))
                    if g and not in_verwijzing(bron, *g):
                        voeg(*g, T, "TEMPORAL_DESCRIPTION", self.REGELS[3], hoofd=t.tekst)
            if t.deprel not in {"obl", "nmod"}:
                continue
            ids = a.subboom(t.i)
            g = bereik(a, ids)
            # Alleen een nominale adjunct aan een hoofdzin, geen volledige boom/subzin.
            if (g and _elliptisch().match(bron.tekst[g[0]:g[1]])
                    and not any(a.tokens[i].feat("VerbForm") == "Fin" for i in ids)):
                voeg(*g, VW, "CONDITIONAL_ELLIPSIS", self.REGELS[4], hoofd=t.tekst, governor=t.head)
        return resultaat(self, bron, ks)
