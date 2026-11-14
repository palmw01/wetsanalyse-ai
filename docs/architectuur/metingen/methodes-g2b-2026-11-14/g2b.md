# G2b – de toelichting zelfstandig, parameter tegenover variabele (14 nov 2026)

Soort: *meting*, licht regime: twee vragen, één run, alleen de supervisor. Plan:
[`../../plan-methodes-scheiden.md`](../../plan-methodes-scheiden.md), deel 2, G2b. Aanleiding:
[`../methodes-g2-2026-11-14/g2.md`](../methodes-g2-2026-11-14/g2.md) §*Open*.

- **Code:** graph-qa op `b4d348a5` (bundel 107, met G2b #1461), `CENTRALE_AGENT=meten`.
- **Nulpunt:** de G2-meting op `f5b92a4e`. Die heeft cijfers voor beide vragen: k-awb67 en k-awb68.
- **Wat G2b verandert:**
  - de toelichting van `jas_klasse_opvragen` verwijst niet meer naar "hierboven";
  - de afbakening zet de parameter tegenover de variabele;
  - de tool kent gangbare namen ("Parameterwaarde" → *Parameter en parameterwaarde*).

  De `system_hash` van *duiding* is gelijk aan G1b en G2 (`22b928451b1c`). De `tools_hash` veranderde van `bd1e5c2040e6`
  in `9b441e88ec2d`.

## Kort

- **Inhoud (k-awb67): gehaald.**
  - Het antwoord zegt nu: "een tijdsaanduiding die een parameter verbijzondert — niet een zelfstandige parameterwaarde".
    De tijdsaanduiding is de specifiekere klasse, en "de parameterrelatie gaat daarbij niet verloren".
  - Het past de toets van de parameter goed toe: "Zes weken" is "voor alle bezwaar- en beroepschriften gelijk", en heeft
    "daarmee ook de kenmerken van een parameter (een constante)".
  - De fout uit G2 is weg. Daar werd de parameter verworpen omdat de waarde niet per rechtssubject verschilt.
  - Het woord *variabele* noemt het antwoord niet. Het onderscheid zit er in de toets wel in.
- **Kanttekening.** De toelichting die de tool nu teruggeeft, gebruikt zelf "zes weken" als voorbeeld, dezelfde bepaling
  als de testvraag. Dat k-awb67 nu goed gaat, zegt dus weinig over andere termijnen. Een vraag over een andere duur hoort
  bij de volgende meting.
- **Citaten letterlijk: gehaald.** Alle blokcitaten staan letterlijk in de Awb. *Gegrond* in beide beurten.
- **Omvang onder 4.000 tekens: gehaald.** In de beurt 2.252 tekens (Tijdsaanduiding) en 2.537 (*Parameterwaarde*, nu
  via de alias). Over alle dertien klassen is het grootste resultaat 3.782 tekens (Rechtsbetrekking).
- **Tool niet slechter: gehaald.**
  - k-awb67 roept de tool twee keer aan in plaats van drie, zonder foutbericht.
  - Het kost 4 rondes in plaats van 6, en 14,4k gewogen warm in plaats van 19,7k (−27 %).
  - k-awb68 roept de tool niet aan, net als in G2.
- **k-awb68 is duurder.** 26,2k → 42,9k gewogen warm (+64 %), in 8 rondes in plaats van 6. Dat komt door één weigering
  `passage_niet_te_tonen` en twee extra citaten (6:7 en 3:41 lid 1). De inhoud is even goed als in G2. G2b raakt deze
  vraag niet, want de tool werd niet aangeroepen. Met één run is dit spreiding of iets anders; dat blijft open.
- **Probe vooraf.** Na de infra-deploy is eerst gekeken of de graaf weer gevuld was. Dat gebeurde met één overzichtsvraag
  (K19, route in code, 0 tokens), die de Iw en de Awb vond. Daarna begon de meting.
- **Verbruik:** 0,21M ruw (zie §*Verbruik*).

## Wat er gemeten is

| | Commando | Vorm | Runs |
|---|---|---|---|
| Probe | `centrale_agent_meting.mjs vragen kwaliteit 1 … K19` (overzicht, zonder model) | supervisor | 1 |
| G2b | `centrale_agent_meting.mjs vragen klassen 1 … k-awb67-termijn k-awb68-aanvang` | supervisor | 1 |

- Gescoord is met `eval.centrale_agent_sets`.
- De omvang van het toolresultaat is lokaal gemeten op `b4d348a5`: de lengte van `_jas_klasse_opvragen(naam)`, met
  dezelfde namen als in de beurt.
- De inhoud heb ik beoordeeld tegen de `beoordeling` van de set en de afbakening die de tool teruggeeft.

Gegevens: [`g2b-sets.jsonl`](g2b-sets.jsonl), twee regels.

## Per vraag

| | k-awb67, G2 | k-awb67, G2b | k-awb68, G2 | k-awb68, G2b |
|---|---|---|---|---|
| Geslaagd | ja | ja | ja | ja |
| Route | *duiding* | *duiding* | *duiding* | *duiding* |
| `jas_klasse_opvragen` | 3× (één foutbericht) | 2× | 0 | 0 |
| Rondes | 6 | 4 | 6 | 8 |
| Gewogen warm | 19,7k | 14,4k | 26,2k | 42,9k |
| Koud | 46,3k (eerste begin) | 45,2k (eerste begin) | – | – |
| Weigeringen | – | – | – | `passage_niet_te_tonen` 1× |
| Citaten | 2 | 2 | 5 | 4 |

## Inhoud

**k-awb67, "zes weken" in 6:7.**

| | G2 | G2b |
|---|---|---|
| Klasse | tijdsaanduiding, "niet onder Parameter en parameterwaarde" | "een tijdsaanduiding die een parameter verbijzondert" |
| Voorrangsregel | "een vaste termijn … is de specifiekere klasse en gaat voor" | "de specifiekere klasse … maar de parameterrelatie gaat daarbij niet verloren" |
| Toets parameter | "geen waarde die … per rechtssubject verschilt, dus de parameterklasse is hier niet de juiste keuze" (fout) | "voor alle bezwaar- en beroepschriften gelijk … daarmee ook de kenmerken van een parameter (een constante)" (goed) |
| Verwijzing | "kon niet worden geverifieerd" (de "hierboven" uit de toelichting) | noemt H2:107, wat in de toelichting staat |

Het onderscheid uit de referentie staat er nu: een duur is één tijdsaanduiding die een parameter verbijzondert. Het
antwoord noemt ook de geneste parameterwaarde, voor een los getal in cijfers. Ook dat staat in de toelichting.

**k-awb68, "met ingang van de dag na die waarop het besluit … is bekendgemaakt" in 6:8 lid 1.** Het antwoord noemt
"primair een tijdsaanduiding", en de bekendmaking als het rechtsfeit dat haar activeert. Dat is de referentie. G2 zei
hetzelfde. Nieuw is dat het antwoord 3:41 lid 1 erbij citeert als de handeling van de bekendmaking. Dat is letterlijk en
klopt.

## Keuzes die ik maakte

De gebruiker sliep en vroeg bij een keuze de aanbevolen optie te nemen. Hieronder staat wat ik zelf besliste.

- **De probe vooraf is een overzichtsvraag (K19).** Die loopt via de route in code en kost geen modeltokens. De tool
  `graaf_lezen` van de acceptatie-MCP mag een agent niet gebruiken zonder de omgevingsvariabelen die de gebruiker zet.
- **De inhoud van k-awb67 beoordeel ik als *gehaald*.** Het woord *variabele* ontbreekt, maar het antwoord past de
  toets goed toe, en daar ging de fout in G2 over.
- **Het nulpunt voor k-awb68 is G2.** Die meting heeft k-awb68, dus er is een nulpunt.

## Open

1. **De toelichting gebruikt de testvraag als voorbeeld.** De afbakening noemt letterlijk "zes weken". Een volgende meting
   heeft een twijfelvraag nodig over een andere duur of een ander getal: een termijn in dagen, of een bedrag dat per
   jaar verandert.
2. **k-awb68 +64 %** door een weigering `passage_niet_te_tonen` en extra citaten. Het is één run, en de tool speelt niet
   mee. Het past bij wat de meting van #1457 liet zien: `passage_niet_te_tonen` is nu de duurste weigering.

## Verbruik

| | Ruw |
|---|---|
| Probe (K19) | 0 |
| k-awb67 | 52,5k |
| k-awb68 | 161,6k |
| **Totaal** | **0,21M** |

Bron: de delta van het accountverbruik per beurt. Over de hele meting liep het account van 60.215 naar 274.271
(+214.056). Dat is gelijk aan de som van de twee beurten, dus in die tijd verbruikte het account verder niets.
