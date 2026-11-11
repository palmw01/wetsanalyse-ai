"""De bronconnectors (ADR-013): één beschrijving per connector, de enige bron voor de hele keten.

Een bronconnector is code (getypeerde tools in graph-qa, `agent/tools/`), maar wát hij is, staat hier: naam en label,
het soort vindplaats, wat hij dekt, welke tools erbij horen, hoe je eruit citeert en waar hij in een antwoord voor
staat. Daaruit leiden de api (het register, de toegestane namen) en graph-qa (toollaag, specialisten, routering,
scope, prompt en verificatie) alles af. Een nieuwe connector is dus: een beschrijving hier, zijn tools in graph-qa en
een straatvlag (`CONNECTOR_<NAAM>`). De poorttest `tests/poort/test_connectorbeschrijving.py` maakt een onvolledige
beschrijving rood.

Wetgeving (de BWB-graaf) is geen connector: die staat altijd aan.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extern import externe_verwijzingen, externe_verwijzingen_met_plek, externe_vindplaats


def _opsomming(delen: tuple[str, ...]) -> str:
    return delen[0] if len(delen) == 1 else ", ".join(delen[:-1]) + " en " + delen[-1]


def bronnen_tekst(labels: list[str] | tuple[str, ...]) -> str:
    """Waar Lex zoekt, voor de algemene stappen in het denkproces: "de kennisgraaf" zonder connector, anders "de
    wetgeving en Kamerstukken"."""
    return "de kennisgraaf" if not labels else "de wetgeving en " + _opsomming(tuple(labels))


#: De metadata van een stuk, in vaste sleutels voor elke connector, met hun type. Een connector levert een deel ervan;
#: welk deel, en waar het bij de dienst vandaan komt, staat in zijn beschrijving (`metadata`). Zo vult dezelfde code de
#: lijst in een antwoord, de kop van een gelezen stuk en de werkplek, welke connector het ook is: een feit als de datum
#: komt uit de dienst, niet uit de tekst van het model.
METADATA_SLEUTELS: dict[str, str] = {
    "datum": "datum",          # de datum van het stuk zelf
    "gepubliceerd": "datum",   # wanneer de dienst het publiceerde
    "gewijzigd": "datum",      # wanneer de dienst de publicatie het laatst bijwerkte
    "ondertekend": "datum",    # wanneer het besluit is ondertekend
    "inwerking": "datum",      # wanneer de tekst waar het stuk bij hoort in werking trad
    "tekst_vanaf": "datum",    # sinds wanneer de tekst van de bepaling gold waaraan het stuk gekoppeld is
    "tekst_tot": "datum",      # tot wanneer die tekst gold; leeg: hij geldt nog, of het is onbekend
    "tekststand": "tekst",     # die tekst tegenover de tekst in de graaf: huidige tekst, eerdere tekst of onbekend
    "op_peildatum": "waarheid",  # of die tekst gold op de peildatum van de vraag of het werkgebied
    "publicatie": "tekst",     # waarin het stuk verscheen (Staatsblad, Staatscourant)
    "titel": "tekst",          # de titel van het stuk zelf
    "soort": "tekst",          # het soort stuk ("Memorie van toelichting", "Motie", "Uitspraak")
    "reeks": "lijst",          # waar het stuk bij hoort (een dossier, een zaak); de eerste is de hoofdreeks
    "reekstitel": "tekst",     # de titel van de hoofdreeks
    "nummer": "tekst",         # het nummer binnen de reeks
    "jaar": "tekst",           # het (vergader)jaar
    "orgaan": "tekst",         # wie het stuk uitbracht (een Kamer, een gerecht)
    "indieners": "lijst",      # wie het stuk indiende of ondertekende
    "status": "tekst",         # de stand van de publicatie (onopgemaakt, opgemaakt)
    "versie": "tekst",         # herdruk, rectificatie
    "procedure": "tekst",      # de procedure waarin het stuk tot stand kwam (cassatie, hoger beroep)
    "rechtsgebied": "tekst",   # het rechtsgebied of de rechtsgebieden ("Bestuursrecht; Belastingrecht")
    "wetsverwijzing": "tekst", # de bepaling die het stuk noemt ("artikel 36 van de Invorderingswet 1990")
    "samenvatting": "tekst",   # een korte samenvatting van de bron zelf (de inhoudsindicatie), geen tekst van Lex
    "leesbaar": "waarheid",    # of de leestool de tekst kan lezen
    "in_graaf": "waarheid",    # of de bron (een regeling) ook in de kennisgraaf staat; dan leest Lex haar daar
}


#: Hoe een zoektool kan ordenen: op relevantie (de rangschikking van de dienst, bij woorden), op de standaarddatum
#: (`nieuwste`, `oudste`) of op het nummer binnen de reeks.
VOLGORDES = ("relevantie", "nieuwste", "oudste", "nummer")


@dataclass(frozen=True)
class MetadataVeld:
    """Eén metadataveld dat een connector per stuk levert."""
    #: Een sleutel uit `METADATA_SLEUTELS`.
    sleutel: str
    #: In de woorden van de jurist ("documentdatum", "dossier").
    label: str
    #: Waar het bij de dienst vandaan komt (de index of het element), voor wie de connector onderhoudt.
    bron: str
    #: Wat het veld betekent, in één zin; ook wat het níet is, als dat verwarring voorkomt.
    betekenis: str
    #: De argumenten van de zoektool die op dit veld filteren (een datum heeft er twee: vanaf en tot); leeg als het niet kan.
    filters: tuple[str, ...] = ()
    #: Of Lex de stukken op dit veld kan ordenen (bij de dienst of in de tool).
    sorteerbaar: bool = False
    #: De waarden die een jurist in een lijstvraag noemt, met een patroon: "in het belastingrecht" → het filter van dit veld
    #: krijgt "belastingrecht" (`agent/bron_lijst.py`). Leeg: de lijstvraag leest dit veld niet.
    waarden: tuple[tuple[str, str], ...] = ()

    @property
    def type(self) -> str:
        return METADATA_SLEUTELS.get(self.sleutel, "")


