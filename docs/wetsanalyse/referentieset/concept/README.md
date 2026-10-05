# Conceptcasussen – nog niet beoordeeld

Casussen die nog niet in een versie van de referentieset horen. Ze staan bewust **buiten `v1/`**:
de evaluatie (`tools/graph-qa/eval/referentieset.py`) en de meetlogboeken lezen alleen de versies,
en een casus erbij zou de nulmeting verschuiven.

Een conceptcasus is een **voorstel, geen referentie**. Hij gaat pas naar een versie (`v<N+1>`) als
een jurist hem volgens het [adjudicatieprotocol](../adjudicatieprotocol.md) heeft beoordeeld. Laat
het concept niet zien aan wie blind annoteert: het is bedoeld voor de conceptbespreking erna.

| Casus | Bepaling | Aanleiding |
|---|---|---|
| [`IW05.json`](IW05.json) | art. 9 lid 5 Invorderingswet 1990 | Externe review van de TriG-export (5 okt 2026): NP-first-classificatie, ontbrekende normatieve predicaten ("vervalt", "vindt … toepassing"), ALS→DAN en de afleiding "zoveel … als". |

Per casus naast de gewone velden (zie `v1/cases.json`):

- `export_vergelijking` per element: behouden, wijzigen of ontbrak in de export;
- `verwijderd_uit_export`: exportelementen die in dit concept geen eigen markering zijn, met reden;
- `relaties`: voorgestelde verbanden (`uitkomst_van`, `invoer_van`, `vervalmoment_van`,
  `voorwaarde_voor`) – een kandidaat-uitbreiding na V7, nog geen onderdeel van het schema;
- `concept`: herkomst van het voorstel.

Brongetrouwheid: `tools/graph-qa/tests/test_referentieset_concept.py` eist dat elk element letterlijk
in de tekst staat, op woordgrenzen ligt, een geldige JAS-klasse heeft en dat `tekst_sha256` klopt.
