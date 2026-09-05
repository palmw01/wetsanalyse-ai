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
**Voettekst:** Belastingdienst · Cluster Inning · *(datum van vandaag)*

_De datum wordt **dynamisch** ingevuld: zet er een `<span id="datum-vandaag">` neer en vul die
bij het laden met `new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long',
year: 'numeric' })`. Nooit een vaste datum in het bestand — die is bij de volgende demo
verouderd, en een vergeten placeholder komt als "[datum]" in beeld._

Boven de koptekst: een korte lintblauwe balk (48px breed, 4px hoog, `border-radius: 2px`) als
visueel ankerpunt. De titeldia heeft een lege, ruime opzet — geen bullets.

---

#### Dia 2 — Het startpunt — Uitvoering begint bij de wet

**Koptekst:** Uitvoering begint bij de wet

**Visueel — geen opsomming.** Deze dia is een keten in beeld: één openingsregel, drie
knelpuntkaarten met een rode bovenrand, één gevolgkaart, en daaronder een lintblauwe band met het
antwoord. Dezelfde vorm als de potentiedia (kaarten → band), zodat "probleem → antwoord" twee keer
hetzelfde ritme krijgt.

- **openingsregel:** elke invorderingsbeslissing steunt op de wet — en bij elke wetswijziging moet
  elke geraakte bepaling opnieuw worden gelezen
- **drie knelpunten:** *vraagt specialistische kennis* · *kost tijd* · *wisselt per persoon*
- **het gevolg:** de bron schuift weg — welke versie gold, en welk lid precies?
- **de band:** markeert op de actuele wettekst · elk fragment herleidbaar tot artikel, lid en
  vindplaats · de jurist beslist en blijft eindverantwoordelijk

De uitgeschreven versie (wetsanalyse maakt de juridische structuur expliciet, grondstof voor
uitvoerbare regels) hoort in de speaker notes, niet op de dia.

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

#### Dia 4 — Het Juridisch Analyseschema in één zin

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

#### Dia 5 — Eerst de bepaling, letterlijk (de casus)

**Koptekst:** Wat levert het op

Eén vraag, één antwoord, één vindplaats — drie rijen onder elkaar:

1. **De vraag** — "Wanneer is een belastingaanslag invorderbaar?" (*gewoon getypt, in je eigen woorden*)
2. **Lex zoekt** — vindt de bepaling en haalt de letterlijke tekst op (*artikel 9, eerste lid, IW 1990*)
3. **Het antwoord** — het citaat met een lintblauwe streep ervoor, en daaronder de jci op een
   **eigen regel** (inline loopt hij achter het citaat aan en breekt hij halverwege af)

Kernzin: **"Dit citaat is niet geschreven maar opgezocht — en de vindplaats komt mee."**

Neem de zin letterlijk over uit `tools/graph-qa/eval/bronteksten.json`; dat is dezelfde bron
waartegen de eval scoort.

---

#### Dia 6 — Dezelfde zin, als structuur

**Koptekst:** Dezelfde zin, als structuur

Dezelfde zin als op dia 5, nu met de markeringen eroverheen — in de **officiële klassekleuren uit
`api/app/jas_klassen.py`**, dus dezelfde die de werkplek gebruikt:

| fragment | klasse | vulling / rand |
|---|---|---|
| Een belastingaanslag | Rechtsobject | `#b2c3e3` / `#8a98b1` |
| is invorderbaar | Rechtsbetrekking | `#90a2d0` / `#707ea2` |
| zes weken na de dagtekening van het aanslagbiljet | Tijdsaanduiding | `#cbb8d6` / `#9e8fa6` |

Daaronder een legenda met een korte uitleg per klasse, en drie stappen: **Lex stelt voor → Critic
beoordeelt → jij beslist**. Kernzin: *"Van losse wettekst naar benoemde, doorzoekbare bouwstenen."*

De herhaling van dezelfde zin is opzet: eerst als betrouwbaar antwoord, dan als structuur.
De drie markeringen zijn de ankers uit `eval/golden_annotatie.jsonl` — geen illustratie.

---

#### Dia 7 — Jij beslist — de Critic

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

#### Dia 8 — Brongetrouwheid

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

#### Dia 9 — Drie lagen, één werkstroom

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

#### Dia 10 — Waar staat wat (architectuur)

**Koptekst:** Waar staat wat

