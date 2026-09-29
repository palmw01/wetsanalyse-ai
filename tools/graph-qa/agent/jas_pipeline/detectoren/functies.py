"""Functiehypothesen met benoemde uitkomst/invoer; geen berekening of juridische beslissing.

Dependencies begrenzen de beschreven datum en elliptische voorwaarde. Rekenkundige
constructies gebruiken beschermde segmenten; de parse is vereist en wordt niet aangepast.
"""
import json
import re

from ..kandidaten import Candidate, Evidence
from ..taal.grenzen import analyseer_grenzen
from . import resultaat
from .syntactisch import _parse_of_reden, _bereik, _zonder_randfunctie, _in_verwijzing

AR, T, VW = "Afleidingsregel", "Tijdsaanduiding", "Voorwaarde"
_GROOTHEID = re.compile(r"\b(?:bedrag|premie|rente|percentage|tarief|termijn|vervaldag|datum|tijdstip|aantal|waarde)\b", re.I)
_PASSIEF = re.compile(r"\bword(?:t|en)\b[\s\S]*\bop\b[\s\S]*\b(?:vast)?gesteld\b", re.I)
_AANTAL = re.compile(r"\bzoveel\s+(?P<uitkomst>.+?)\s+als\s+(?P<invoer>[\s\S]*\b(?:overblijven|resteren)\b)", re.I)
_ELLIPTISCH = re.compile(r"\bBij\s+(?:afwijkende|ontbrekende|ongewijzigde)\s+", re.I)


class FunctieDetector:
    naam = "functie"
    versie = "1"
    REGELS = ("jas.afleiding.passieve_toewijzing", "jas.afleiding.aantal_uit_restant",
              "jas.afleiding.kalenderpositie", "jas.tijd.datumomschrijving",
              "jas.voorwaarde.elliptisch")

    def detecteer(self, bron):
        a, reden = _parse_of_reden(bron)
        if a is None:
            return resultaat(self, bron, overgeslagen=True, reden=reden)
        ks = []

        def voeg(s, e, klasse, code, regel, **bewijs):
            ks.append(Candidate.maak(bron.span(s, e), [klasse], [Evidence(
                detector=self.naam, code=code, regel=regel,
                detail=json.dumps(bewijs, ensure_ascii=False, sort_keys=True))]))

        for segment in analyseer_grenzen(bron.tekst).segmenten(bron.tekst):
            s, e = segment.start, segment.eind
            tekst = bron.tekst[s:e]
            if _PASSIEF.search(tekst) and _GROOTHEID.search(tekst) and not re.search(r"\bregels\b", tekst, re.I):
                voeg(s, e, AR, "CALCULATION_ASSIGNMENT", self.REGELS[0],
                     predicaat="stellen op", uitkomst=_GROOTHEID.search(tekst).group())
            if m := _AANTAL.search(tekst):
                voeg(s, e, AR, "CALCULATION_QUANTITY", self.REGELS[1],
                     **{naam: {"start": s + m.start(naam), "eind": s + m.end(naam), "tekst": m[naam]}
                        for naam in ("uitkomst", "invoer")})
            # Een ordinaliteitsvergelijking bij het bepalen van een vervaldatum, geen losse 'als'.
            if (re.search(r"\bvervalt\b", tekst, re.I)
                    and re.search(r"\bdag\s+die\s+hetzelfde\s+nummer\s+heeft\s+als\b", tekst, re.I)):
                voeg(s, e, AR, "CALCULATION_CALENDAR_POSITION", self.REGELS[2],
                     bewerking="gelijke kalenderpositie", uitkomst="vervaldag")

        for t in a.tokens:
            if (t.lemma or t.tekst).lower() in {"dag", "datum", "tijdstip", "vervaldag"}:
                if any(a.tokens[i].deprel == "acl:relcl" for i in a.kinderen(t.i)):
                    ids = set(a.subboom(t.i))
                    ids -= {i for k in a.kinderen(t.i) if a.tokens[k].deprel in {"conj", "parataxis", "cc"}
                            for i in a.subboom(k)}
                    g = _bereik(a, _zonder_randfunctie(a, ids, t.i))
                    if g and not _in_verwijzing(bron, *g):
                        voeg(*g, T, "TEMPORAL_DESCRIPTION", self.REGELS[3], hoofd=t.tekst)
            ids = a.subboom(t.i)
            g = _bereik(a, ids)
            if g and _ELLIPTISCH.match(bron.tekst[g[0]:g[1]]) and t.deprel in {"obl", "nmod"}:
                # Alleen een nominale adjunct aan een hoofdzin, geen volledige boom/subzin.
                if not any(a.tokens[i].feat("VerbForm") == "Fin" for i in ids):
                    voeg(*g, VW, "CONDITIONAL_ELLIPSIS", self.REGELS[4],
                         hoofd=t.tekst, governor=t.head)
        return resultaat(self, bron, ks)