@dataclass(frozen=True)
class ConnectorBeschrijving:
    #: De sleutel: in het register, in `ChatRequest.bronnen`, in `Settings.connector_<naam>`.
    naam: str
    #: Leesbaar, voor het menu en de meldingen ("Kamerstukken").
    label: str
    #: Het soort vindplaats (`extern.BRONTYPEN`, nooit `wettekst`: dat is de kennisgraaf; live gelezen wet is `wettekst_live`).
    brontype: str
    #: De kop in de bronnenlijst van de werkplek ("Parlementaire stukken").
    groep: str
    #: Wat de bron dekt, in één zin voor de router en de scope ("wetsgeschiedenis: …").
    dekt: str
    #: Patronen (hoofdletterongevoelig) waaraan een vraag naar deze bron herkenbaar is.
    signalen: tuple[str, ...]
    #: De tools van de connector in graph-qa.
    tools: frozenset[str]
    #: De tool waarvan het resultaat de citeerbare tekst draagt; een zoekresultaat draagt alleen titels. Het contract van
    #: een leestool: het resultaat draagt `stuk: {id, label, link, bron_hash, gewijzigd?}` en per rij `{nr, tekst, kop?}`
    #: (genummerde passages in documentvolgorde), zodat het blok `extern` (ADR-008) voor elke connector met dezelfde code
    #: wordt gevuld. `bron_hash` is de hash van het gelezen document: de passages van één blok komen uit één lezing.
    #: Een rij mag `soort` dragen (`alinea`, `voetnoot`, `tabel`, `tabelrij`); een `tabel` draagt `openen` naar deze
    #: leestool (de tabel zelf, met de kolommen als `cellen` op de kop), een `tabelrij` haar `cellen`.
    leestool: str
    #: Het argument van de leestool dat het id draagt: een vraag die een id noemt, leest de code direct
    #: (`nodes/bron_lezen.py`), zonder dat het model eerst gaat zoeken.
    lees_argument: str
    #: De vorm van het id dat het antwoord noemt (`extern.externe_vindplaats` leest het).
    id_prefixen: tuple[str, ...]
    #: De rollen (specialisten) die de tools krijgen, als de connector aanstaat.
    specialisten: frozenset[str]
    #: Waar de bron in een antwoord voor staat, en waarvoor niet.
    rol_in_antwoord: str
    #: De kop boven het blok `extern` in een antwoord ("Uit de parlementaire geschiedenis").
    kop_in_antwoord: str
    #: Wat de connector niet kan bij het zoeken: de jurist moet het weten voor hij op een stilte vertrouwt.
    grenzen: str
    #: Wat de leestool levert, als rijsoorten in de woorden van de jurist (`alinea` → "alinea's"); en wat er niet in de
    #: opgehaalde tekst staat. Daaruit komt `capaciteit`, zodat Lex niet zegt dat iets ontbreekt wat de tool wel geeft
    #: (bundel 22: tabellen en voetnoten kwamen erbij, de vaste tekst bleef "staan er niet in"). Een test toetst het
    #: tegen wat de leestool echt teruggeeft.
    levert: tuple[str, ...]
    niet_in_tekst: tuple[str, ...]
    #: Per tool wat Lex doet, in de woorden van de jurist, voor het denkproces (`narratie._toolregel`). Per tool een of
    #: meer vormen met `{argument}`; de eerste waarvan alle argumenten in de aanroep staan, telt. Een tool zonder
    #: werkwoord heette "raadpleegt de kennisgraaf", ook als Lex een Kamerstuk las (acceptatie 8 nov 2026).
    werkwoorden: dict[str, tuple[str, ...]]
    #: De beschrijving in de beheertab.
    beheer: str
    #: Vragen die binnen scope vallen en deze bron raken; routering, tests en de meting gebruiken ze.
    voorbeeldvragen: tuple[str, ...]
    #: Een echt id van een stuk, als voorbeeld in de sjabloonvelden (`sjablonen/extern.py`) en de meldingen: zo noemt een
    #: schema de ids van de connectors die aanstaan, niet een vaste vorm.
    voorbeeld_id: str = ""
    #: Wat de connector per stuk aan metadata levert (`MetadataVeld`, sleutels uit `METADATA_SLEUTELS`). Leeg mag alleen
    #: voor een nep in een test; de poorttest eist het voor elke echte connector.
    metadata: tuple[MetadataVeld, ...] = ()
    #: De datum waar "nieuwste" en "oudste" op ordenen: een sleutel van het type `datum` uit `metadata`.
    standaard_datum: str = ""
    #: De volgordes die de zoektool kent (uit `VOLGORDES`); het argument `volgorde` van de zoektool is precies deze enum.
    volgordes: tuple[str, ...] = ()
    #: Hoe een jurist een stuk noemt zonder id ("Kamerstuk 32140, nr. 342"): per vorm een patroon met benoemde groepen
    #: en het id dat eruit volgt ("kst-{dossier}-{nummer}"). De leestool lost dat id op bij de bron, ook als het stuk
    #: daar een ander id draagt (een herdruk, een onopgemaakt stuk). Zo leest de code een genoemd stuk direct, net als
    #: een id (gesprek e906567a: "Kamerstuk 32140, nr. 342" ging langs het model en heette onbereikbaar).
    citeervormen: tuple[tuple[str, str], ...] = ()
    #: De soorten stukken in de woorden van de jurist, met een patroon dat ook het meervoud vindt; voor de vaste route
    #: van een lijstvraag ("de laatste vijf moties"). De waarde gaat als filter `soort` naar de zoektool.
    soorten: tuple[tuple[str, str], ...] = ()
    #: Wie een stuk uitbrengt, zoals de zoektool het filter `orgaan` kent ("Eerste Kamer").
    organen: tuple[str, ...] = ()
    #: Kort, in de woorden van de jurist: waarom een stuk geen tekst heeft om te lezen (`leesbaar: false`). Het staat
    #: naast het stuk in een lijst en in het blok; zonder eigen tekst de algemene. Een uitspraak zonder tekst heette
    #: "onopgemaakt, alleen PDF", de vorm van Kamerstukken (vierde meting Rechtspraak, 10 nov 2026).
    zonder_tekst: str = "geen tekst bij de bron"
    #: Hoe de jurist de stukken van deze bron als geheel noemt ("kamerstukken", "jurisprudentie"): in een lijstvraag
    #: zoeken ze niets, en na "de laatste" zijn ze een meervoud (geen aantal 1). Kleine letters.
    verzamelnamen: tuple[str, ...] = ()
    #: Andere woorden die in een lijstvraag naar deze bron staan zonder iets te zoeken ("dossier" bij Kamerstukken).
    vulwoorden: tuple[str, ...] = ()
    _patronen: tuple[re.Pattern[str], ...] = field(init=False, repr=False, compare=False)
    _citeer: tuple[tuple[re.Pattern[str], str], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_patronen", tuple(re.compile(s, re.IGNORECASE) for s in self.signalen))
        object.__setattr__(self, "_citeer", tuple((re.compile(p, re.IGNORECASE), v) for p, v in self.citeervormen))

    def geciteerd(self, tekst: str) -> list[tuple[int, str]]:
        """(plek, id) van elk stuk dat de tekst in een citeervorm noemt, zonder id ("Kamerstuk 32140, nr. 342"). Een
        groep wordt hoofdletters zonder spaties ("36200 ix" → "36200-IX"); een id dat geen vindplaats is, telt niet."""
        uit: list[tuple[int, str]] = []
        for patroon, vorm in self._citeer:
            for m in patroon.finditer(tekst or ""):
                delen = {k: re.sub(r"\s+", "-", v.strip()).upper() for k, v in m.groupdict().items() if v}
                try:
                    ident = vorm.format(**delen)
                except KeyError:
                    continue
                vp = externe_vindplaats(ident)
                if vp is not None and vp.brontype == self.brontype and vp.id.startswith(self.id_prefixen):
                    uit.append((m.start(), vp.id))
        return uit

    @property
    def capaciteit(self) -> str:
        """"levert alinea's, voetnoten en tabellen; illustraties staan niet in de opgehaalde tekst"."""
        zin = f"de tekst komt per stuk met {_opsomming(self.levert)}"
        return zin + (f"; {_opsomming(self.niet_in_tekst)} staan niet in de opgehaalde tekst" if self.niet_in_tekst else "")

    def werkwoord(self, tool: str, invoer: dict) -> str | None:
        """Wat Lex doet met deze aanroep, of None als de tool niet van deze connector is."""
        vormen = self.werkwoorden.get(tool)
        if not vormen:
            return None
        waarden = {k: str(v).strip() for k, v in (invoer or {}).items() if str(v).strip()}
        for vorm in vormen:
            nodig = re.findall(r"\{(\w+)\}", vorm)
            if all(n in waarden for n in nodig):
                return vorm.format(**{n: waarden[n][:60] for n in nodig})
        return re.sub(r"\s*\{\w+\}", "", vormen[-1]).strip()

    def veld(self, sleutel: str) -> MetadataVeld | None:
        """Het metadataveld met deze sleutel, of None als de connector het niet levert."""
        return next((v for v in self.metadata if v.sleutel == sleutel), None)

    @property
    def filters(self) -> dict[str, MetadataVeld]:
        """Per argument van de zoektool het metadataveld waarop het filtert."""
        return {arg: v for v in self.metadata for arg in v.filters}

    @property
    def env(self) -> str:
        """De straatvlag die de connector aanbiedt."""
        return f"CONNECTOR_{self.naam.upper()}"

    def herkent(self, tekst: str) -> bool:
        """Gaat deze tekst (ook) over deze bron? Een signaalwoord, of een id van zijn soort."""
        if any(p.search(tekst or "") for p in self._patronen):
            return True
        return any(e.brontype == self.brontype and e.id.startswith(self.id_prefixen)
                   for e in externe_verwijzingen(tekst or ""))


KAMERSTUKKEN = ConnectorBeschrijving(
    naam="kamerstukken",
    label="Kamerstukken",
    brontype="kamerstuk",
    groep="Parlementaire stukken",
    dekt=("wetsgeschiedenis uit de officiële publicaties: het voorstel van wet, de memorie van toelichting, nota's, "
          "verslagen, het advies van de Raad van State en het nader rapport"),
    signalen=(r"\bkamerstuk", r"\bmemorie\s+van\s+toelichting\b", r"\bmvt\b", r"\bwetsgeschiedenis\b",
              r"\bparlementaire\s+(?:stukken|geschiedenis|behandeling)\b", r"\bnota\s+naar\s+aanleiding\b",
              r"\bnader\s+rapport\b", r"\badvies\s+van\s+de\s+raad\s+van\s+state\b",
              r"\bbedoel(?:de|ing\s+van)\s+de\s+wetgever\b"),
    tools=frozenset({"zoek_kamerstukken", "get_kamerstuk"}),
    leestool="get_kamerstuk",
    lees_argument="id",
    id_prefixen=("kst-",),
    voorbeeld_id="kst-33755-3",
    specialisten=frozenset({"definitie", "duiding", "algemeen"}),
    rol_in_antwoord=("een Kamerstuk laat zien wat de wetgever bedoelde; het onderbouwt nooit wat de wet zegt – dat "
                     "doet alleen de opgehaalde bepaling"),
    kop_in_antwoord="Uit de parlementaire geschiedenis",
    zonder_tekst="onopgemaakt, alleen PDF",
    grenzen=("zoeken gaat op dossier en nummer, woorden uit de titel of de hele tekst, soort, documentdatum, "
             "vergaderjaar en Kamer, en ordent op nummer, op datum of op relevantie. Een stuk dat alleen als PDF bestaat "
             "(nog onopgemaakt) wordt gevonden, maar de tekst is niet te lezen; zoeken in de tekst gaat op de index van "
             "KOOP, niet op wat Lex las. De zoekdienst heeft Kamerstukken vanaf het vergaderjaar 1994-1995; oudere "
             "parlementaire geschiedenis staat er niet in"),
    levert=("alinea's", "voetnoten", "tabellen (op te halen met hun rijen)"),
    niet_in_tekst=("illustraties",),
    werkwoorden={
        "zoek_kamerstukken": ("zoekt de Kamerstukken van dossier {dossier}", "zoekt Kamerstukken over „{woorden}”",
                              "zoekt in de tekst van Kamerstukken naar „{tekst}”", "zoekt Kamerstukken"),
        "get_kamerstuk": ("leest tabel {tabel} van Kamerstuk {id}", "zoekt in Kamerstuk {id} naar „{woorden}”",
                          "leest Kamerstuk {id}", "leest een Kamerstuk"),
    },
    beheer=("Wetsgeschiedenis uit de officiële publicaties: memorie van toelichting, nota's, verslagen en het advies "
            "van de Raad van State. Openbaar, zonder sleutel."),
    voorbeeldvragen=(
        "Wat kun je vinden in de Kamerstukken?",
        "Wat staat er in de memorie van toelichting bij Kamerstuk 33755, nummer 3?",
        "Welke Kamerstukken horen bij de Invorderingswet 1990?",
        "Wat zegt kst-33755-3 over de bestuurdersaansprakelijkheid?",
        "Wat bedoelde de wetgever met artikel 36 van de Invorderingswet 1990?",
    ),
    # Uit de SRU-records van KOOP (handleiding SRU 2.0 v1.4, p. 16–23), live getoetst op 9 nov 2026. `w.ondertekening`
    # en `w.datumBrief` bestaan als index, maar stonden in geen enkel Kamerstukrecord: die bieden we niet aan.
    metadata=(
        MetadataVeld("datum", "documentdatum", "dt.date",
                     "de datum van het stuk zelf; daarop ordenen 'nieuwste' en 'oudste'", filters=("vanaf", "tot"),
                     sorteerbaar=True),
        MetadataVeld("gepubliceerd", "gepubliceerd", "dt.available",
                     "wanneer KOOP het stuk publiceerde; dat kan weken na de documentdatum zijn", sorteerbaar=True),
        MetadataVeld("gewijzigd", "gewijzigd", "dt.modified",
                     "wanneer KOOP de publicatie het laatst bijwerkte, niet wanneer het stuk zelf veranderde"),
        MetadataVeld("titel", "titel", "w.documenttitel", "de titel van het stuk, zonder de dossiertitel; 'woorden' "
                     "zoekt in de hele titel (dt.title), met de dossiertitel", filters=("woorden",)),
        MetadataVeld("soort", "soort stuk", "w.subrubriek",
                     "het soort Kamerstuk, zoals 'Memorie van toelichting', 'Motie' of 'Brief regering'; bij oudere "
                     "stukken staat er 'Overig', en dan komt het soort uit de titel; daarom zoekt 'soort' in allebei",
                     filters=("soort",)),
        MetadataVeld("reeks", "dossier", "w.dossiernummer",
                     "de dossiers waar het stuk bij hoort; het eerste is het hoofddossier", filters=("dossier",)),
        MetadataVeld("reekstitel", "dossiertitel", "w.dossiertitel", "de titel van het hoofddossier"),
        MetadataVeld("nummer", "nummer", "w.ondernummer",
                     "het nummer binnen het dossier; letters zijn stukken van de Eerste Kamer", filters=("nummer",),
                     sorteerbaar=True),
        MetadataVeld("jaar", "vergaderjaar", "w.vergaderjaar", "het vergaderjaar, zoals '2025-2026'",
                     filters=("vergaderjaar",)),
        MetadataVeld("orgaan", "Kamer", "dt.creator", "de Tweede of de Eerste Kamer der Staten-Generaal",
                     filters=("kamer",)),
        MetadataVeld("indieners", "indieners", "w.indiener", "wie het stuk indiende, bij een motie of amendement"),
        MetadataVeld("status", "documentstatus", "w.documentstatus",
                     "Onopgemaakt, Opgemaakt of Opgemaakt na onopgemaakt; een onopgemaakt stuk wordt later vervangen "
                     "door de opgemaakte versie, onder een ander id"),
        MetadataVeld("versie", "versie", "w.versieinformatie, w.versienummer",
                     "herdruk, rectificatie of herplaatsing; een herdruk heeft een eigen id (kst-…-n1)"),
        MetadataVeld("leesbaar", "leesbaar", "itemUrl manifestation=xml",
                     "of de tekst te lezen is; een onopgemaakt stuk heeft vaak alleen een PDF"),
    ),
    standaard_datum="datum",
    volgordes=VOLGORDES,
    # "Kamerstuk 32140, nr. 342", "Kamerstukken II 2013/14, 33754, nr. 7", "kamerstuk 36200 IX nummer 2".
    citeervormen=((r"\bkamerstuk(?:ken)?\s+(?:I{1,2}\s+)?(?:\d{4}\s*/\s*\d{2,4},?\s+)?"
                   r"(?P<dossier>\d{4,6}(?:[- ](?:[IVXLC]{1,6}|[A-Z]|\d{1,2})\b)?),?\s*(?:nr\.?|nummer)\s*"
                   r"(?P<nummer>[0-9A-Z]{1,6})\b", "kst-{dossier}-{nummer}"),),
    soorten=(
        ("memorie van toelichting", r"\bmemorie(?:s)?\s+van\s+toelichting\b|\bmvt'?s?\b"),
        ("voorstel van wet", r"\b(?:wets)?voorstel(?:len)?\s+van\s+wet\b|\bwetsvoorstel(?:len)?\b"),
        ("nota van wijziging", r"\bnota'?s\s+van\s+wijziging\b|\bnota\s+van\s+wijziging\b"),
        ("nota naar aanleiding van het verslag", r"\bnota'?s?\s+naar\s+aanleiding\s+van\s+het\s+verslag\b"),
        ("advies raad van state", r"\badvie(?:s|zen)\s+van\s+de\s+raad\s+van\s+state\b"),
        ("nader rapport", r"\bnader(?:e)?\s+rapport(?:en)?\b"),
        ("motie", r"\bmotie(?:s)?\b"),
        ("amendement", r"\bamendement(?:en)?\b"),
        ("verslag", r"\bverslag(?:en)?\b"),
        ("brief", r"\bbrie(?:f|ven)\b"),
    ),
    organen=("Tweede Kamer", "Eerste Kamer"),
    verzamelnamen=("kamerstukken",),
    vulwoorden=("kamerstuk", "parlementaire", "dossier", "dossiernummer", "kamerstukdossier"),
)

#: De instanties waarop `zoek_uitspraken` filtert, in de woorden van de jurist; uit de code in de ECLI.
INSTANTIES = ("Hoge Raad", "Parket bij de Hoge Raad", "Raad van State", "Centrale Raad van Beroep",
              "College van Beroep voor het bedrijfsleven", "gerechtshof", "rechtbank",
              "Europees Hof voor de Rechten van de Mens", "Hof van Justitie van de EU", "overig")
#: Het meervoud waarin een jurist een soort gerecht noemt ("de uitspraken van gerechtshoven"), naar die soort. De lijstroute
#: leest het als orgaan en de zoektool zet het om (meting 11 nov 2026, R06: "gerechtshoven" ging naar het model).
INSTANTIE_MEERVOUD = {"gerechtshoven": "gerechtshof", "hoven": "gerechtshof", "rechtbanken": "rechtbank"}

#: De rechtsgebieden uit de waardelijst van de Rechtspraak die een jurist in een lijstvraag noemt ("de nieuwste
#: uitspraken van de Hoge Raad in het belastingrecht"); de tool zoekt de URI in de waardelijst zelf.
_RECHTSGEBIEDEN = tuple((g, r"\b" + g.replace(" ", r"\s+") + r"\b") for g in (
    "belastingrecht", "bestuursrecht", "bestuursprocesrecht", "bestuursstrafrecht", "ambtenarenrecht", "omgevingsrecht",
    "socialezekerheidsrecht", "vreemdelingenrecht", "mededingingsrecht", "civiel recht", "arbeidsrecht",
    "insolventierecht", "ondernemingsrecht", "verbintenissenrecht", "goederenrecht", "aanbestedingsrecht", "strafrecht",
    "strafprocesrecht"))
#: De gerechten van nu bij naam, voor de lijstvraag ("de laatste uitspraken van Rechtbank Gelderland"); een naam gaat
#: vóór de soort gerecht die erin zit, want de lijstvraag neemt de eerste die past.
_GERECHTEN = ("Rechtbank Amsterdam", "Rechtbank Den Haag", "Rechtbank Gelderland", "Rechtbank Limburg",
              "Rechtbank Midden-Nederland", "Rechtbank Noord-Holland", "Rechtbank Noord-Nederland",
              "Rechtbank Oost-Brabant", "Rechtbank Overijssel", "Rechtbank Rotterdam", "Rechtbank Zeeland-West-Brabant",
              "Gerechtshof Amsterdam", "Gerechtshof Arnhem-Leeuwarden", "Gerechtshof Den Haag",
              "Gerechtshof 's-Hertogenbosch", "CRvB", "CBb")

#: Een gerecht in de woorden van de jurist, voor de signalen hierboven.
_GERECHT = (r"(?:rechter|rechtbank|(?:gerechts)?hof|hoge\s+raad|raad\s+van\s+state|centrale\s+raad(?:\s+van\s+beroep)?|"
            r"crvb|cbb|college\s+van\s+beroep(?:\s+voor\s+het\s+bedrijfsleven)?|gerecht)\b")

RECHTSPRAAK = ConnectorBeschrijving(
    naam="rechtspraak",
    label="Rechtspraak",
    brontype="uitspraak",
    groep="Uitspraken",
    dekt=("uitspraken en conclusies die een wetsartikel noemen (de koppelingen van Linked Data Overheid), de uitspraken "
          "van een gerecht of rechtsgebied in een periode (de zoekfeed van de Rechtspraak), en de tekst van een "
          "Nederlandse uitspraak uit de open data van de Rechtspraak"),
    # Niet het kale "uitspraak" of "rechter": "uitspraak op bezwaar", "de inspecteur doet uitspraak" en "beroep bij de
    # rechter" zijn gewone wetstaal, en op een straat zonder deze connector nam de melding "staat uit" ze dan over.
    # Een uitspraak telt als ze van een gerecht is, of als rechterlijke uitspraak; een gerecht als het iets oordeelde.
    signalen=(r"\b(?:rechterlijke|gerechtelijke)\s+uitspra(?:ak|ken)\b",
              rf"\buitspra(?:ak|ken)\s+(?:van|door|bij)\s+(?:de\s+|het\s+)?{_GERECHT}",
              r"\buitspraken\b(?!\s+(?:op|in)\s+(?:het\s+|de\s+)?(?:bezwaar|beroep|administratief))",
              rf"\b{_GERECHT}[^.?!]{{0,40}}?\b(?:geoordeeld|oordeelt|oordeelde|gezegd|zegt|zei|beslist|overwogen|uitgemaakt)\b",
              r"\bjurisprudentie\b", r"\brechtspraak\b", r"\barrest(?:en)?\b", r"\bvonnis(?:sen)?\b",
              r"\bafdeling\s+bestuursrechtspraak\b",
              r"\bconclusie\s+(?:van\s+de\s+)?a(?:dvocaat)?[.-]?\s*g(?:eneraal)?\b", r"\becli\b"),
    tools=frozenset({"zoek_uitspraken", "get_uitspraak"}),
    leestool="get_uitspraak",
    lees_argument="id",
    id_prefixen=("ECLI:NL:",),
    voorbeeld_id="ECLI:NL:HR:2022:50",
    specialisten=frozenset({"definitie", "duiding", "algemeen"}),
    rol_in_antwoord=("een uitspraak laat zien hoe een rechter een bepaling toepaste of uitlegde; ze onderbouwt nooit "
                     "wat de wet zegt – dat doet alleen de opgehaalde bepaling. Een uitspraak die een artikel noemt, "
                     "gaat er niet altijd over. De uitspraken zijn gepseudonimiseerd: herleid nooit wie een partij is"),
    kop_in_antwoord="Uit de rechtspraak",
    zonder_tekst="geen tekst in de open data",
    grenzen=("zoeken gaat per wetsartikel of op gerecht, rechtsgebied, soort en periode, nooit op woorden in de tekst. "
             "Linked Data Overheid koppelt een uitspraak aan een "
             "artikel als de tekst het noemt (automatisch herkend of redactioneel), op artikelniveau en niet per lid. "
             "Een vermelding is geen uitleg; de lijst is 'ten minste deze', want LiDO loopt achter op de wetgeving en "
             "kan versies missen. LiDO hangt een uitspraak aan de tekst van het artikel die gold op de datum van de "
             "uitspraak; welke tekst de rechter toepaste (een eerder belastingjaar, overgangsrecht) staat pas in de "
             "uitspraak zelf. De divisies van een beleidsregel kent LiDO niet. Alleen Nederlandse uitspraken zijn "
             "te lezen, één tegelijk: de Rechtspraak vraagt hoogstens 10 verzoeken per seconde en geen volledige download"),
    levert=("alinea's (de inhoudsindicatie en de uitspraak of conclusie)",),
    niet_in_tekst=("vindplaatsen in tijdschriften",),
    werkwoorden={
        "zoek_uitspraken": ("zoekt uitspraken bij artikel {artikel} van {bwb_id}", "zoekt uitspraken bij {bwb_id}",
                            "zoekt uitspraken van {instantie}", "zoekt uitspraken in het {rechtsgebied}",
                            "zoekt uitspraken"),
        "get_uitspraak": ("leest uitspraak {id}", "leest een uitspraak"),
    },
    beheer=("Uitspraken die een wetsartikel noemen (Linked Data Overheid, KOOP) en de tekst van een Nederlandse "
            "uitspraak (open data van de Rechtspraak). Openbaar, zonder sleutel."),
    voorbeeldvragen=(
        "Welke uitspraken noemen artikel 36 van de Invorderingswet 1990?",
        "Is er jurisprudentie over artikel 25 van de Invorderingswet 1990?",
        "Wat heeft de Hoge Raad gezegd over de bestuurdersaansprakelijkheid in artikel 36 Iw?",
        "Wat staat er in ECLI:NL:HR:2022:50?",
        "Geef de 10 nieuwste uitspraken van de Hoge Raad in het belastingrecht",
    ),
    # De datum, het orgaan en het zaaknummer komen bij het zoeken uit de titel die LiDO van de Rechtspraak overneemt
    # ("ECLI:NL:HR:2022:50 - Hoge Raad, 21-01-2022 / 21/00733"), bij het lezen uit de metadata van de Rechtspraak zelf.
    # Live getoetst op 10 nov 2026 (docs/architectuur/metingen/lido-spike-2026-11-10).
    metadata=(
        MetadataVeld("datum", "datum uitspraak", "titel in LiDO; dcterms:date bij de Rechtspraak",
                     "de datum waarop de uitspraak is gedaan; daarop ordenen 'nieuwste' en 'oudste'",
                     filters=("vanaf", "tot"), sorteerbaar=True),
        MetadataVeld("gepubliceerd", "gepubliceerd", "dcterms:issued (Rechtspraak)",
                     "wanneer de Rechtspraak de uitspraak publiceerde; alleen bij het lezen"),
        MetadataVeld("gewijzigd", "gewijzigd", "dcterms:modified",
                     "wanneer de publicatie het laatst werd bijgewerkt, niet wanneer de uitspraak veranderde"),
        MetadataVeld("titel", "titel", "dcterms:title", "de titel zoals LiDO en de Rechtspraak die geven: ECLI, "
                     "instantie, datum en zaaknummer"),
        MetadataVeld("soort", "soort", "de code in de ECLI (PHR = conclusie); dcterms:type bij de Rechtspraak",
                     "'Uitspraak' of 'Conclusie' (van de advocaat-generaal bij de Hoge Raad)", filters=("soort",)),
        MetadataVeld("orgaan", "instantie", "titel in LiDO; dcterms:creator bij de Rechtspraak",
                     "het gerecht dat de uitspraak deed; het filter 'instantie' kiest een soort gerecht",
                     filters=("instantie",)),
        MetadataVeld("nummer", "zaaknummer", "titel in LiDO; psi:zaaknummer", "het zaaknummer bij het gerecht"),
        MetadataVeld("wetsverwijzing", "bepaling", "de koppeling in LiDO",
                     "de bepaling waarbij gezocht is; een uitspraak die haar noemt, gaat er niet altijd over",
                     filters=("bwb_id", "artikel")),
        MetadataVeld("tekst_vanaf", "tekst geldig vanaf", "de versie van het artikel in LiDO (de geldigheid in de id)",
                     "sinds wanneer de tekst van het artikel gold waaraan LiDO de uitspraak koppelde; LiDO koppelt naar "
                     "de datum van de uitspraak, niet naar de tekst die de rechter toepaste. Alleen bij een artikel"),
        MetadataVeld("tekst_tot", "tekst geldig tot", "de begindatum van de volgende versie in LiDO",
                     "tot wanneer die tekst gold; leeg als hij nog geldt. Alleen bij een artikel"),
        MetadataVeld("tekststand", "tekst", "de versie in LiDO tegenover bwb:inwerking van het artikel in de graaf",
                     "'huidige tekst' (de tekst in de graaf), 'eerdere tekst' (het artikel is daarna gewijzigd) of "
                     "'onbekend'; alleen bij een artikel", filters=("tekststand",)),
        MetadataVeld("op_peildatum", "op de peildatum", "de versie in LiDO tegenover de meegegeven peildatum",
                     "of die tekst gold op de peildatum; alleen met 'peildatum'", filters=("peildatum",)),
        MetadataVeld("procedure", "procedure", "psi:procedure (Rechtspraak)",
                     "de procedure, zoals 'Cassatie' of 'Hoger beroep'; alleen bij het lezen"),
        MetadataVeld("rechtsgebied", "rechtsgebied", "dcterms:subject (Rechtspraak)",
                     "het rechtsgebied of de rechtsgebieden van de uitspraak (waardelijst Rechtsgebieden); het filter "
                     "werkt alleen in de zoekfeed, zonder artikel", filters=("rechtsgebied",), waarden=_RECHTSGEBIEDEN),
        MetadataVeld("samenvatting", "samenvatting", "atom:summary (zoekfeed)",
                     "de ingekorte inhoudsindicatie van de Rechtspraak zelf; alleen bij zoeken zonder artikel"),
        MetadataVeld("leesbaar", "leesbaar", "de vorm van de ECLI",
                     "of de tekst te lezen is: alleen een Nederlandse ECLI staat bij de open data van de Rechtspraak"),
    ),
    standaard_datum="datum",
    volgordes=("nieuwste", "oudste"),
    # "ecli nl hr 2022 50", "ECLI: NL: HR: 2022: 50": een ECLI die niet in de vaste vorm staat.
    citeervormen=((r"\becli\s*[: ]\s*nl\s*[: ]\s*(?P<gerecht>[a-z]{2,7})\s*[: ]\s*(?P<jaar>\d{4})\s*[: ]\s*"
                   r"(?P<nummer>[0-9a-z.]{1,25})\b", "ECLI:NL:{gerecht}:{jaar}:{nummer}"),),
    soorten=(
        # "conclusies van de advocaat-generaal" is één soort: de rest is geen woord dat de lijstroute moet plaatsen
        # (meting 11 nov 2026, R05).
        ("conclusie", r"\bconclusie(?:s)?(?:\s+van\s+(?:de\s+)?a(?:dvocaat)?[.-]?\s*g(?:eneraal)?)?\b"),
        ("uitspraak", r"\buitspra(?:ak|ken)\b|\barrest(?:en)?\b"),
    ),
    organen=("Parket bij de Hoge Raad", *_GERECHTEN, *INSTANTIE_MEERVOUD,
             *(i for i in INSTANTIES if i != "Parket bij de Hoge Raad")),
    verzamelnamen=("jurisprudentie", "rechtspraak"),
    vulwoorden=("gerechten", "instanties", "rechters"),
)


#: De soorten bekendmaking die een jurist in een lijstvraag noemt, zoals `dt.type` ze kent (live, 10 nov 2026). "Wet"
#: alleen in het meervoud: "de wet" staat in bijna elke vraag, "wetten" wijst een soort aan ("hoeveel wetten van
#: Financiën staan er in het Staatsblad van 2024", iteratie bekendmakingen ronde 1, B20).
_BEKENDMAKINGSOORTEN = (
    # Geen `dt.type`: een inwerkingtredingsbesluit is een AMvB of KB met "inwerkingtreding" in de titel (5.466 in het
    # Staatsblad, live 10 nov 2026); de zoektool zoekt het in de titel.
    ("inwerkingtredingsbesluit", r"\binwerkingtredingsbesl(?:uit|uiten)\b"),
    ("amvb", r"\bamvb'?s?\b|\balgemene\s+maatregel(?:en)?\s+van\s+bestuur\b"),
    ("klein koninklijk besluit", r"\b(?:klein(?:e)?\s+)?koninklijk(?:e)?\s+besl(?:uit|uiten)\b"),
    ("ministeriële regeling", r"\bministeriële\s+regeling(?:en)?\b"),
    ("beleidsregel", r"\bbeleidsregel(?:s)?\b"),
    ("circulaire", r"\bcirculaire(?:s)?\b"),
    ("rijkswet", r"\brijkswet(?:ten)?\b"),
    ("wet", r"\bwetten\b"),
    ("verbeterblad", r"\bverbeterblad(?:en)?\b|\brectificatie(?:s)?\b"),
)

BEKENDMAKINGEN = ConnectorBeschrijving(
    naam="bekendmakingen",
    label="Staatsblad en Staatscourant",
    brontype="bekendmaking",
    groep="Staatsblad en Staatscourant",
    dekt=("de officiële bekendmakingen: wetten, AMvB's en koninklijke besluiten in het Staatsblad (ook wijzigingswetten "
          "en inwerkingtredingsbesluiten) en ministeriële regelingen, beleidsregels en besluiten in de Staatscourant (zoals "
          "de wijzigingen van de Leidraad Invordering); per bepaling de publicatie die haar huidige tekst gaf en het "
          "besluit waarmee die in werking trad"),
    # "publicaties" ook: "wat zijn de 10 meest recente publicaties?" (vraag van de gebruiker, 10 nov 2026).
    signalen=(r"\bstaatsblad(?:en)?\b", r"\bstaatscourant(?:en)?\b", r"\bpublicaties\b", r"\bstb\.", r"\bstcrt\.",
              r"\b(?:officiële\s+)?bekendmaking(?:en)?\b", r"\binwerkingtredingsbesluit(?:en)?\b",
              r"\bwijzigingsbesluit(?:en)?\b"),
    tools=frozenset({"zoek_bekendmakingen", "get_bekendmaking"}),
    leestool="get_bekendmaking",
    lees_argument="id",
    id_prefixen=("stb-", "stcrt-"),
    voorbeeld_id="stb-2010-176",
    specialisten=frozenset({"definitie", "duiding", "algemeen"}),
    rol_in_antwoord=("een bekendmaking laat zien wanneer en hoe een tekst is vastgesteld, gewijzigd of in werking trad; "
                     "wat de wet nu zegt, onderbouwt alleen de opgehaalde bepaling. Een wijzigingsbesluit geeft de "
                     "wijzigingsopdracht, niet de geldende tekst"),
    kop_in_antwoord="Uit de officiële bekendmakingen",
    zonder_tekst="alleen als PDF",
    grenzen=("zoeken gaat per bepaling (de publicaties die de BWB bij haar huidige tekst noemt: de laatste wijziging en "
             "het inwerkingtredingsbesluit, niet eerdere toestanden), op woorden in de titel of de hele tekst, soort, "
             "Staatsblad of Staatscourant, datum, jaargang, ministerie en Kamerdossier. Uit de Staatscourant alleen "
             "regelgeving, beleid en adviezen van de Raad van State; aankondigingen over personen (deurwaardersexploten, "
             "faillissementen, curatele) staan wel in de Staatscourant, maar worden niet gezocht of gelezen. Stukken van vóór ongeveer 1995 "
             "staan bij KOOP meestal alleen als PDF: ze worden gevonden, maar de tekst is niet te lezen. Een "
             "wijzigingsbesluit geeft de wijzigingsopdrachten, niet de geconsolideerde tekst"),
    levert=("alinea's (de aanhef, de artikelen en wijzigingsonderdelen, de toelichting)", "voetnoten",
            "tabellen (op te halen met hun rijen)"),
    niet_in_tekst=("illustraties", "ondertekeningen"),
    werkwoorden={
        "zoek_bekendmakingen": ("zoekt de bekendmakingen bij artikel {artikel} van {bwb_id}",
                                "zoekt de bekendmakingen bij {bwb_id}", "zoekt bekendmakingen over „{woorden}”",
                                "zoekt in de tekst van bekendmakingen naar „{tekst}”",
                                "zoekt de bekendmakingen van dossier {dossier}", "zoekt bekendmakingen"),
        "get_bekendmaking": ("leest wat {id} aan artikel {artikel} wijzigt", "leest tabel {tabel} van {id}",
                             "leest bekendmaking {id}", "leest een bekendmaking"),
    },
    beheer=("De officiële bekendmakingen van KOOP: het Staatsblad (wetten, AMvB's, inwerkingtredingsbesluiten) en de "
            "Staatscourant (ministeriële regelingen, beleidsregels). Openbaar, zonder sleutel."),
    voorbeeldvragen=(
        "Welke bekendmakingen horen bij artikel 36 van de Invorderingswet 1990?",
        "Wat staat er in Stb. 2010, 176?",
        "Welke wijzigingen van de Leidraad Invordering 2008 staan in de Staatscourant?",
        "Wat veranderde stcrt-2026-37344 aan artikel 1.1.5 van de Leidraad?",
        "Geef de 5 nieuwste beleidsregels in de Staatscourant",
    ),
    # Uit de SRU-records van KOOP, live getoetst op 10 nov 2026 (dezelfde dienst als Kamerstukken). De koppeling met een
    # bepaling komt uit de graaf: de importer schrijft per tekstdeel `bwb:bron` en `bwb:inwerkingtredingsbron`.
    metadata=(
        MetadataVeld("datum", "datum", "dt.date",
                     "de datum van de publicatie zelf (bij een Staatsblad de uitgifte); daarop ordenen 'nieuwste' en "
                     "'oudste'", filters=("vanaf", "tot"), sorteerbaar=True),
        MetadataVeld("gepubliceerd", "gepubliceerd", "dt.available", "wanneer KOOP het stuk beschikbaar stelde"),
        MetadataVeld("ondertekend", "ondertekend", "w.datumOndertekening",
                     "de datum waarop het besluit of de wet is ondertekend; niet de datum van inwerkingtreding"),
        MetadataVeld("gewijzigd", "gewijzigd", "dt.modified",
                     "wanneer KOOP de publicatie het laatst bijwerkte, niet wanneer het besluit veranderde"),
        MetadataVeld("titel", "titel", "dt.title", "de titel van het besluit of de wet", filters=("woorden",)),
        MetadataVeld("soort", "soort", "dt.type",
                     "het soort bekendmaking, zoals 'Wet', 'AMvB', 'Klein Koninklijk Besluit', 'beleidsregel' of 'ander "
                     "besluit van algemene strekking'; een 'Verbeterblad' herstelt een eerdere publicatie. Het soort "
                     "'inwerkingtredingsbesluit' zoekt de tool in de titel",
                     filters=("soort",)),
        MetadataVeld("publicatie", "publicatieblad", "w.publicatienaam", "het Staatsblad of de Staatscourant",
                     filters=("publicatie",),
                     waarden=(("Staatsblad", r"\bstaatsblad(?:en)?\b|\bstb\b"),
                              ("Staatscourant", r"\bstaatscourant(?:en)?\b|\bstcrt\b"))),
        MetadataVeld("jaar", "jaargang", "w.jaargang", "het jaar van het publicatieblad", filters=("jaar",)),
        MetadataVeld("nummer", "nummer", "w.publicatienummer", "het nummer in de jaargang"),
        MetadataVeld("orgaan", "ministerie", "dt.creator", "het ministerie of het orgaan dat het besluit nam",
                     filters=("orgaan",)),
        MetadataVeld("reeks", "Kamerdossier", "w.behandeldDossier",
                     "het Kamerdossier van de wet die het Staatsblad bekendmaakt; daar staat de wetsgeschiedenis",
                     filters=("dossier",)),
        MetadataVeld("wetsverwijzing", "regeling", "bwb:bron en bwb:inwerkingtredingsbron in de graaf",
                     "welke regeling de publicatie volgens de BWB wijzigt of in werking zet, en hoeveel bepalingen; bij "
                     "zoeken per bepaling: de laatste wijziging van haar huidige tekst of het besluit waarmee die in "
                     "werking trad. Alleen de toestand die Lex leest", filters=("bwb_id", "artikel")),
        MetadataVeld("inwerking", "in werking", "bwb:inwerking in de graaf",
                     "wanneer de huidige tekst van de bepaling in werking trad, volgens de BWB; alleen bij zoeken per "
                     "bepaling"),
        MetadataVeld("samenvatting", "samenvatting", "dcterms:abstract",
                     "de korte omschrijving die de publicatie zelf draagt; alleen bij een deel van de Staatscourant"),
        MetadataVeld("versie", "versie", "w.versieinformatie, w.versienummer",
                     "herdruk of herplaatsing; een herdruk heeft een eigen id"),
        MetadataVeld("leesbaar", "leesbaar", "itemUrl manifestation=xml",
                     "of de tekst te lezen is; een oud stuk heeft vaak alleen een PDF"),
    ),
    standaard_datum="datum",
    volgordes=("relevantie", "nieuwste", "oudste"),
    # "Stb. 2010, 176", "Stb.2009-610" (de vorm van de BWB), "Staatsblad 2010, nr. 176", "Stcrt. 2026, 37344".
    citeervormen=((r"\b(?:stb\.?|staatsblad)\s*(?P<jaar>(?:18|19|20)\d{2})\s*[,-]\s*(?:nr\.?|nummer)?\s*"
                   r"(?P<nummer>\d{1,6})\b", "stb-{jaar}-{nummer}"),
                  (r"\b(?:stcrt\.?|staatscourant)\s*(?P<jaar>(?:19|20)\d{2})\s*[,-]\s*(?:nr\.?|nummer)?\s*"
                   r"(?P<nummer>\d{1,6})\b", "stcrt-{jaar}-{nummer}")),
    soorten=_BEKENDMAKINGSOORTEN,
    # Zoals `dt.creator` ze noemt; de zoektool zoekt de woorden (`dt.creator all`), dus "Financiën" vindt ook het
    # Ministerie van Financiën.
    organen=("Ministerie van Financiën", "Ministerie van Justitie en Veiligheid",
             "Ministerie van Binnenlandse Zaken en Koninkrijksrelaties", "Ministerie van Sociale Zaken en Werkgelegenheid",
             "Ministerie van Volksgezondheid, Welzijn en Sport", "Ministerie van Infrastructuur en Waterstaat",
             "Ministerie van Economische Zaken", "Ministerie van Onderwijs, Cultuur en Wetenschap"),
    verzamelnamen=("bekendmakingen", "publicaties", "staatsbladen", "staatscouranten"),
    vulwoorden=("bekendmaking", "officiële", "staatsblad", "staatscourant", "publicatie", "publicatieblad"),
)

#: De soorten regelingen in de woorden van de jurist, zoals `dcterms.type` van de BWB ze noemt. Alleen vormen die geen
#: andere connector draagt: een lijstvraag over "ministeriële regelingen" in de Staatscourant blijft bij Bekendmakingen
#: (die staat eerder in `CONNECTORS`).
_REGELINGSOORTEN = (
    ("wet", r"\bformele\s+wet(?:ten)?\b"),
    ("AMvB", r"\balgemene\s+maatregel(?:en)?\s+van\s+bestuur\b"),
    ("ministeriele-regeling", r"\bministeri[eë]le\s+regeling(?:en)?\b"),
    ("beleidsregel", r"\bbeleidsregel(?:s)?\b"),
    ("circulaire", r"\bcirculaire(?:s)?\b"),
)

WETGEVING_LIVE = ConnectorBeschrijving(
    naam="wetgeving_live",
    label="Wetgeving buiten de kennisgraaf",
    brontype="wettekst_live",
    groep="Wetgeving buiten de kennisgraaf",
    dekt=("de wettekst van elke regeling in het Basiswettenbestand (wetten, AMvB's, ministeriële regelingen, "
          "beleidsregels) die niet in de kennisgraaf staat, en de eerdere of toekomstige tekst van een regeling die er wel "
          "in staat, live gelezen bij overheid.nl op een peildatum"),
    # Een regeling bij naam herkent de code, niet een signaal: elke wetsnaam zou er een zijn. De signalen zijn de woorden
    # waarmee een jurist deze bron zelf noemt.
    signalen=(r"\bwetten\.overheid\.nl\b", r"\bbasiswettenbestand\b", r"\bbwbt:",
              r"\b(?:eerdere|vorige|oude|toekomstige|historische)\s+(?:wets)?(?:tekst|versie|toestand)(?:en)?\b",
              r"\bwettekst\s+(?:van|op)\s+\d{1,2}\s+\w+\s+\d{4}\b", r"\bbuiten\s+de\s+(?:kennis)?graaf\b"),
    tools=frozenset({"zoek_regelingen", "zoek_artikelen", "get_wettekst"}),
    leestool="get_wettekst",
    lees_argument="id",
    id_prefixen=("bwbt:",),
    voorbeeld_id="bwbt:BWBR0015703:2026-07-01_0:artikel:31",
    specialisten=frozenset({"definitie", "duiding", "algemeen"}),
    rol_in_antwoord=("wat de wet zegt, letterlijk uit een toestand van het Basiswettenbestand die niet in de kennisgraaf "
                     "staat: een regeling die niet geïmporteerd is, of de tekst op een andere peildatum dan de graaf. Noem "
                     "altijd welke tekst het is (geldig van … tot …) en dat de bepaling niet in de kennisgraaf staat; "
                     "annoteren of opnemen in een werkgebied kan pas na een import"),
    kop_in_antwoord="Wettekst van overheid.nl (niet in de kennisgraaf)",
    zonder_tekst="niet volledig te lezen",
    grenzen=("leest één toestand van het Basiswettenbestand per keer, per artikel, lid, divisie of bijlage, met de opbouw "
             "en zoeken op woorden in de tekst van één regeling. De huidige tekst van een regeling die in de kennisgraaf "
             "staat, komt altijd uit de graaf, niet hieruit. Verwijzingen naar deze tekst, definities, annotaties, "
             "begrippen en semantisch zoeken kent deze bron niet: die bestaan alleen in de kennisgraaf. Een bepaling "
             "hieruit kan geen bron in een werkgebied worden en niet geannoteerd worden zonder import. Een toestand die "
             "niet volledig te lezen is (een structuur die de lezer niet kent), weigert de bron in plaats van een deel"),
    levert=("leden en onderdelen (met hun nummer en de koppen erboven)", "de status (vervallen, nog niet in werking)"),
    niet_in_tekst=("tabellen als rijen en kolommen", "illustraties", "redactionele opmerkingen"),
    werkwoorden={
        "zoek_regelingen": ("zoekt de regeling „{naam}” in het Basiswettenbestand",
                            "zoekt {bwb_id} in het Basiswettenbestand", "zoekt regelingen in het Basiswettenbestand"),
        "zoek_artikelen": ("zoekt „{woorden}” in de tekst van {bwb_id}", "zoekt de artikelen van {bwb_id}",
                           "zoekt de artikelen van een regeling"),
        "get_wettekst": ("leest artikel {artikel} van {bwb_id} bij overheid.nl", "leest {id} bij overheid.nl",
                         "leest wettekst bij overheid.nl"),
    },
    beheer=("De wettekst van het Basiswettenbestand, live bij overheid.nl (zoekdienst en repository van KOOP), met de "
            "lezer van de importer. Voor regelingen die niet in de kennisgraaf staan en voor eerdere teksten. Openbaar, "
            "zonder sleutel."),
    voorbeeldvragen=(
        "Wat zei de wettekst op 1 januari 2020 van artikel 9 van de Invorderingswet 1990?",
        "Zoek de Participatiewet in het basiswettenbestand",
        "Wat is de eerdere tekst van artikel 25 van de Invorderingswet 1990?",
        "Lees bwbt:BWBR0015703:2026-07-01_0:artikel:31",
    ),
    # Uit de SRU van de BWB (`x-connection=BWB`), live getoetst op 11 nov 2026: `dcterms.modified` sorteert met `sortBy`,
    # `overheid.authority` en `overheidbwb.rechtsgebied` filteren, `overheidbwb.citeertitel` bestaat niet als index.
    metadata=(
        MetadataVeld("datum", "geldig vanaf", "overheidbwb:geldigheidsperiode_startdatum; inwerking (artikel)",
                     "sinds wanneer de tekst geldt: bij een regeling de toestand, bij een artikel zijn inwerkingtreding; "
                     "niet de datum van de regeling zelf"),
        MetadataVeld("nummer", "BWB-id", "dcterms:identifier",
                     "het BWB-id van de regeling (BWBR…): daarmee lees je de opbouw en de artikelen"),
        MetadataVeld("reeks", "plek in de regeling", "de structuur van de toestand (hoofdstuk, afdeling, paragraaf)",
                     "de koppen boven een artikel, van boven naar beneden"),
        MetadataVeld("in_graaf", "in de kennisgraaf", "bwb:Regeling in de kennisgraaf",
                     "of de regeling ook in de kennisgraaf staat; dan lees je de huidige tekst daar (get_artikel)"),
        MetadataVeld("publicatie", "bron van het artikel", "@bron van het artikel in de toestand",
                     "de bekendmaking (Stb., Stcrt.) waarmee het artikel het laatst is ingevoegd of gewijzigd, zoals de "
                     "BWB haar noemt; niet het besluit over de inwerkingtreding"),
        MetadataVeld("gewijzigd", "laatst gewijzigd", "dcterms:modified",
                     "wanneer de BWB de regeling het laatst bijwerkte; daarop ordenen 'nieuwste' en 'oudste'",
                     sorteerbaar=True),
        MetadataVeld("tekst_vanaf", "tekst geldig vanaf", "overheidbwb:geldigheidsperiode_startdatum",
                     "het begin van de periode waarin de gelezen tekst geldt"),
        MetadataVeld("tekst_tot", "tekst geldig tot", "overheidbwb:geldigheidsperiode_einddatum",
                     "het einde van die periode; leeg als hij nog geldt"),
        MetadataVeld("tekststand", "tekststand", "de peildatum tegenover de toestand in de kennisgraaf",
                     "huidige tekst, eerdere tekst of toekomstige tekst; bij een regeling die niet in de graaf staat: de "
                     "tekst op de peildatum"),
        MetadataVeld("op_peildatum", "op de peildatum", "de gekozen toestand",
                     "of de gelezen tekst gold op de peildatum (de toestand is erop gekozen, dus altijd waar)",
                     # De peildatum kiest de toestand die dan gold; ze is geen begindatum ("vanaf 1 januari 1995" onder
                     # de lijst, meting ronde 2).
                     filters=("peildatum",)),
        MetadataVeld("inwerking", "in werking", "inwerking (artikel)",
                     "wanneer deze tekst van het artikel in werking trad; bij 'nog niet in werking' de datum waarop het "
                     "gaat gelden"),
        MetadataVeld("titel", "titel", "dcterms:title", "de citeertitel van de regeling", filters=("naam",)),
        MetadataVeld("soort", "soort", "dcterms:type",
                     "het soort regeling: wet, AMvB, ministeriele-regeling, beleidsregel, circulaire", filters=("soort",)),
        MetadataVeld("orgaan", "ministerie", "overheid:authority", "het verantwoordelijke ministerie",
                     filters=("orgaan",)),
        MetadataVeld("rechtsgebied", "rechtsgebied", "overheidbwb:rechtsgebied", "de rechtsgebieden volgens de BWB",
                     filters=("rechtsgebied",)),
        MetadataVeld("status", "status", "status (artikel)", "vervallen, nog niet in werking, of geldend"),
        MetadataVeld("versie", "toestand", "locatie_toestand",
                     "de toestand zoals het repository hem noemt (2026-07-01_0); een tweede op dezelfde datum (_1) is "
                     "een later zichtbare versie"),
        MetadataVeld("leesbaar", "leesbaar", "de bronmeting van de lezer",
                     "of de toestand volledig te lezen is (dezelfde dekkingsdrempel als de importer)"),
    ),
    standaard_datum="gewijzigd",
    volgordes=("relevantie", "nieuwste", "oudste"),
    # Met een BWB-id is een artikel te lezen zonder naam; een naam lost de code op (zoek_regelingen of de vooraf-stap).
    citeervormen=((r"\bartikel\s+(?P<artikel>[0-9]+[a-z]*(?:\.[0-9]+[a-z]*)*)\s+(?:van\s+)?(?P<bwb>BWB[RV]\d{7})\b",
                   "bwbt:{bwb}:artikel:{artikel}"),
                  (r"\b(?P<bwb>BWB[RV]\d{7})\s*,?\s*(?:art\.|artikel)\s*(?P<artikel>[0-9]+[a-z]*(?:\.[0-9]+[a-z]*)*)\b",
                   "bwbt:{bwb}:artikel:{artikel}")),
    soorten=_REGELINGSOORTEN,
    organen=("Financiën", "Justitie en Veiligheid", "Binnenlandse Zaken en Koninkrijksrelaties",
             "Sociale Zaken en Werkgelegenheid", "Volksgezondheid, Welzijn en Sport", "Infrastructuur en Waterstaat",
             "Economische Zaken", "Onderwijs, Cultuur en Wetenschap"),
    verzamelnamen=("basiswettenbestand",),
    vulwoorden=("regeling", "regelingen", "toestand", "toestanden"),
)

#: De bronconnectors, in de volgorde van het menu en de beheertab.
CONNECTORS: dict[str, ConnectorBeschrijving] = {
    c.naam: c for c in (KAMERSTUKKEN, BEKENDMAKINGEN, RECHTSPRAAK, WETGEVING_LIVE)}

#: De namen, als tuple voor een `Literal[NAMEN]` in de contracten.
NAMEN: tuple[str, ...] = tuple(CONNECTORS)

def herkende(tekst: str) -> tuple[str, ...]:
    """De connectors waar deze tekst (ook) over gaat, in de volgorde van `CONNECTORS`."""
    return tuple(n for n, c in CONNECTORS.items() if c.herkent(tekst))


def van_id(ident: str) -> ConnectorBeschrijving | None:
    """De connector die een extern id levert: zijn brontype en de vorm van zijn id. None als geen connector het levert
    (een ECLI zonder connector voor rechtspraak, of geen extern id)."""
    vp = externe_vindplaats(ident)
    if vp is None:
        return None
    return next((c for c in CONNECTORS.values() if c.brontype == vp.brontype and vp.id.startswith(c.id_prefixen)), None)


def leestools() -> frozenset[str]:
    """De tools waarvan het resultaat citeerbare tekst van een bron naast de wet draagt."""
    return frozenset(c.leestool for c in CONNECTORS.values())


def genoemde_stukken(tekst: str) -> list[tuple[ConnectorBeschrijving, str]]:
    """De stukken van een connector die de tekst noemt, in de volgorde van de tekst: bij id (`kst-35496-F`) of in een
    citeervorm van de connector ("Kamerstuk 32140, nr. 342" → `kst-32140-342`). Ontdubbeld op id."""
    gevonden: list[tuple[int, ConnectorBeschrijving, str]] = []
    for plek, e in externe_verwijzingen_met_plek(tekst or ""):
        if (c := van_id(e.id)) is not None:
            gevonden.append((plek, c, e.id))
    for c in CONNECTORS.values():
        gevonden += [(plek, c, ident) for plek, ident in c.geciteerd(tekst)]
    uit: list[tuple[ConnectorBeschrijving, str]] = []
    for _, c, ident in sorted(gevonden, key=lambda x: x[0]):
        if all(ident != i for _, i in uit):
            uit.append((c, ident))
    return uit
