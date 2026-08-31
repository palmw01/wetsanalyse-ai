# Prompt: genereer een HTML-presentatie over Wetsanalyse-AI (demo BRM-team)

Kopieer de volledige tekst hieronder en plak hem in een nieuw Claude-gesprek.

---

## ── BEGIN PROMPT ──

Je bent een senior presentatieontwerper met ervaring in overheidscommunicatie en juridische tools.
Maak een **reveal.js HTML-diashow** als één zelfstandig `.html`-bestand.
Geen externe afbeeldingen of bestanden — alleen CDN-links (reveal.js, Fira Sans via Google Fonts).

### Doelgroep en context

Het publiek is het **Business Rules Management-team van de Belastingdienst**: juridisch en
analytisch opgeleide mensen die wetten omzetten naar uitvoerbare bedrijfsregels. Ze kennen
de term JAS (Juridisch Analyseschema) en weten wat rechtssubjecten en rechtsbetrekkingen zijn,
maar hebben het platform nog nooit gezien.

De sessie duurt **45-60 minuten**: ~10 min presentatie (de dia's), ~35 min live demo in de
webapplicatie, ~10 min vragen.

**Toon:** zakelijk, helder, geen hype. Onderbouw claims met concrete voorbeelden uit de wet.
**Doel:** enthousiasme wekken zodat het team het platform gaat gebruiken.

---

### Stijl

- Achtergrond: wit (`#ffffff`)
- Primaire accentkleur: **lintblauw `#154273`** (koppen, lijnen, knoppen)
- Secundaire accentkleur: `#e8eff7` (lichte vlakken, kaartachtergronden)
- Lettertype: **Fira Sans** (Google Fonts; gewichten 400 en 600)
- Koppen: 600, lintblauw
- Broodtekst: 400, `#1a1a1a`
- Geen gebruik van emoji tenzij als icon-vervanging in de JAS-kleurstrip
- Accentstrips voor JAS-klassen: kleine gekleurde rechthoekjes (`8px` hoog, `border-radius: 4px`)
  met de exacte kleurwaarden uit onderstaande tabel

**JAS-klassenkleurentabel:**

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

---

### Dia-inhoud

#### Dia 1 — Titeldia

**Titel:** Lex — wetsanalyse met de kennisgraaf
**Ondertitel:** Een hulpmiddel voor gestructureerde, brongetrouwe JAS-annotatie
**Voettekst:** Belastingdienst · BRM-team · demo [datum]

_(Laat de gebruiker [datum] handmatig invullen.)_

---

#### Dia 2 — Het startpunt

**Koptekst:** BRM begint bij de wet

**Kernboodschap (opsomming, max 4 punten):**

- Van wet naar uitvoerbare regel: de wet is het vertrekpunt, niet een samenvatting ervan
- Handmatig JAS-annoteren kost tijd: een artikel met vijf leden kan tientallen markeringen bevatten
- De koppeling naar de bron raakt snel los: welke wettekstversie? welk lid precies?
- Doel van dit platform: die koppeling automatisch en controleerbaar houden

---

#### Dia 3 — Zes activiteiten van Wetsanalyse *(nieuw)*

**Koptekst:** Zes activiteiten van Wetsanalyse

**Inleiding (klein, onder de koptekst):**
Wetsanalyse werkt iteratief — activiteiten lopen in de praktijk in elkaar over.

**Visueel:** zes blokken naast elkaar in een rij. Activiteit 2 is volledig uitgelicht (lintblauw border,
lintblauwe koptekst, badge "Lex ondersteunt dit"). De overige vijf zijn gedempt (lage opacity).

| # | Naam | Korte omschrijving |
|---|---|---|
| 1 | Werkgebied bepalen | Scope en relevante bronnen vaststellen |
| **2** | **Juridische structuur zichtbaar maken** | **Formuleringen markeren en JAS-klasse toekennen** |
| 3 | Betekenis vaststellen | Begrippen, definities en afleidingsregels |
| 4 | Analyseresultaten valideren | Juistheid en volledigheid toetsen met voorbeelden |
| 5 | Ontbrekende beleidsregels signaleren | Leemten in uitvoeringsbeleid in kaart brengen |
| 6 | Kennismodel opstellen | Gegevens-, regel- en procesmodel samenbrengen |

**Voetnoot onder de blokken:**
Activiteiten 3–6 doe je nu zelf. Activiteit 1 ook — Lex helpt daarbij wel bij het zoeken van relevante
bronnen en het volgen van verwijzingen. De volgende stap is activiteit 2 agentisch uitbreiden naar activiteit 3.

*Bron: Handleiding Wetsanalyse in de Praktijk, Expertisecentrum BRM, Belastingdienst, versie 1.0 (2023).*

---

#### Dia 4 — Wat is JAS (kort)

**Koptekst:** Het Juridisch Analyseschema in één zin

**Kernboodschap:**
JAS verdeelt de wettekst in **13 klassen** — van rechtssubject tot delegatiebevoegdheid —
zodat elke zin van de wet terug te vinden is als een benoemd, gestructureerd element.

**Visueel element:** een horizontale strip van 13 gekleurde rechthoekjes (de kleuren uit de tabel
hierboven), elk gelabeld met de klassenaam in kleine letters. Onder de strip: de tekst
"De jurist beslist — de AI stelt voor."

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

---

#### Dia 6 — De drie stappen

**Koptekst:** Van vraag tot beoordeelde annotatie

**Drie blokken naast elkaar (ieder met een koptekst + twee zinnen):**

**1 · Stel een vraag**
Typ een juridische vraag in de werkplek: "Binnen welke termijn is een naheffingsaanslag
invorderbaar?" Lex zoekt in de graaf, haalt artikel 9 Invorderingswet 1990 op en antwoordt met
een letterlijk citaat en een bronverwijzing.

**2 · Ontvang een annotatie**
Vraag een JAS-annotatie: "annoteer artikel 36 lid 4 van de Invorderingswet 1990." Lex haalt de
exacte wettekst op, stelt markeringen voor in alle van toepassing zijnde JAS-klassen, en laat de
Critic elk element controleren.

**3 · Beoordeel en beslis**
Elk voorstel verschijnt als een kaart: aandachtsniveau (groen/geel/rood), klassenaam,
fragment, toelichting. Jij drukt op Akkoord of Verwerpen. Wat jij beslist staat in het
audittrail, met tijdstip en naam.

---

#### Dia 7 — Brongetrouwheid

**Koptekst:** Geen fragment zonder bron

**Kernboodschap (twee kolommen of opsomming):**

- Elk JAS-element bevat het **letterlijke tekstfragment** uit de opgehaalde wettekst
- Een algoritme (geen tweede AI-aanroep) controleert: staat dit citaat écht in de tekst die
  uit de graaf is gehaald?
- Als het er niet in staat, markeert de werkplek het en legt Lex uit waarom
- Resultaat: elk element is herleidbaar naar een **jci-uri** (de officiële verwijzing naar
  artikel + lid + bwb-identificatie)

**Voorbeeld (als code-blok of gekleurd tekstvak):**
```
jci1.31:c:BWBR0004770&artikel=36&lid=4
Invorderingswet 1990, art. 36 lid 4
```

---

#### Dia 8 — De Critic

**Koptekst:** Jij beslist — de AI controleert zichzelf

**Drie niveaus als gekleurde kaartjes (gebruik de kleur als linkerbalk):**

🟢 **Geen bezwaar** (linkerbalk groen `#4caf50`)
Het element klopt: klasse, fragment en afbakening zijn correct. Snel door met Akkoord.

🟡 **Even kijken** (linkerbalk amber `#f59e0b`)
De Critic twijfelt — bijvoorbeeld Voorwaarde of Afleidingsregel? De kaart toont een
alternatief als klikbare chip. Jij kiest; je keuze staat in het audittrail.

🔴 **Waarschijnlijk fout** (linkerbalk rood `#ef4444`)
De Critic heeft de correctie al doorgevoerd in de code (niet door een tweede AI-aanroep).
Wat er stond en waarom het is aangepast, is zichtbaar in de kaart.

**Ondertekst:** "Het model doet wat zeker is automatisch. Wat twijfelachtig is, legt het voor."

---

#### Dia 9 — Over naar de demo

**Koptekst:** Laten we het zien

**Drie bullets (wat we in de demo gaan doen):**
- Een vraag stellen en het antwoord met bronvermelding bekijken
- Artikel 36 lid 4 Invorderingswet 1990 laten annoteren
- De review doorlopen: akkoord geven, een alternatief kiezen, Lex iets vragen

**Grote lintblauwe tekst centraal:** "De werkplek staat klaar."

**Klein onder:** Acceptatie-omgeving · let op: analyses kunnen verloren gaan

---

### Demo-script (voor in de sprekersnoten van elke demo-dia)

Voeg aan de HTML een verborgen `<section class="demo-stap">` toe voor elke demo-stap, zodat
de presentator ze kan doorlopen met de pijltoetsen maar ze niet op het scherm komen bij normale
weergave. Of zet ze als `<aside class="notes">` in de reveal.js speaker notes.

**Stap 1 — Rondleiding**
Klik "Laat me de werkplek zien" op het lege gespreksvenster. Loop de 13 rondleiding-stappen
door: gespreksvenster → sidebar → invoerveld → bronnen → brongetrouwheid → denkproces →
annotatie openen → wettekst → reviewlijst → reviewkaart → Jij beslist (hier: echt op Akkoord
klikken) → zelf markeren → afronden.

**Stap 2 — Vraag stellen**
Typ in het invoerveld:
> Binnen welke termijn is een naheffingsaanslag invorderbaar?

Wacht tot het antwoord volledig is. Wijs aan: het denkproces-blok (inklapbaar), de
bronnen-collapsible, de brongetrouwheid-indicatie. Klik de bron open om de jci-uri te tonen.

**Stap 3 — Annotatie aanvragen**
Typ:
> annoteer artikel 36 lid 4 van de Invorderingswet 1990

Wacht ~60-90 seconden. Wijs aan: de annotatie-chip die verschijnt, het automatisch openen
van het ArtefactPaneel, het denkproces-logje ("supervisor koos de annotatie-worker · Critic
las mee").

**Stap 4 — Review doorlopen**
- Wijs de drie aandacht-niveaus aan in de reviewlijst (filter op "Met aandacht")
- Selecteer een gele kaart, wijs het alternatief aan als klikbare chip, klik het om te wisselen
- Druk `a` om een kaart te accorderen — de kaart wordt grijs, selectie springt door
- Open een kaart-footer: toon "voorstel van Lex · [tijdstip]"

**Stap 5 — Vraag Lex iets over een markering**
Selecteer een gele kaart, klik "Vraag Lex". Typ in het invoerveld:
> Waarom is dit een Voorwaarde en niet een Afleidingsregel?

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
- Google Fonts voor Fira Sans (400, 600)
- Geen externe afbeeldingen; gebruik SVG inline voor het stroomdiagram op dia 4
- Speaker notes zichtbaar via `S`-toets (standaard reveal.js)
- Sla het bestand op als `presentatie-brm.html`

## ── EINDE PROMPT ──
