"""Aanhef → onderdeel → omschrijving, onafhankelijk van de regelopmaak.

De aanroeper bepaalt welk aanhefpatroon inhoudelijk relevant is. Deze laag kent
geen JAS-klassen. Alleen eigen tekst levert annotatiebereiken; oudercontext geeft
uitsluitend aan dat de eigen bronnode binnen een opsomming valt.
"""
from dataclasses import dataclass
import re

from .grenzen import Bereik, onderdeel_labels

VERSIE = "1"


@dataclass(frozen=True, slots=True)
class Aanhef:
    bron: str  # eigen of ouder; de offsets horen bij die tekst
    bereik: Bereik


@dataclass(frozen=True, slots=True)
class Onderdeel:
    aanhef: Aanhef
    term: Bereik
    omschrijving: Bereik
    label: Bereik | None = None


@dataclass(frozen=True, slots=True)
class _Venster:
    """Alle zoekposities worden hier eenmaal naar de eigen bron terugvertaald."""
    tekst: str
    start: int

    def bereik(self, start: int, eind: int, reden: str) -> Bereik:
        if not 0 <= start < eind <= len(self.tekst):
            raise ValueError("structuurbereik buiten eigen zoekvenster")
        return Bereik(self.start + start, self.start + eind, reden)


_TERM = re.compile(r"[ \t\r\n]*(?P<term>[^:;\n]{1,120}?)[ \t]*:\s+(?=\S)")


def herken_onderdelen(tekst: str, context: str, patroon: re.Pattern) -> tuple[Onderdeel, ...]:
    eigen = list(patroon.finditer(tekst))
    vensters = []
    if eigen:
        for i, m in enumerate(eigen):
            eind = eigen[i + 1].start() if i + 1 < len(eigen) else len(tekst)
            vensters.append((Aanhef("eigen", Bereik(m.start(), m.end(), "aanhef")), m.end(), eind))
    elif ouders := list(patroon.finditer(context)):
        m = ouders[-1]
        vensters.append((Aanhef("ouder", Bereik(m.start(), m.end(), "aanhef")), 0, len(tekst)))
    uit = []
    for aanhef, start, eind in vensters:
        venster = _Venster(tekst[start:eind], start)
        lokaal = venster.tekst
        labels = {b.start: b for b in onderdeel_labels(lokaal)}
        starts = {0, *labels}
        # Een ongenummerd vervolglied heeft een regelstart én een afgesloten
        # voorganger nodig. Een dubbele punt binnen een omschrijving is geen lid.
        for m in re.finditer(r"\n[ \t]*(?=\S)", lokaal):
            if lokaal[:m.start()].rstrip().endswith(";"):
                starts.add(m.end())
        treffers = []
        for pos in sorted(starts):
            while pos < len(lokaal) and lokaal[pos].isspace():
                pos += 1
            label = labels.get(pos)
            m = _TERM.match(lokaal, label.eind if label else pos)
            if m and not any(t[0] == pos for t in treffers):
                treffers.append((pos, m, label))
        for i, (_, m, label) in enumerate(treffers):
            oms_eind = treffers[i + 1][0] if i + 1 < len(treffers) else len(lokaal)
            while oms_eind > m.end() and lokaal[oms_eind - 1].isspace():
                oms_eind -= 1
            if oms_eind <= m.end():
                continue
            uit.append(Onderdeel(
                aanhef, venster.bereik(*m.span("term"), "term"),
                venster.bereik(m.end(), oms_eind, "omschrijving"),
                venster.bereik(label.start, label.eind, label.reden) if label else None))
    return tuple(uit)
