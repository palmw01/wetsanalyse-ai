---
name: wetsanalyse
description: >-
  Voert Wetsanalyse uit op Nederlandse wet- en regelgeving volgens de methode
  Wetsanalyse (Ausems, Bulles & Lokin) en het Juridisch Analyseschema (JAS):
  activiteit 2 (wetsformuleringen markeren en classificeren in JAS-klassen). Dit is de
  inhoudelijke methodebeschrijving; het draaiende platform voert de analyse uit in de
  werkplek. Gebruik deze skill zodra de gebruiker een
  wetsartikel of regeling juridisch wil analyseren, structureren, ontleden of
  "wetsanalyse" wil doen – ook bij vragen als "classificeer dit artikel", "welke
  rechtssubjecten/rechtsbetrekkingen/voorwaarden zitten hierin",
  "ontleed deze bepaling juridisch", of wanneer een
  bepaling brongetrouw en uitlegbaar moet worden vastgelegd voor uitvoering
  (bijvoorbeeld bij de Belastingdienst). Trigger ook bij twijfel: dit is de aangewezen werkwijze voor het
  gestructureerd duiden van de betekenis van wetgeving.
---

# Wetsanalyse (activiteit 2)

> **Scope.** Deze skill dekt op dit moment **activiteit 2** (markeren + classificeren in
> JAS-klassen). Activiteit 3 (begrippen + afleidingsregels) en de RegelSpraak-vervolgstap zijn
> uit scope – die worden later op een agentische basis opnieuw opgebouwd.

## Wat dit is en waarom het zo werkt

Wetsanalyse is een gestructureerde methode om de betekenis van wetgeving expliciet,
traceerbaar en uitlegbaar te maken, zodat besluiten in de uitvoering te verantwoorden
zijn. Deze skill voert de analytische kern uit:

- **Activiteit 2 – juridische structuur zichtbaar maken**: relevante wetsformuleringen
  *markeren* (2a) en elke markering een *klasse* uit het Juridisch Analyseschema (JAS)
  geven (2b).

**De analyse-eenheid is het *werkgebied* (kennisdomein), niet één artikel.** Een werkgebied
is een afbakening rond een hoofdvraag die zich over **meerdere bronnen** uitstrekt – leden,
artikelen, hoofdstukken, en zelfs meerdere regelingen (bv. een wet + de gedelegeerde
regeling). Eén *bron* is één `(bwbId, artikel, lid?)`-eenheid ("tekstdeel"). Activiteit 2
doe je per bron (markeren/classificeren). Een werkgebied met één bron is het triviale geval.

**Deze skill beschrijft de methode, niet een uitvoerbare werkstroom.** Het platform doet de
analyse: de kennisgraaf levert de wettekst, de agent stelt markeringen voor en de jurist
beoordeelt ze in de werkplek. Werk je hier buitenom, dan gelden dezelfde eisen – werk met
letterlijk opgehaalde wettekst en laat een mens het resultaat beoordelen.

**Dit is een hulpmiddel, geen vervanger van de analist.** De methode draait om het
*expliciet maken van interpretatiekeuzes* zodat juristen, informatieanalisten en
ICT-ontwikkelaars er samen over kunnen beslissen. Lever dus een onderbouwd, eerlijk
concept op: classificeer wat helder is, en markeer twijfel, aannames en open normen
als zodanig in plaats van een schijnzekerheid te produceren. Een goede analyse die haar
eigen onzekerheden benoemt is waardevoller dan een gladde die ze verbergt.

## Brongetrouwheid is niet onderhandelbaar

In een professionele uitvoeringscontext (zoals de Belastingdienst) hangt rechtmatigheid
aan de bron. Daarom:

- **Werk alleen met de letterlijke, opgehaalde wettekst.** Verzin nooit tekst, leden of
  artikelnummers. Citeer formuleringen letterlijk.
- **Houd alles herleidbaar.** Elke markering verwijst naar haar bron (`bron_id`) + lid en,
  waar beschikbaar, de `bronreferentie` (jci-link). Id's zijn **werkgebied-breed
  uniek** (`m1..` voor markeringen, `v1..` voor verwijzingen).
- **Gebruik uitsluitend de dertien JAS-klassen** hieronder. Verzin geen eigen klassen.

