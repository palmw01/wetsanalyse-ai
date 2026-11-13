# Toolgebruik van de centrale agent, ronde 3 (master 171c38f4, na A2-2b)

Uit de ruwe runs van het meetspoor; 54 beurten, waarvan 36 bij de centrale agent (de rest: een route in code of een specialist).
Soort: *meting*, bijlage bij [`ronde-3.md`](ronde-3.md). De gegevens per aanroep staan niet in de repo.

Een **ronde** is een modelronde: het veld `ronde` op elke toolaanroep (vanaf A2-2b). Wat als `a+b` staat, vroeg het model in één antwoord. Wat de code zelf deed (ronde 0) staat er niet bij.
**Na elkaar leeswerk** is een aanwijzing, geen bewijs: twee opeenvolgende rondes met alleen leestools, waarbij de tweede iets las dat al in de vraag stond of met dezelfde tool als de ronde ervoor.

## Welke tools (alleen de centrale agent)

| Tool | Aanroepen |
|---|---|
| `get_bepaling` | 39 |
| `get_artikel` | 31 |
| `search_wetgeving` | 30 |
| `get_uitspraak` | 27 |
| `raw_sparql` | 25 |
| `get_regeling_info` | 25 |
| `grondslagen` | 18 |
| `geldigheid` | 11 |
| `get_lid` | 9 |
| `list_regelingen` | 7 |
| `inhoudsopgave` | 7 |
| `follow_verwijzingen` | 6 |
| `zoek_opbouw` | 6 |
| `graph_schema` | 4 |
| `zoek_uitspraken` | 4 |
| `verwijst_naar_deze` | 3 |
| `zoek_definitie` | 3 |
| `get_context` | 3 |

- Toolrondes: 146; daarvan met meer dan één tool: 63.
- Beurten met ten minste één geval van na elkaar leeswerk: 19 van 36; gevallen samen: 32.
- Sjabloonweigeringen: 17 in 13 beurten.

## Per beurt

