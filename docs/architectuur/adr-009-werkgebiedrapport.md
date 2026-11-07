# ADR-009: Het werkgebiedrapport als gestructureerd document

**Status:** aangenomen, 7 nov 2026.

## Context

De export van een werkgebied maakte regels `(stijl, tekst)` rechtstreeks uit de stand. De PDF kende geen document, en de Markdown was een aparte functie in de werkplek die alleen het dossier gaf. Twee uitvoervormen van hetzelfde werk konden zo uit elkaar lopen, en een JSON-export had niets om te tonen.

## Besluit

**Het rapport is één document, en elke uitvoervorm komt daaruit.**

```
verzamel → bouw_rapport → Rapport (JSON) → rapport_regels → [(stijl, tekst)] → PDF of Markdown
```

- **Contract:** `api/app/werkgebied_rapport.py`, in Pydantic, met `schema_naam`, `versie` en `extra="forbid"`. Het staat in de api, want alleen de api gebruikt het.
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

## Aanvulling (nov 2026): opmaak, indeling en graaf

**Status:** aangenomen, 7 nov 2026. Het rapport moet er professioneel uitzien en een jurist moet het kunnen overdragen. De lijn hierboven blijft staan: één document, en de uitvoer ziet alleen het document.

- **Versie 2 (`werkgebied-rapport-v2`).** Nieuw zijn `document` (titel, kenmerk `WG-<id[:8]>-r<revisie>`, `concept` zolang het werkgebied niet `afgerond` is), `samenvatting` (kerncijfers als `{code, aantal}` in een vaste volgorde) en `verantwoording.besluiten` (het besluitenlog: de beslissende audit-acties met datum, wie, onderwerp en reden; het werk van Lex zelf staat alleen geteld). Het JSON-schema staat in `api/app/schemas/werkgebied-rapport-v2.schema.json`, gemaakt met `werkgebied_rapport.schrijf_schema()` en bewaakt door een test. Er is geen compat-laag naar v1, want niemand buiten de api las het.
- **Kenmerk en inhoudscode.** Het kenmerk `WG-<id[:8]>-r<revisie>` zegt welk werkgebied en welke revisie het is. Maar de revisie verandert niet als annotaties, begrippen of graafgegevens veranderen. `document.inhoud_hash` is daarom de identiteit van de inhoud: SHA-256 over het document zonder `stand` en zonder de hash zelf, als JSON met gesorteerde sleutels (`werkgebied_rapport.inhoud_hash`). Gelijke inhoud geeft dezelfde code, ongeacht moment of exporteur; dus is achteraf exact vast te stellen welke analyseversie beoordeeld of gedeeld is. De code staat kort (12 tekens) op het titelblad en in de voetregel, en volledig in het colofon en de JSON.
- **Een documentstatus wordt niet verzonnen.** Het titelblad en het colofon noemen de status van het werkgebied en "concept" volgt uit een code. Het woord "definitief" staat er niet, want daarover beslist geen code.
- **Indeling.** Vooraan staan het titelblad, het colofon, de inhoud, de samenvatting, een leeswijzer, het werkgebied, de deelvragen, de analyse per bepaling en een begrippenlijst. Bijlagen met letters bevatten de naslag: de begripskaarten, het bronnenregister, de contextbepalingen, de samenhang, wat niet is meegenomen en de verantwoording. Annotatie en wettekst blijven bij elkaar. Alleen de contextbepalingen zonder markering gaan naar een bijlage.
- **Graafgegevens komen via de api in het document** (`rapport_graaf`), net als de toestanden: de regeling (WTI-soort, verantwoordelijke, toestand), de opbouw van elke bepaling en de verwijzingen vanuit het dossier (alleen uitgaand; inkomende verwijzingen uit de hele graaf zijn ruis). Dat gebeurt best-effort met het signaal `graaf_onvolledig`, alleen met strikt gelezen IRI's in de query, en altijd met een expliciete sortering.
- **Toegankelijkheid.** Reportlab (open source) maakt geen tagged PDF, dus volledige PDF/UA-1 is met deze renderer niet haalbaar. Het rapport doet wat wél kan: `/Lang nl-NL`, de titel in het venster, metadata, bladwijzers, ingesloten letters, één kolom en contrast volgens WCAG AA. Kleur is nooit de enige drager. Een overstap naar een renderer met tags (WeasyPrint of ReportLab PLUS) vraagt een eigen ADR. De laag `(stijl, tekst)` houdt die overstap beperkt.
- **Markeringen staan in de wettekst.** Een bepaling draagt `spans` (start, eind, nr, klasse; offsets in codepoints, alleen ankers die nog letterlijk op hun plek staan). De tekstlaag zet ze als eigen regel `Spans` (JSON) vlak vóór het citaat, zodat elke regel `(stijl, tekst)` blijft. De PDF kleurt het fragment in de klassekleur, onderstreept waar markeringen overlappen en zet het nummer erachter. Markdown maakt het vet met ⁽ⁿ⁾. Zonder die tekens staat de wettekst er letterlijk. De lijst onder de bepaling herhaalt het citaat dan niet.