**Visueel:** één inline SVG met de gegevensstroom van boven naar beneden. Elk blok draagt **twee
regels**: de technische naam én één regel gewone taal — dat is wat de dia leesbaar houdt voor zowel
een technisch als een niet-technisch publiek.

```
overheid.nl  ──►  BWB-importer (wekelijks)
                       │
                  Kennisgraaf · GraphDB      RDF · SPARQL · zoekindex
                       │  (19 vaste gereedschappen)
      Claude  ◄──►  Lex (graph-qa, LangGraph)  ──►  API · PostgreSQL
 (Azure AI Foundry)                                  auditspoor · accounts
                       │                                   │
                  Werkplek (Next.js)  ◄────────────────────┘
                       │
                  De jurist beslist
```

Rechts een aparte kolom **Meekijken**: OpenTelemetry, Application Insights, Log Analytics, Grafana.
Om het geheel een gestippeld kader: *Azure Container Apps — twee gescheiden straten (acceptatie,
productie)*.

Onder het diagram een legenda (AI-onderdeel / code die wij schreven / opslag) en de kernzin:
**"De wettekst komt rechtstreeks van overheid.nl — er zit geen kopie tussen."**

Baseer de onderdelen op `deploy/azure/main.bicep`; noem niets wat daar niet in staat.

---

#### Dia 11 — Hoe werkt Lex van binnen

**Koptekst:** Hoe werkt Lex van binnen

**Visueel:** zeven genummerde stappen onder elkaar, elk met een badge die zegt wíé de stap doet:
Supervisor (AI) · Ophalen (AI + graaf) · Annoteerder/Antwoorder (AI · op de tekst) ·
Grounding (Code) · Critic (AI) · Patch (Code) · Werkplek (Jurist).

Kernzin eronder: **"Eén stap haalt de tekst op. Alles daarna werkt op díe tekst — en kost
hoogstens vier AI-aanroepen per annotatie."**

Die badges zijn geen sfeer maar een controleerbare bewering: in de code krijgt precies één
aanroep gereedschap mee (`agent/nodes/antwoord.py`, `anthropic_schemas(only=spec.tools)`); de
supervisor, de annoteerder, de Critic en de herziener draaien alle vier met `tools=[]`. Loop dat
na vóór je de badges wijzigt.

---

#### Dia 12 — Wat Lex mag opvragen

**Koptekst:** Wat Lex mag opvragen

**Visueel:** géén opsomming van namen, maar acht clusters als tegels, met de toolnamen in
`Fira Mono` als kleine chips. Clusters: Zoeken · Tekst ophalen · Structuur · Verwijzingen ·
Begrippen · Herkomst & tijd · Regelingen · Verkennen. `raw_sparql` gestippeld: laatste redmiddel.

Daaronder een strook met de vier rollen en hoeveel gereedschap elk krijgt:
Ophalen 11 · Begrippen 9 · Duiding 17 · Algemeen 19.

Kernzin: **"Lex zoekt niet vrij in de database — hij kiest uit gereedschap dat wij bouwden en
testten."**

Neem de namen en aantallen letterlijk over uit `tools/graph-qa/agent/tools/__init__.py` en
`agent/specialists.py`; verzin er niets bij.

---

#### Dia 13 — Waarmee is dit gebouwd

**Koptekst:** Waarmee is dit gebouwd

**Visueel:** een gelaagde stapel van zes rijen; per rij de laagnaam met één regel "waarvoor", en
daarnaast de onderdelen als tegels. Geen externe logo's — alleen tekst-tegels in lintblauw.

- **Bouwen** — de code zelf schrijven en herzien: Claude Code (CLI), eigen skills, MCP naar de
  kennisgraaf, GitHub
- **Redeneren** — het taalmodel achter Lex: Claude via Azure AI Foundry
- **Kennis** — de wet opslaan en doorzoekbaar maken: GraphDB 11.4, RDF/SPARQL, Lucene, rdflib + lxml
- **Diensten** — de agent, de opslag en het scherm: Python/FastAPI, LangGraph, Next.js/React,
  Auth.js, PostgreSQL
- **Uitrollen** — Azure Container Apps, GitHub Actions, Docker/GHCR, Trivy
- **Meekijken** — OpenTelemetry, Application Insights, Grafana

Kernzin: **"Standaardonderdelen, geen eigen bouwsels — behalve de wetsanalyse zelf."**

Leid de onderdelen af uit de `pyproject.toml`/`package.json` van elk onderdeel en uit
`deploy/azure/*.bicep`.