## Stap 1 – Verwijzingen inventariseren en volgen

Wetsformuleringen verwijzen naar andere bepalingen die de betekenis bepalen: het
definitieartikel, andere leden ("in afwijking van het eerste lid"), schakelbepalingen ("van
overeenkomstige toepassing") en gedelegeerde regelingen. Inventariseer die uitgaande
verwijzingen **per bron** vóór je classificeert, volg de relevante volgens beleid, en leg ze
vast als `verwijzingen`-array op die bron (elke verwijzing draagt het `bron_id` van haar bron).

Wordt een gevolgde definitie of gedelegeerde regeling zelf zo relevant dat je haar wilt
markeren/classificeren, **promoveer haar dan tot een eigen bron** in het werkgebied (het
werkgebied mag groeien) in plaats van haar enkel als verwijzing te noteren.

De graaf levert per lid de getagde verwijzingen (intref/extref, óók als inline-link in de
tekst); natuurlijke-taalverwijzingen ("het eerste lid") herken je
zelf en noteer je met `soort: "natuurlijk"`. Classificeer elke verwijzing naar **functie**
(definitie / schakel / delegatie / intra-artikel / informatief) en bepaal het **scope-besluit**
volgens de beleidstabel, met een **diepte-cap van 1** en een **relevantie-gate** (volg alleen
op als het de focus-bepaling betekenis geeft). Delegaties zijn *bounded*: identificeren +
betekenis verwerken, volledige sub-analyse signaleren als validatiepunt.

`verwijzingen` is een **aparte as** náást de markeringen – uitgaande pointers, geen tweede
registratie van JAS-klassen.

**Houd deze stap licht** (inventariseren + gericht ophalen, niet al classificeren). De
volledige werkwijze, beleidstabel en grenzen staan in `references/verwijzingen-volgen.md`.
De verwijzing-inventaris hoort bij wat de analist beoordeelt, zodat hij de scope kan bijsturen.

## Stap 2 – Activiteit 2: markeren en classificeren

Doorloop de bronnen één voor één ("pak eerstvolgende tekstdeel uit het werkgebied"). Lees
per bron de tekst lid voor lid. Identificeer samenhangende formuleringen (2a) en ken elk een
JAS-klasse toe (2b). Werk fijnmazig: een lid bevat vrijwel altijd meerdere markeringen. Geef
elke markering het `bron_id` van haar bron en een werkgebied-breed uniek id.

**Werkset-discipline bij veel bronnen.** De tekst van één bron is fors (~5–50 KB);
houd de hoofdcontext klein. Bij een werkgebied met meerdere bronnen: overweeg activiteit 2
**per bron via een sub-agent** te draaien – de sub-agent markeert de volledige wettekst van
één bron en meldt alléén de markeringen + verwijzingen terug (niet de leden-tekst), zodat de
brontekst van afgeronde bronnen niet in de hoofdcontext blijft hangen terwijl je de volgende
bron doet. Laad de `references/` één keer; herhaal ze niet per bron.

Gebruik per klasse de **herkenningsvraag** als grammaticale ontleedvraag op de tekst. Dit
is de compacte checklist; voor de volledige omschrijving, herkenningsvragen en
uitdrukkingswijzen zie `references/jas-klassen-referentie.md` (raadpleeg bij twijfel of bij
samenloop van klassen).

| Klasse | Kern | Herken aan |
| --- | --- | --- |
| **Rechtssubject** | Drager van rechten/plichten; partij in een rechtsbetrekking. *Wie heeft het recht/de plicht?* | Zelfstandig naamwoord voor persoon/entiteit; 'hij', 'degene', 'een ieder', 'iemand' |
| **Rechtsobject** | Voorwerp van een rechtsbetrekking/rechtsfeit. *Waar gaat het recht/de plicht over?* | Zelfstandig naamwoord (een woning, een dienst); 'dat', 'hetgeen', 'welk(e)' |
| **Rechtsbetrekking** | Juridische relatie tussen twee rechtssubjecten: de een heeft een plicht, de ander het recht. | Werkwoord(combinatie): 'heeft recht op', 'heeft aanspraak op' (recht); 'stelt vast', 'moet', 'is verplicht', 'dient te' (plicht) |
| **Rechtsfeit** | Handeling, gebeurtenis of tijdsverloop dat een rechtsbetrekking creëert, wijzigt of beëindigt. | Actieve werkwoordsvorm + zn: 'indienen van een bezwaarschrift', 'toekennen van een subsidie' |
| **Voorwaarde** | Conditie waaraan voldaan moet zijn voor een rechtsgevolg. *Welke eis wordt gesteld?* | Voorwaardelijke bijzin: 'indien', 'als', 'mits', 'tenzij', 'voor zover', 'met uitzondering van' |
| **Afleidingsregel** | Regel die nieuwe feiten/waarden afleidt (beslis-, reken- of specialisatieregel). *Hoe wordt iets berekend/bepaald?* | 'verminderd met', 'vermeerderd met', 'bedraagt', 'wordt gesteld op', 'het gezamenlijke bedrag van' |
| **Variabele en variabelewaarde** | Kenmerk dat per geval een andere waarde kan hebben (+ die waarde). | Getal, datum, tekst, enumeratie (limitatieve opsomming) of booleaanse waarde (ja/nee) |
| **Parameter en parameterwaarde** | Vaste waarde, gelijk voor allen over een periode (+ die waarde). 'Constante.' | Tarief, percentage, (drempel)bedrag, vrijstelling met vaste waarde over een periode |
| **Operator** | Bewerking, vergelijking of logische verbinding. | Reken: 'som van', 'vermeerderd met'; vergelijk: 'groter dan', 'gelijk aan'; logisch: 'en', 'of', 'niet', 'ten minste' |
| **Tijdsaanduiding** | Tijdstip of tijdvak (geldigheid, peildatum, termijn). | Concrete datum, 'kalenderjaar', 'maand', 'week'. *Meest specifieke klasse: wint van variabele/parameter.* |
| **Plaatsaanduiding** | Plaats/gebied dat het toepassingsbereik bepaalt. | 'Nederland', 'de gemeente Amsterdam', 'een lidstaat van de EU'. *Wint ook van variabele/parameter.* |
| **Delegatiebevoegdheid en delegatie-invulling** | Bevoegdheid/opdracht om nadere regels te stellen (+ de regeling die dat invult). | 'Bij (of krachtens) algemene maatregel van bestuur/ministeriële regeling worden regels gesteld' (verplicht); 'kunnen regels worden gesteld' (facultatief) |
| **Brondefinitie** | Begripsomschrijving die expliciet in de wet staat en een term eenduidig betekent. | Definitieartikel vooraan de wet ('In deze wet wordt verstaan onder…') |

Vuistregels bij het classificeren:

- **Bij samenloop kiest de meest specifieke klasse.** Een datum die de geldigheid duidt is
  een *tijdsaanduiding*, geen variabele; een gebied is een *plaatsaanduiding*.
- **'bij of krachtens'** in een delegatiebevoegdheid duidt op mogelijke subdelegatie
  (amvb → ministeriële regeling). Noteer dat: de gedelegeerde regeling hoort tot het
  werkgebied en moet later apart geanalyseerd worden.
- **Twijfel je tussen twee klassen?** Kies de best passende, noteer het alternatief in de
  toelichting, en benoem het als aandachtspunt bij de oplevering. Forceer niets.

Vat daarna kort samen hoe de klassen *samenhangen* rond de centrale klassen
(rechtsbetrekking en rechtsfeit): wie is rechthebbende, wie plichthebbende, welk
rechtsobject, onder welke voorwaarden. Dit is de "structuur" die activiteit 2 zichtbaar
maakt.

## Kwaliteitscheck voordat je oplevert

- Is elke markering herleidbaar naar artikel + lid (en bronreferentie)?
- Zijn alle klassen uit het JAS, en geen verzonnen klassen?
- Zijn brondefinities opgehaald waar de bepaling naar gedefinieerde termen verwijst?
- Zijn de uitgaande verwijzingen geïnventariseerd, geclassificeerd naar functie en gevolgd
  volgens beleid (diepte-cap + relevantie-gate)?
- Zijn interpretatiekeuzes en twijfel expliciet benoemd in plaats van weggepoetst?
- Heeft een mens het resultaat beoordeeld voordat het als vastgesteld geldt?
- Klopt de letterlijke wettekst met de bron (geen parafrase als citaat)?
