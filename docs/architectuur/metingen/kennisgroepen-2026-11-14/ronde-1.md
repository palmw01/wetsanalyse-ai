# Kennisgroepstandpunten, ronde 1 – 14 november 2026

- **Soort:** *meting* (plan-connector-kennisgroepen §4, stap 7; licht regime: één run, alleen centraal).
- **Code:** master `b4d348a5` (bundel 107, met de hele stapel kennisgroepen en kg-8), op acceptatie voor alle vier de
  images; `CONNECTOR_KENNISGROEPEN=true` na de infra-deploy, de connector aan in het register (00:52 UTC). De index stond
  er bij de eerste vraag (de import-job van 00:40 UTC).
- **Straat:** acceptatie. **Model:** `claude-sonnet-4-6`.
- **Uitvoering:** de 20 vragen uit [`../../../acceptatie/kennisgroepen-meting.md`](../../../acceptatie/kennisgroepen-meting.md), elk in een eigen
  gesprek, via de acceptatie-MCP, met `extra: {"agentvorm": "centraal", "bronnen": ["kennisgroepen", "wetgeving_live",
  "kamerstukken", "rechtspraak"], "bronnen_herkomst": "gesprek"}` (vraag 17 met `bronnen: []`). Tokens uit het
  `meting`-event. De aantekeningen per vraag (gesprek, run-id, route, tools, tokens) staan in
  [`ronde-1-aantekeningen.md`](ronde-1-aantekeningen.md).
- **Controle vooraf:** de dertien kenmerken uit het meetplan op 14 nov ~00:55 UTC tegen de live bron gelezen: status en
  datum gelijk, totaal 1180. KG:041:2026:8 vindt `?search=` niet, omdat de titel `KG:041:2026:008` schrijft; via de index
  wel (vraag 16 las het).

## Uitkomst

**Garanties 20/20; kwaliteit 12 goed, 2 matig, 6 fout.** Het doel (≥ 17 goed, 0 fout) is niet gehaald, dus er komt een
tweede ronde. Geen enkele fout is een standpunt dat als wet of als geldend beleid werd gepresenteerd; ze zitten in de
weg ernaartoe (welke bron een beurt krijgt, een naam van een wet) en in wat de tool niet meegaf (een telling, een
opvolger, een tekststand).

| Garantie | Uitkomst |
|---|---|
| geen standpunt onder een `doel` of als wettekst | 20/20 |
| elk standpuntblok heeft de statusregel en een datum | 20/20 (13 blokken in 10 antwoorden) |
| een ingetrokken of vervallen standpunt nooit als geldend | 20/20 (vraag 2, 5, 9 en 10 raken het) |
| elk citaat letterlijk in de gelezen tekst | 20/20 (grounding nergens `niet_letterlijk`) |
| een uitgezette connector wordt niet gebruikt | 20/20 (vraag 17: melding zonder model) |

| # | soort | oordeel | wat er gebeurde |
|---|---|---|---|
| 1 | genoemd kenmerk | goed | gelezen in code, blok met statusregel en datum, intrekking van KG:013:2018:0173 in de tekst |
| 2 | per artikel, in de graaf | matig | de lijstroute vond het ene geldende standpunt; het verborgen ingetrokken standpunt, de herkomst van de koppeling en "ten minste" ontbraken in het blok |
| 3 | per artikel, buiten de graaf | **fout** | "Kennisgroepstandpunten heeft in deze beurt geen tools": de route die artikel 3.111 live las, beperkte de beurt |
| 4 | wet + beleid | **fout** | "Een regeling met de naam „Wet BPM 1992” vind ik niet": de BWB kent de afkorting "BPM", niet "Wet BPM 1992" |
| 5 | onderwerp, woorden | goed | twee geldende standpunten gelezen; het vervallen genoemd als geen geldend beleid |
| 6 | lijstvraag, nieuwste | goed | de vijf verwachte kenmerken, nieuwste eerst, totaal 29 |
| 7 | lijstvraag, metadata | goed | de vier verwachte kenmerken met kennisgroep, rubriek en periode |
| 8 | telvraag | **fout** | 12 modelrondes door 93 standpunten, een tabel met geschatte aantallen ("~38"), sjabloon gemist |
| 9 | ingetrokken | goed | ingetrokken gemarkeerd, opvolger KG:204:2024:14 |
| 10 | vervangen | **fout** | "niet gevonden, controleer het id": het oude kenmerk staat niet op de site, en de index werd niet gevraagd wie het intrekt |
| 11 | status/waarde | matig | de status juist, maar het vertrouwensbeginsel uit eigen kennis en geen vindplaats |
| 12 | niet gepubliceerd | goed | "geen gepubliceerd standpunt", met de grens |
| 13 | tekststand | **fout** | "1 oktober 2026 … nog niet in werking (ligt in de toekomst)" op 14 november 2026: het model vergeleek de datums zelf |
| 14 | ketting / omgekeerd | **fout** | de uitspraak goed gelezen, maar "Kennisgroepstandpunten zijn in deze beurt niet doorzoekbaar" (zelfde oorzaak als 3) |
| 15 | wetsgeschiedenis | goed | kst-31930-3 en -9 uit de tekst, bevestigd bij Kamerstukken |
| 16 | vergelijken | goed | beide gelezen, verschil met citaten |
| 17 | connector uit | goed | melding zonder model, `bron_uit` met reden `gesprek` |
| 18 | AVG | goed | herleidt niemand, zegt dat de casus geanonimiseerd is |
| 19 | controle wettekst | goed | route `bepaling_lezen`, geen standpunt, 1.579 + 177 tokens |
| 20 | buiten scope | goed | geen casusadvies, geen persoonsgegevens gevraagd |

