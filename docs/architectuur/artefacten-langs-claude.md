# Artefacten langs het artefactmodel van Claude (toets, 4 nov 2026)

**Status:** toets met besluiten van de gebruiker (4 nov 2026, onderaan). De uitvoering krijgt een eigen plan.

## Waarom

De werkplek leent haar vorm van Claude. Lex levert in het gesprek een **artefact** op, dat naast het gesprek opent.
Op het artefact lees, bewerk en besluit je. Zoeken en maken gaat via het gesprek; het resultaat opent weer naast het
gesprek. Dat principe is vastgelegd op 4 november 2026: een bepaling noemen is een voorstel in het paneel, en
het samenstellen van een werkgebied loopt door in de bronselectie.

Dit document legt de artefacten van de werkplek naast wat een artefact bij Claude is en kan. Per punt staat wat er
al is, wat ontbreekt en wat niet bij het platform past.

## Wat een artefact bij Claude is

1. **Een product van het gesprek, met een chip in de thread**: de soort, de titel en een klik om het te openen.
2. **Eén artefact tegelijk naast het gesprek**, als eigen kolom. Op een smal scherm ligt het eroverheen.
3. **Bijwerken via het gesprek levert een nieuwe versie op.** Er is een versiekiezer (‹ versie n van m ›), en een
   oudere versie blijft te bekijken.
4. **Kleine bewerkingen direct op het artefact**, zonder omweg via het gesprek.
5. **Kopiëren, downloaden en exporteren** vanuit de kop van het artefact.
6. **Volledig scherm of een eigen pagina.**
7. **Terugvinden over gesprekken heen**: een overzicht van alles wat er gemaakt is.
8. **Het artefact hoort bij het gesprek waarin het ontstond**, en het gesprek verwijst ernaar.

## De artefacten van de werkplek

De soorten staan in `frontend/lib/artefact.ts`: annotatie, begrippen, bronnen (gevonden bepalingen), werkgebied,
deelvraag, begrip, bronselectie en regels (gereserveerd).

| punt van Claude | stand in de werkplek | oordeel |
|---|---|---|
| 1. chip in de thread | Elke soort heeft een chip met soort en titel (`ArtefactChip`, `AnnotatieChip`); een verwijderde annotatie wordt een tombstone. | **Er.** |
| 2. één tegelijk naast het gesprek | Kolom vanaf 1280px, daaronder een sheet. `nodeDoel`, `wgArtefact` en `ctx` sluiten elkaar uit. | **Er.** |
| 3. versies via het gesprek | Een artefact is een levend object bij de api (werkgebied, begrip, annotatielaag). Een beurt van Lex wijzigt het. Sinds 5 nov 2026 legt de api bij elke beurt de stand vast (`artefact_versies`), en de chip opent zijn eigen versie met ‹ versie n van m › en *Nu* (`VersieKiezer`). | **Opgelost.** Stond als grootste afwijking van Claude. |
| 4. kleine bewerkingen erop | Dossier (*Gegevens bewerken*), definitie en uitleg van een begrip, besluiten in het paneel en in de reviewlijst. | **Er.** |
| 5. kopiëren / exporteren | De annotatie heeft PDF, CSV, JSON en TriG (`ExportKnop`); begrippen hebben CSV, JSON en Turtle (NL-SBB). Werkgebied (dossier), bronselectie en deelvraag hebben geen export en geen *Kopieer*. | **Deels.** |
| 6. volledige pagina | Elk paneel heeft *Open volledige pagina* (`paginaVan`). | **Er.** |
| 7. terugvinden | De overzichten Werkgebieden, Annotaties en Begrippen, en per werkgebied de tab Artefacten. De gesprekken staan per werkgebied in de sidebar. | **Er**, per soort; er is geen "alle artefacten van dit gesprek". |
| 8. bij het gesprek | Het bericht draagt het artefact (`Bericht.artefact`); een werkgebied koppelt het gesprek. | **Er.** |

Verdere bevindingen:

- **Het artefact `bronnen` (gevonden bepalingen) maakt graph-qa niet meer.** Sinds spoor J zoekt de bronselectie zelf;
  alleen oude berichten openen het nog (`BronKandidaten`). Het is een wees naast `bronselectie`.
- **`bronselectie` is een artefact zonder eigen item in de thread.** Het antwoord met het kaartje blijft staan en het
  paneel opent ernaast. Dat is bewust ("kaart compact, paneel beslist"), maar het wijkt af van de andere soorten: daar
  ís de chip het item.
- **De annotatie heeft een eigen paneel** (`NodeAnnotatiePaneel`) met een eigen kop. De werkgebiedsoorten delen
  `WerkgebiedArtefactPaneel` met `PaneelKop`. Dat zijn twee schillen voor hetzelfde idee.
- **Bijwerken in de chip.** Bij Claude verwijst een latere beurt naar hetzelfde artefact met een nieuwe versie. In de
  werkplek maakt elke beurt een nieuwe chip, en alle chips tonen dezelfde stand van nu.

## Keuzes voor de gebruiker

1. **Versies.** Moet een chip de stand tonen *zoals Lex hem opleverde*, met een versiekiezer naar later, zoals bij
   Claude? Of blijft de chip een venster op het levende object, met de historie als apart onderdeel? Het eerste vraagt
   per artefactsoort een momentopname of een revisienummer op het bericht. De api heeft revisies en audit, dus het
   kan.
2. **Export en kopiëren voor elke soort.** Moeten dossier, bronselectie en deelvraag een *Kopieer* (Markdown) en een
   export krijgen, net als annotatie en begrippen, met één generieke knop in `PaneelKop`?
3. **Het artefact `bronnen` opruimen.** Laten we het opgaan in `bronselectie` (oude chips openen dan de bronselectie),
   of houden we de bronverkenner als eigen artefact?
4. **Eén paneelschil.** Brengen we de annotatie onder dezelfde kop (`PaneelKop`) als de werkgebiedsoorten, met
   dezelfde plek voor export, volledige pagina en sluiten?
5. **Artefacten van dit gesprek.** Komt er een lijst van wat Lex in dit gesprek opleverde, naast de overzichten per
   soort?

## Besluiten (gebruiker, 4 nov 2026)

1. **Versies: een versiekiezer zoals Claude.** De chip opent de stand zoals Lex hem bij die beurt opleverde, met
   ‹ versie n van m › naar later en naar nu. Uitgevoerd met eigen momentopnamen (`artefact_versies`, api), omdat alleen
   een begrip oude inhoud bewaart. De nieuwste versie opent als *Nu*; een oudere is alleen te lezen. Klaar op alle
   soorten: werkgebied, deelvraag, bronselectie, begrip, begrippen en annotatie.
2. **Export: één knop voor elke soort**, in de kop van elk paneel: *Kopieer als Markdown* plus de exportvormen die bij
   de soort passen.
3. **Het artefact `bronnen` gaat op in `bronselectie`.** Een oude chip opent de bronselectie van dat werkgebied; de
   bronverkenner blijft als pagina.
4. **Eén paneelschil.** De annotatie krijgt dezelfde kop (`PaneelKop`) als de andere artefacten. De inhoud, de
   wettekst en de review, blijft zoals hij is.
5. **Artefacten van dit gesprek:** nog niet gekozen; later.
