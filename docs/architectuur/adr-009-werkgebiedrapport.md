# ADR-009: Het werkgebiedrapport als gestructureerd document

**Status:** aangenomen, 7 nov 2026.

## Context

De export van een werkgebied maakte regels `(stijl, tekst)` rechtstreeks uit de stand. De PDF kende geen document, en de Markdown was een aparte functie in de werkplek die alleen het dossier gaf. Twee uitvoervormen van hetzelfde werk konden zo uit elkaar lopen, en een JSON-export had niets om te tonen.

## Besluit

**Het rapport is één document, en elke uitvoervorm komt daaruit.**

```
verzamel → bouw_rapport → Rapport (JSON) → rapport_regels → [(stijl, tekst)] → PDF of Markdown
```

- **Contract:** `api/app/werkgebied_rapport.py`, in Pydantic, met `schema`, `versie` en `extra="forbid"`. Het staat in de api, want alleen de api gebruikt het.
- **Codes in het document, woorden in de tekstlaag.** Het document draagt `lifecycle: "human_approved"` en ISO-datums. Alleen `rapport_regels` maakt labels en zinnen. Uitzondering: de leesbare herkomstnamen komen uit `verklaringen` en gaan als tekst het document in.
- **`door`:** `bron`, `lex` of `analist`, bij wat inhoud draagt.
- **De uitvoer ziet alleen het document.** De PDF gaat letterlijk door de JSON heen, dus wat niet in het document staat, kan niet in het rapport komen.

## Wat van ADR-008 komt, en wat niet

Overgenomen: een gesloten contract met een versie, `door`, tekst die uit de structuur volgt, en feiten uit de code. Wat ontbreekt wordt gezegd.

Bewust anders, want een rapport is geen chatantwoord:

- **Geen `blokken: list[Blok]`.** Een antwoord kiest per vraag een sjabloon. Een rapport heeft altijd dezelfde delen in dezelfde volgorde, dus dat zijn vaste velden, en een vergeten deel is een fout.
- **Geen gedeelde blokken.** `Markering` en `VastgelegdBegrip` zijn chatmaat. Het rapport vraagt status, herkomst, koppelingen en toen en nu; delen zou de blokken opblazen en de werkplek raken. Alleen `Vindplaats` komt uit `bronmodel/antwoord.py`, dat daarvoor niet wijzigt.
- **`door` is ruimer.** Een geaccordeerd begrip is geen `bron` en geen `lex`.
- **Geen `Onvulbaar`.** Er zit geen model in de keten. Wat niet te lezen was, staat in het rapport op het voorblad en op zijn plek.

## Gevolgen

Een JSON-export voor de gebruiker vraagt `formaat=json`, een schemabestand uit `Rapport.model_json_schema()` en een knop, zonder wijziging aan het document. Een nieuw veld hoort in het contract én in de tekstlaag; de dekkingstest faalt als het niet in de regels terechtkomt.
