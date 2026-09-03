# Prompt: genereer een HTML-presentatie over Wetsanalyse-AI (demo Cluster Inning)

Kopieer de volledige tekst hieronder en plak hem in een nieuw Claude-gesprek.

---

## ── BEGIN PROMPT ──

Je bent een senior presentatieontwerper met ervaring in overheidscommunicatie en juridische tools.
Maak een **reveal.js HTML-diashow** als één zelfstandig `.html`-bestand.
Geen externe afbeeldingen of bestanden — alleen CDN-links (reveal.js, Fira Sans + Fira Mono via Google Fonts).

### Doelgroep en context

Het publiek bestaat uit **behandelfunctionarissen en analisten van Cluster Inning (Belastingdienst)**.
Ze voeren dagelijks invorderingstaken uit op basis van de Invorderingswet 1990, de Leidraad
Invordering 2008, de URIW en de IIB. Ze kennen het invorderingsproces van binnen:
aanslag → aanmaning → dwangbevel → beslaglegging. Ze zijn analytisch opgeleid maar geen klassieke
juristen — ze passen beleidsregels toe en signaleren uitvoerbaarheidsknelpunten.

De sessie duurt **45-60 minuten**: ~10 min presentatie (de dia's), ~35 min live demo in de
webapplicatie, ~10 min vragen.

**Toon:** zakelijk, concreet, geen hype. Begin met wat het oplevert voor de medewerker, dan pas hoe.
Benadruk dat AI de medewerker ondersteunt — de behandelfunctionaris beslist en is eindverantwoordelijk.
**Doel:** laten zien dat Lex wetswijzigingen sneller hanteerbaar maakt zonder kwaliteitsverlies.

---

### Stijl — modern, aansluitend op de webapplicatie

De presentatie moet visueel aanvoelen als de webapplicatie zelf: slides als kaarten op een
lichtgrijze achtergrond, blauw-getinte schaduwen, subtiele entree-animatie. Geen gradients,
geen blur, geen glassmorphism — het modern zit in de schaduwen, de grote radius en de
kleurlaagstapeling.

#### CSS-architectuur

```css
:root {
  --lint:          #154273;   /* koppen, primaire acties */
  --lint-mid:      #3a6ea8;
  --lint-light:    #e8eff7;
  --surface:       #f5f6f8;   /* presentatieachtergrond */
  --surface-2:     #edf0f4;   /* genest panel */
  --paper:         #ffffff;   /* slideachtergrond */
  --ink:           #1a1a1a;   /* broodtekst */
  --muted:         #4a5a6e;   /* secundaire tekst */
  --faint:         #6b7685;   /* metadata, hints */
  --line:          #d1d6dd;   /* borders, dividers */
  --succes:        #39870c;
  --waarschuwing:  #e17000;
  --fout:          #d52b1e;
  --schaduw-kaart: 0 4px 14px rgb(21 66 115 / 0.08), 0 1px 3px rgb(21 66 115 / 0.06);
  --schaduw-zacht: 0 1px 2px rgb(21 66 115 / 0.06), 0 1px 3px rgb(21 66 115 / 0.05);
  --r-kaart:       14px;
  --r-vorm:        32px;
  --r-btn:         5px;
  --r-badge:       3px;
}
```

**Presentatieachtergrond:** de `.reveal`-root krijgt `background: var(--surface)` (#f5f6f8).

**Slides als kaarten:** elke `section` krijgt:
- `background: var(--paper)`
- `border: 1px solid var(--line)`
- `border-radius: var(--r-vorm)` (32px)
- `box-shadow: var(--schaduw-kaart)` (blauw getint)
- `padding: 2.5rem 3rem`

**Entree-animatie:**
```css
@keyframes rise {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.reveal .slides section {
  animation: rise 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
}
```

**Typografie:**
- Font: Fira Sans 400/600 + Fira Mono via Google Fonts
- Koppen: 600, `--lint`, `letter-spacing: -0.01em`, `line-height: 1.2`
- Broodtekst: 400, `--ink`, `font-size: 0.85em`
- Metadata/labels: 400, `--faint`, `font-size: 0.65em`, uppercase + `letter-spacing: 0.08em`

**Duale radii — dit geeft de moderne uitstraling:**
- Controls (knoppen, badges, codeblokken): `var(--r-btn)` = 5px
- Kaarten/blokken in slides: `var(--r-kaart)` = 14px
- Slide-containers zelf: `var(--r-vorm)` = 32px

**Lijstitems:** geen standaard bullet. Vervang door een em-dash in lintblauw als `::before`-pseudo-element (`content: '—'; color: var(--lint)`).

**Alertkleuren als tint:** gebruik bij kaartachtergronden altijd de `/10` rgba-variant:
- Groen bg: `rgba(57,135,12,0.10)`, border: `rgba(57,135,12,0.30)`
- Amber bg: `rgba(225,112,0,0.10)`, border: `rgba(225,112,0,0.30)`
- Rood bg: `rgba(213,43,30,0.10)`, border: `rgba(213,43,30,0.30)`

#### JAS-klassenkleurentabel

| Klasse | Kleur |
|---|---|
| Rechtssubject | `#d8eaf7` |
| Rechtsobject | `#b2c3e3` |
| Rechtsbetrekking | `#90a2d0` |
| Rechtsfeit | `#bad8f1` |
| Voorwaarde | `#b7d8cd` |
| Afleidingsregel | `#d47479` |
| Variabele en variabelewaarde | `#f5dc5e` |
| Parameter en parameterwaarde | `#e6b8bb` |
| Operator | `#d7e8e2` |
| Tijdsaanduiding | `#cbb8d6` |
| Plaatsaanduiding | `#e6d3e5` |
| Delegatiebevoegdheid | `#b0b1b2` |
| Brondefinitie | `#edefef` |

JAS-strips: `8px` hoog, `border-radius: 4px`, aaneengesloten rij met `gap: 4px`.

---

### Dia-inhoud

#### Dia 1 — Titeldia

**Titel:** Lex — wetsanalyse met de kennisgraaf
**Ondertitel:** Een hulpmiddel voor gestructureerde, brongetrouwe JAS-annotatie
**Voettekst:** Belastingdienst · Cluster Inning · [datum]

_(Laat de gebruiker [datum] handmatig invullen.)_

Boven de koptekst: een korte lintblauwe balk (48px breed, 4px hoog, `border-radius: 2px`) als
visueel ankerpunt. De titeldia heeft een lege, ruime opzet — geen bullets.

---

#### Dia 2 — Het startpunt

**Koptekst:** Uitvoering begint bij de wet

**Kernboodschap (opsomming, 4 punten):**

- Bij Inning komen IW, Leidraad Invordering, URIW en IIB samen — bij elke wetswijziging moeten behandelaars snel weten wat er precies verandert en hoe de stukken samenhangen
- Handmatig JAS-annoteren kost tijd: één artikel met vijf leden kan tientallen markeringen bevatten
- De koppeling naar de bron raakt snel los: welke versie van de wettekst? welk lid precies?
- Doel van dit platform: die koppeling automatisch en controleerbaar houden

---

#### Dia 3 — Zes activiteiten van Wetsanalyse

**Koptekst:** Zes activiteiten van Wetsanalyse

**Inleiding (klein, onder de koptekst):**
Wetsanalyse werkt iteratief — activiteiten lopen in de praktijk in elkaar over.

**Visueel:** zes blokken naast elkaar in een rij. Activiteit 2 is volledig uitgelicht (lintblauwe
border `2px solid var(--lint)`, lintblauwe achtergrond `var(--lint-light)`, lintblauwe koptekst,
badge "Lex ondersteunt dit" in wit op lintblauw, `border-radius: var(--r-kaart)`).
De overige vijf zijn gedempt (`opacity: 0.45`, border `1.5px solid var(--line)`,
achtergrond `var(--surface-2)`).

| # | Naam | Korte omschrijving |
|---|---|---|
| 1 | Werkgebied bepalen | Scope en relevante bronnen vaststellen |
| **2** | **Juridische structuur zichtbaar maken** | **Formuleringen markeren en JAS-klasse toekennen** |
| 3 | Betekenis vaststellen | Begrippen, definities en afleidingsregels |
| 4 | Analyseresultaten valideren | Juistheid en volledigheid toetsen met voorbeelden |
| 5 | Ontbrekende beleidsregels signaleren | Leemten in uitvoeringsbeleid in kaart brengen |
| 6 | Kennismodel opstellen | Gegevens-, regel- en procesmodel samenbrengen |

**Voetnoot onder de blokken:**
Activiteiten 3–6 doe je nu zelf. Activiteit 1 ook — Lex helpt daarbij wel bij het zoeken van
relevante bronnen en het volgen van verwijzingen. De volgende stap is activiteit 2 agentisch
uitbreiden naar activiteit 3.

*Bron: methode Wetsanalyse — Ausems, Bulles & Lokin.*

---

#### Dia 4 — JAS in één zin

**Koptekst:** Het Juridisch Analyseschema in één zin

**Kernboodschap:**
JAS verdeelt de wettekst in **13 klassen** — van rechtssubject tot delegatiebevoegdheid —
zodat elke zin terug te vinden is als een benoemd, gestructureerd element.

**Visueel element:** een horizontale strip van 13 gekleurde rechthoekjes (de kleuren uit de tabel
hierboven), elk gelabeld met de klassenaam in kleine letters.

**Inning-toelichting (klein, onder de strip):**
In het invorderingsdomein zijn dit bijvoorbeeld: rechtssubject = "de ontvanger", rechtsfeit = "aanmaning verstuurd".

**Tagline:** "De jurist beslist — de AI stelt voor."

---

#### Dia 5 — Het platform

**Koptekst:** Drie lagen, één werkstroom

**Visueel:** een eenvoudig stroomdiagram (pijlen naar rechts), vier blokken:

```
Kennisgraaf (BWB)  →  Lex (AI-agent)  →  Werkplek  →  Jurist
```

Korte toelichting per blok (klein, onder het blok):
- **Kennisgraaf:** letterlijke wettekst van overheid.nl, opgeslagen als RDF-graaf
- **Lex:** beantwoordt vragen en stelt JAS-markeringen voor; alle antwoorden grounded op de graaf
- **Werkplek:** de browser-interface; chat + annotatie-review in één scherm
- **Jurist:** beoordeelt elk voorstel, geeft akkoord of verwerpt, export naar PDF/CSV/JSON

Render dit als een inline SVG (geen externe afbeeldingen). Gebruik lintblauw voor de blokken en
pijlen, witte tekst in het Jurist-blok (donker gevuld). Subteksten in `--faint`.

---

#### Dia 6 — De drie stappen

**Koptekst:** Van vraag tot beoordeelde annotatie

**Drie blokken naast elkaar** (`border-radius: var(--r-kaart)`, `border-top: 3px solid var(--lint)`,
`background: var(--lint-light)`, padding `1em`):

**1 · Stel een vraag**
Typ een juridische vraag in de werkplek: "Wanneer is een bestuurder persoonlijk aansprakelijk
voor de belastingschuld van zijn vennootschap?" Lex zoekt in de graaf, haalt het relevante artikel
op en antwoordt met een letterlijk citaat en een bronverwijzing.

**2 · Ontvang een annotatie**
Vraag een JAS-annotatie voor een specifiek artikel. Lex haalt de exacte wettekst op, stelt
markeringen voor in alle van toepassing zijnde JAS-klassen en laat de Critic elk element
controleren.

**3 · Beoordeel en beslis**
Elk voorstel verschijnt als een kaart: aandachtsniveau (groen/geel/rood), klassenaam,
fragment, toelichting. Jij drukt op Akkoord of Verwerpen. Wat jij beslist staat in het
audittrail, met tijdstip en naam.

---

#### Dia 7 — Brongetrouwheid

**Koptekst:** Geen fragment zonder bron

**Kernboodschap (opsomming):**

- Elk JAS-element bevat het **letterlijke tekstfragment** uit de opgehaalde wettekst
- Een algoritme — geen tweede AI-aanroep — controleert: staat dit citaat écht in de tekst die uit de graaf is gehaald?
- Als het er niet in staat, markeert de werkplek het en legt Lex uit waarom
- Elk element is herleidbaar naar een **jci-uri**: de officiële verwijzing naar artikel + lid + BWB-identificatie

**Voorbeeld (als codeblok of gekleurd tekstvak):**
```
jci1.31:c:BWBR0004770&artikel=36&lid=4
Invorderingswet 1990, art. 36 lid 4
```

Stijl van het tekstvak: `background: var(--surface)`, `border: 1px solid var(--line)`,
`border-left: 3px solid var(--lint)`, `border-radius: var(--r-badge)`,
`font-family: Fira Mono`, `color: var(--lint)`.

---

#### Dia 8 — De Critic

**Koptekst:** Jij beslist — de AI controleert zichzelf

**Drie niveaus als gekleurde kaartjes** (`border-radius: var(--r-kaart)`, `border: 1px solid var(--line)`,
gekleurde balk van 6px links):

🟢 **Geen bezwaar** (linkerbalk `#4caf50`, bg `rgba(57,135,12,0.06)`)
Het element klopt: klasse, fragment en afbakening zijn correct. Snel door met Akkoord — of de pijltoets.

🟡 **Even kijken** (linkerbalk `#f59e0b`, bg `rgba(225,112,0,0.06)`)
De Critic twijfelt — Voorwaarde of Afleidingsregel? De kaart toont een alternatief als klikbare
chip. Jij kiest; je keuze staat in het audittrail.

🔴 **Waarschijnlijk fout** (linkerbalk `#ef4444`, bg `rgba(213,43,30,0.06)`)
De Critic heeft de correctie al doorgevoerd in de code (niet door een tweede AI-aanroep). Wat er
stond en waarom het is aangepast, is zichtbaar in de kaart.

**Ondertekst:** "Het model doet wat zeker is automatisch. Wat twijfelachtig is, legt het voor."

---

#### Dia 9 — Stand van zaken

**Koptekst:** Wat werkt al — wat komt er aan

**Visueel:** twee kolommen naast elkaar (50/50), `gap: 1.2em`.

**Links — Gerealiseerd** (`border-top: 3px solid var(--lint)`, `background: var(--lint-light)`,
`border-radius: var(--r-kaart)`, koptekst in `--lint` uppercase):
- Kennisgraaf: officiële wettekst van overheid.nl
- Brongetrouwe antwoorden op juridische vragen
- JAS-annotatie + Critic-controle (activiteit 2)
- Audit trail en export (JSON, CSV, PDF)

**Rechts — Op de roadmap** (`border-top: 3px solid var(--line)`, `background: var(--surface-2)`,
`border-radius: var(--r-kaart)`, koptekst in `--faint` uppercase, bullets in `--muted`):
- Begripsvorming en definities (activiteit 3)
- Valideren en beleidsleemten signaleren (act. 4–5)
- Vertaling naar uitvoerbare bedrijfsregels
- Leidraad Invordering en URIW naast IW doorzoekbaar

---

#### Dia 10 — Over naar de demo

**Koptekst:** Laten we het zien

**Drie bullets (wat we in de demo doen):**
- Een vraag stellen over aansprakelijkheid en het antwoord met bronvermelding bekijken
- Artikel 36 lid 4 Invorderingswet 1990 laten annoteren
- De review doorlopen: akkoord geven, een alternatief kiezen, Lex iets vragen

**Grote lintblauwe tekst centraal (font-size: 1.6em, font-weight: 600):** "De werkplek staat klaar."

**Klein onder (gedempt, border-top):** Acceptatie-omgeving · let op: analyses kunnen verloren gaan

---

### Demo-script (verborgen dia's)

Voeg zes verborgen `<section data-visibility="hidden">` dia's toe — één per demo-stap.
Ze zijn doorloopbaar met de pijltoetsen maar verschijnen niet in de normale diaweergave.
Elke verborgen dia heeft een stijl-klasse `demo-stap`:
- Header: kleine lintblauwe uppercase-label ("Demo · Stap N")
- Commando: donker lintblauw vlak (`background: var(--lint)`, witte cursieve tekst, `border-radius: var(--r-btn)`)
- Bullets: compacte opsomming van aanwijspunten

**Stap 1 — Rondleiding starten**
Klik "Laat me de werkplek zien" op het lege gespreksvenster. Loop de 13 rondleiding-stappen door:
gespreksvenster → sidebar → invoerveld → bronnen → brongetrouwheid → denkproces →
annotatie openen → wettekst → reviewlijst → reviewkaart → Jij beslist (hier: echt op Akkoord
klikken) → zelf markeren → afronden.

**Stap 2 — Vraag stellen**
Typ in het invoerveld:
> Wanneer is een bestuurder persoonlijk aansprakelijk voor de belastingschuld van zijn vennootschap?

Wacht tot het antwoord volledig is. Wijs aan: het denkproces-blok (inklapbaar), de
bronnen-collapsible, de brongetrouwheid-indicatie. Klik de bron open om de jci-uri te tonen.

**Stap 3 — Annotatie aanvragen**
Typ:
> annoteer artikel 36 lid 4 van de Invorderingswet 1990

Wacht ~60-90 seconden. Wijs aan: de annotatie-chip die verschijnt, het automatisch openen
van het ArtefactPaneel, het denkproces-logje ("supervisor koos de annotatie-worker · Critic las mee").

**Stap 4 — Review doorlopen**
- Wijs de drie aandacht-niveaus aan in de reviewlijst (filter op "Met aandacht")
- Selecteer een gele kaart, wijs het alternatief aan als klikbare chip, klik het om te wisselen
- Druk `a` om een kaart te accorderen — de kaart wordt grijs, selectie springt door
- Open een kaart-footer: toon "voorstel van Lex · [tijdstip]" — dit is het audittrail

**Stap 5 — Vraag Lex iets over een markering**
Selecteer een gele kaart → klik "Vraag Lex". Typ in het invoerveld:
> Waarom is dit een Voorwaarde en niet een Rechtsbetrekking?

Wijs aan: de chip boven het invoerveld met het fragment, het antwoord van Lex in de chat
zonder dat de annotatie verandert.

**Stap 6 — Export**
Klik "Exporteren → JSON". Open het gedownloade bestand in een teksteditor. Wijs aan:
het audittrail per element (beslissingen met tijdstip), de `agent_run`-velden (modelnaam,
provider, Critic-rondes).

---

### Technische vereisten voor de HTML

- Eén `.html`-bestand, klaar om lokaal te openen (geen server nodig)
- reveal.js 4.x via CDN (`https://cdn.jsdelivr.net/npm/reveal.js@4/`)
- Google Fonts: Fira Sans (400, 600) + Fira Mono (400)
- Geen externe afbeeldingen; gebruik SVG inline voor het stroomdiagram op dia 5
- Speaker notes zichtbaar via `S`-toets (standaard reveal.js)
- reveal.js-opties: `transition: 'fade'`, `transitionSpeed: 'fast'`, `center: false`,
  `width: 1280`, `height: 720`, `margin: 0.04`, `progress: false`,
  `slideNumber: 'c/t'`, `showSlideNumber: 'speaker'`
- Sla het bestand op als `presentatie-inning.html`

## ── EINDE PROMPT ──
