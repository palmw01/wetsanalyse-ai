# ADR-005 — Vraag Lex en de agents onder de supervisor

Status: **aangenomen, in uitvoering** · Datum: 2026-10-21 · Hoort bij: [PLAN spoor F3](../PLAN.md), [ADR-001](adr-001-hybride-jas-pijplijn.md), [ADR-004](adr-004-begrippenketen.md)

## Context

Tot F3 kende de supervisor drie workers: `antwoord`, `annotatie` en `werkgebied` (samenstellen). Bronnen
zoeken, begrippen voorstellen, meedenken en de kaartacties waren **harde routes vóór de supervisor**,
gekozen op tekstpatronen in `_stroom_voor` (`is_bronnenvraag`, `is_begrippenvraag`, `is_kaartvraag`,
`is_verdiepvraag`, `is_werkgebied_annoteervraag`). Een vraag als "is deelvraag 2 gedekt?" had geen route,
en een vraag die toevallig op een patroon leek, belandde in een route die de analist niet bedoelde.
"Vraag Lex" bestond alleen voor markeringen.

## Besluit

### Eén Vraag Lex-contract (F3b)

Vanuit elk object – markering, deelvraag, bron, kandidaat, begrip, werkgebied – stuurt de werkplek alleen
`onderwerp: {soort, werkgebied_id, id, label}`; graph-qa haalt het object bij de api (`agent/onderwerp.py`)
en zet het als context naast de vraag. Het onderwerp is **context, geen filter en geen route**. Een
markering blijft de adviesvraag (`modus: "advies"`), byte-gelijk.

### Vijf agents onder één supervisor (F3c)

De supervisor kiest uit `antwoord`, `annotatie`, `werkgebied`, **`deelvragen`** en **`begrippen`**. Voor
de agents zet hij een `TAAK:`-regel uit een vaste lijst (`agents/register.py`). De grenzen:

| Agent | Taken | Wat het níét is |
|---|---|---|
| `deelvragen` | `voorstellen`, `verbeteren` (herformuleren of splitsen), `bronnen_zoeken`, `dekking` | uitleg waarom een bepaling bij een deelvraag hoort → `antwoord`/`duiding` |
| `begrippen` | `voorstellen`, `meedenken`, `brondefinitie`, `scherper`, `voorbeelden`, `betekenisverschil`, `uitwerken`, `relaties` | de wettelijke definitie van een term → `antwoord`/`definitie` |
| `annotatie` | één bepaling (de keten van ADR-001), en `werkgebied`: het voorstel om het hele werkgebied te annoteren | – |
| `werkgebied` | een werkgebied samenstellen (activiteit 1, eigen stapmachine) | – |
| `antwoord` | vragen beantwoorden en duiden, gegrond op de graaf | – |

### De vorm van een agent

Elke agent is een Python-module (`agent/agents/`) met een vaste lijst `Taak`, een Pydantic-`Invoer` en
de gedeelde `Uitkomst` (`status` ok/bevestiging/geweigerd/fout, `reden`, `voorstellen`, `artefact`,
`bevestiging`, `tekst`, `meting`). De keten bestaat uit gewone functies. **Een model komt alleen in een
stap die een oordeel of formulering vraagt**, als één `strict` tool met validatie in code (deelvragen
opstellen en verbeteren, een definitie, voorbeelden, betekenisverschil, de twijfelparen). Zoeken,
koppelen, dekking, rangschikken en opslaan is code; er is geen vrije tool-lus. De tekst van een uitkomst
komt uit code.

### Wat een agent mag, wat de analist beslist

Een agent schrijft alleen **voorstellen en kandidaten** bij de api: deelvraagvoorstellen,
bronkandidaten (met `deelvraag_id`), kaartvoorstellen, begripsgroepen. Overnemen, aanpassen, afwijzen en
accorderen doet de analist. Wat duur is – meedenken, het hele werkgebied annoteren – levert eerst een
`bevestiging` op; pas met `bevestigd` gelijk aan de actuele werkvoorraad draait het.

### Suggesties zijn deterministisch

Een klik op een suggestie stuurt een `actie` mee (`models.ACTIE_TAAK`). De supervisor kiest dan agent en
taak **zonder model**, net als bij een meegegeven `doel`. Getypte tekst gaat altijd langs de supervisor;
de tekstpatronen zijn weg. Zo kost een klik nooit een routeringscall en kan hij niet anders uitvallen dan
de knop zegt, terwijl een vrije vraag nog altijd de juiste agent vindt.

### Uitvoering

De node `agent_taak` draait de async agent op de event loop van de beurt (`agents/uitvoering.draai`): de
api-client hoort bij die loop, de nodes zijn synchroon. Stoppen blijft een vlag (`Context.gestopt`). De
node emit `status`, de tekst als `token`, en `artefact`/`bevestiging`; de beurt-driver legt ze op het
bericht. Eén uitzondering blijft een eigen stroom: het werkgebied annoteren **met** bevestiging, omdat dat
per bepaling een gewone beurt draait (`werkgebied_annotatie_beurt`).

## Gevolgen

- De routering naar de agents is een modelbeslissing en wordt gemeten: `eval/golden_gesprek.jsonl`,
  scenario F (getypte vragen, vervolgvragen, en negatieven die bij `antwoord` horen te blijven).
- `vervangt` op een deelvraagvoorstel (de oude deelvraag automatisch intrekken bij overnemen) bestaat nog
  niet: de tekst van Lex zegt het, de analist trekt in. Komt met het deelvraagpaneel (F3d).
- Bronnen per deelvraag op lidniveau komen met de intake (F3f), via dezelfde zoekfunctie.
