# Kamerstukken, iteratieve verbeterrondes – ronde 5 (12 november 2026)

Soort: *meting* · Code: master `e7e2ab8a` (bundels 49–51, met de PR van ronde 4 en de telvragen in de lijstroute, #1252)
· Straat: acceptatie, alle connectors aan · Model: `claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP, elke
vraag in een eigen gesprek (de vervolgvragen K21–K22 en K23–K24 in één gesprek). Vragenset: dezelfde 30 als in ronde 1–4,
plus zes telvragen bij twee andere connectors: Rechtspraak (R21, R22 en RX1) en Staatsblad en Staatscourant (B10, B20 en
BX1).

De ruwe gegevens staan in [`runs.jsonl`](runs.jsonl) (`"ronde": 5`). De tokens zijn de som van cache lezen, cache
schrijven, uitvoer en invoer uit het `meting`-event; de tellers van de sjablonen komen uit `meting.sjabloon`.

**Twee herhalingen.**
- K04 gaf de eerste keer een inlogfout van de MCP-sessie, voordat Lex de vraag kreeg.
- RX1 kreeg de eerste keer `zoekvraag_geweigerd` van LiDO (zie B2).

Beide zijn één keer opnieuw gedraaid. Bij RX1 staan beide runs in de gegevens.

**Hoe er gekeken is.**
- Elke telling is nageteld bij de officiële zoekdienst (`repository.overheid.nl/sru`), met de query die de connector bouwt
  (`dt.type==Kamerstuk`, `dt.title any …`).
- R21, R22 en RX1 zijn tellingen van LiDO. Daarvan is de som per instantie nagelopen.
- Bij de vragen met een model zijn tekst, toolaanroepen en grounding gelezen.
- Bij K16 is ook de gelezen uitspraak zelf nagelopen (ECLI:NL:HR:2023:1371 bij data.rechtspraak.nl).

## Uitkomst

**De 30 vragen: 28 goed, 2 deels, 0 fout. Samen 1,95M tokens en 59 modelrondes.** In ronde 4 was dat 27 goed, 3 deels,
0 fout en 2,36M tokens.

| vraag | oordeel (ronde 4 → 5) | modelrondes | tokens |
|---|---|---|---|
| K01–K06, K08, K09 | goed → **goed** | 0 → 0 | 0 → 0 |
| K07 | goed → **goed** | 11 → 7 | 392k → 230k |
| K10 | deels → **deels** | 7 → 11 | 227k → 397k |
| K11 | goed → **goed** | 1 → 1 | 34k → 35k |
| K12 | goed → **goed** | 0 → 0 | 0 → 0 |
| K13 | goed → **goed** | 1 → 1 | 34k → 35k |
| K14 | goed → **goed** | 1 → 1 | 34k → 35k |
| K15 | goed → **goed** | 7 → 5 | 264k → 182k |
| K16 | deels → **deels** | 14 → 13 | 504k → 466k |
| K17 | deels → **goed** | 8 → **0** | 259k → **0** |
| K18 | goed → **goed** | 5 → 6 | 162k → 206k |
| K19 | goed → **goed** | 1 → 2 | 30k → 64k |
| K20 | goed → **goed** | 4 → 4 | 98k → 99k |
| K21 | goed → **goed** | 0 → 0 | 0 → 0 |
| K22 | goed → **goed** | 2 → 2 | 34k → 34k |
| K23 | goed → **goed** | 0 → 0 | 0 → 0 |
| K24 | goed → **goed** | 3 → 3 | 63k → 63k |
| K25 | goed → **goed** | 0 → 0 | 0 → 0 |
| K26 | goed → **goed** | 5 → **0** | 122k → **0** |
| K27 | goed → **goed** | 0 → 0 | 0 → 0 |
| K28 | goed → **goed** | 2 → 2 | 69k → 69k |
| K29 | goed → **goed** | 1 → 1 | 34k → 34k |
| K30 | goed → **goed** | 0 → 0 | 0 → 0 |

**De telvragen bij de andere connectors.** Alle zes goed, en vijf van de zes zonder model.

| vraag | connector | telling (bron) | nageteld | modelrondes | tokens |
|---|---|---|---|---|---|
| K25 "Hoeveel stukken zitten er in dossier 33755?" | Kamerstukken | 16, precies | SRU 16 | 0 | 0 |
| K26 "Hoeveel Kamerstukken hebben de Douanewet in de titel?" | Kamerstukken | 72, precies | SRU 72 | 0 | 0 |
| R21 "Hoeveel uitspraken noemen artikel 36 van de Invorderingswet 1990?" | Rechtspraak | ten minste 623 | LiDO | 0 | 0 |
| R22 "Hoe verdelen de uitspraken over artikel 36 Invorderingswet 1990 zich over de instanties?" | Rechtspraak | ten minste 623, per instantie | de som klopt (75 + 91 + 1 + 2 + 222 + 232) | 0 | 0 |
| RX1 "Hoeveel uitspraken noemen artikel 67f van de Algemene wet inzake rijksbelastingen?" | Rechtspraak | eerste run een fout van LiDO, herhaling ten minste 1.191 | LiDO | 3 → 0 | 90k → 0 |
| B10 "Hoeveel ministeriële regelingen van het Ministerie van Financiën staan er uit 2025 in de Staatscourant?" | Staatsblad en Staatscourant | 38, precies | SRU 38 | 0 | 0 |
| B20 "Hoeveel wetten van het Ministerie van Financiën staan er in het Staatsblad van 2024?" | Staatsblad en Staatscourant | 20, precies | SRU 20 | 0 | 0 |
| BX1 "Hoeveel bekendmakingen horen bij de Invorderingswet 1990?" | Staatsblad en Staatscourant | 88, precies (de koppeling in de graaf) | – | 0 | 0 |

**De correctierondes en de sjablonen** (`meting.sjabloon`, over de 30 vragen):
- **Gevuld**: `antwoord_extern` 14 keer en `antwoord_duiding` 1 keer.
- **Geweigerd**: twee keer, dus twee correctierondes.
  - K10: `antwoord_extern:extern.lijsten`;
  - K15: `antwoord_extern:extern.blokken`.
- **`gevraagd`, `gemist`, `als_tekst` en `uitgesteld`**: 0.
- **`tekst_ernaast`**: 1.494 tekens over 8 vragen (K10 299, K16 227, K15 222, K11 219, K29 203, K19 137, K14 106, K07 81).
  Na #1257 komen ze niet meer in het denkproces of de historie. Het model schrijft ze wel nog, maar het gaat om een paar
  honderd uitvoertokens.
- **Telvragen**: alleen de eerste RX1-run telt `gemist: 1`. Het model antwoordde daar in tekst na de fout van de bron.

## Wat de PR van ronde 4 en de telvragen opleverden

1. **De telvraag in code** (K26, R22). K26 kostte drie rondes lang vijf modelrondes en 122k tokens; nu is het één aanroep
   zonder model. Het antwoord zegt "Kamerstukken telt 72 stukken bij deze zoekvraag", met de zoekvraag "op „Douanewet” in de
   titel". R22 geeft de verdeling uit `per_instantie` van LiDO, en de code telt niets zelf uit een pagina. Hetzelfde
   mechanisme werkt bij drie connectors: Kamerstukken, Rechtspraak, en Staatsblad en Staatscourant.
2. **Stukken bij een regeling** (K17: deels → goed, 259k → 0).
   - Kamerstukken koppelt niet aan een regeling. Daarom zoekt de code op de naam in de titel: 211 stukken, en de SRU telt
     er ook 211. De kanttekening zegt dat een stuk met een andere titel ontbreekt. Het verzonnen dossier en de verkeerd
     geplaatste intrekking zijn er niet meer.
   - Bij Staatsblad en Staatscourant zoekt dezelfde vraag op het bwb-id (BX1).
3. **Nul treffers bij `woorden` per woord** (de PR van ronde 4).
   - K07 ging van 11 naar 7 rondes (392k → 230k). Er was één aanroep met nul treffers ("bestuurdersaansprakelijkheid
     loonbelasting"). Daarna koos het model "bestuurder aansprakelijk", met zes treffers.
   - K16 had er nog één ("artikel 36 aansprakelijkheid bestuurder"). Ook daar kwam de volgende aanroep met vier treffers.
4. **Van andere sessies**:
   - K16 leest nu wel de uitspraak van de Hoge Raad (#1255, `get_uitspraak` met foutclassificatie). In ronde 4 was die
     tweemaal onbereikbaar.
   - Het antwoord staat niet meer in het denkproces (#1257).

## Bevindingen, per oorzaak

### A. Eigen code (opgelost in de PR van deze ronde)

1. **Een zoekvraag op de regeling als geheel heette "artikel  van BWBR0004770"** (BX1). Onder de lijst stond "Gezocht bij
   artikel  van BWBR0004770.", met een leeg artikel en het bwb-id in plaats van de naam.
   - `zoekvraag_tekst` maakte bij het veld `wetsverwijzing` altijd "artikel {artikel} van {bwb_id}". Bij
     Staatsblad en Staatscourant zet de tool zelf geen `bepaling` in de zoekvraag.
   - Nu zet `zoek_bekendmakingen` de bepaling met de naam uit de graaf ("artikel 36 van Invorderingswet 1990" of
     "Invorderingswet 1990 als geheel"), in de vorm van Rechtspraak.
   - Zonder `artikel` geeft `zoekvraag_tekst` de regeling, nooit een leeg artikel. Dat geldt voor elke connector met het
     veld.
2. **"In de titel" stond er twee keer** (K17): "Gezocht op „Invorderingswet 1990” in de titel. … ik zocht op
   „Invorderingswet 1990” in de titel, dus …". De zoekvraag zegt het al, dus de kanttekening zegt nu alleen wat het
   betekent.

### B. Gedeelde code of een andere connector (vervolgwerk, niet gebouwd)

3. **Een fout van de bron in de lijstroute gaat naar het model** (RX1, eerste run).
   - `zoek_uitspraken` gaf na 92 s `zoekvraag_geweigerd`, want LiDO gaf een 4xx (`foutcode_van_status`). Een herhaling
     een kwartier later gaf gewoon 1.191.
   - Daarna nam het model het over: drie rondes en 90k tokens om de fout uit te leggen en `search_wetgeving` aan te
     roepen. Zo werkt het ontwerp: bij een fout krijgt de agent het resultaat, met de tools voor een tweede poging
     (`nodes/bron_lijst.py`).
   - Bij een storing of een weigering van de bron kan het model niets beters dan een vaste melding.
     `bron_lezen._zonder_tekst` doet dat al voor een genoemd stuk.
   - De lijstroute zou bij `bron_onbereikbaar`, `bron_bezet` en `zoekvraag_geweigerd` dezelfde vaste melding kunnen
     geven, en alleen bij `ongeldige_argumenten` naar het model kunnen gaan. Dat is een ontwerpkeuze in gedeelde code, dus
     hier alleen voorgesteld.
   - Dat LiDO een 4xx gaf, en dat pas na 92 s, is iets voor de Rechtspraak-sessie: is het een time-out die als 4xx
     terugkomt?
4. **LiDO is traag bij een telvraag**: R21, R22 en RX1 duurden elk ongeveer 60 s, voor één aanroep zonder model. Dat
   ligt aan de koppelingen per versie, voor de Rechtspraak-sessie.

### C. Wat het model doet

5. **K10 telt de amendementen zelf, en fout.**
   - De toelichting zegt "90 amendementen bij het Belastingplan 2025 (36602)" en "2 bij dossier 36604".
   - De bron telt er 88 en 3 (SRU, `dt.type==Kamerstuk`, `w.subrubriek==Amendement`). Het totaal van de zoekvraag was
     94.
   - Het model bladerde alle pagina's door: 11 rondes en 397k tokens, de duurste vraag.
   - De beweringentoets (#1255) zag de telling niet. "90 amendementen" is een getal van twee cijfers, en het staat bij
     een totaal dat wel in de trace staat.
   - Een vraag als "geef de amendementen bij X" is pas in code te lezen als de code het dossier van een wetsvoorstel uit
     zijn naam kan halen. Dat is een nieuw mechanisme, geen fix.
6. **K16: het jaar bij 20 588 klopt niet.**
   - Het dossiernummer komt nu uit de gelezen uitspraak (Kamerstukken II 1987/88, 20 588, nr. 3). Dat is beter dan in
     ronde 4: daar stond het nummer er zonder bron, al was het nummer juist.
   - Wel zegt de toelichting "ingediend in 1988-1989", en de uitspraak zegt 1987/88.
   - De rest van het antwoord rust op de wettekst (vier leden, letterlijk) en de Hoge Raad.
7. **Tekst naast een sjabloon** (1.494 tekens, 8 vragen): klein, en sinds #1257 onzichtbaar.

## Wat de PR van ronde 5 verandert

1. `zoek_bekendmakingen` met `bwb_id` zet `zoekvraag.bepaling` met de naam uit de graaf (`regelingnamen`), zoals
   Rechtspraak.
2. `zoekvraag_tekst`: zonder artikel de regeling, niet "artikel  van …".
3. `bron_lijst._bij_regeling`: de kanttekening zegt "in de titel" niet nog eens.

Tests:
- `test_de_zoekvraag_noemt_de_bepaling_bij_naam`: met en zonder artikel, en met en zonder naam;
- `test_een_regeling_zonder_artikel_is_geen_leeg_artikel`;
- de K17-test eist "in de titel" één keer.

## Wat deze meting niet zegt

- Dit is één run per vraag. RX1 laat zien dat dezelfde vraag aan dezelfde bron de ene keer faalt en de andere keer
  niet.
- De fixes van deze ronde staan nog niet op acceptatie.
- BX1 (88) is niet nageteld: de koppeling komt uit de graaf (`bwb:bron`), en een tweede bron daarvoor is er niet.
- Het oordeel is van deze sessie, tegen de bron. Het is geen juridisch oordeel over de stukken.