| Opdracht | Run | Beurt | Modelrondes | Toolrondes | Tools per ronde | Na elkaar leeswerk | Sjabloon |
|---|---|---|---|---|---|---|---|
| B01 (centraal) | 1 | gemeten | 7 | 5 | search_wetgeving → geldigheid → geldigheid → geldigheid → geldigheid | ronde 2–3; ronde 3–4; ronde 4–5 | tekst |
| B02 (centraal) | 1 | gemeten | 18 | 15 | search_wetgeving → grondslagen → grondslagen+grondslagen+list_regelingen → grondslagen+grondslagen+grondslagen+grondslagen+grondslagen+grondslagen+grondslagen+grondslagen+grondslagen → raw_sparql → graph_schema → graph_schema → raw_sparql+raw_sparql → raw_sparql → raw_sparql → raw_sparql → raw_sparql+raw_sparql → raw_sparql+raw_sparql → raw_sparql+raw_sparql → raw_sparql+get_artikel+get_artikel+get_artikel+get_artikel+get_artikel+get_artikel | – | antwoord_duiding (w1) |
| B03 (centraal) | 1 | gemeten | 6 | 3 | search_wetgeving → verwijst_naar_deze → get_regeling_info | – | tekst |
| B04 (centraal) | 1 | gemeten | 4 | 3 | list_regelingen → inhoudsopgave → inhoudsopgave | ronde 2–3 | tekst |
| B01 (centraal) | 2 | gemeten | 6 | 4 | search_wetgeving → geldigheid → geldigheid → geldigheid | ronde 2–3; ronde 3–4 | tekst |
| B02 (centraal) | 2 | gemeten | 10 | 8 | search_wetgeving → grondslagen → get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info → list_regelingen → grondslagen+grondslagen → search_wetgeving+search_wetgeving → get_artikel+get_artikel → get_lid | – | tekst |
| B03 (centraal) | 2 | gemeten | 6 | 3 | search_wetgeving → verwijst_naar_deze → get_regeling_info | – | tekst |
| B04 (centraal) | 2 | gemeten | 6 | 3 | list_regelingen → inhoudsopgave → inhoudsopgave | ronde 2–3 | tekst |
| B01 (centraal) | 3 | gemeten | 9 | 6 | search_wetgeving → geldigheid → geldigheid → geldigheid → geldigheid → get_artikel | ronde 2–3; ronde 3–4; ronde 4–5; ronde 5–6 | antwoord_duiding (w1) |
| B02 (centraal) | 3 | gemeten | 20 | 18 | search_wetgeving → grondslagen → grondslagen+grondslagen+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info+get_regeling_info → list_regelingen → raw_sparql → graph_schema → raw_sparql → graph_schema → raw_sparql+raw_sparql → search_wetgeving+search_wetgeving → get_regeling_info+get_regeling_info → raw_sparql+raw_sparql → raw_sparql → raw_sparql → raw_sparql → raw_sparql → raw_sparql → raw_sparql | – | tekst |
| B03 (centraal) | 3 | gemeten | 5 | 2 | search_wetgeving → verwijst_naar_deze | – | tekst |
| B04 (centraal) | 3 | gemeten | 4 | 3 | list_regelingen → inhoudsopgave → inhoudsopgave | ronde 2–3 | tekst |
| E01 (algemeen) | 1 | gemeten | 1 | 0 | – | – | – |
| E02 (overzicht) | 1 | gemeten | 0 | 0 | – | – | – |
| E03 (centraal) | 1 | gemeten | 6 | 3 | search_wetgeving → follow_verwijzingen+get_artikel → follow_verwijzingen+get_lid | ronde 2–3 | tekst (w2) |
| E04 (algemeen) | 1 | gemeten | 0 | 0 | – | – | – |
| E05 (antwoord) | 1 | gemeten | 2 | 0 | – | – | antwoord_extern |
| E06 (centraal) | 1 | gemeten | 1 | 0 | – | – | – |
| E07 (centraal) | 1 | gemeten | 4 | 2 | zoek_definitie → get_regeling_info | – | antwoord_begrip |
| E08 (centraal) | 1 | gemeten | 7 | 5 | zoek_opbouw+search_wetgeving → get_artikel+get_bepaling → get_lid+get_bepaling+get_bepaling → get_bepaling+get_bepaling → get_bepaling | ronde 3–4; ronde 4–5 | antwoord_duiding (w1) |
| E09 (centraal) | 1 | gemeten | 4 | 3 | get_artikel+get_artikel → get_context+search_wetgeving → get_artikel+search_wetgeving | – | antwoord_duiding |
| E10 (antwoord) | 1 | gemeten | 2 | 1 | search_annotaties | – | antwoord_annotaties |
| F01 (centraal) | 1 | opzet1:S01 | 10 | 8 | search_wetgeving → zoek_uitspraken → get_uitspraak+get_uitspraak+get_uitspraak+get_uitspraak+get_uitspraak → get_uitspraak+get_uitspraak+get_uitspraak → get_uitspraak+zoek_uitspraken → get_uitspraak+get_uitspraak+get_uitspraak → get_uitspraak+get_uitspraak → get_uitspraak | ronde 3–4; ronde 6–7; ronde 7–8 | antwoord_extern (w1) |
| F01 (centraal) | 1 | gemeten | 3 | 2 | get_uitspraak → get_uitspraak | ronde 1–2 | – |
| F02 (centraal) | 1 | opzet1:V01 | 10 | 8 | search_wetgeving+zoek_opbouw → get_artikel+zoek_uitspraken → get_artikel+inhoudsopgave → zoek_uitspraken → get_uitspraak+get_uitspraak+get_uitspraak+get_uitspraak+get_uitspraak → get_uitspraak+get_uitspraak+get_uitspraak → get_uitspraak → get_uitspraak | ronde 5–6; ronde 6–7; ronde 7–8 | antwoord_extern (w1) |
| F02 (centraal) | 1 | gemeten | 2 | 1 | get_artikel | – | antwoord_bepaling |
| F03 (–) | 1 | opzet1:M02 | None | 0 | – | – | – |
| F03 (–) | 1 | opzet1:M02:bevestigd | None | 0 | – | – | – |
| F03 (centraal) | 1 | opzet2:deelgesprek | 4 | 3 | search_wetgeving+zoek_opbouw → get_artikel+get_bepaling → get_lid+get_artikel+get_bepaling | – | tekst |
| F03 (centraal) | 1 | gemeten | 1 | 0 | – | – | tekst |
| F04 (centraal) | 1 | opzet1:E08 | 6 | 4 | zoek_opbouw+search_wetgeving → get_artikel+get_bepaling → get_lid+get_bepaling+get_bepaling → get_bepaling+get_bepaling+get_bepaling | ronde 3–4 | antwoord_duiding (w1) |
| F04 (centraal) | 1 | gemeten | 3 | 2 | get_bepaling → get_bepaling+get_bepaling+get_bepaling | ronde 1–2 | antwoord_duiding |
| F05 (algemeen) | 1 | opzet1 | 1 | 0 | – | – | – |
| F05 (centraal) | 1 | gemeten | 7 | 5 | list_regelingen → get_bepaling → get_bepaling+get_bepaling+get_bepaling+get_bepaling → get_bepaling+get_bepaling+get_bepaling → get_bepaling+get_bepaling | ronde 2–3; ronde 3–4; ronde 4–5 | antwoord_duiding (w1) |
| E01 (algemeen) | 2 | gemeten | 1 | 0 | – | – | – |
| E02 (overzicht) | 2 | gemeten | 0 | 0 | – | – | – |
| E03 (centraal) | 2 | gemeten | 6 | 3 | search_wetgeving → follow_verwijzingen+get_artikel → get_lid+follow_verwijzingen | ronde 2–3 | tekst (w2) |
| E04 (algemeen) | 2 | gemeten | 0 | 0 | – | – | – |
| E05 (antwoord) | 2 | gemeten | 2 | 1 | get_bekendmaking | – | antwoord_extern |
| E06 (centraal) | 2 | gemeten | 1 | 0 | – | – | – |
| E07 (centraal) | 2 | gemeten | 4 | 2 | zoek_definitie → get_regeling_info | – | antwoord_begrip |
| E08 (centraal) | 2 | gemeten | 7 | 4 | zoek_opbouw+search_wetgeving → get_artikel+get_bepaling → get_lid+get_bepaling+get_bepaling → get_bepaling+get_bepaling+get_bepaling | ronde 3–4 | tekst (w2) |
| E09 (centraal) | 2 | gemeten | 7 | 5 | get_artikel+get_artikel → get_context → get_artikel → search_wetgeving → search_wetgeving | ronde 1–2 | antwoord_duiding (w1) |
| E10 (antwoord) | 2 | gemeten | 2 | 1 | search_annotaties | – | antwoord_annotaties |
| E01 (algemeen) | 3 | gemeten | 1 | 0 | – | – | – |
| E02 (overzicht) | 3 | gemeten | 0 | 0 | – | – | – |
| E03 (centraal) | 3 | gemeten | 8 | 3 | search_wetgeving → get_artikel+follow_verwijzingen → follow_verwijzingen+get_lid | ronde 2–3 | tekst (w2) |
| E04 (algemeen) | 3 | gemeten | 0 | 0 | – | – | – |
| E05 (antwoord) | 3 | gemeten | 3 | 2 | get_bekendmaking → get_bekendmaking | ronde 1–2 | antwoord_extern |
| E06 (centraal) | 3 | gemeten | 1 | 0 | – | – | – |
| E07 (centraal) | 3 | gemeten | 4 | 2 | zoek_definitie → get_regeling_info | – | antwoord_begrip |
| E08 (centraal) | 3 | gemeten | 6 | 4 | zoek_opbouw+search_wetgeving → get_artikel+get_bepaling → get_lid+get_bepaling+get_bepaling → get_bepaling+get_bepaling | ronde 3–4 | antwoord_duiding (w1) |
| E09 (centraal) | 3 | gemeten | 5 | 4 | get_artikel+get_artikel → get_context+search_wetgeving → get_artikel+search_wetgeving → search_wetgeving+get_artikel | – | antwoord_duiding |
| E10 (antwoord) | 3 | gemeten | 2 | 1 | search_annotaties | – | antwoord_annotaties |