---

#### Dia 14 — Waar we nu staan

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

#### Dia 15 — Waar dit heen kan

**Koptekst:** Waar dit heen kan

Vier kaarten, elk met een eerlijke statusregel eronder (*Werkt vandaag* / *Plan ligt er, nog niet
gebouwd* / *Gemeten, zie hieronder*):

- **Eén plek om te vragen** — vandaag de wet in gewone woorden met de vindplaats erbij;
  beleidsstukken en handleidingen kunnen er als tweede bron naast
- **Structuur die je opnieuw gebruikt** — een geannoteerde bepaling als grondstof: uitvoerbare
  regels, impact van een wetswijziging, terugvinden waar een termijn staat
- **Werk dat blijft staan** — één corpus dat aangroeit in plaats van losse documenten
- **De graaf groeit met zichzelf mee** — elke nieuwe regeling legt zijn verbindingen vanzelf

Daaronder een lintblauwe balk met de **gemeten** cijfers: 7 regelingen / 1.162 artikelen · 192
regelingen worden genoemd maar ontbreken · 1.198 verwijzingen wachten daarop (ruim een derde van
3.490) · 201× de Wet inkomstenbelasting 2001, daarna het Wetboek van Burgerlijke Rechtsvordering.

Kernzin: **"Elke wet die erbij komt, maakt de wetten die er al staan bruikbaarder."**

Meet die cijfers opnieuw vóór elke uitlevering en verifieer wetsnamen op wetten.overheid.nl —
een verzonnen citeertitel op een dia voor de Belastingdienst is precies wat dit platform niet doet.

**Toon:** dit is géén roadmap. Beschrijf wat de opzet mogelijk maakt, niet wat er gebouwd gaat
worden. Dezelfde regel geldt voor de statusdia: "nog niet" in plaats van "op de roadmap".

---

#### Dia 16 — Over naar de demo

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

### Verhaallijn en taalgebruik

De dia's lopen in zeven blokken in elkaar over: *waarom (2) → wat is het (3-4) → wat doet Lex
ermee (5-7) → waarom je het kunt vertrouwen (8) → hoe het werkt (9-13) → waar we staan (14-15) →
demo (16)*. Elke overgang moet te benoemen zijn; waar de sprong groot is staat een brugzin in de
`.kernzin`-vorm. Vertel hetzelfde niet twee keer: de casus op dia 5-7 lát zien wat een abstracte
"van vraag tot annotatie"-dia zou samenvatten, dus die dia bestaat niet.

**Schrijf elke afkorting voluit bij het eerste gebruik** — Juridisch Analyseschema (JAS),
Basiswettenbestand, Invorderingswet 1990, tweestapsaanmelding. Productnamen op de
technologiedia (RDF, SPARQL, MCP, CLI, GHCR) blijven zoals ze heten.

### Technische vereisten voor de HTML

- Eén `.html`-bestand, klaar om lokaal te openen (geen server nodig)
- reveal.js 4.x via CDN (`https://cdn.jsdelivr.net/npm/reveal.js@4/`)
- Google Fonts: Fira Sans (400, 600) + Fira Mono (400)
- Geen externe afbeeldingen; gebruik SVG inline voor het stroomdiagram op dia 10
- Speaker notes zichtbaar via `S`-toets (standaard reveal.js)
- reveal.js-opties: `transition: 'fade'`, `transitionSpeed: 'fast'`, `center: false`,
  `width: 1280`, `height: 720`, `margin: 0.04`, `progress: false`,
  `slideNumber: 'c/t'`, `showSlideNumber: 'speaker'`
- **Responsief:** media queries op ~900 px en ~600 px (rasters naar één kolom, kleinere basis,
  `overflow-y:auto` op dia's die anders afkappen), `minScale: 0.2` en `maxScale: 1.5` in
  `Reveal.initialize`, en rasters als `repeat(auto-fit, minmax(…))` in plaats van een vast
  kolomaantal. Elke SVG krijgt `viewBox` + `width:100%; height:auto`.
- **Favicon:** hetzelfde beeldmerk als de webapp (`frontend/public/favicon-32.png`), inline als
  data-URI zodat het bestand zelfstandig blijft
- Gebruik visualisaties in plaats van tekstlijsten waar dat kan; bullet-lijsten alleen als een
  beeld niets toevoegt
- Sla het bestand op als `presentatie-inning.html`

## ── EINDE PROMPT ──
