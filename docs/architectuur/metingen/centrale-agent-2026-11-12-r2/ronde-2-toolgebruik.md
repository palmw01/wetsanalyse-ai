# Toolgebruik van de centrale agent in ronde A2 (master 06556097)

Uit de ruwe runs van het meetspoor; 43 beurten, waarvan 25 bij de centrale agent (de rest: een route in code of een specialist).
Soort: *meting*, bijlage bij [`ronde-2.md`](ronde-2.md). De gegevens per aanroep (tool, doel, filters, aantal, duur) staan niet in de repo.

Een **ronde** is hier een groep toolaanroepen met aaneengesloten event-nummers. De stroom die het meetscript krijgt, draagt geen event per modelronde (de status- en denkregels vallen weg), dus de grens is afgeleid.
**Let op: dit overschat het aantal rondes.** Staat er tussen twee tools van dezelfde modelronde een statusregel (bij connectortools na elke aanroep, soms ook bij graaftools), dan telt dat hier als een nieuwe ronde. Waar de kolom meer toolrondes toont dan er modelrondes waren, is dat zichtbaar. Wat hier naast elkaar staat (`a+b`), liep zeker in één ronde; wat na elkaar staat, mogelijk ook.
**Na elkaar leeswerk** is een aanwijzing, geen bewijs: twee opeenvolgende rondes met alleen leestools, waarbij de tweede iets las dat al in de vraag stond of met dezelfde tool als de ronde ervoor.

## Welke tools (alleen de centrale agent)

| Tool | Aanroepen |
|---|---|
| `get_bepaling` | 43 |
| `get_uitspraak` | 43 |
| `get_artikel` | 30 |
| `search_wetgeving` | 19 |
| `get_lid` | 9 |
| `follow_verwijzingen` | 6 |
| `zoek_opbouw` | 6 |
| `zoek_definitie` | 4 |
| `get_context` | 4 |
| `zoek_uitspraken` | 4 |
| `list_regelingen` | 2 |

- Toolrondes: 129; daarvan met meer dan één tool: 33.
- Beurten met ten minste één geval van na elkaar leeswerk: 14 van 25; gevallen samen: 60.
- Sjabloonweigeringen: 20 in 12 beurten.

## Per beurt

