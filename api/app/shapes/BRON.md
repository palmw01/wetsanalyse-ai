# Herkomst van de shapes

| bestand | bron | licentie |
|---|---|---|
| `jas-v2.ttl` | eigen werk (dit project) | als de repo |
| `nl-sbb-1.0.0.ttl` | Geonovum, *NL-SBB – Nederlandse standaard voor het beschrijven van begrippen*, toepassingsprofiel `skosapnl:` versie 1.0.0 | CC-BY 4.0 |
| `begrippen-wa.ttl` | eigen werk (dit project): herkomst en review van begrippen | als de repo |

`nl-sbb-1.0.0.ttl` is letterlijk en ongewijzigd overgenomen uit
`https://github.com/geonovum/NL-SBB/blob/main/shacl/1.0.0/skos-ap-nl.ttl` (gelijk aan
`profiles/skos-ap-nl.ttl`, waarnaar de vastgestelde specificatie van 10 oktober 2024 verwijst:
<https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/>). Die specificatie valt onder de
Creative Commons Attribution 4.0 International Public License. © Geonovum.

sha256 `9f123fc852d6debccdf0bead2e498e686d0832fbeb04abf7b211df17e0b3e9af`; `tests/test_begrip_projectie.py`
bewaakt die. Een nieuwe NL-SBB-versie is een bewuste overstap (ADR-003): nieuw bestand, nieuwe hash,
`NL_SBB_VERSIE` in `app/begrip_projectie.py` mee.
