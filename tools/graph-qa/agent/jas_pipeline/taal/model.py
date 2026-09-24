"""Het provider-onafhankelijke taalmodel: Universal Dependencies, offsets in codepoints.

JAS-logica leest alléén deze typen. Welke parser erachter zit (spaCy, Stanza, Alpino) is een
eigenschap van de analyse (`provider`, `model`), geen afhankelijkheid van de detectoren – zo is de
provider te wisselen zonder dat er één regel JAS-code verandert, en blijft in de provenance
zichtbaar wélke parser een kandidaat heeft aangedragen.

De offsets slaan op de tekst die geanalyseerd is: de eigen tekst van één bronnode, dezelfde tekst
waar `bronmodel.Span` naar wijst. Een token kan dus direct een bronanker worden.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Niveau(str, Enum):
    """Wat een analyse levert. Een detector die meer nodig heeft, weet zo dat hij niet kan draaien."""

    VOLLEDIG = "volledig"   # tokens, lemma, POS, morfologie en dependencies
    TOKENS = "tokens"       # alleen tokens en zinnen: de parser ontbrak of faalde


@dataclass(frozen=True, slots=True)
class Token:
    i: int                  # index in de analyse (over zinnen heen)
    tekst: str
    start: int              # codepoints in de geanalyseerde tekst, [start, eind)
    eind: int
    zin: int                # index van de zin
    lemma: str = ""
    upos: str = ""          # UD universal POS; "" als onbekend
    xpos: str = ""
    morf: tuple[tuple[str, str], ...] = ()   # UD-features, gesorteerd
    head: int = -1          # index van het hoofd; -1 = root of onbekend
    deprel: str = ""        # UD-relatie, incl. subtype ("obl:agent"); "" als onbekend

    def feat(self, naam: str) -> str:
        return dict(self.morf).get(naam, "")


@dataclass(frozen=True, slots=True)
class Zin:
    i: int
    start: int
    eind: int
    tokens: tuple[int, int]   # [eerste, laatste+1) tokenindex


@dataclass(frozen=True)
class LinguisticAnalysis:
    tekst: str
    tokens: tuple[Token, ...]
    zinnen: tuple[Zin, ...]
    provider: str                 # "spacy", "stanza", "null"
    model: str = ""               # modelnaam + versie, voor de provenance
    niveau: Niveau = Niveau.VOLLEDIG
    fout: str = ""                # waarom de analyse gedegradeerd is; leeg als ze dat niet is
    _kinderen: dict[int, tuple[int, ...]] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self):
        kinderen: dict[int, list[int]] = {}
        for t in self.tokens:
            if t.head >= 0:
                kinderen.setdefault(t.head, []).append(t.i)
        object.__setattr__(self, "_kinderen", {k: tuple(v) for k, v in kinderen.items()})

    @property
    def gedegradeerd(self) -> bool:
        return self.niveau is not Niveau.VOLLEDIG

    def kinderen(self, i: int) -> tuple[int, ...]:
        return self._kinderen.get(i, ())

    def subboom(self, i: int) -> tuple[int, ...]:
        """Alle tokenindices onder `i`, inclusief `i` zelf, gesorteerd."""
        gezien, stapel = set(), [i]
        while stapel:
            k = stapel.pop()
            if k in gezien:
                continue            # een kapotte parse met een cyclus mag hier niet hangen
            gezien.add(k)
            stapel.extend(self.kinderen(k))
        return tuple(sorted(gezien))

    def bereik(self, indices: tuple[int, ...] | list[int]) -> tuple[int, int]:
        """Het tekstbereik van een reeks tokens: van de eerste start tot het laatste eind."""
        return self.tokens[min(indices)].start, self.tokens[max(indices)].eind

    def aaneengesloten(self, indices: tuple[int, ...]) -> bool:
        return max(indices) - min(indices) + 1 == len(indices)
