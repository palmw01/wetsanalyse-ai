# Betekenisonderzoek (spoor M), 28 oktober 2026

Meting bij de PR-stapel M1–M4 (#774–#777): contextbewuste begripsvorming. Plan, opdrachttoets en
afwijkingen staan in [`../../plan-betekenisonderzoek.md`](../../plan-betekenisonderzoek.md).

**De casussen zijn een ontwikkelset.** Casus A en B zijn de twee foutgevallen uit de opdracht, en de
toetsen zijn met die gevallen in gedachten ontworpen. De cijfers laten zien dat het mechanisme doet
wat het moet doen op deze twee gevallen. Ze zeggen niet dat het generaliseert. Of de definities juridisch
juist zijn, beoordeelt een jurist.

## Casussen

`tools/graph-qa/eval/betekenisonderzoek_casus.json`: art. 30fb en 30fc AWR, alle leden en onderdelen,
letterlijk uit de graaf op acceptatie, met `bron_hash` = `bronmodel.tekst_hash`.

- **A**: "herziening" in 30fb lid 4. De leden 1–6 beginnen met "Bij herziening van een voorlopige
  aanslag …" en verschillen in de bedragovergang.
- **B**: "belasting" in 30fc lid 1 en 2 (de passage "te betalen bedrag aan belasting"). Lid 7
  kwalificeert *het te betalen bedrag aan belasting*.

## 1. Regressie van de keten (offline, geen model)

`python -m eval.begrippen_eval --variant keten` op v1, heldout-v1 en heldout-v2: na M2 is het rapport
**bitgelijk** aan de nulmeting (alle sleutels gelijk; v1 F 1,000, heldout-v1 0,956, heldout-v2 0,973).
Zonder onderzoek verandert de keten dus niets. Het nieuwe tegen-signaal `BEREKENING_IN_BEPALING` gaat op
geen van die sets af. Voor die regel is er dus nog geen held-out-bewijs.

Gegevens: `nulmeting-keten-*.json`, `m2-keten-*.json`.

## 2. Het mechanisme (offline, geen model)

`python -m eval.betekenisonderzoek_eval`: de foutdefinities uit de opdracht, getoetst zonder dossier
(oud) en met dossier (nieuw).

| | context (bepalingen) | foutdefinitie gemarkeerd | scherper-prompt |
|---|---|---|---|
| A | 1 → 8 | oud nee, nieuw ja (`ALGEMENE_NAAM_SPECIFIEKE_DEFINITIE`) | 2.139 → 7.039 tekens |
| B | 2 → 10 | oud nee, nieuw ja (`RECHTSGEVOLG_IN_DEFINITIE`, `TEGENBEWIJS_IN_ONDERZOEK`) | 2.088 → 4.832 tekens |

Ook bij een budgettekort en bij een onbereikbare graaf herkent het dossier de parallelle leden nog, en
het meldt dan `CONTEXT_NIET_ONDERZOCHT`. Het rapport is deterministisch.

Gegevens: `m2-betekenisonderzoek-eval.json`.

## 3. Live: kaart, scherper en voorbeelden (3 runs, vóór en na)

Opzet:

- per casus en per run drie aanroepen: kaart, scherper en voorbeelden op een vaste definitie;
- vóór = `origin/master` (`03739283`), zonder onderzoek;
- na = deze branch, met het onderzoek zoals de api het zou bouwen (de andere leden van het artikel);
- model `claude-sonnet-4-6` via Azure AI Foundry, lokaal, zonder graaf (de casussen zijn offline);
- scripts `live_meet.py` en `live_scoor.py`, ruwe uitvoer `live-voor.json` en `live-na.json`.

**Eén meetlat** voor beide versies: de nieuwe toetsen met het dossier, op elke voorgestelde definitie
(kaart en scherper, niet letterlijk). Telt mee als een van de kernsignalen afgaat:
`ALGEMENE_NAAM_SPECIFIEKE_DEFINITIE`, `RECHTSGEVOLG_IN_DEFINITIE`, `AFLEIDING_IN_DEFINITIE` of
`TEGENBEWIJS_IN_ONDERZOEK`.

| | vóór | na |
|---|---|---|
| voorgestelde definities (6 runs × kaart + scherper) | 6 | 5 |
| met een kernsignaal | **6 / 6** | **1 / 5** |
| A: scherper | 3× de variant van lid 4 ("… met een negatief bedrag tot … positief") | 3× algemeen ("wijziging van een voorlopige aanslag IB/Vpb waarbij het bedrag verandert"), duiding *begrip, algemeen* |
| B: scherper | 3× "het bedrag dat de belastingplichtige verschuldigd is op grond van een aanslag …" (de samenstelling, onder de naam *belasting*) | 3× afgezien: "Onvoldoende bewijs: de fragmenten definiëren de kale term niet; lid 7 kwalificeert alleen de samenstelling" |
| kaart | 6× geen definitie (circulair verworpen) | A: 1× algemeen geformuleerd; B: 1× samengesteld uit lid 7 (`AFLEIDING_IN_DEFINITIE`, duiding *specifiek*, voorkeursterm "te betalen bedrag aan belasting"); 4× afgezien met een reden |
| voorbeelden met een tegenvoorbeeld | 6 / 6 | 6 / 6 |
| voorbeelden met een soort (positief, tegenvoorbeeld, grensgeval, afwijkend) | – | 29 / 29 |
| tokens per aanroep (mediaan: kaart / scherper / voorbeelden) | 1.672 / 2.117 / 1.860 | 3.787 / 4.120 / 3.915 |
| duur per casus, drie aanroepen (mediaan) | 32 s | 46 s |

Lezing:

- **A** doet wat de opdracht vroeg: de algemene definitie in plaats van een toepassingsgeval.
- **B** voorkomt dat de samenstelling onder de kale naam terechtkomt. Lex ziet nu meestal af met een
  reden en wijst één keer de samenstelling aan als specifiek begrip, met de verrekening gemarkeerd. Of
  "belasting" hier een eigen begrip moet krijgen, en met welke definitie, beslist de jurist.
- Het verbruik verdubbelt ongeveer, vooral door de extra fragmenten en het dossier in de prompt.
- **Kanttekening bij de meetlat**: de toetsen zijn met deze twee gevallen in gedachten gemaakt. "1 / 5
  tegen 6 / 6" is dus geen onafhankelijk kwaliteitsoordeel. De definities zelf staan in `live-score.json`.
