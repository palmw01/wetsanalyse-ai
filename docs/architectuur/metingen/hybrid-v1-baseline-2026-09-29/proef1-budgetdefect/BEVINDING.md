# Proef 1: afgekeurd wegens tokenbudget

De eerste baselineproef (84 pogingen, allemaal technisch geslaagd, geraamd $4,35) is **niet** de
baseline. Uit de ruwe antwoorden bleek een structureel defect dat de vergelijking vertekent:

| Variant | Review-aanroepen afgekapt | Classifier-aanroepen afgekapt |
|---|---:|---:|
| A (master) | 2 van 5 | 0 van 24 |
| U0 | 10 van 10 | 5 van 27 |
| K0 | 3 van 3 | 9 van 153 |
| UC | 2 van 2 | 0 van 6 |
| KC | 1 van 1 | 3 van 44 |

Het model schrijft eerst een analyse in tekst en bereikt `max_tokens` voordat het hulpmiddel wordt
aangeroepen (classifier `512 + 64·n`, reviewer `256 + 160·n`; geforceerde tool-use is op de
nieuwste modellen niet toegestaan). De uitgebreidere instructies van deze ronde en het verplichte
motiveringsveld maakten dat erger; ook A kende het al bij de reviewer. Gevolg: de reviewroute —
inclusief de herbeoordeling van centrale normen — is in proef 1 feitelijk niet getest, en IW 9
lid 1 viel in U0-ronde 2 en 3 volledig terug naar menselijke beoordeling.

Herstel (commit na deze bevinding): budget `1536 + 96·n` resp. `1536 + 256·n`, de instructie om
direct aan te roepen met de motivering in het veld, en tellers `afgekapt`/`review_afgekapt` in
de runmeting. De mechanische uitkomst van proef 1 (`universeel`, 4/8 casussen met KC ≥ UC) staat
in [model-vergelijking.md](model-vergelijking.md) en blijft ter vergelijking bewaard.
