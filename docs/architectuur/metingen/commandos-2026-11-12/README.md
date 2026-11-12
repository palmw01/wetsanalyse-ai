# /commando's in de werkplek: UI-test en tokenmeting (12 nov 2026)

Op acceptatie, bundel 58 (#1289, master `3fcefd5e`), met #1276 (`/commando's`) en de fix van de browsertest (`68b4dada`).
Testwerkgebied `Test commando's (Claude, 12 nov 2026)` (`4f072454-…`), met één deelvraag. Account palmw01 (gedeeld).

## Tokenmeting: getypt tegen het commando

De vraag *Stel deelvragen voor* in een werkgebied is drie keer getypt en drie keer als commando gestuurd. Het commando
geeft `actie: deelvragen_voorstellen`, en dat is hetzelfde verzoek als een klik op de suggestie. Beurt 1 ging via de UI in
de ingebouwde browser, de rest via de acceptatie-MCP (`lex_start` met en zonder `actie`). De cijfers komen uit het
`meting`-event van elke run. Er is geen verbruiksdelta gebruikt, omdat het account gedeeld is.

| # | Hoe | Gesprek | Supervisor (invoer / cache-lezen / uitvoer, ms) | Agent (invoer / uitvoer) | Beurt (ms) |
|---|---|---|---|---|---|
| 1 | `/deelvragen` (UI) | eerste vraag | – | 1.790 / 177 | 10.915 |
| 2 | getypt (UI) | vervolgvraag | 633 / 2.189 / 145, 10.447 | 1.884 / 177 | 22.079 |
| 3 | getypt (MCP) | eerste vraag | 207 / 2.189 / 72, 3.296 | 1.884 / 177 | 6.232 |
| 4 | actie (MCP) | eerste vraag | – | 1.884 / 177 | 2.929 |
| 5 | getypt (MCP) | vervolgvraag | 602 / 2.189 / 154, 3.716 | 1.884 / 177 | 6.468 |
| 6 | actie (MCP) | vervolgvraag | – | 1.884 / 177 | 3.305 |

In alle zes beurten was de route `deelvragen:voorstellen`. De agentaanroep was gelijk (de invoer van beurt 1 is kleiner,
omdat er toen minder deelvragen stonden).

**Uitkomst.** Een commando met een actie spaart per beurt precies de supervisor-aanroep uit:

- **Tokens**: 207–633 invoer, 2.189 cache-lezen en 72–154 uitvoer. In een vervolggesprek is het ongeveer het drievoudige
  van de eerste vraag, door de herschrijfstap (`VERVOLG_SYSTEM`, `system_variabel_tekens` 568 → ~1.770).
- **Tijd**: 3,3–10,4 s per beurt. Een beurt duurt ongeveer de helft: 6,2–22,1 s getypt tegen 2,9–10,9 s als actie.

Dit is een kleine besparing in tokens, want de agentaanroep zelf blijft. Het grootste effect zit in de wachttijd. Bij een
duurdere taak (annoteren, bronselectie) is de besparing even groot in absolute zin, en dus relatief kleiner.

## UI-test op acceptatie

In de ingebouwde browser, eerst in het smalle paneel (519 px) en daarna als telefoon (375 px, touch).

| Wat | Uitkomst |
|---|---|
| `/` opent het menu op de plek van de suggesties | ok: 13 commando's in het werkgebied, `role=combobox`, `aria-expanded`, `aria-controls`, `aria-activedescendant` op een regel met `aria-selected`, en de live-regel "13 commando's" |
| `/dee` + Enter | ok: *Stel deelvragen voor*, route `deelvragen:voorstellen`, geen supervisor (beurt 1 hierboven) |
| `/annoteer` + ↓ + Tab | ok: `/annoteer` eerst, ↓ kiest `/annoteer-deelvragen`, Tab vult dat aan en verstuurt niets |
| Escape | ok: het menu gaat dicht, de tekst blijft, het veld is weer een gewoon tekstveld |
| Onbekend (`/xyzq`) | ok: "Geen commando – Enter verstuurt je tekst als vraag. Typ /help voor de lijst." |
| `/help` | ok: het veld wordt `/`, het menu toont alle 13 |
| `/bron ` | ok: de vier bronnen met hun stand ("Kamerstukken staat nu aan – zet uit") |
| `/bron kam` + Enter, daarna `/bron kamerstukken` | ok: het bronnenmenu toont "4 van 5 aan" en daarna weer "alle 5 aan"; geen beurt |
| `/nieuw` | ok: een leeg gesprek in hetzelfde werkgebied (`?werkgebied=…`), de suggestierij staat er weer; geen beurt |
| Deelvraag als onderwerp, `/s` | ok: alleen `/scherper` en `/splits`; Enter → route `deelvragen:verbeteren`, één modelaanroep (1.893 / 260, 16 s) |
| Telefoon 375 px, touch | ok: `pointer: coarse`, het menu van 16 tot 359 px, geen horizontale scroll, elke regel ≥ 44 px |

**Opgemerkt.** Op een telefoon staat de hulptekst naast de naam, in een smalle kolom. Een regel wordt daardoor tot 92 px
hoog. Dat is leesbaar, maar de hulptekst onder de naam zetten zou het menu korter maken.

Niet getest in de UI: een commando tijdens een lopende beurt of zonder budget. Dat dekt `lib/commandos.test.ts`.
