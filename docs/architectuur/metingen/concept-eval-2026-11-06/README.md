# Conceptset met model, 6 november 2026

Nulmeting vóór PR 4–6 van het verbeterplan: `azure-infra` → `eval`, `eval_set=concept`, drie runs op acceptatie
(run 42184895648, code `dbdad9b8`, 650.000 tokens per run). Geen schrijfacties op de lagen.

**Lezen met voorbehoud.** De referentie is een AI-concept dat nog geen jurist zag, en bewust onvolledig: `voorstellen - raak`
is een bovengrens voor wat onjuist is. Bij een onderdeel-casus annoteert de keten het hele lid, dus die tellen meer voorstellen dan de casus zelf toetst.
`gedekt`: dezelfde klasse op minstens de helft van het kortste fragment (`eval/scoring.py`, `klasse_dekking`).

## Nulmeting

| klasse | n | gedekt | exact | voorstellen | raak |
|---|---:|---:|---:|---:|---:|
| Afleidingsregel | 3 | 1 / 1 / 1 | 0 / 0 / 0 | 1 / 1 / 1 | 1 / 1 / 1 |
| Brondefinitie | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Delegatiebevoegdheid en delegatie-invulling | 6 | 6 / 6 / 6 | 4 / 4 / 4 | 10 / 10 / 10 | 6 / 6 / 6 |
| Operator | 2 | 2 / 2 / 2 | 1 / 1 / 1 | 14 / 14 / 14 | 2 / 2 / 2 |
| Parameter en parameterwaarde | 1 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Plaatsaanduiding | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Rechtsbetrekking | 10 | 4 / 5 / 5 | 2 / 2 / 2 | 4 / 5 / 5 | 4 / 5 / 5 |
| Rechtsfeit | 7 | 1 / 1 / 1 | 1 / 1 / 1 | 5 / 3 / 5 | 1 / 1 / 1 |
| Rechtsobject | 5 | 5 / 5 / 5 | 4 / 4 / 4 | 141 / 138 / 143 | 12 / 12 / 12 |
| Rechtssubject | 15 | 15 / 15 / 15 | 15 / 15 / 15 | 89 / 85 / 90 | 25 / 23 / 25 |
| Tijdsaanduiding | 2 | 2 / 2 / 2 | 2 / 2 / 2 | 2 / 2 / 2 | 2 / 2 / 2 |
| Variabele en variabelewaarde | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 18 / 17 / 16 | 0 / 0 / 0 |
| Voorwaarde | 7 | 5 / 5 / 5 | 1 / 1 / 1 | 39 / 39 / 39 | 6 / 6 / 6 |
| **totaal** | 58 | 41 / 42 / 42 | 30 / 30 / 30 | 323 / 314 / 325 | 59 / 58 / 60 |
