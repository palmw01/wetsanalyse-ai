"""Taalanalyse-providers: één protocol, verwisselbare parsers, en nooit een stille terugval.

`analyseer()` gooit niet. Faalt de parser (niet geïnstalleerd, model ontbreekt, exceptie), dan
komt er een analyse op niveau `TOKENS` terug met de reden in `fout`. Detectoren die dependencies
nodig hebben slaan zich dan zichtbaar over, en de kandidaten krijgen een onzekerheidssignaal
(ADR-001 §4: "geen stille fallback"). Terugvallen op een volledige LLM-annotatie is hier bewust
geen optie.

Keuze van de provider: `maak_provider("spacy:nl_core_news_md")`, `"stanza:nl"` of `"null"`. De
benchmark die de default onderbouwt staat in `eval/taal_benchmark.py`.
"""
from __future__ import annotations

import re
import threading
from typing import Protocol

from .grenzen import analyseer_grenzen
from .model import LinguisticAnalysis, Niveau, Token, Zin


class TaalProvider(Protocol):
    naam: str
    model: str

    def analyseer(self, tekst: str) -> LinguisticAnalysis: ...


# --- terugval: alleen tokens en zinnen ---------------------------------------------------------

_TOKEN_RE = re.compile(r"\w+(?:[-']\w+)*|[^\w\s]", re.UNICODE)

def tokens_en_zinnen(tekst: str) -> tuple[tuple[Token, ...], tuple[Zin, ...]]:
    tokens: list[Token] = []
    zinnen: list[Zin] = []
    for zin in analyseer_grenzen(tekst).zinnen(tekst):
        eerste = len(tokens)
        for m in _TOKEN_RE.finditer(tekst, zin.start, zin.eind):
            tokens.append(Token(len(tokens), m.group(), m.start(), m.end(), len(zinnen)))
        if len(tokens) > eerste:
            zinnen.append(Zin(len(zinnen), tokens[eerste].start, tokens[-1].eind, (eerste, len(tokens))))
    return tuple(tokens), tuple(zinnen)


def gedegradeerd(tekst: str, provider: str, model: str, fout: str) -> LinguisticAnalysis:
    tokens, zinnen = tokens_en_zinnen(tekst)
    return LinguisticAnalysis(tekst, tokens, zinnen, provider, model, Niveau.TOKENS, fout)


class NullProvider:
    """Geen parser. Expliciet gekozen, dus niet 'gefaald' – maar wel een lager niveau."""

    naam = "null"
    model = ""

    def analyseer(self, tekst: str) -> LinguisticAnalysis:
        return gedegradeerd(tekst, self.naam, self.model, "geen parser geconfigureerd")


# --- spaCy ---------------------------------------------------------------------------------------

def _morf(feats: str) -> tuple[tuple[str, str], ...]:
    paren = (f.split("=", 1) for f in feats.split("|") if "=" in f)
    return tuple(sorted((k, v) for k, v in paren))


