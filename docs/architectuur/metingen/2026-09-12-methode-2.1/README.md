# Meting 12 september 2026: methode 2.1 in de legacy-keten

Soort: *meting* · Model: `claude-sonnet-4-6`, providerdefault-temperatuur · Referentie: concept
(provisional)

**Historisch.** Deze proeven liepen op de generatieve annotatieketen (annotator → Critic →
herziening), die met ADR-001 PR 18 op 25 september 2026 is verwijderd, samen met de scripts
`eval/compare_annotatie_prompts.py` en `eval/compare_methodeketen.py`. De uitkomsten verklaren
enkele projectregels in de methode (P04, P05). Ze zeggen niets over de huidige keten en zijn geen
juridische kwaliteitsscore. De methode zelf staat in
[`docs/wetsanalyse/methode-onderzoek.md`](../../../wetsanalyse/methode-onderzoek.md).

## 1. Directe annotator: oude prompt tegen protocol 2.0 (24 aanvragen)

Vier ontwikkelgevallen, drie herhalingen per variant, een identiek bronpakket, een tokenlimiet van
8192 en een wisselende volgorde. Er was geen retrieval, Critic of herziening.
Bestanden: [`modelvergelijking.json`](modelvergelijking.json) en
[`modelvergelijking-prompts.json`](modelvergelijking-prompts.json).

| Controle | Oude prompt | Protocol 2.0 | Betekenis |
|---|---:|---:|---|
| Letterlijke uitvoerfragmenten | 97/97 | 104/104 | Tekst komt voor in het corpus; geen kwaliteitsscore |
| IW01: volledige dragende invorderingszin | 0/3 | 0/3 | Beide bleven bij het losse gezegde |
| AWB04: volledige staffel als afleidingsregel | 1/3 | 3/3 | De berekening bleef beter bijeen |
| IW01: extra parameterlabel op *zes weken* | 0/3 | 2/3 | Ongewenste dubbele duiding; regressiesignaal |

## 2. Hertoets protocol 2.1 (6 aanvragen)

Protocol 2.1 schrijft de volledige normformulering bij een rechtsbetrekking explicieter voor. Het
bepaalt ook dat een gelijkblijvende tijdsduur geen extra parameterlabel rechtvaardigt (P04/P05).
Bestand: [`modelvergelijking-v21.json`](modelvergelijking-v21.json). Het ging om
ontwikkelmateriaal, dus dit is geen generalisatietoets.

| Controle IW01 | Oude prompt | Protocol 2.1 |
|---|---:|---:|
| Volledige invorderingszin als rechtsbetrekking | 0/3 | 3/3 |
| Extra parameterlabel op *zes weken* | 0/3 | 1/3 |
| Letterlijke fragmenten | 12/12 | 12/12 |

## 3. Import van de skill in de agentrollen (8 ketens)

Hier zijn vier ontwikkelcasussen door de volledige keten gegaan, vóór en na de import van het
methodepakket, met vaste openbare bronpassages. De bronselectie is daarbij niet gemeten.
Bestanden:
- [`agentimport-keten-voor.json`](agentimport-keten-voor.json)
- [`agentimport-keten-na.json`](agentimport-keten-na.json)
- [`agentimport-vergelijking.json`](agentimport-vergelijking.json)
- [`agentimport-methodepakket-gemeten.json`](agentimport-methodepakket-gemeten.json)

| Casus | Elementen vóór → na | Letterlijk vóór → na | Geel vóór → na | Rood vóór → na |
|---|---|---|---|---|
| IW01 | 5 → 5 | 5/5 → 5/5 | 1 → 4 | 0 → 0 |
| AWB04 | 9 → 8 | 9/9 → 8/8 | 6 → 4 | 0 → 0 |
| WZT01 | 15 → 16 | 15/15 → 16/16 | 8 → 7 | 0 → 0 |
| RVV03 | 9 → 10 | 9/9 → 10/10 | 4 → 6 | 1 → 0 |

Wat opviel:
- De IW-normzin en de AWB-staffel bleven in beide varianten intact.
- Bij WZT bleven korte fragmenten van rechtsbetrekking en afleidingsregel staan.
- Na de import werd *over te steken* in RVV als Rechtsobject geclassificeerd; dat moet
  inhoudelijk opnieuw beoordeeld worden.

Geel en rood zijn modeloordelen, geen onafhankelijke meting. Na de start van de proef zijn alleen
opmaak en uitleg gecorrigeerd. De 16 gemeten systeemprompts zijn byte voor byte gelijk aan de
definitieve prompts; beide pakketidentiteiten staan in het vergelijkingsbestand.

## Technische controle op dezelfde dag

- De gerichte regressies op annotatie, klassen, contractdrift, bronankers en promptpropagatie
  slaagden: 190 tests.
- De volledige graph-qa-suite slaagde: 700 tests, 16 optionele overgeslagen.
- Het wheel is geïnstalleerd zonder repository en de rolprompts werken zonder skillbestanden.
