"""Wirecontract voor open punten (L-X-1 uit de lessen van Termijnen; ADR-018 §6; skill `afleidingsregels.md`,
*Wat open blijft*).

Een open punt is wat een analyse niet stil mag beslissen: een interpretatiekeuze, ontbrekend uitvoeringsbeleid, een
onderzoekspunt of een gat in de annotatie. Het hoort bij het werkgebied en hangt aan een of meer regels, gevallen,
markeringen, begrippen of deelvragen: één keuze kan meer regels raken (lezing C van art. 72 Mbw raakt er twee).

De vorm komt uit de skill: de soort, waar het aan hangt, de lezingen met hun grondslag, de keuze en wie die maakte, en
wat nog getoetst moet worden. De methode van de keuze (teleologisch, wetshistorisch, systematisch, grammaticaal) komt
uit ADR-018 §6. De codes van de soorten staan hier, hun namen in de skill; `tests/test_open_punten.py` houdt beide
gelijk (zoals de klassennamen in `jas_klassen.py`).

Lex signaleert en legt lezingen voor; de jurist kiest (`Besluit`, een eigen route die het agent-token niet mag).
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ID = r"^[A-Za-z0-9._:#/-]{1,300}$"


class Soort(str, Enum):
    """De vier soorten uit de skill (*Wat open blijft*), in die volgorde."""
    interpretatiekeuze = "interpretatiekeuze"
    ontbrekend_uitvoeringsbeleid = "ontbrekend_uitvoeringsbeleid"
    onderzoekspunt = "onderzoekspunt"
    gat_in_de_annotatie = "gat_in_de_annotatie"


#: De naam van elke soort zoals de skill hem schrijft; de drift-test leest de skill en vergelijkt.
SOORT_NAMEN: dict[Soort, str] = {
    Soort.interpretatiekeuze: "interpretatiekeuze",
    Soort.ontbrekend_uitvoeringsbeleid: "ontbrekend uitvoeringsbeleid",
    Soort.onderzoekspunt: "onderzoekspunt",
    Soort.gat_in_de_annotatie: "gat in de annotatie",
}


class Status(str, Enum):
    open = "open"                  # nog geen keuze
    gekozen = "gekozen"            # de jurist koos een lezing (of: legde vast hoe het verder gaat)
    getoetst = "getoetst"          # gekozen, en alles wat getoetst moest worden is getoetst
    # Alleen bij ontbrekend uitvoeringsbeleid: de jurist stelde vast dat het beleid ontbreekt, en het punt gaat naar de
    # beleidsverantwoordelijken (M01 stap 5). Dat is geen keuze, dus ook niet *gekozen* (e2e-run 20 nov 2026, B5).
    gesignaleerd = "gesignaleerd"


class Uitkomst(str, Enum):
    """Wat het besluit is. `gesignaleerd` kan alleen bij ontbrekend uitvoeringsbeleid."""
    gekozen = "gekozen"
    gesignaleerd = "gesignaleerd"


class Methode(str, Enum):
    """De interpretatiemethode van een keuze (ADR-018 §6)."""
    grammaticaal = "grammaticaal"
    systematisch = "systematisch"
    wetshistorisch = "wetshistorisch"
    teleologisch = "teleologisch"


class Bronsoort(str, Enum):
    """Waaraan een punt nog getoetst moet worden ("niet getoetst aan de memorie van toelichting")."""
    wettekst = "wettekst"
    wetsgeschiedenis = "wetsgeschiedenis"          # memorie van toelichting, nota's, Kamerstukken
    jurisprudentie = "jurisprudentie"
    beleid = "beleid"                              # beleidsregels, Leidraad, besluiten
    kennisgroepstandpunt = "kennisgroepstandpunt"
    uitvoeringspraktijk = "uitvoeringspraktijk"
    literatuur = "literatuur"


class Aanhaking(BaseModel):
    """Waar het punt aan hangt. `geval` alleen bij een regel: het label van de rij. `werkgebied` is het werkgebied zelf:
    een onderzoekspunt bij de bronselectie van een werkgebied zonder deelvragen (de analysevraag)."""
    model_config = ConfigDict(extra="ignore")

    soort: Literal["regel", "geval", "markering", "begrip", "deelvraag", "werkgebied"]
    id: str = Field(pattern=_ID)
    geval: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def _geval(self) -> "Aanhaking":
        if self.soort == "geval" and not self.geval.strip():
            raise ValueError("een geval noemt het label van de rij")
        if self.soort != "geval" and self.geval:
            raise ValueError("alleen een geval heeft een label")
        return self


class Grondslag(BaseModel):
    """Waar een lezing op rust: een markering, een bepaling (bron-IRI), een begrip, of een stuk naast de wet."""
    model_config = ConfigDict(extra="ignore")

    soort: Literal["markering", "bron", "begrip", "stuk"]
    id: str = Field(pattern=_ID)
    label: str = Field(default="", max_length=300)


class Lezing(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(min_length=1, max_length=20)              # "A", "B", "C"
    omschrijving: str = Field(min_length=1, max_length=4000)
    grondslag: list[Grondslag] = Field(default_factory=list, max_length=20)


class TeToetsen(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bronsoort: Bronsoort
    omschrijving: str = Field(default="", max_length=2000)       # "de MvT bij art. 9 lid 5"
    getoetst: bool = False
    uitkomst: str = Field(default="", max_length=4000)           # wat de toets opleverde

    @model_validator(mode="after")
    def _uitkomst(self) -> "TeToetsen":
        if self.getoetst and not self.uitkomst.strip():
            raise ValueError("een getoetst punt zegt wat de toets opleverde")
        return self


class OpenPuntInhoud(BaseModel):
    """Wat de jurist (of Lex als voorstel) vastlegt. De keuze zelf staat hier niet: die gaat via `Besluit`."""
    model_config = ConfigDict(extra="ignore")

    soort: Soort
    vraag: str = Field(min_length=1, max_length=2000)            # wat open is, als vraag of in één zin
    hangt_aan: list[Aanhaking] = Field(min_length=1, max_length=40)
    lezingen: list[Lezing] = Field(default_factory=list, max_length=10)
    te_toetsen: list[TeToetsen] = Field(default_factory=list, max_length=20)
    toelichting: str = Field(default="", max_length=8000)

    @field_validator("lezingen")
    @classmethod
    def _labels(cls, v: list[Lezing]) -> list[Lezing]:
        labels = [x.label.strip() for x in v]
        if len(set(labels)) != len(labels):
            raise ValueError("de labels van de lezingen zijn uniek")
        return v

    @model_validator(mode="after")
    def _keuze_heeft_lezingen(self) -> "OpenPuntInhoud":
        if self.soort == Soort.interpretatiekeuze and len(self.lezingen) < 2:
            raise ValueError("een interpretatiekeuze heeft ten minste twee lezingen")
        return self


class OpenPuntAanmaak(BaseModel):
    inhoud: OpenPuntInhoud
    herkomst: Literal["lex", "import", "jurist", "regelspecialist"] = "jurist"


class Revisie(BaseModel):
    """De basis van elke wijziging. Een onbekend veld is een 422: een besluit met `besluit` en `reden` in plaats van
    `gekozen` en `motivering` deed anders stil niets (e2e-run 20 nov 2026, B5)."""
    model_config = ConfigDict(extra="forbid")

    verwachte_revisie: int = Field(ge=1)


class OpenPuntWijziging(Revisie):
    inhoud: OpenPuntInhoud


class Besluit(Revisie):
    """De keuze van de jurist. Bij een punt met lezingen is `gekozen` het label van een lezing; zonder lezingen (een
    onderzoekspunt, een gat) is de `motivering` hoe het verder gaat. `gekozen` leeg en `motivering` leeg heropent een
    besloten punt; op een punt dat open is, is dat een 422. Bij ontbrekend uitvoeringsbeleid zegt `uitkomst` of het
    beleid gevonden is (`gekozen`) of ontbreekt (`gesignaleerd`)."""
    gekozen: str = Field(default="", max_length=20)
    motivering: str = Field(default="", max_length=4000)
    methode: Methode | None = None
    uitkomst: Uitkomst | None = None


class Omhangen(Revisie):
    """Waar het punt aan hangt, en verder niets (A2): na een vervanging naar de opvolger, per geval. De rest van de
    inhoud en de keuze blijven staan."""
    hangt_aan: list[Aanhaking] = Field(min_length=1, max_length=40)