class SpacyProvider:
    naam = "spacy"

    def __init__(self, modelnaam: str = "nl_core_news_md"):
        self.modelnaam = modelnaam
        self.model = modelnaam
        self._nlp = None
        self._laadfout = ""
        # Het model laden kost seconden. Zonder lock laadden twee gelijktijdige beurten (of de
        # opwarmthread bij het opstarten en de eerste beurt) het allebei.
        self._slot = threading.Lock()

    def _laad(self):
        if self._nlp is not None or self._laadfout:
            return self._nlp
        with self._slot:
            if self._nlp is None and not self._laadfout:
                try:
                    import spacy
                    self._nlp = spacy.load(self.modelnaam, exclude=["ner"])
                    self.model = f"{self.modelnaam}-{self._nlp.meta.get('version', '?')}"
                except Exception as exc:          # ImportError, OSError (model ontbreekt), …
                    self._laadfout = f"spaCy-model {self.modelnaam} niet beschikbaar: {type(exc).__name__}"
        return self._nlp

    def warm_op(self) -> None:
        """Het model vooraf laden (bij het opstarten), zodat de eerste beurt er niet op wacht."""
        self._laad()

    def analyseer(self, tekst: str) -> LinguisticAnalysis:
        nlp = self._laad()
        if nlp is None:
            return gedegradeerd(tekst, self.naam, self.model, self._laadfout)
        try:
            doc = nlp(tekst)
        except Exception as exc:
            return gedegradeerd(tekst, self.naam, self.model, f"parserfout: {type(exc).__name__}")
        tokens: list[Token] = []
        zinnen: list[Zin] = []
        # Witruimte-tokens (spaCy maakt die van "\n\n") horen niet in het UD-model; de indexen
        # worden daarom opnieuw genummerd en de heads meevertaald.
        nieuw = {t.i: n for n, t in enumerate(t for t in doc if not t.is_space)}
        for zi, sent in enumerate(t for t in doc.sents if any(not x.is_space for x in t)):
            eerste = len(tokens)
            for t in sent:
                if t.is_space:
                    continue
                head = -1 if t.head.i == t.i or t.head.i not in nieuw else nieuw[t.head.i]
                tokens.append(Token(nieuw[t.i], t.text, t.idx, t.idx + len(t.text), zi,
                                    t.lemma_, t.pos_, t.tag_, _morf(str(t.morph)), head,
                                    t.dep_.lower() if head >= 0 else "root"))
            zinnen.append(Zin(zi, tokens[eerste].start, tokens[-1].eind, (eerste, len(tokens))))
        return LinguisticAnalysis(tekst, tuple(tokens), tuple(zinnen), self.naam, self.model)


# --- Stanza --------------------------------------------------------------------------------------

class StanzaProvider:
    naam = "stanza"

    def __init__(self, taal: str = "nl", model_dir: str | None = None):
        self.taal = taal
        self.model_dir = model_dir
        self.model = f"stanza-{taal}"
        self._nlp = None
        self._laadfout = ""

    def _laad(self):
        if self._nlp is None and not self._laadfout:
            try:
                import stanza
                kw = {"dir": self.model_dir} if self.model_dir else {}
                self._nlp = stanza.Pipeline(self.taal, processors="tokenize,mwt,pos,lemma,depparse",
                                            verbose=False, download_method=None, **kw)
                self.model = f"stanza-{stanza.__version__}-{self.taal}"
            except Exception as exc:
                self._laadfout = f"Stanza-model {self.taal} niet beschikbaar: {type(exc).__name__}"
        return self._nlp

    def analyseer(self, tekst: str) -> LinguisticAnalysis:
        nlp = self._laad()
        if nlp is None:
            return gedegradeerd(tekst, self.naam, self.model, self._laadfout)
        try:
            doc = nlp(tekst)
        except Exception as exc:
            return gedegradeerd(tekst, self.naam, self.model, f"parserfout: {type(exc).__name__}")
        tokens: list[Token] = []
        zinnen: list[Zin] = []
        for zi, sent in enumerate(doc.sentences):
            basis = len(tokens)
            eerste = basis
            for w in sent.words:
                tok = w.parent
                head = -1 if w.head == 0 else basis + w.head - 1
                tokens.append(Token(len(tokens), w.text, tok.start_char, tok.end_char, zi,
                                    w.lemma or "", w.upos or "", w.xpos or "", _morf(w.feats or ""),
                                    head, (w.deprel or "") if head >= 0 else "root"))
            zinnen.append(Zin(zi, tokens[eerste].start, tokens[-1].eind, (eerste, len(tokens))))
        return LinguisticAnalysis(tekst, tuple(tokens), tuple(zinnen), self.naam, self.model)


def maak_provider(spec: str) -> TaalProvider:
    """`"spacy[:model]"`, `"stanza[:taal]"` of `"null"`. Onbekend is een configuratiefout."""
    soort, _, arg = spec.partition(":")
    if soort == "spacy":
        return SpacyProvider(arg or "nl_core_news_md")
    if soort == "stanza":
        return StanzaProvider(arg or "nl")
    if soort == "null":
        return NullProvider()
    raise ValueError(f"Onbekende taalprovider: {spec!r}")
