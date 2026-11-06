# Conceptset met model, nameting, 6 november 2026

Nameting na PR 4–6 van het verbeterplan: `azure-infra` → `eval`, `eval_set=concept`, drie runs op acceptatie
(run 42209413630, graph-qa `25424a4c`, circa 650.000 tokens per run). Dezelfde lezing en voorbehouden als de
[nulmeting](../concept-eval-2026-11-06/README.md): een AI-concept dat nog geen jurist zag, en bewust onvolledig.

## Nameting

| klasse | n | gedekt | exact | voorstellen | raak |
|---|---:|---:|---:|---:|---:|
| Afleidingsregel | 3 | 1 / 1 / 1 | 0 / 0 / 0 | 1 / 1 / 1 | 1 / 1 / 1 |
| Brondefinitie | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Delegatiebevoegdheid en delegatie-invulling | 6 | 6 / 6 / 6 | 4 / 4 / 4 | 10 / 10 / 10 | 6 / 6 / 6 |
| Operator | 2 | 2 / 2 / 2 | 2 / 2 / 2 | 14 / 14 / 14 | 2 / 2 / 2 |
| Parameter en parameterwaarde | 1 | 1 / 1 / 1 | 1 / 1 / 1 | 1 / 1 / 1 | 1 / 1 / 1 |
| Plaatsaanduiding | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Rechtsbetrekking | 10 | 5 / 5 / 5 | 2 / 2 / 2 | 5 / 5 / 5 | 5 / 5 / 5 |
| Rechtsfeit | 7 | 1 / 1 / 1 | 1 / 1 / 1 | 5 / 5 / 5 | 1 / 1 / 1 |
| Rechtsobject | 5 | 5 / 5 / 5 | 4 / 4 / 4 | 131 / 127 / 130 | 12 / 12 / 12 |
| Rechtssubject | 15 | 15 / 15 / 15 | 15 / 15 / 15 | 97 / 94 / 95 | 26 / 25 / 25 |
| Tijdsaanduiding | 2 | 2 / 2 / 2 | 2 / 2 / 2 | 2 / 2 / 2 | 2 / 2 / 2 |
| Variabele en variabelewaarde | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 13 / 14 / 10 | 0 / 0 / 0 |
| Voorwaarde | 7 | 5 / 5 / 5 | 1 / 1 / 1 | 39 / 40 / 39 | 6 / 6 / 6 |
| **totaal** | 58 | 43 / 43 / 43 | 32 / 32 / 32 | 318 / 313 / 312 | 62 / 61 / 61 |

## Tegen de nulmeting

- Gedekt 41–42 naar 43 van 58, en exact 30 naar 32: de aantalsregels leveren Operator en Parameter op, Rechtsbetrekking is stabiel op 5.
- Voorstellen 314–325 naar 312–318. Rechtsobject 138–143 naar 127–131 en Variabele 16–18 naar 10–14; Rechtssubject stijgt van 85–90 naar 94–97.
- **Rechtsfeit bleef 1 van 7.** De reparatie haalde Rechtsobject weg, maar het model koos daarna niet Rechtsfeit: bij de heropname op acceptatie kregen alle zes nominalisaties met een eigen voorwerp "geen annotatie", terwijl Rechtsfeit en Voorwaarde waren toegestaan. De klasse krijgt dus niet meer treffers. Of dat een fout is, is een juridische vraag: de referentie is een concept, en een rechtsfeit vraagt een rechtsgevolg (H2:53).

## Heropname op acceptatie

Vier bepalingen uit het werkgebied opnieuw geannoteerd met `hergebruik: opnieuw`: 4 van 4 opgeslagen (vóór #881: 0 van 4). De slottekst noemt het aantal nieuw en het aantal dat er al lag. De centrale norm van Awir 25 lid 1 werd in deze run door de reviewer herbeoordeeld tot Rechtsbetrekking. Eén run per bepaling, dus een controle en geen meting.
