"""
JAS-klassen-referentie – de dertien klassen van het Juridisch Analyseschema.

Per klasse een omschrijving, een herken-vraag (à la zinsontleding) en de uitdrukkingswijze in
wetgeving. Deze referentie voedt de annotatie-prompt (`agent/annotatie_prompt.py`).

HET BLOK HIERONDER IS GEGENEREERD, geen handwerk. Bron is de wetsanalyse-skill
(`.claude/skills/wetsanalyse/references/jas-klassen-referentie.md`), die op zijn beurt letterlijk
verwijst naar `docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md`. Bijwerken doe je in die markdown,
gevolgd door `scripts/genereer_jas_klassen.py`; `tests/test_methode_drift.py` faalt als dat
vergeten is.

Waarom die kant op en niet andersom: de duiding stond eerder op twee plekken en liep ongemerkt uit
elkaar — de skill was op zeven plekken armer dan zijn eigen bron. Nu is er één plek om te
bewerken, en die is leesbaar.

De klasse-*namen* zijn de canonieke JAS-namen (dezelfde weergave-volgorde als
`docs/wetsanalyse/wa-table.png`) en worden apart bewaakt tegen `api/app/jas_klassen.py` en
`frontend/lib/jas.ts`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JasKlasse:
    naam: str
    omschrijving: str
    vraag: str
    uitdrukkingswijze: str


# --- BEGIN GEGENEREERD uit de wetsanalyse-skill (scripts/genereer_jas_klassen.py) ---
# Niet met de hand bijwerken: bewerk
# .claude/skills/wetsanalyse/references/jas-klassen-referentie.md en draai
# scripts/genereer_jas_klassen.py. De volledige bronvelden staan daar, met
# regelverwijzingen naar docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md.
JAS_KLASSEN: tuple[JasKlasse, ...] = (
    JasKlasse(
        naam="Rechtssubject",
        omschrijving=(
            "Een rechtssubject is de drager van rechten en plichten. Het is een partij in een "
            "rechtsbetrekking."
        ),
        vraag=(
            "Wie heeft het recht? Wie heeft de plicht? Van wie is een rechtsobject? Bij wie hoort een waarde?"
        ),
        uitdrukkingswijze=(
            "Te herkennen aan een zelfstandig naamwoord waarmee een persoon of andere entiteit wordt "
            "beschreven, of aan een persoonlijk voornaamwoord zoals ‘hij’, ‘zij’ en soms ook ‘het’. Maar ook "
            "een onbepaald of betrekkelijk voornaamwoord kan wijzen op een rechtssubject, bijvoorbeeld "
            "‘iemand’, ‘een ieder’ of ‘degene’."
        ),
    ),
    JasKlasse(
        naam="Rechtsobject",
        omschrijving=(
            "Een rechtsobject is het voorwerp van een rechtsbetrekking en/of rechtsfeit. Een rechtsobject kan "
            "zowel een fysieke (bijvoorbeeld een personenauto of een huis) als een niet-fysieke "
            "verschijningsvorm (bijvoorbeeld medische zorg) hebben."
        ),
        vraag=(
            "Wat is het voorwerp van een recht of plicht? Waar is het rechtssubject eigenaar of houder van? "
            "Waar heeft een waarde betrekking op? Waarover is iets verschuldigd?"
        ),
        uitdrukkingswijze=(
            "Te herkennen aan een zelfstandig naamwoord waarmee het voorwerp van een recht of plicht wordt "
            "omschreven, bijvoorbeeld een studie, een woning of een dienstbetrekking. Ook een aanwijzend of "
            "betrekkelijk voornaamwoord kan wijzen op een rechtsobject, bijvoorbeeld ‘dat’, ‘hetgeen’ en "
            "‘welk(e)’."
        ),
    ),
    JasKlasse(
        naam="Rechtsbetrekking",
        omschrijving=(
            "Een rechtsbetrekking is een juridische relatie tussen twee rechtssubjecten en beschrijft een "
            "specifieke juridische toestand tussen deze rechtssubjecten. Een van deze rechtssubjecten heeft "
            "een plicht en de ander het bijbehorend recht. De algemene juridische toestand van een "
            "rechtssubject is de verzameling van alle specifieke rechtsbetrekkingen waarin dit rechtssubject "
            "als rechthebbende of plichthebbende partij optreedt."
        ),
        vraag=(
            "Hoe verhouden twee rechtssubjecten zich tot elkaar? Welke relatie(s) hebben twee rechtssubjecten "
            "met elkaar?"
        ),
        uitdrukkingswijze=(
            "Te herkennen aan een of meer werkwoorden, langs twee herkenningsroutes: hoofdwerkwoord met "
            "hulpwerkwoord — bij een recht: ‘kan verzoeken’, ‘mag wijzigen’; bij een plicht: ‘stelt vast’, "
            "‘mag niet inhalen’, ‘is verplicht informatie te verstrekken’, ‘moet informeren’, ‘dient te "
            "voldoen’. samengesteld werkwoord — bij een recht: ‘heeft recht op’, ‘heeft aanspraak op’; bij "
            "een plicht: ‘heeft de plicht om’, ‘draagt de last om’."
        ),
    ),
    JasKlasse(
        naam="Rechtsfeit",
        omschrijving=(
            "Een rechtsfeit is een handeling of gebeurtenis die, of tijdsverloop dat een wijziging in de "
            "juridische toestand teweegbrengt. Aan een rechtsfeit zijn dus rechtsgevolgen verbonden die een "
            "rechtsbetrekking creëren, wijzigen of beëindigen."
        ),
        vraag=(
            "Wat is de gebeurtenis of handeling die, of het tijdsverloop dat gevolgen heeft voor de "
            "rechtsbetrekking?"
        ),
        uitdrukkingswijze=(
            "Te herkennen aan een actieve werkwoordsvorm, al dan niet in combinatie met een zelfstandig "
            "naamwoord, zoals ‘indienen van een bezwaarschrift’, ‘toekennen van een subsidie’, ‘horen van "
            "belanghebbende’ of ‘kenbaar maken van elektronische bereikbaarheid’."
        ),
    ),
    JasKlasse(
        naam="Voorwaarde",
        omschrijving=(
            "Een voorwaarde is een conditie die beschrijft aan welke omstandigheid voldaan moet zijn voor het "
            "intreden van een rechtsgevolg. Een voorwaarde kan ook betrekking hebben op een rechtssubject of "
            "op een waarde die bij een rechtsobject of bij een afleidingsregel hoort. Een voorwaarde bevat "
            "vaste elementen, die in de logica operanden en operatoren worden genoemd. Operanden kunnen "
            "rechtssubjecten of rechtsobjecten, eigenschappen van rechtssubjecten of rechtsobjecten, "
            "berekeningen of waarden zijn. Een operator is de beschrijving van een vergelijking die in de "
            "voorwaarde voorkomt, zoals ‘groter dan’, ‘kleiner dan’ en ‘gelijk aan’."
        ),
        vraag=(
            "Welke eisen worden gesteld aan een rechtssubject, een rechtsobject, een rechtsbetrekking of een "
            "rechtsfeit? Onder welke omstandigheden geldt een waarde bij een rechtsobject?"
        ),
        uitdrukkingswijze=(
            "Te herkennen aan een voorwaardelijke bijzin, in de meeste gevallen ingeleid door een voegwoord "
            "zoals ‘indien’, ‘als’, ‘tenzij’, ‘mits’ of een combinatie van woorden, zoals ‘met dien verstande "
            "dat’ of ‘met uitzondering van’. Ook kan een voorwaarde afgeleid worden uit een bijwoord bij een "
            "werkwoord, zoals ‘schriftelijk’ of ‘elektronisch’. Voorwaarden kunnen enkelvoudig of "
            "samengesteld zijn: een samengestelde voorwaarde bestaat uit verschillende eisen die alle vervuld "
            "moeten zijn (cumulatief) of waarvan er één vervuld moet zijn (alternatief)."
        ),
    ),
    JasKlasse(
        naam="Afleidingsregel",
        omschrijving=(
            "Een afleidingsregel is een regel die nieuwe feiten of waarden creëert met behulp van bestaande "
            "feiten of waarden. Te denken valt aan regels die bepalen of een recht bestaat (een beslisregel), "
            "of die de hoogte en duur van een recht bepalen (een rekenregel). De variabele die vastgesteld "
            "wordt door de afleidingsregels, noemen we uitvoervariabele. Bij een rekenregel is dit de "
            "uitkomst van de rekensom; bij een beslisregel een conclusie als ja/nee of waar/onwaar. De "
            "variabelen die gebruikt worden voor de vaststelling, noemen we invoervariabelen. Als sprake is "
            "van vaste getallen of waarden in een afleidingsregel die over een periode gelijk zijn voor alle "
            "rechtssubjecten en rechtsobjecten, noemen we deze parameters. Afleidingsregels worden ook "
            "gebruikt om te bepalen of een rechtssubject of rechtsobject tot een bepaalde doelgroep behoort; "
            "het gaat dan om het afleiden van specialisaties van rechtssubjecten en rechtsobjecten op basis "
            "van bepaalde kenmerken."
        ),
        vraag=(
            "Hoe wordt een variabele berekend of afgeleid? Hoe wordt een specifiek rechtssubject of "
            "rechtsobject bepaald?"
        ),
        uitdrukkingswijze=(
            "Te herkennen aan woorden die duiden op een berekening of afleiding, zoals ‘is (…) verminderd "
            "met’, ‘bedraagt (…) vermeerderd met’, ‘wordt gesteld op’ of ‘is het gezamenlijke bedrag van’, "
            "maar ook eenvoudigweg ‘en’."
        ),
    ),
    JasKlasse(
        naam="Variabele en variabelewaarde",
        omschrijving=(
            "Een variabele is een kenmerk van een rechtssubject, rechtsobject, rechtsbetrekking of rechtsfeit "
            "dat voor verschillende instanties daarvan (dus voor specifieke personen, zaken, relaties, "
            "handelingen of gebeurtenissen in de werkelijkheid) een andere waarde kan hebben. Een "
            "variabelewaarde geeft de waarde aan die een bepaalde variabele kan hebben. De wijze waarop een "
            "variabelewaarde is omschreven in wetgeving kan een beperking in de mogelijke waarden voor een "
            "variabele inhouden, of een voorwaarde aan een variabele stellen."
        ),
        vraag=(
            "Wat zijn de specifieke kenmerken van een rechtsobject, rechtssubject, rechtsbetrekking of "
            "rechtsfeit? Welke eigenschappen worden genoemd? Welke waarde heeft een rechtsobject? Hoe lang of "
            "hoe hoog is een rechtsobject? En voor de waarde: welk bedrag, welke duur of welke hoogte hoort "
            "bij deze variabele?"
        ),
        uitdrukkingswijze=(
            "vier varianten: getal of datum — een concreet bedrag, een concrete datum, een concrete tijdsduur "
            "of een andere numerieke waarde; tekst — bijvoorbeeld de variabele ‘naam van een werkgever’; "
            "enumeratiewaarde — een limitatieve opsomming van de mogelijke waarden, in getallen of tekst; "
            "booleaanse waarde — een bijzondere enumeratiewaarde met twee waarden, ‘ja’ (waar) of ‘nee’ "
            "(onwaar); bijvoorbeeld de variabele ‘geregistreerd in het donorregister’."
        ),
    ),
    JasKlasse(
        naam="Parameter en parameterwaarde",
        omschrijving=(
            "Een parameter is een beschrijving van een waarde die gelijk is voor alle rechtssubjecten, "
            "rechtsobjecten, rechtsbetrekkingen en rechtsfeiten. Vanwege de stabiele waarde wordt een "
            "parameter ook wel constante genoemd. Parameters worden gebruikt in afleidingsregels en "
            "voorwaarden. In de regel geldt een parameter voor een bepaalde periode, bijvoorbeeld een "
            "kalenderjaar, maar hij kan ook voor een onbepaalde duur gelden (bijvoorbeeld voor de hele "
            "geldigheidsduur van de wettelijke regel). De waarde die een parameter in de desbetreffende "
            "periode heeft, is een parameterwaarde. De parameter is dus de omschrijving van de waarde, en de "
            "parameterwaarde is de concrete waarde die daaraan is toegekend."
        ),
        vraag=(
            "Is sprake van een waarde die gedurende een periode een vaste hoogte heeft voor alle "
            "rechtssubjecten en rechtsobjecten?"
        ),
        uitdrukkingswijze=(
            "Een parameter is te herkennen aan een beschrijving van een waarde, bijvoorbeeld van een tarief, "
            "een (drempel)bedrag (eventueel met een maximum of een minimum) of een vrijstelling. Een "
            "parameterwaarde is te herkennen aan bijvoorbeeld een bedrag in geld, een percentage of een "
            "datum."
        ),
    ),
    JasKlasse(
        naam="Operator",
        omschrijving=(
            "Een operator is een woord, een combinatie van woorden of een teken dat een rekenkundige "
            "bewerking, een samengestelde voorwaarde, een gelijkstelling of een vergelijking van twee waarden "
            "of berekeningen uitdrukt. Een operator beschrijft hoe verschillende elementen van een "
            "berekening, voorwaarde of samengestelde voorwaarde met elkaar verbonden worden om tot een "
            "resultaat te leiden. Drie typen: rekenkundige operatoren — voeren een bewerking uit, zoals "
            "optellen, aftrekken, vermenigvuldigen; vergelijkingsoperatoren — vergelijken variabelen met "
            "elkaar of een variabele met een parameter; logische operatoren — bepalen bij samengestelde "
            "voorwaarden of aan (ten minste) één voorwaarde moet worden voldaan (OF, disjunctie, alternatief) "
            "of aan alle (EN, conjunctie, cumulatief); ook kan er sprake zijn van een voorwaarde waaraan niet "
            "voldaan mag zijn (NIET, negatie)."
        ),
        vraag=(
            "Hoe worden variabelen of parameters verbonden in een berekening? In welke verhouding staan "
            "voorwaarden tot elkaar? Welke vergelijking wordt in een voorwaarde gemaakt?"
        ),
        uitdrukkingswijze=(
            "rekenkundig: ‘het gezamenlijke bedrag van’, ‘de som van’, ‘vermeerderd met’, ‘verminderd met’, "
            "‘percentage van’; vergelijking: ‘groter dan’, ‘kleiner dan’, ‘meer bedraagt dan’, ‘is gelijk "
            "aan’; logisch: ‘en’, ‘of’, ‘niet’, ‘ten minste’."
        ),
    ),
    JasKlasse(
        naam="Tijdsaanduiding",
        omschrijving=(
            "Een tijdsaanduiding is een omschrijving van een tijdstip of tijdvak. Een tijdsaanduiding is "
            "nodig om de geldigheid van een rechtsbetrekking te duiden, om een tijdsverloop met rechtsgevolg "
            "uit te drukken of als variabele bij een specifiek rechtssubject of rechtsobject. Ook kan een "
            "tijdsaanduiding (met name een tijdstip) een parameterwaarde zijn — een voorbeeld is een "
            "peildatum die wordt vergeleken met een andere datum (als variabele) in een voorwaarde. De "
            "tijdsaanduiding is als aparte klasse opgenomen, hoewel deze ook beschouwd zou kunnen worden als "
            "een verduidelijking van de klassen variabele of parameter. Gelet op het belang van de "
            "tijdsaanduiding voor het bepalen van de duur van een rechtsbetrekking of het tijdstip van een "
            "tijdsverloop met rechtsgevolgen, is tijdsaanduiding als aparte klasse opgenomen."
        ),
        vraag="Wanneer, op welk moment? Sinds wanneer of tot wanneer, vanaf welk moment of tot welk moment?",
        uitdrukkingswijze=(
            "Te herkennen aan een concrete datum (bijvoorbeeld 1 september 2009), of aan een omschrijving die "
            "een datum beschrijft (de eerste maandag van de maand). Tijdvakken zijn vaak te herkennen aan "
            "woorden die een periode duiden, zoals jaar, maand, week en dag, of specialisaties daarvan zoals "
            "kalenderjaar."
        ),
    ),
    JasKlasse(
        naam="Plaatsaanduiding",
        omschrijving=(
            "Een plaatsaanduiding is een plaats of een gebied waar bepaalde wetgeving betrekking op heeft. "
            "Zij bepaalt het toepassingsbereik van de regels voor rechtssubjecten, rechtsobjecten, "
            "rechtsbetrekkingen of rechtsfeiten. De meeste wetgeving geldt voor heel Nederland en heeft "
            "daarom geen expliciete plaatsaanduiding. Zodra het werkingsgebied beperkter of ruimer moet zijn, "
            "wordt in wetgeving wel een expliciete plaatsaanduiding opgenomen."
        ),
        vraag="Waar (voor welk gebied of welke plaats) geldt de wettelijke regel (niet)?",
        uitdrukkingswijze=(
            "Uitgedrukt met een algemene beschrijving van het gebied (een lidstaat van de EU) of met de naam "
            "van een specifiek gebied (de gemeente Amsterdam, de provincie Limburg, Nederland, Zwitserland)."
        ),
    ),
    JasKlasse(
        naam="Delegatiebevoegdheid en delegatie-invulling",
        omschrijving=(
            "Een delegatiebevoegdheid maakt het mogelijk of schrijft voor dat (nadere) regels worden gesteld "
            "over een rechtsbetrekking, rechtsfeit of afleidingsregel. Met delegatie-invulling duiden we de "
            "regeling of het regelingsonderdeel aan waarin de delegatiebevoegdheid is gebruikt. Een "
            "delegatiebevoegdheid wordt altijd aan een specifiek rechtssubject toegekend: de regering (bij "
            "een amvb, vastgesteld door de Koning) of een minister (bij een ministeriële regeling). De "
            "delegatie kan verplicht of facultatief zijn. Vaak is subdelegatie mogelijk: bepalingen in een "
            "amvb kunnen verder worden uitgewerkt in een ministeriële regeling. Vier dingen die de bron hier "
            "expliciet maakt en die je bij het annoteren nodig hebt: 1. Delegaties bepalen het werkgebied. "
            "\"Het herkennen van delegatiebevoegdheden is vooral van belang voor het bepalen van het "
            "werkgebied van de Wetsanalyse. Als de delegatiebevoegdheid daadwerkelijk is gebruikt, moet de op "
            "grond daarvan vastgestelde gedelegeerde regelgeving in het werkgebied worden betrokken.\" 2. De "
            "delegerende wet wijst nooit naar de invulling. \"De delegerende wet bevat logischerwijs geen "
            "concrete verwijzingen naar de delegatie-invulling. Die is immers op het moment van voorbereiden "
            "van die wet nog niet vastgesteld.\" Zoek een delegatie-invulling dus niet in de moederwet. 3. "
            "wetten.nl-metadata is onvolledig. De wetsinformatie bij een artikel \"is echter niet altijd "
            "volledig. Afstemming met wetgevingsjuristen om het werkgebied compleet te maken is daarom van "
            "belang.\" Dat geldt ook voor de verwijzingen die de kennisgraaf uit die bron overneemt. 4. Een "
            "delegatie-invulling is niet lexicaal te herkennen. \"In de delegatie-invulling wordt niet met "
            "standaard uitdrukkingswijzen gewerkt\" (H2:127). Je vindt hem alleen via de relatie met de "
            "grondslag, niet via signaalwoorden."
        ),
        vraag=(
            "Geeft een wetsartikel de opdracht om (nadere) regels te stellen? Verwijst een bepaling in een "
            "gedelegeerde regeling naar een artikel in de bovenliggende wet?"
        ),
        uitdrukkingswijze=(
            "Verplichte delegatie: ‘bij (of krachtens) algemene maatregel van bestuur / bij ministeriële "
            "regeling worden regels gesteld (…)’. Facultatieve bevoegdheid: ‘kunnen regels worden gesteld’. "
            "Bij ‘bij of krachtens’ kan subdelegatie plaatsvinden."
        ),
    ),
    JasKlasse(
        naam="Brondefinitie",
        omschrijving=(
            "Een brondefinitie is een begripsomschrijving die expliciet is opgenomen in de wetgeving en een "
            "eenduidige betekenis geeft aan een in de wetgeving (veel) gebruikte term. Brondefinities staan "
            "in de regel in een of meer artikelen aan het begin van een wet of gedelegeerde regeling. Als in "
            "de wet een term is gedefinieerd, wordt deze definitie standaard hergebruikt in de daarop "
            "gebaseerde gedelegeerde regelingen. De definities worden in de gedelegeerde regeling niet "
            "opnieuw opgenomen. \"Brondefinities moeten worden onderscheiden van de begrippen en "
            "begripsomschrijvingen die bij de Wetsanalyse worden gemaakt voor geclassificeerde formuleringen "
            "in de wetgeving. Deze begrippen hebben geen directe wettelijke bron, maar zijn nodig om "
            "formuleringen uniek te kunnen aanduiden.\""
        ),
        vraag="Is deze term uitdrukkelijk omschreven in de wetgeving?",
        uitdrukkingswijze=(
            "Een artikel met brondefinities bestaat in de regel uit een aanhef en verschillende onderdelen, "
            "bij voorkeur in alfabetische volgorde. Vaak staat dit artikel aan het begin van de regeling, "
            "maar er kunnen ook brondefinities zijn die voor een specifiek onderdeel gelden — een hoofdstuk, "
            "paragraaf of zelfs één artikel."
        ),
    ),
)
# --- EINDE GEGENEREERD ---

# Canonieke weergave-volgorde + naamlijst (drift-guard: gelijk aan validation.JAS_KLASSEN_VOLGORDE).
JAS_KLASSEN_VOLGORDE: tuple[str, ...] = tuple(k.naam for k in JAS_KLASSEN)
GELDIGE_JAS_KLASSEN: frozenset[str] = frozenset(JAS_KLASSEN_VOLGORDE)


# ---------------------------------------------------------------------------
# JAS-regels – machineleesbare annotatie-regels naast de klasse-specificaties
#
# Eén definitie voedt prompts, deterministisch validators en toekomstige tools.
# Nieuwe regels toevoegen hier; nooit dezelfde logica op drie plekken herhalen.
# ---------------------------------------------------------------------------

from dataclasses import dataclass as _dc
from enum import Enum as _Enum


class RegelType(_Enum):
    """Categorieën van JAS-regels. Uitbreidbaar zonder bestaande code te breken."""
    PRIORITEIT  = "priority"      # hogere klasse prevaleert bij samenloop
    CONFLICT    = "conflict"      # twee klassen sluiten elkaar uit
    EXCLUSIE    = "exclusion"     # klasse is niet van toepassing onder een conditie
    SPAN        = "span"          # eisen aan de afbakening van het fragment
    CONSISTENTIE = "consistency"  # structurele samenhang-eis (bv. subject bij betrekking)


@_dc(frozen=True)
class JASRule:
    """Eén machineleesbare JAS-annotatieregel.

    `id`          – unieke identificator, formaat JAS-<TYPE>-<NNN>
    `type`        – zie RegelType
    `applies_to`  – klassen waarop de regel van toepassing is
    `description` – mensleesbare toelichting (voor prompts en documentatie)
    `priority`    – alleen voor RegelType.PRIORITEIT: dict van klasse → rang (hoger = wint).
                    Ontbrekende klassen krijgen impliciet rang 0.
    """
    id: str
    type: RegelType
    applies_to: tuple[str, ...]
    description: str
    priority: tuple[tuple[str, int], ...] = ()   # tuple van (klasse, rang) – hashable


def _prio(klassen_met_rang: dict[str, int]) -> tuple[tuple[str, int], ...]:
    """Helperfunctie: zet een dict om naar een hashbare tuple voor JASRule.priority."""
    return tuple(sorted(klassen_met_rang.items()))


REGELS: tuple[JASRule, ...] = (
    JASRule(
        id="JAS-PRIORITY-001",
        type=RegelType.PRIORITEIT,
        applies_to=(
            "Tijdsaanduiding",
            "Variabele en variabelewaarde",
            "Parameter en parameterwaarde",
        ),
        description=(
            "Indien een formulering zowel als tijdsaanduiding als variabele of parameter kan worden "
            "geclassificeerd, prevaleert tijdsaanduiding als de meest specifieke klasse."
        ),
        priority=_prio({
            "Tijdsaanduiding": 100,
            "Variabele en variabelewaarde": 50,
            "Parameter en parameterwaarde": 50,
        }),
    ),
    JASRule(
        id="JAS-PRIORITY-002",
        type=RegelType.PRIORITEIT,
        applies_to=(
            "Plaatsaanduiding",
            "Variabele en variabelewaarde",
            "Parameter en parameterwaarde",
        ),
        description=(
            "Indien een formulering zowel als plaatsaanduiding als variabele of parameter kan worden "
            "geclassificeerd, prevaleert plaatsaanduiding als de meest specifieke klasse."
        ),
        priority=_prio({
            "Plaatsaanduiding": 100,
            "Variabele en variabelewaarde": 50,
            "Parameter en parameterwaarde": 50,
        }),
    ),
)