## Bevindingen en wat er verandert

Elke fix is generiek: hij zit in de connectorbeschrijving, de gedeelde herkenning of het resultaatcontract, niet in een
regel voor één vraag.

| # | bevinding | vragen | fix |
|---|---|---|---|
| B1 | de bronnenlijst noemt wetsartikelen die een gelezen standpunt alleen noemt ("8 bronnen" voor één standpunt) | 1, 5, 13, 16, 18 | `grounding.alleen_gelezen_extern`: een bepaling die alleen in het resultaat van een connector staat, is geen bron (de regel van B12 bij het Staatsblad, nu voor wettekst) |
| B2 | het blok van een lijst zonder model toont niet wat de tool alleen aan het model zei | 2 | `zoek_standpunten` zet het verborgen aantal, de herkomst en "ten minste" in `kanttekening`, die het blok `stukken` overneemt (zoals Kamerstukken en Wetgeving) |
| B3 | een route in code (wettekst buiten de graaf, een genoemde uitspraak) beperkt de bronnen van de beurt, en "standpunten" alleen was geen signaal | 3, 14 | het kale "standpunt(en)" is een signaal van Kennisgroepstandpunten. Een bron te veel kost een toolschema; een te weinig een fout antwoord. "Beleid" blijft geen signaal |
| B4 | "Heeft de Belastingdienst een standpunt …" noemde geen bron, dus alle vier de connectors deden mee (25.969 tegen 5.634 tekens toolschema) | 5, 8, 20 | dezelfde fix als B3 |
| B5 | "Wet BPM 1992" herkent de BWB niet; zijn afkorting is "BPM" | 4 | `buiten_graaf._wet_afkorting`: "Wet <afkorting> <jaar>" zoekt de afkorting alleen, en kiest alleen bij één regeling waarvan de titel met "Wet" begint en het jaar draagt |
| B6 | geen telling per belastingsoort of kennisgroep: het model bladerde en schatte | 8 | `zoek_standpunten` geeft `per_belastingsoort` en `per_kennisgroep`, geteld in de index met de status van de zoekvraag; de vorm `per_<woord>` leest ook de lijstroute (`telling`) |
| B7 | een kenmerk dat niet gepubliceerd is maar in de index als `vervangt` staat, noemde zijn opvolger niet | 10 | `get_standpunt` vraagt bij `niet_gevonden` de index wie het intrekt en geeft `vervangen_door` in de fout; `bron_lezen` zegt dan "ingetrokken door …" in plaats van "controleer het id" |
| B8 | de vraag naar de status van een standpunt kreeg eigen kennis zonder vindplaats | 11 | **open**: de statusregel komt uit de code, maar de bron zelf heeft geen pagina in de index die de status uitlegt. Niet in deze ronde |
| B9 | het model vergeleek de datum van een toestand met vandaag, en fout | 13 | `get_standpunt` geeft `tekststanden`: per genoemd artikel in de graaf sinds wanneer de tekst geldt en of die "gewijzigd na dit standpunt" is, uit de code |
| B10 | `?search=` vindt een kenmerk met voorloopnullen in de titel niet (KG:041:2026:008) | controle | **open**, klein: alleen de terugvalweg zonder index raakt het |

## Kosten

Samen **1.259.074** tokens (invoer 1.664, uitvoer 10.457, cache lezen 1.022.874, cache schrijven 224.079). Vier vragen
gingen zonder model (2, 4, 10 en 17). Vraag 8 alleen was 503.175 tokens (40 %): de telling uit B6 haalt die weg. Een gewone
leesvraag over één standpunt kostte 17–27k (vraag 1, 9, 16, 18), vergelijkbaar met Rechtspraak en Kamerstukken.

## Wat deze ronde niet zegt

- Eén run per vraag; de spreiding is niet gemeten.
- De werkplek is niet in de browser bekeken; de blokken en de bronnenlijst komen uit de events.
- Vraag 4 en 13 raken code buiten de connector (de naam van een wet, de tekststand), die ook de andere connectors gebruiken.

Voor deze ronde zijn 20 gesprekken aangemaakt; het eerste was de probe op de index, en dat was vraag 6. Er is niets
gewijzigd of gewist.