| Opdracht | Run | Beurt | Modelrondes | Toolrondes (afgeleid) | Tools per ronde | Na elkaar leeswerk | Sjabloon |
|---|---|---|---|---|---|---|---|
| E07 (centraal) | 1 | gemeten | 4 | 1 | zoek_definitie | – | antwoord_begrip |
| E01 (algemeen) | 1 | gemeten | 1 | 1 | get_lid | – | – |
| E02 (overzicht) | 1 | gemeten | 0 | 1 | overzicht_onderwerp | – | – |
| E03 (centraal) | 1 | gemeten | 5 | 4 | search_wetgeving → follow_verwijzingen → get_artikel → get_lid+follow_verwijzingen | ronde 2–3; ronde 3–4 | antwoord_duiding (w1) |
| E04 (algemeen) | 1 | gemeten | 0 | 1 | zoek_uitspraken | – | – |
| E05 (antwoord) | 1 | gemeten | 3 | 2 | get_bekendmaking → get_bekendmaking | ronde 1–2 | antwoord_extern |
| E06 (centraal) | 1 | gemeten | 1 | 0 | – | – | – |
| E07 (centraal) | 1 | gemeten | 4 | 1 | zoek_definitie | – | antwoord_begrip |
| E08 (centraal) | 1 | gemeten | 8 | 6 | zoek_opbouw → search_wetgeving → get_artikel+get_bepaling → get_lid+get_bepaling → get_bepaling+get_bepaling → get_bepaling | ronde 4–5; ronde 5–6 | tekst (w2) |
| E09 (centraal) | 1 | gemeten | 7 | 8 | get_artikel+get_artikel → get_context+get_context → search_wetgeving → get_artikel → search_wetgeving → get_artikel → get_artikel+get_artikel → get_artikel | ronde 1–2; ronde 6–7; ronde 7–8 | antwoord_duiding |
| E10 (antwoord) | 1 | gemeten | 3 | 3 | search_annotaties → list_regelingen → search_annotaties | – | antwoord_annotaties |
| F01 (centraal) | 1 | opzet1:S01 | 13 | 19 | search_wetgeving → zoek_uitspraken → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak+get_uitspraak → get_uitspraak → zoek_uitspraken → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak | ronde 3–4; ronde 4–5; ronde 5–6; ronde 6–7; ronde 7–8; ronde 8–9; ronde 9–10; ronde 10–11; ronde 13–14; ronde 14–15; ronde 15–16; ronde 16–17; ronde 17–18; ronde 18–19 | tekst (w2) |
| F01 (centraal) | 1 | gemeten | 6 | 5 | get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak | ronde 1–2; ronde 2–3; ronde 3–4; ronde 4–5 | antwoord_extern |
| F02 (centraal) | 1 | opzet1:V01 | 12 | 15 | search_wetgeving → list_regelingen → get_artikel+get_artikel → zoek_uitspraken → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak+get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak+get_uitspraak → get_uitspraak | ronde 5–6; ronde 6–7; ronde 7–8; ronde 8–9; ronde 9–10; ronde 10–11; ronde 11–12; ronde 12–13; ronde 13–14; ronde 14–15 | tekst (w2) |
| F02 (centraal) | 1 | gemeten | 7 | 9 | search_wetgeving → zoek_uitspraken → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak → get_uitspraak+get_uitspraak | ronde 3–4; ronde 4–5; ronde 5–6; ronde 6–7; ronde 7–8; ronde 8–9 | antwoord_extern (w1) |
| F03 (–) | 1 | opzet1:M02 | None | 0 | – | – | – |
| F03 (–) | 1 | opzet1:M02:bevestigd | None | 0 | – | – | – |
| F03 (centraal) | 1 | opzet2:deelgesprek | 6 | 5 | zoek_opbouw → search_wetgeving → get_artikel+get_artikel → get_bepaling → get_lid+get_artikel+get_bepaling | – | tekst (w2) |
| F03 (centraal) | 1 | gemeten | 1 | 0 | – | – | tekst |
| F04 (centraal) | 1 | opzet1:E08 | 10 | 9 | zoek_opbouw → search_wetgeving → get_artikel+get_bepaling → get_lid+get_bepaling → get_bepaling+get_bepaling → get_bepaling+get_bepaling → get_bepaling+get_bepaling → get_bepaling → get_bepaling | ronde 4–5; ronde 5–6; ronde 6–7; ronde 7–8; ronde 8–9 | antwoord_duiding (w1) |
| F04 (centraal) | 1 | gemeten | 9 | 6 | get_bepaling → get_bepaling+get_bepaling+get_bepaling → search_wetgeving → get_lid → get_artikel → get_artikel | ronde 1–2; ronde 5–6 | tekst (w2) |
| F05 (algemeen) | 1 | opzet1 | 1 | 1 | get_lid | – | – |
| F05 (centraal) | 1 | gemeten | 7 | 5 | list_regelingen → zoek_opbouw → get_bepaling → get_bepaling+get_bepaling+get_bepaling+get_bepaling+get_bepaling+get_bepaling+get_bepaling+get_bepaling → get_bepaling | ronde 3–4; ronde 4–5 | antwoord_duiding (w1) |
| E01 (algemeen) | 2 | gemeten | 1 | 1 | get_lid | – | – |
| E02 (overzicht) | 2 | gemeten | 0 | 1 | overzicht_onderwerp | – | – |
| E03 (centraal) | 2 | gemeten | 6 | 5 | search_wetgeving → follow_verwijzingen → get_artikel → follow_verwijzingen → get_lid | ronde 2–3; ronde 3–4; ronde 4–5 | tekst (w2) |
| E04 (algemeen) | 2 | gemeten | 0 | 1 | zoek_uitspraken | – | – |
| E05 (antwoord) | 2 | gemeten | 2 | 2 | get_bekendmaking → get_bekendmaking | ronde 1–2 | antwoord_extern |
| E06 (centraal) | 2 | gemeten | 1 | 0 | – | – | – |
| E07 (centraal) | 2 | gemeten | 4 | 1 | zoek_definitie | – | antwoord_begrip |
| E08 (centraal) | 2 | gemeten | 6 | 6 | zoek_opbouw → search_wetgeving → get_artikel+get_bepaling → get_lid+get_bepaling → get_bepaling+get_bepaling → get_bepaling+get_bepaling | ronde 4–5; ronde 5–6 | antwoord_duiding |
| E09 (centraal) | 2 | gemeten | 6 | 7 | get_artikel+get_artikel → get_context+search_wetgeving → get_artikel → search_wetgeving → get_artikel → search_wetgeving → get_artikel | – | antwoord_duiding |
| E10 (antwoord) | 2 | gemeten | 2 | 2 | search_annotaties → search_annotaties | – | antwoord_annotaties |
| E01 (algemeen) | 3 | gemeten | 1 | 1 | get_lid | – | – |
| E02 (overzicht) | 3 | gemeten | 0 | 1 | overzicht_onderwerp | – | – |
| E03 (centraal) | 3 | gemeten | 6 | 5 | search_wetgeving → follow_verwijzingen → get_artikel → follow_verwijzingen → get_lid | ronde 2–3; ronde 3–4; ronde 4–5 | tekst (w2) |
| E04 (algemeen) | 3 | gemeten | 0 | 1 | zoek_uitspraken | – | – |
| E05 (antwoord) | 3 | gemeten | 3 | 2 | get_bekendmaking → get_bekendmaking | ronde 1–2 | antwoord_extern |
| E06 (centraal) | 3 | gemeten | 1 | 0 | – | – | – |
| E07 (centraal) | 3 | gemeten | 4 | 1 | zoek_definitie | – | antwoord_begrip |
| E08 (centraal) | 3 | gemeten | 8 | 6 | zoek_opbouw → search_wetgeving → get_artikel+get_bepaling → get_lid+get_bepaling → get_bepaling+get_bepaling → get_bepaling+get_bepaling | ronde 4–5; ronde 5–6 | tekst (w2) |
| E09 (centraal) | 3 | gemeten | 5 | 5 | get_artikel+get_artikel → get_context+search_wetgeving → get_artikel → search_wetgeving → get_artikel | – | antwoord_duiding |
| E10 (antwoord) | 3 | gemeten | 2 | 2 | search_annotaties → search_annotaties | – | antwoord_annotaties |
