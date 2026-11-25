# Meting keten-rekenvoorbeelden met het model (25 nov 2026)

Soort: *meting*. Vervolg op [`keten-rekenvoorbeelden-2026-11-24/`](../keten-rekenvoorbeelden-2026-11-24/README.md) (zonder
model). Code `a74c0041` (master, #1856 gemerged; `voorbeeld.py` versie 1). Plan:
[`plan-lessen-termijnen-bibliotheek.md`](../../plan-lessen-termijnen-bibliotheek.md), V8 en M2. Eerst één run (licht regime, ADR-010), daarna op verzoek van de
eigenaar drie runs extra en een nulmeting op dezelfde code (twee runs zonder de stap).

## Opzet: de keten met het model, zonder schrijfpad

`meting.py` draait `jas_pipeline.keten.analyseer` met het echte model op de tekst van de bepaling zoals die op acceptatie
staat (`acc.json` van de vorige meting). Er is geen api in het spel. Niets komt in een laag, en de geaccordeerde laag van
Termijnen blijft ongemoeid: er is niets heropend of overschreven. Lex op acceptatie kon dit niet: een beurt met
`hergebruik: "opnieuw"` op een geaccordeerde laag stopt vóór de analyse (`AFGEROND`).

- **Model en instellingen zoals op acceptatie** (25 nov 2026): `claude-sonnet-4-6` voor de classifier en de reviewer (de
  modelkeuzes in het beheer: geen eigen keuze, het standaardprofiel), dezelfde Foundry-dienst, de standaardinstellingen van
  `Settings` en `RELATIE_VOORSTELLEN=true`.
- **Wat anders is dan een beurt op acceptatie**: de snapshot is de bepaling alleen, zonder ouder en zonder broncontext
  (`BronContext` leeg). Op deze twee bepalingen zonder verwijzingen raakt dat de classifier hooguit via het contextblok.
- **De nulmeting** is dezelfde code met `--zonder-voorbeeldstap`: de keten slaat de stap uit `voorbeeld.py` over. Dat is
  nodig omdat de run die op acceptatie ligt (19 nov 2026) van oudere code is: sinds die dag veranderde de keten ook op
  andere punten (onder meer #1842 en #1853). Het verschil tussen de nulmeting en de runs met de stap komt alleen van de stap.
- **De vergelijking met de jurist** is met de beslissingen op acceptatie, per element op dezelfde grens (Leidraad 9.5: 67
  voorstellen van 19 nov, 16 geaccordeerd, 1 gecorrigeerd, 50 afgewezen).

## Uitkomst

Vier runs met de stap, twee zonder. De twee runs zonder de stap zijn identiek; de vier met de stap verschillen onderling in
hoogstens drie voorstellen. Op IW 9 lid 1 zijn alle zes runs identiek.

| Leidraad 9.5 | acceptatie (19 nov, oudere code) | zonder de stap (2 runs) | met de stap (4 runs) |
|---|---|---|---|
| voorstellen | 67 | 64 | **44–46** |
| waarvan in een voorbeeldzin | 42 | 41 | **20–22** |
| kandidaten afgewezen met `VOORBEELD_WAARDE` (een datum) | – | – | 12 |
| kandidaten afgewezen met `VOORBEELD_GEEN_NORM` | – | – | 11 |
| kandidaten met het kenmerk `IN_VOORBEELD` | – | – | 28 |
| geaccordeerd of gecorrigeerd door de jurist: nog voorgesteld | 17 van 17 | 17 van 17 | **17 van 17** (elke run) |
| afgewezen door de jurist: nog voorgesteld | 50 van 67 (75%) | 46 van 64 (72%) | **26–28 van 44–46 (59–61%)** |
| modelaanroepen per run | – | 11 classifier, 0 reviewer | 11 classifier, 0 reviewer |
| tokens per run (invoer + uitvoer, geen cache) | – | 21.958 | 20.975–21.398 |

IW 9 lid 1 (controle), in alle zes runs: 7 voorstellen, geen voorbeeldzin, geen kenmerk, de 6 geaccordeerde elementen
staan er alle (5 met dezelfde klasse), 7 classifieraanroepen, 9.384 tokens.

Tokens samen: 184.574 (vier runs met en twee zonder de stap, beide bepalingen).

Wat dat zegt:

- **De stap haalt in elke run dezelfde 20 voorstellen weg, en de jurist had ze alle afgewezen.** Het gaat om alle in een
  voorbeeldzin:
  - 12 data;
  - 5 operatoren ("vervalt op" driemaal, "valt op", "en");
  - 2 voorwaarden;
  - 1 afleidingsregel.

  Dat de operatoren wegvallen, is dus geen spreiding: zonder de stap zijn ze er in beide runs, met de stap in geen enkele.
  De classifier wijst ze af met het kenmerk in zijn signalen.
- **De stap voegt twee voorstellen toe.** Zonder de stap stelt de keten ze niet voor; in de run van 19 nov stonden ze er wel,
  en de jurist wees ze af, vóór de regel in de skill:
  - "het jaartal" (Variabele, in het voorbeeld van het schrikkeljaar). Zonder de stap stond daar alleen de voorwaarde
    "tenzij het jaartal aangeeft dat het een schrikkeljaar is", en die vervalt als normklasse. Volgens de skill hoort dit
    voorstel er te zijn: het jaartal is een kenmerk dat een regel nodig heeft.
  - "hetzelfde nummer" (Variabele), buiten de voorbeeldzinnen, in de algemene regel. Daar komt de stap niet aan; het is
    een gevolg van de gewijzigde kandidatenset in dezelfde alinea.
- **Niets wat de jurist accordeerde, valt weg**, met of zonder de stap, in geen van de zes runs. De gecorrigeerde
  ("de dagtekening van het aanslagbiljet") stelt de keten in alle runs voor als Tijdsaanduiding, de klasse van vóór de
  correctie; dat staat los van de stap.
- **Het aandeel afgewezen daalt door de stap van 72% naar 59–61%.** Dat is nog een bovengrens: de afwijzingen zijn van
  vóór de regel in de skill ("wijs een markering in een voorbeeld niet af omdat het maar een voorbeeld is"), en van de
  20–22 voorstellen die in een voorbeeldzin blijven, horen er volgens die regel meerdere te blijven. Vooral variabelen
  (12–13) en tijdsaanduidingen (6), zoals het jaartal, een schrikkeljaar en de dagtekening.
- **Wat in de eerste run op spreiding leek, is van andere code.** "de dag" en "een andere dag" buiten de voorbeeldzinnen,
  de nieuwe Voorwaarde "die hetzelfde nummer heeft als dat van de dagtekening" en de Rechtsfeit-klasse op de hele zin van
  IW 9 lid 1 staan in alle zes runs gelijk, met en zonder de stap. Ze komen dus uit wat er tussen 19 nov en `a74c0041` aan
  de keten veranderde, niet uit deze stap en niet uit het model.
- **De spreiding tussen runs is klein.** De vier runs met de stap verschillen alleen in "tenzij" (Operator, in een
  voorbeeldzin, door de jurist afgewezen; valt in twee runs weg) en "de dagtekening" (Variabele, in een voorbeeldzin,
  afgewezen; valt in één run weg).
- **De reviewerzin is niet geraakt.** In geen van de runs ging een twijfelgeval naar de reviewer, dus de nieuwe zin in
  `review.py` is niet gemeten.

## Wat niet gemeten is

- **De reviewerzin**: er kwam geen twijfelgeval. Dat vraagt een bepaling met een rekenvoorbeeld waarin de classifier
  twijfelt.
- **Een blinde bepaling**: in de graaf heeft geen andere regeling rekenvoorbeelden (zie de vorige meting).
- **Recall tegen de referentie met het model**: de referentie is lokaal (materiaal van derden). De kandidaat-dekking stond
  in de vorige meting; hier staan alleen de voorstellen naast de beslissingen van de jurist.

## Bestanden

- `meting.py`: het script (vraagt een `.env` met de Foundry-gegevens; die staat niet in de repo).
- `uit.json`: `met_voorbeeldstap` (vier runs) en `zonder_voorbeeldstap` (twee runs); per run en bepaling de tellingen, de
  modelaanroepen met hun gebruik, en de voorstellen (klasse, wettekst, grens, of ze in een voorbeeldzin liggen).
