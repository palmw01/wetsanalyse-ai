# Meting keten-rekenvoorbeelden met het model (25 nov 2026)

Soort: *meting*. Vervolg op [`keten-rekenvoorbeelden-2026-11-24/`](../keten-rekenvoorbeelden-2026-11-24/README.md) (zonder
model). Code `a74c0041` (master, #1856 gemerged; `voorbeeld.py` versie 1). Plan:
[`plan-lessen-termijnen-bibliotheek.md`](../../plan-lessen-termijnen-bibliotheek.md), V8 en M2. Licht regime (ADR-010): één
run per bepaling, de gerichte set.

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
- **De vergelijking** is met de beslissingen van de jurist op acceptatie, per element op dezelfde grens. De meting vóór met
  het model is de run van 19 nov 2026 die daar ligt (Leidraad 9.5: 67 voorstellen, 16 geaccordeerd, 1 gecorrigeerd, 50
  afgewezen).

## Uitkomst

| | Leidraad 9.5 vóór (19 nov) | Leidraad 9.5 na | IW 9 lid 1 (controle) |
|---|---|---|---|
| voorbeeldzinnen herkend | – | 4 van 5 | 0 |
| voorstellen | 67 | **46** | 7 |
| waarvan in een voorbeeldzin | 42 (alle afgewezen) | **22** (13 variabelen, 6 tijdsaanduidingen, 2 operatoren, 1 rechtsobject) | 0 |
| kandidaten afgewezen met `VOORBEELD_WAARDE` (een datum) | – | 12 | 0 |
| kandidaten afgewezen met `VOORBEELD_GEEN_NORM` | – | 11 | 0 |
| kandidaten met het kenmerk `IN_VOORBEELD` | – | 28 | 0 |
| geaccordeerd of gecorrigeerd door de jurist: nog voorgesteld | 17 van 17 | **17 van 17** (16 met dezelfde klasse; de 17e is het element dat de jurist van klasse veranderde) | 6 van 6 |
| afgewezen door de jurist: niet meer voorgesteld | – | **22 van 50** (20 in een voorbeeldzin, 2 daarbuiten) | – |
| afgewezen door de jurist: nog voorgesteld | 50 | 28 (22 in een voorbeeldzin, 6 daarbuiten) | – |
| modelaanroepen | – | 11 classifier, 0 reviewer | 7 classifier, 0 reviewer |
| tokens (invoer + uitvoer, geen cache) | – | 20.975 | 9.384 |

Samen 30.359 tokens.

Wat dat zegt:

- **Het aandeel voorstellen dat de jurist afwees, daalt van 75% (50 van 67) naar hoogstens 61% (28 van 46).** Dat is een
  bovengrens: de afwijzingen zijn van vóór de regel in de skill ("wijs een markering in een voorbeeld niet af omdat het
  maar een voorbeeld is"), en van de 22 voorstellen in een voorbeeldzin horen er volgens die regel meerdere te blijven (het
  jaartal, een schrikkeljaar, de dagtekening).
- **Er vallen 22 voorstellen weg, en het zijn allemaal voorstellen die de jurist afwees.** In de voorbeeldzinnen 20 van
  de 42: de 12 data, 2 voorwaarden en 1 afleidingsregel, zoals zonder model voorspeld (de derde voorwaarde blijft, als
  tijdsaanduiding, zie hieronder), en daarnaast 5 operatoren ("vervalt op" driemaal, "valt op", "en"): die wees de
  classifier nu zelf af, met het kenmerk in zijn signalen. Of dat aan het kenmerk ligt of aan de spreiding tussen runs,
  zegt één run niet; die spreiding is groot. Buiten de voorbeeldzinnen vallen er 2 weg ("de dag", "een andere dag", door
  de jurist afgewezen als dubbel); daar komt deze stap niet aan, dus dat is spreiding.
- **Niets wat de jurist accordeerde, valt weg.** Alle 17 staan er nog, op dezelfde grens; 16 met dezelfde klasse, en de
  17e ("de dagtekening van het aanslagbiljet") stelt de keten voor als Tijdsaanduiding, zoals vóór de correctie van de
  jurist.
- **In een voorbeeldzin wordt de voorwaarde een tijdsaanduiding.** "de dagtekening van een aanslagbiljet" in het eerste
  voorbeeld was een Voorwaarde (afgewezen); de normklasse vervalt (`VOORBEELD_GEEN_NORM`) en de classifier koos de
  Tijdsaanduiding die overbleef.
- **De reviewerzin is niet geraakt.** In geen van beide bepalingen ging een twijfelgeval naar de reviewer, dus de nieuwe
  zin in `review.py` is met deze run niet gemeten.
- **Buiten een voorbeeld verandert niets door deze stap.** In IW 9 lid 1 herkent hij geen voorbeeld (`voorbeeldmeting`
  leeg, geen enkel kenmerk), en de 6 geaccordeerde elementen staan er alle zes. Eén verschil komt uit het model, niet uit
  deze stap: het element op de hele zin wordt Rechtsfeit, waar de jurist Rechtsbetrekking accordeerde. Ook buiten de
  voorbeeldzinnen van 9.5 is er één nieuw voorstel, een Voorwaarde "die hetzelfde nummer heeft als dat van de
  dagtekening" in de algemene regel. Daar komt deze stap niet aan, dus dat is spreiding tussen runs.

## Wat niet gemeten is

- **Meer runs.** Het lichte regime is één run; de verschillen buiten de voorbeeldzinnen laten zien dat de spreiding
  meetelt. Drie runs zouden zeggen of de 5 extra operatoren structureel wegvallen.
- **De reviewerzin**: er kwam geen twijfelgeval. Dat vraagt een bepaling met een rekenvoorbeeld waarin de classifier
  twijfelt.
- **Een blinde bepaling**: in de graaf heeft geen andere regeling rekenvoorbeelden (zie de vorige meting).
- **Recall tegen de referentie met het model**: de referentie is lokaal (materiaal van derden). De kandidaat-dekking stond
  in de vorige meting; hier staan alleen de voorstellen naast de beslissingen van de jurist.

## Bestanden

- `meting.py`: het script (vraagt een `.env` met de Foundry-gegevens; die staat niet in de repo).
- `uit.json`: per bepaling de tellingen, de modelaanroepen met hun gebruik, en de voorstellen (klasse, wettekst, grens,
  of ze in een voorbeeldzin liggen).
