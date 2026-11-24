"""Wirecontract voor afleidingsregels (activiteit 3b, ADR-018).

Een regel leidt precies één begrip af (de uitvoer) uit andere begrippen (de invoer), en heeft een begrip voor zichzelf
("bepalen <uitvoer>"). Hij heeft altijd één of meer gevallen: een regel met één geval heeft één rij (ADR-018 §3). Een
geval heeft voorwaarden (een boom van "alle" en "één van") en een uitkomst (begrippen, operatorbegrippen en vaste tekst
op volgorde). De regeltekst wordt afgeleid (`regeltekst.py`), nooit getypt; de toelichting is vrij.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

_ID = r"^[A-Za-z0-9._:-]{1,64}$"

#: De klassen die zelf een grondslag van een regel zijn (ADR-018 §2). Een andere klasse mag alleen als de passage het
#: uitvoerbegrip aanduidt. Een begrip dat een regel afleidt zonder eigen formulering (een tussenresultaat, of het
#: regelbegrip van een beslisregel op een Rechtsbetrekking) rust met de rol `afgeleid` op een markering van deze klassen
#: (`begrip_store.toets_afgeleid`, A3 van de e2e-run van 20 nov 2026).
GRONDSLAG_KLASSEN = ("Afleidingsregel", "Rechtsbetrekking", "Tijdsaanduiding")
#: De rollen waarmee een drager de regel draagt. Een contextdrager draagt niets en vraagt dus geen oordeel, zoals een
#: begripskoppeling met een rol die niet dragend is. Eén plek: de poort (`regel_store`) en de projectie
#: (`regel_projectie`, `wa:rustOp`) lezen deze tuple (review regelstapel 20 nov 2026, bevinding 12).
DRAGEND = ("grondslag", "voorwaarde", "invoer", "uitvoer", "tijd")


class RegelSoort(str, Enum):
    rekenregel = "rekenregel"          # een hoogte, aantal, duur of datum
    beslisregel = "beslisregel"        # ja of nee, ook: bestaat een recht of bevoegdheid
    specialisatie = "specialisatie"    # hoort een rechtssubject of rechtsobject tot een groep


class Brontype(str, Enum):
    wet = "wet"
    beleid = "beleid"                  # de grondslag is een beleidsregel: accorderen geeft `geaccordeerd_als_beleidsregel`


class DragerRol(str, Enum):
    grondslag = "grondslag"            # de Afleidingsregel, of de formulering van het afgeleide begrip (ADR-018 §2)
    voorwaarde = "voorwaarde"
    invoer = "invoer"
    uitvoer = "uitvoer"
    tijd = "tijd"
    context = "context"


class Beoordeling(str, Enum):
    open = "open"
    akkoord = "akkoord"
    afgewezen = "afgewezen"


class VoorbeeldOordeel(str, Enum):
    open = "open"                      # nog niet beoordeeld (een voorstel van Lex)
    juist = "juist"                    # de uitkomst is juridisch juist
    onjuist = "onjuist"                # de regel geeft een uitkomst die niet klopt
    kan_niet = "kan_niet"              # deze invoer mag zich niet voordoen


#: Zoveel tekens mag één tekstdeel van een uitkomst hebben. Een langer deel is meestal een voorwaarde of een tweede
#: geval dat in de uitkomst terechtkwam; de melding zegt dat (e2e-run 20 nov 2026: een kale 422 zei het niet).
MAX_TEKSTDEEL = 500


class Term(BaseModel):
    """Eén stuk van een uitkomst. `begrip` en `operator` verwijzen naar een begrip (een operatorbegrip ontstaat op een
    gemarkeerde formulering, #1766); `tekst` is vaste taal van het patroon of een tijdsaanduiding ("een maand na"),
    hoogstens `MAX_TEKSTDEEL` tekens."""
    model_config = ConfigDict(extra="ignore")

    soort: Literal["begrip", "operator", "tekst"]
    begrip_id: str = Field(default="", max_length=64)
    tekst: str = Field(default="", json_schema_extra={"maxLength": MAX_TEKSTDEEL},
                       description=f"Vaste taal van het taalpatroon, hoogstens {MAX_TEKSTDEEL} tekens.")

    @field_validator("tekst")
    @classmethod
    def _lengte(cls, v: str) -> str:
        if len(v) > MAX_TEKSTDEEL:
            raise ValueError(f"een tekstdeel van een uitkomst is hoogstens {MAX_TEKSTDEEL} tekens (dit deel heeft er "
                             f"{len(v)}): splits het in meer delen, of zet een voorwaarde bij de voorwaarden van het geval")
        return v

    @model_validator(mode="after")
    def _vorm(self) -> "Term":
        if self.soort in ("begrip", "operator") and not self.begrip_id:
            raise ValueError(f"een {self.soort} verwijst naar een begrip")
        if self.soort == "tekst" and not self.tekst.strip():
            raise ValueError("een tekst is niet leeg")
        return self


class GevalVerwijzing(BaseModel):
    """Een voorwaarde over welk geval van een andere regel geldt ("het aantal termijnen is bepaald volgens geval lid 5
    van de regel aantal termijnen"). Als verwijzing, niet als tekst: zo sluit de keten ook op het niveau van een geval,
    en ziet de toets dat de uitvoer van die regel dan invoer van deze is."""
    model_config = ConfigDict(extra="forbid")

    regel_id: str = Field(pattern=_ID)
    geval: str = Field(default="", max_length=80)        # leeg: de regel als geheel (bij één geval)


class Voorwaarde(BaseModel):
    """Een blad: de omschrijving "indien …" in eigen woorden, met de markeringen waarop ze rust, en zo nodig het geval
    van een andere regel waarover ze gaat (`geval_van`)."""
    model_config = ConfigDict(extra="ignore")

    tekst: str = Field(min_length=1, max_length=1000)
    element_ids: list[str] = Field(default_factory=list, max_length=20)
    niet: bool = False
    geval_van: GevalVerwijzing | None = None


class Voorwaarden(BaseModel):
    """Een groep: alle delen moeten gelden, of ten minste één. Genest tot elke diepte (M02 §3.5.5)."""
    model_config = ConfigDict(extra="ignore")

    verband: Literal["alle", "een_van"] = "alle"
    delen: list[Union["Voorwaarden", Voorwaarde]] = Field(min_length=1, max_length=40)


class Geval(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(default="", max_length=80)
    voorwaarden: Voorwaarden | None = None
    uitkomst: list[Term] = Field(min_length=1, max_length=40)
    voorrang: int = Field(default=0, ge=0, le=100)      # hoger gaat voor bij overlap (R7: rij 2 gaat voor)


class Invoer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    begrip_id: str = Field(pattern=_ID)
    rol: Literal["invoer", "parameter"] = "invoer"


class VoorbeeldWaarde(BaseModel):
    """De waarde van één invoerbegrip in een voorbeeld ("dagtekening van het aanslagbiljet: 10-05-2026")."""
    model_config = ConfigDict(extra="forbid")

    begrip_id: str = Field(pattern=_ID)
    waarde: str = Field(min_length=1, max_length=200)


class RegelVoorbeeld(BaseModel):
    """Een voorbeeld met invoer en uitkomst (methode 8). Het oordeel, wie het voorbeeld maakte en wie het beoordeelde,
    zet de server (`regel_store.voorbeelden_na`): een nieuw of gewijzigd voorbeeld is altijd `open`, en een oordeel komt
    alleen via `…/voorbeelden/{nr}/oordeel` (B4: maken en beoordelen zijn twee handelingen)."""
    model_config = ConfigDict(extra="ignore")

    geval: str = Field(default="", max_length=80)         # het label; leeg bij een regel met één geval
    invoer: str = Field(min_length=1, max_length=2000)
    uitkomst: str = Field(min_length=1, max_length=2000)
    oordeel: VoorbeeldOordeel = VoorbeeldOordeel.open
    toelichting: str = Field(default="", max_length=2000)
    door: str = Field(default="", max_length=64)
    beoordeeld_door: str = Field(default="", max_length=64)
    beoordeeld_op: str = Field(default="", max_length=40)
    # De grond van het oordeel ("nagerekend met lid 1"), bij het voorbeeld; zet de server, met `beoordeeld_door`.
    reden: str = Field(default="", max_length=2000)
    # Narekenbaar (regels herleidbaar, 20 nov 2026): de invoer per invoerbegrip, en welk geval van een regel eronder
    # geldt (bij een voorwaarde met `geval_van`). `geval` is het gekozen geval, `uitkomst` de verwachte uitkomst. De api
    # rekent niet: hij toetst of het voorbeeld bij het gekozen geval past (`regel_store.toets_voorbeeld`).
    waarden: list[VoorbeeldWaarde] = Field(default_factory=list, max_length=40)
    van_geval: list[GevalVerwijzing] = Field(default_factory=list, max_length=20)


class RegelInhoud(BaseModel):
    model_config = ConfigDict(extra="ignore")

    soort: RegelSoort
    regelbegrip_id: str = Field(pattern=_ID)
    uitvoer_begrip_id: str = Field(pattern=_ID)
    # Bij een beslisregel of specialisatie: over wie of wat de regel beslist ("Een natuurlijke persoon is …").
    onderwerp_begrip_id: str = Field(default="", max_length=64)
    invoer: list[Invoer] = Field(default_factory=list, max_length=40)
    gevallen: list[Geval] = Field(min_length=1, max_length=40)
    voorbeelden: list[RegelVoorbeeld] = Field(default_factory=list, max_length=100)
    toelichting: str = Field(default="", max_length=8000)
    brontype: Brontype = Brontype.wet
    # Het lidwoord van de uitvoer in het taalpatroon ("Het termijnbedrag moet …"): het begrip draagt het niet.
    lidwoord: Literal["de", "het", ""] = "de"
    # Wie de regel beheert (V4, plan lessen Termijnen-bibliotheek): een organisatieonderdeel. Optioneel.
    eigenaar: str = Field(default="", max_length=200)

    @field_validator("gevallen")
    @classmethod
    def _labels(cls, v: list[Geval]) -> list[Geval]:
        if len(v) > 1:
            labels = [g.label.strip() for g in v]
            if not all(labels):
                raise ValueError("bij meer gevallen heeft elk geval een label")
            if len(set(labels)) != len(labels):
                raise ValueError("de labels van de gevallen zijn uniek")
        return v

    @model_validator(mode="after")
    def _uitvoer_niet_invoer(self) -> "RegelInhoud":
        if any(i.begrip_id == self.uitvoer_begrip_id for i in self.invoer):
            raise ValueError("de uitvoer is geen invoer van dezelfde regel")
        return self


class DragerInvoer(BaseModel):
    element_id: str = Field(pattern=_ID)
    rol: DragerRol
    geval: str = Field(default="", max_length=80)


#: Wie een regel of open punt maakte: Lex, de import, of de discipline van de mens die het vastlegde (methode 10: de
#: multidisciplinaire review). `jurist` blijft de standaard; een regelspecialist heette anders ook "jurist". De kolom
#: is 16 tekens: een langere naam past er op Postgres niet in.
Herkomst = Literal["lex", "import", "jurist", "regelspecialist"]


class RegelAanmaak(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inhoud: RegelInhoud
    # De grondslag is verplicht: een regel zonder grondslag in de tekst bestaat niet (ADR-018 §2, #1760).
    dragers: list[DragerInvoer] = Field(min_length=1, max_length=60)
    herkomst: Herkomst = "jurist"


class Revisie(BaseModel):
    """De basis van elke schrijfroute op een regel. Een onbekend veld is een 422: een besluit dat stil niets doet,
    bestaat niet (B5)."""
    model_config = ConfigDict(extra="forbid")

    verwachte_revisie: int = Field(ge=1)


class RegelWijziging(Revisie):
    inhoud: RegelInhoud


class DragersToevoegen(Revisie):
    dragers: list[DragerInvoer] = Field(min_length=1, max_length=60)


class DragerWijziging(Revisie):
    beoordeling: Beoordeling
    # De grond van het oordeel ("letterlijk op de plek van het anker, getoetst aan de toestand van 1 okt 2026").
    motivering: str = Field(default="", max_length=2000)


class DragerVerversing(Revisie):
    """Een drager op de stand van nu zetten (de markering is gewijzigd, bijvoorbeeld verlengd): het bewijs wordt de
    markering van nu, en het oordeel wordt opnieuw gegeven. `akkoord` met een motivering als de beoordelaar de nieuwe
    stand gezien heeft; anders staat hij weer open."""
    beoordeling: Literal["open", "akkoord"] = "open"
    motivering: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _akkoord_met_grond(self) -> "DragerVerversing":
        # Een akkoord op de nieuwe stand zegt waarom (review regelstapel 20 nov 2026, bevinding 9).
        if self.beoordeling == "akkoord" and not self.motivering.strip():
            raise ValueError("een akkoord op de nieuwe stand vraagt een motivering: wat zag je aan de markering van nu")
        return self


class VoorbeeldBeoordeling(Revisie):
    """Het oordeel over één voorbeeld. `open` zet het oordeel terug."""
    oordeel: VoorbeeldOordeel
    toelichting: str | None = Field(default=None, max_length=2000)
    # De grond van het oordeel; `motivering` is hetzelfde veld, zoals bij accorderen.
    reden: str = Field(default="", max_length=2000, validation_alias=AliasChoices("reden", "motivering"))
    # Zet de reden achter de bestaande (met wie), in plaats van haar te vervangen, zoals `motivatie_aanvullen` bij een
    # begripskoppeling. Bij hetzelfde oordeel blijven `beoordeeld_door` en `beoordeeld_op` staan.
    reden_aanvullen: bool = False


#: De grond van een besluit over de hele regel (accorderen, afwijzen) heet `reden`, zoals bij een begrip. Wie
#: `motivering` stuurt (de naam bij een drager en een open punt), krijgt geen 422 meer: het is hetzelfde veld.
_REDEN = dict(default="", max_length=2000, validation_alias=AliasChoices("reden", "motivering"))


class Afwijzing(Revisie):
    reden: str = Field(**_REDEN)
    # De regel die deze vervangt (bijvoorbeeld drie regels samengevoegd tot één beslistabel): de status wordt dan
    # `vervangen`, met `vervangen_door`, en de opvolger draagt `opvolger_van` (A2).
    opvolger_id: str = Field(default="", max_length=64)


class Accordering(Revisie):
    reden: str = Field(**_REDEN)


class ParameterWaardeInvoer(BaseModel):
    parameter_begrip_id: str = Field(pattern=_ID)
    waarde_begrip_id: str = Field(default="", max_length=64)
    waarde: str = Field(min_length=1, max_length=200)
    eenheid: str = Field(default="", max_length=40)
    geldig_vanaf: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    geldig_tot: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    element_id: str = Field(default="", max_length=64)
    getoetst: str = Field(default="", max_length=500)
