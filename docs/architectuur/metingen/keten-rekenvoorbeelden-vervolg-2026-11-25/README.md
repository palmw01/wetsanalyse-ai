# Meting keten-rekenvoorbeelden, vervolg (25 nov 2026)

Soort: *meting*. Vervolg op [`keten-rekenvoorbeelden-model-2026-11-25/`](../keten-rekenvoorbeelden-model-2026-11-25/README.md).
Plan: [`plan-lessen-termijnen-bibliotheek.md`](../../plan-lessen-termijnen-bibliotheek.md), M2, *Vervolg*. Code: de branch
`claude/keten-voorbeeld-vervolg` op `d2a25585` (master), met vier wijzigingen in de annotatieketen:

1. een tijdstip zonder van-bepaling ("de dagtekening") krijgt hetzelfde bewijs als het tijdstip met van-bepaling dat de
   tekst al noemt: tijd gaat voor variabele (H2:107);
2. de duur in een herhaling ("een maand" in "een maand later") is de kern ervan en krijgt geen eigen markering;
3. met een voorwaarde ervoor is de hoofdzin geen tweede Afleidingsregel naast de ALS→DAN-zin;
4. een operator in een rekenvoorbeeld vervalt, zoals de normklassen (`voorbeeld.py` versie 2).

Twee delen: zonder model op vier hele regelingen (wat verandert er buiten 9.5?), en met het model op Leidraad 9.5 en
IW 9 lid 1 (twee runs, zonder schrijfpad, zoals de vorige meting).

## Zonder model: vier regelingen

`haal.py` haalt de huidige toestand van de Invorderingswet 1990, de Leidraad Invordering 2008, de AWR en de Awb bij
overheid.nl, met de lezer van de importer. `kandidaten.py` draait detectie, fusie, de voorbeeldstap en het vaste besluit
op elke node waarvan de tekst een tijdstip, "later"/"eerder", "vervalt", "indien" of "als" noemt (1873 nodes), één keer
met de code van master en één keer met de branch. `verschil.py` telt de verschillen (`verschil.txt`).

15 van de 1873 nodes zijn geraakt, alle op de bedoelde punten:

| verschil | aantal | waar |
|---|---|---|
| de hoofdzin van een ALS→DAN-regel verliest Afleidingsregel (blijft Rechtsbetrekking of Rechtsfeit) | 9 | Leidraad 9.5 (3), AWR 16 lid 4, 20 lid 4, 30g lid 3, Awb 4:23 lid 2, 5:45 lid 1, 9:24 lid 2 |
| de duur in "telkens een maand/jaar later" is kern, geen vast besluit meer | 8 | IW 9 lid 5–7, 25a lid 3, 25b lid 1, 70g lid 3, 70h lid 3; Leidraad 9.5 |
| een operator in een voorbeeldzin vervalt | 7 | alleen Leidraad 9.5 |
| "de dagtekening", "het tijdstip" zonder van-bepaling: Tijdsaanduiding in plaats van Variabele | 5 | Leidraad 9.5 (4), AWR 5b lid 7 |

Er verdwijnt geen kandidaat. De ALS→DAN-zin houdt in alle negen gevallen Afleidingsregel, met de hoofdzin als optie.
De jurist wees in IW 9 lid 5 op acceptatie "een maand" los af en keurde "telkens een maand later" goed; dat is wat
punt 2 doet.

## Met het model: Leidraad 9.5 en IW 9 lid 1

Dezelfde opzet als de vorige meting: `../keten-rekenvoorbeelden-model-2026-11-25/meting.py`, `claude-sonnet-4-6`, de
tekst van acceptatie, geen api. Twee runs; ze zijn identiek.

| Leidraad 9.5 | met de stap, vóór dit vervolg (4 runs) | na dit vervolg (2 runs) |
|---|---|---|
| voorstellen | 44–46 | **39** |
| waarvan in een voorbeeldzin | 20–22 | **16** |
| afgewezen door de jurist, toch voorgesteld | 26–28 (59–61%) | **21 (54%)** |
| geaccordeerd of gecorrigeerd: nog voorgesteld | 17 van 17 (16 dezelfde klasse) | 17 van 17 (15 dezelfde klasse) |
| `VOORBEELD_WAARDE` / `VOORBEELD_GEEN_NORM` / `IN_VOORBEELD` | 12 / 11 / 28 | 12 / 18 / 21 |
| modelaanroepen | 11 classifier, 0 reviewer | 11 classifier, 0 reviewer |
| tokens per run | 20.975–21.398 | 19.243–19.446 |

IW 9 lid 1: in beide runs gelijk aan vóór (7 voorstellen, 6 van 6 geaccordeerd, 9.384 tokens).

Wat dat zegt:

- **Er vallen 9 voorstellen weg, waarvan de jurist er 8 afwees:**
  - de operatoren "tenzij" en "dan wel" in een voorbeeldzin (punt 4);
  - "een maand" binnen "een maand later" (punt 2);
  - de Afleidingsregel op de hoofdzin "vervalt de termijn een maand later …" (punt 3);
  - "de dagtekening" in de voorbeeldzinnen (drie keer) en "de dagtekening van een aanslagbiljet" in het eerste voorbeeld.
    Ook als Tijdsaanduiding stelt de keten ze niet meer voor.
- **De negende is een klassewissel, geen verlies.** "de dagtekening" in de algemene regel accordeerde de jurist als
  Variabele; de keten stelt haar nu voor als Tijdsaanduiding, zoals H2:107 vraagt en zoals de jurist dezelfde formulering
  in IW 9 lid 1 goedkeurde. Daarom zakt "dezelfde klasse" van 16 naar 15. Dat is een punt voor de jurist (plan, M2
  *Vervolg*).
- **Punt 3 is half gelukt.** De hoofdzin is geen Afleidingsregel meer, maar het model stelt haar nu voor als Rechtsfeit
  (de jurist wees die grens af). Het voorstel blijft dus, met een andere klasse. Of de hoofdzin van een ALS→DAN-regel een
  eigen Rechtsbetrekking of Rechtsfeit mag dragen, is een vraag over de methode: de markeringslijst noemt bij één normzin
  de hele zin het dragende fragment. Dat is niet in deze ronde beslist.
- **Het aandeel afgewezen daalt van 59–61% naar 54%.** Dat blijft een bovengrens: de afwijzingen zijn van vóór de regel
  in de skill, en "het jaartal", "een schrikkeljaar" en "hetzelfde nummer" staan er nog, terwijl de skill ze als kenmerk
  noemt.
- **De reviewerzin is nog steeds niet geraakt**: geen twijfelgeval.

Tokens samen (twee runs, beide bepalingen): 57.457.

## Bestanden

- `haal.py`, `kandidaten.py`, `verschil.py`: het deel zonder model (de teksten zelf staan niet in de repo; ze komen
  van overheid.nl).
- `verschil.txt`: de verschillen tussen master en de branch, per soort met voorbeelden.
- `uit.json`: de twee runs met het model, per bepaling in de vorm van de vorige meting.
