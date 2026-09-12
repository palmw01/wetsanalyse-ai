# Kwaliteitsrubriek en gezamenlijke beoordeling

Grondslag: [bronnen en beslisregister](bronnen.md) — P09.
Een concept is niet goedgekeurd omdat een model het zelf groen noemt. Beoordeel per casus:

| Aspect | Voldoende bewijs |
|---|---|
| Bronintegriteit | Citaten, vindplaatsen en versie kloppen; geen verzonnen passages. |
| Grammatica | Materiële scope, negatie, antecedenten en opsommingen correct verklaard. |
| JAS | Klassen en grenzen dragen de functie; relevante overlap en alternatieven verantwoord. |
| Samenhang | Partijen, voorwaarden, feiten en gevolgen consistent verbonden waar van toepassing. |
| Interpretatie | Materiële keuzes onderbouwd, bronstatus onderscheiden, alternatieven zichtbaar. |
| Dekking | Iedere normeenheid verantwoord; geen verborgen uitzondering of contextlacune. |
| Scenario's | Verwachte uitkomsten volgen uit bronnen; grens en onbekende invoer gecontroleerd. |
| Reviewbaarheid | Open vragen hebben impact en vervolgstap; menselijke besluiten blijven traceerbaar. |

Gebruik per aspect: voldoende / tekort / niet beoordeelbaar / niet van toepassing (met reden).
Een verzonnen bron, betekenisveranderende omissie of onbewezen conclusie als zekerheid
blokkeert vaststelling. Een kritieke open vraag blokkeert de betrokken conclusie; andere
zelfstandige delen kunnen wel beoordeeld worden. Geen gemiddeld cijfer dat een kritieke fout maskeert.

## Referentieset

Conceptvoorbeelden zijn geen gold. Laat een deskundige eerst zelf duiden, vergelijk daarna
met het voorstel en leg adjudicatie en aanvaardbare alternatieven vast. Waar slechts één
reviewer beschikbaar is, rapporteer dat expliciet; noem dit geen interbeoordelaarsmeting.
Een resterend juridisch meningsverschil wordt vastgelegd in plaats van weggestemd.

Splits wetsfamilies vóór promptontwikkeling. Houd dezelfde bronpakketten, modelversie,
instellingen en meetprocedure voor oud/nieuw aan. Gebruik drie herhalingen per casus voor
stabiliteit; bewaar uitkomsten en benodigde handmatige correcties. Held-out voorbeelden
worden niet als few-shotmateriaal in de skill opgenomen.

Rapporteer afzonderlijk: exacte span+klasse-precisie/recall, plaats/voorkomen, ontbrekende
normen/relaties, kritieke fouten, brononderbouwing en menselijke reviewlast. Partiële overlap
is een diagnose, geen correcte juridische annotatie. Zonder beoordeelde referentie of
verwachtingen is een kwaliteitsscore 'niet beoordeelbaar', geen gratis 1.0.

Voor technische oplevering: generatie/drift, promptkoppeling, bestaande contract- en
annotatietests slagen. Voor inhoudelijke acceptatie: alle referenties beoordeeld, geen
kritieke fout in de getoetste analyses, en vergelijking met de oude versie gerapporteerd.
Een niet-uitgevoerde modelvergelijking blijft open; claim geen bewezen verbetering.
