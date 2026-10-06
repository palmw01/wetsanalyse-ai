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

AR, T, VW = "Afleidingsregel", "Tijdsaanduiding", "Voorwaarde"
_AANTAL = re.compile(r"\bzoveel\s+(?P<uitkomst>[\s\S]+?)\s+als\s+(?P<invoer>[\s\S]*\b(?:overblijven|resteren)\b)", re.I)
_VOORWAARDE = {"indien", "als", "wanneer", "zodra"}
_ONTKENNING = {"geen", "niet"}


@cache
def _lijst(naam: str) -> re.Pattern:
    return re.compile(rf"^(?:{woordenlijsten()[naam]})$", re.IGNORECASE)


@cache
def _elliptisch() -> re.Pattern:
    return re.compile(rf"\bBij\s+(?:{woordenlijsten()['ELLIPTISCH']})\s+", re.IGNORECASE)


class FunctieDetector:
    naam = "functie"
    # 3: afleiding en toepassingskeuze op hun eigen span, het segment als optie
    versie = f"3+grenzen.{GRENS_VERSIE}+verwijzing.{VERWIJZING_VERSIE}"
    CODES = ("CALCULATION_ASSIGNMENT", "CALCULATION_QUANTITY", "CALCULATION_CALENDAR_POSITION",
             "TEMPORAL_DESCRIPTION", "CONDITIONAL_ELLIPSIS", "CALCULATION_APPLICABILITY")
    REGELS = ("jas.afleiding.passieve_toewijzing", "jas.afleiding.aantal_uit_restant",
              "jas.afleiding.kalenderpositie", "jas.tijd.datumomschrijving",
              "jas.voorwaarde.elliptisch", "jas.afleiding.toepassingskeuze")

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
            ks.append(Candidate.maak(bron.span(s, e), [klasse], [Evidence(
                detector=self.naam, code=code, regel=regel,
                detail=json.dumps(bewijs, ensure_ascii=False, sort_keys=True))], opties))

        def lemma(i):
            return (a.tokens[i].lemma or a.tokens[i].tekst).lower()

        def kind(i, *rels):
            return [k for k in a.kinderen(i) if a.tokens[k].deprel in rels]

        def segment_van(i):
            t = a.tokens[i]
            return next(((g.start, g.eind) for g in segmenten if g.start <= t.start < g.eind), None)

        def onder_voorwaarde(i):
            return any(lemma(m) in _VOORWAARDE for c in kind(i, "advcl") for m in kind(c, "mark")) \
                or any(lemma(c) == "geval" for c in kind(i, "obl"))

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
            if lemma(t.i) == "vinden":
                toep = [i for i in a.subboom(t.i) if lemma(i) == "toepassing"
                        and not any(a.tokens[j].deprel == "advcl" and i in a.subboom(j) for j in a.kinderen(t.i))]
                if toep and onder_voorwaarde(t.i):
                    t0 = toep[0]
                    ontkend = any(lemma(c) in _ONTKENNING for c in (*a.kinderen(t0), *a.kinderen(t.i)))
                    overeenkomstig = any(lemma(c).startswith("overeenkomstig") for c in a.kinderen(t0))
                    regel = [o for o in kind(t.i, "nsubj")]
                    seg = segment_van(t.i)
                    if not (ontkend or overeenkomstig) and regel and seg:
                        ids = set(a.subboom(regel[0])) - set(a.subboom(t0))
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
            if m := _AANTAL.search(tekst):
                voeg(s + m.start(), s + m.end("invoer"), AR, "CALCULATION_QUANTITY", self.REGELS[1], segment=(s, e),
                     **{naam: {"start": s + m.start(naam), "eind": s + m.end(naam), "tekst": m[naam]}
                        for naam in ("uitkomst", "invoer")})
            # Een ordinaliteitsvergelijking bij het bepalen van een vervaldatum, geen losse 'als'.
            if (re.search(r"\bvervalt\b", tekst, re.I)
                    and re.search(r"\bdag\s+die\s+hetzelfde\s+nummer\s+heeft\s+als\b", tekst, re.I)):
                voeg(s, e, AR, "CALCULATION_CALENDAR_POSITION", self.REGELS[2],
                     bewerking="gelijke kalenderpositie", uitkomst="vervaldag")

        for t in a.tokens:
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
