# Briefing: reviewer van Lex Bench

Soort: *werkinstructie* · Plan: [`../architectuur/plan-lex-bench.md`](../architectuur/plan-lex-bench.md) §5, §22 besluit 4
· Profiel: [`.claude/agents/bench-reviewer.md`](../../.claude/agents/bench-reviewer.md)

Het eerste deel van deze briefing gaat mee in de opdracht van de reviewer (`eval/lex_bench_review.py`). Het tweede deel
is voor de coördinator.

## Voor de reviewer

### Modus verschillen

Je krijgt de verschillen tussen de keuze van Lex en de bevroren teamverwachting, elk met een nummer (`V1`, `V2`, …).
De code stelt per verschil al een categorie voor. Jij beoordeelt ze tegen de bron:

- **Lex mist** (`lex_mist`): de bepaling hoort bij de deelvraag, en Lex noemt haar niet. Kan alleen bij een verschil
  waar Lex de bepaling niet koos.
- **Lex onterecht** (`lex_onterecht`): Lex kiest een bepaling die er niet bij hoort, of die het team uitsloot. Kan
  alleen bij een bepaling die Lex koos.
- **Team mist** (`team_mist`): Lex koos een bepaling die er wél bij hoort, en het team miste haar. Ook dat kan alleen
  bij een bepaling die Lex koos. De bevroren teamverwachting verandert er niet door: de bepaling komt in de volgende
  versie van de casus, met `nagekomen: true`.
- **Twijfel** (`twijfel`): zonder de jurist is er geen uitspraak. Twijfel is een eerlijke uitkomst, geen fout.

Geef bij Lex mist en Lex onterecht de **plek** als je die kunt zien. `niet_in_pool`: Lex vond de bepaling niet.
`laag_gerangschikt`: Lex vond haar wel, maar te laag. `verkeerde_rol`: de bepaling is goed gekozen, maar met een
verkeerde rol. Kun je het niet zien, kies dan `onbekend`. De plek is de brug naar een generieke verbetering, dus
gok niet.

Elk verschil krijgt precies één oordeel, met zijn nummer (`verschil`). Beoordeel niets wat geen verschil is.

### Modus tegenlezen

Bij een makkelijke casus werkt één analist, met jou als tegenlezer (besluit 4). Je krijgt zijn formulier en het
dossier, en je ziet Lex niet. Geef per opgenomen bepaling en per twijfelgeval een oordeel:

- **eens**: de bepaling hoort erbij, met de rol die de analist gaf;
- **hoort_er_niet_bij**: ze hoort niet bij de deelvraag;
- **twijfel**: zonder de jurist is er geen uitspraak.

Mist er naar jouw oordeel een bepaling, voeg die dan toe met **ontbreekt**. Lees haar eerst met `bron_lezen` en neem
het citaat op als bewijs. Je hoeft geen oordeel te geven over wat de analist uitsloot. Ben je het daar niet mee eens,
gebruik dan ook `ontbreekt`.

### Het formulier

Je laatste bericht is één JSON-object volgens het formulier in de opdracht, zonder tekst eromheen.

## Voor de coördinator

1. **Verschillen.** Bevries eerst de teamverwachting (`eval/lex_bench_team.py samenvoegen`). Maak daarna de opdracht:
   `uv run python -m eval.lex_bench_review opdracht --casus LB-xx --team <map>/teamverwachting.json --run <run>-r`.
   Bij een blinde casus geef je ook `--dossier` en `--opname` mee: beide staan buiten de repo. De opdracht noemt de
   verschillen van arm L1 tegen de teamverwachting, en de maten met teller en noemer.
2. **Toetsen en verwerken.** Sla het antwoord op en toets het:
   `uv run python -m eval.lex_bench_review verwerk <review.json> --casus LB-xx --team <...>`. Een fout gaat terug naar
   dezelfde reviewer. De uitkomst geeft de telling per categorie met de status *voorstel van de reviewer*, en noemt de
   bepalingen bij *team mist* als voorstel voor `nagekomen`. Aan de casus verandert niets.
3. **Tegenlezen** (makkelijk). Gebruik `uv run python -m eval.lex_bench_review tegenlezen --casus LB-xx --formulier
   formulier-a.json --run <run>-r`. Daarna samenvoegen met `--tegenlezing <review.json>`. Een bepaling waartegen de
   tegenlezer bezwaar maakt, en elke bepaling die volgens hem ontbreekt, komt in `onenig`, met beide standpunten.
4. **De jurist** beslist over de categorieën en over `onenig`. Tot dan blijft alles `concept` (besluit 2).
