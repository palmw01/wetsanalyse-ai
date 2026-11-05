# ADR-006 — Generieke begrippen boven de werkgebieden

Status: **aangenomen, nog niet gebouwd** · Datum: 2026-11-05 · Hoort bij: [PLAN spoor N](../PLAN.md#n-begrippen-nieuwe-bediening-en-generieke-begrippen), [ADR-003](adr-003-nl-sbb-begrippencontract.md)

## Context

Een begrip hoort nu bij precies één werkgebied: `begrippen.werkgebied_id` is verplicht, en er is één impliciet
kader per werkgebied (`urn:wa:kader:<werkgebied>`). Dat past bij de eerste stap van de analyse. Maar een begrip als
*belastingschuldige* komt in veel werkgebieden voor. Nu definieert elk werkgebied het opnieuw, en die definities
lopen uit elkaar.

Tegelijk is een gelijke term geen gelijke betekenis: hetzelfde woord kan per regeling iets anders betekenen. Een
begrip mag dus niet vanzelf gedeeld worden, en wie afwijkt moet dat kunnen vastleggen. En elk begrip moet herleidbaar
blijven naar de wettekst.

## Besluit

- **Eén generiek begrippenkader** boven de werkgebieden (`urn:wa:kader:generiek`), naast het kader per werkgebied.
- **Eén begrip, overal gebruikt.** Een werkgebied gebruikt een generiek begrip zonder kopie: de definitie staat op één
  plek, de passages blijven per werkgebied (`begrip_koppelingen.werkgebied_id` bestaat al). Wijkt de betekenis af, dan
  maakt de analist een lokaal begrip met een relatie naar het generieke.
- **Een generiek begrip ontstaat alleen door *Generiek maken* vanuit een werkgebied**, en alleen als het geaccordeerd
  is. Daarmee heeft het altijd passages en is het herleidbaar. Lex maakt niets generiek.
- **Bevoegdheid zoals nu:** elke analist mag wijzigen en accorderen; de audit legt vast wie.
- **Doorwerking:** elk werkgebied toont direct de stand van nu en krijgt een melding bij *Herbeoordelen*, met toen en
  nu. Een betekeniswijziging levert een opvolger op (PLAN D), die elk werkgebied zelf overneemt.
- **Bewerken van de inhoud gebeurt op de pagina van het generieke begrip**, niet vanuit een werkgebied, zodat niemand
  ongemerkt andere analyses wijzigt. Passages beheert elk werkgebied zelf.
- **Een passage toevoegen of beoordelen heropent een generiek begrip niet.** Dat is een uitzondering op "elke mutatie
  maakt een geaccordeerd begrip weer een concept"; anders zet één analyse het begrip voor iedereen terug.
- **Dezelfde voorkeursterm staat één keer in het generieke kader** (409 `al_generiek`). Homoniemen krijgen een
  onderscheidende naam.
- **Dubbele begrippen:** *Combineren* werkt ook tussen kaders. Het lokale begrip wordt vervangen door het generieke, de
  passages gaan mee, het oude begrip blijft vindbaar.
- **Verwijderen** kan niet zolang een werkgebied het begrip gebruikt (409 `in_gebruik`). Stoppen met gebruiken kan
  wel; de passages van dat werkgebied gaan dan los.
- **Lex** leest generieke begrippen en stelt koppelingen voor ("lijkt op … (generiek)"). Dat is een voorstel; de
  analist koppelt.

## Datamodel

- `begrippen.werkgebied_id` wordt nullable: leeg is generiek. Nieuw `ontstaan_in`: het werkgebied van herkomst.
- Nieuwe tabel `werkgebied_begrippen` (`werkgebied_id`, `begrip_id`, `gezien_revisie`, door, op, verwijderd): het
  gebruik. `gezien_revisie` lager dan de revisie van het begrip is het signaal voor *Herbeoordelen*.
- De identiteit verandert niet: `urn:wa:begrip:<uuid>` blijft, ook na *Generiek maken*.
- `primair` blijft per werkgebied: een element duidt binnen een werkgebied één begrip aan, lokaal of generiek.
- Slotvolgorde blijft werkgebied vóór begrip (`begrip_store._gewijzigd`).
- `werkgebied_audit` kent alleen werkgebieden: een generieke wijziging schrijft een regel bij elk gebruikend
  werkgebied, en `begrip_revisies` blijft de bron.

## Graaf en NL-SBB

- Named graph `urn:wa:graph:kader:generiek`, geregistreerd in `urn:wa:graph:register:begrippen`.
- Een begrip staat in precies één `skos:inScheme`, ook als veel werkgebieden het gebruiken.
- De graph van een werkgebied draagt zijn koppelingen en `wa:gebruiktBegrip` naar het generieke begrip.
- Relaties tussen kaders houden hun predicaten uit ADR-003. Conformiteit en Turtle-export gelden ook voor het
  generieke kader.

## Gevolgen

- Een generiek begrip heeft een eigen pagina (`/begrippen/[id]`) met zijn passages per werkgebied; in een werkgebied
  blijft het begrip op `/werkgebieden/[id]/begrippen/[begrip]`, met de passages van dat werkgebied.
- `BegripInhoud` krijgt een `context` (een werkgebied of generiek), zodat beide pagina's en het paneel één inhoud delen.
- De poort, de herbeoordeling, de projectie, de manifesten en `lijkt_op` lezen voortaan twee kaders.
- Een bestaand begrip blijft lokaal; er is geen migratie van inhoud.

## Alternatieven

- **Lokaal begrip met een NL-SBB-match (`skos:exactMatch`) naar het generieke.** Afgewezen: zuiver per kader, maar de
  definitie bestaat dan in feite meerdere keren, en dat was het probleem.
- **Kopiëren uit een bibliotheek.** Afgewezen: na de kopie lopen de definities uit elkaar.
- **Een werkgebied zet een revisie vast.** Afgewezen: werkgebieden lopen dan uiteen. *Herbeoordelen* maakt een
  wijziging zichtbaar zonder dat.
- **Direct generiek aanmaken, zonder werkgebied.** Afgewezen: een begrip zonder passages is niet herleidbaar en kan
  niet door de poort.
