# ADR-007 — LLM-pad en verwerker

Status: **concept, besluit open** · Datum: 2026-11-06 · Hoort bij: [PLAN spoor E](../PLAN.md)

## Context

Vrije tekst van de jurist en de wettekst gaan naar een taalmodel. De repo noemt dat "Anthropic via Azure AI Foundry", maar
legt niet vast wat dat juridisch en technisch betekent. Dit document zet op een rij wat vaststaat en wat de eigenaar nog moet
besluiten. Het besluit zelf ontbreekt nog, en de open punten zijn hieronder niet ingevuld omdat ze niet in de repo staan.

## Wat vaststaat in de code

- Er is één LLM-pad, achter het protocol `LLMPort`; een tweede provider vraagt een nieuwe adapter.
- `llmApiBase`, `llmModel` en `llmProvider` zijn deployparameters (`deploy/azure/main.bicep`). De provider is standaard `azure_ai`.
- Modellen zijn per rol instelbaar, en de env-waarden seeden alleen het eerste modelprofiel; daarna gaat het via `/v1/admin/profiles`.
- Vrije tekst gaat ongefilterd mee. De code kent geen signaal op persoonsgegevens.
- Tokenverbruik staat per gebruiker in een append-only journaal.

## Wat de leverancier zegt

Microsoft beschrijft voor Claude in Foundry twee hostingopties, en noemt Anthropic bij beide als verkoper en verwerker, onder de eigen
voorwaarden van Anthropic. *Hosted on Azure* kende bij de toets (pagina van 21 sep 2026) Global Standard en Data Zone Standard (VS), geen
EU-zone. Toets dit opnieuw voor een besluit:
[hostingvergelijking](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/claude-models-hosting-comparison),
[gegevens en privacy](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/claude-models/data-privacy).

## Open punten voor de eigenaar

1. Welke hostingoptie en welke regio draaien nu? Dat staat in de Foundry-inrichting, buiten deze repo.
2. Wie is verwerker, en onder welke voorwaarden? Geldt dat ook voor vrije tekst met persoonsgegevens?
3. Wat is de retentie, en is er een afspraak over training?
4. Wat is de terugval als dit pad niet mag: een EU-optie, een ander platform of een ander model?
5. Volstaat de disclaimer, of krijgt de jurist een aparte melding over wat er niet in het gesprek hoort?

## Gevolgen tot het besluit

Wettekst is openbaar en geeft op dit pad geen probleem. Voor casusgegevens is de vraag open: dat oordeel ligt bij FG en CISO. Tot het
besluit er is, hoort er in dit project geen echte casusinformatie in het gesprek.
