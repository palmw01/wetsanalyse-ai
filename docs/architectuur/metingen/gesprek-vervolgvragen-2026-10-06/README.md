# Vervolgvragen in één gesprek – nulmeting en effect (6 oktober 2026)

Soort: *meting* · Meetlat: `eval/golden_gesprek.jsonl` via `eval/run_eval.py --gesprek` (#607)

## Waarom

Juristen merkten dat Lex bij doorvragen de draad kwijtraakte. Het ging om drie situaties:

- **A**: doorvragen op een antwoord;
- **B**: na een annotatie vragen naar andere annotaties;
- **C**: doorvragen op een gemarkeerd element.

De gouden sets stelden tot dan toe één vraag per case, dus het gespreksgeheugen was nooit gemeten. De gesprekkenset bevat negen gesprekken (A, B, C en een regressiecase R) met twaalf vervolgbeurten. Per beurt toetst de set de route, de tools, het antwoord en het grounding-niveau.

## Opzet

- **Waar gedraaid.** Lokaal, in-proces (`run_eval.py --gesprek`), tegen de **graaf van acceptatie** via de MCP-proxy. Het model is `claude-sonnet-4-6` (Azure Foundry). Per run is er een verse SQLite-checkpointer. Er is geen api: de eval annoteert en zoekt via `GesprekAnnotaties`. Er is dus niets in de werkvoorraad van juristen beland.
- **Waarom niet via de eval-job.** De eval-job op Azure kon de gesprekken niet draaien: dat vraagt een `azure-infra deploy`, en die was in deze sessie niet toegestaan.
- **Herhalingen.** Elke reeks bestaat uit 3 runs, vanwege de spreiding tussen runs. Lees de uitkomsten als bandbreedte.
- **Versies van de code:**
  - vóór: `master` op `bd50657` (de meetlat, zonder fixes);
  - na: de stapel #608–#612, op `6d43a8b` (reeks 2) en `d06b849` (reeks 3, met de correctiefix).
- **Versies van de set:**
  - reeks 1 en 2: de set van `bd50657` (sha256 `3e8e3096e5cd2a58…`);
  - reeks 3 en 4: de aangescherpte set (`a1b5d4fe8148ce26…`, zie *Wijziging van de meetlat*).

## Uitkomst

Aantal goede vervolgbeurten, van de 12:

| reeks | code | set | run 1 | run 2 | run 3 |
|---|---|---|---|---|---|
| 1 | vóór | oud | 8 | 7 | 7 |
| 2 | na | oud | 10 | 12 | 10 |
| 3 | na + correctiefix | nieuw | 11 | 12 | 11 |
| 4 | vóór | nieuw | 9 | 7 | 8 |

**De vergelijking op dezelfde meetlat is reeks 4 tegen reeks 3: 7–9 tegenover 11–12.**

Fouten die vóór in elke run terugkwamen en na in geen enkele run meer:

- "Waarom?" na een annotatie werd **afgewezen** (3/3 runs). Oorzaak: de supervisor zag alleen de kale vraag.
- "annoteer artikel 10" na artikel 9 van dezelfde wet gaf **"meer dan één artikel"** (3/3). Oorzaak: de doelbepaling las de hele thread.
- "welke rechtssubjecten ken je nog meer uit andere annotaties" **miste de inspecteur uit de AWR** (3/3). Oorzaak: de leesroute filterde op de wet van een eerdere vraag.
- "doe hetzelfde voor lid 2" werd **niet geannoteerd** (2/3, afgewezen of `algemeen`).

Wat blijft:

- **C, "waarom heb je 'zes weken …' zo gemarkeerd?" is 2 van de 3 keer `ongegrond`.** De oorzaak is een niet-letterlijk citaat: een hoofdletter Z, of een punt erachter. De controle keurt dat terecht af. Het is een citeerfout van het model en geen geheugenprobleem. In reeks 4 slaagt deze beurt wel, maar daar citeerde het model niet.

## Wat de meting zelf opleverde

In reeks 2 antwoordde Lex na een afgekeurd citaat met "U heeft gelijk …" op de *interne* correctiemelding. Dat meta-antwoord werd het zichtbare antwoord én het laatste wat Lex in die beurt "zei". In één run betrok de supervisor de vervolgvraag "en lid 2?" daardoor op artikel 10 in plaats van artikel 9. De correctieronde vraagt nu om een volledig nieuw antwoord op de oorspronkelijke vraag (`d06b849`).

## Wijziging van de meetlat

De case `a-artikel9-doorvragen`, beurt 2 ("En wat staat er precies in lid 2?"), eiste `tools_wel: get_lid/get_artikel/get_context`.

Die eis kwam uit de oude regel "bevraag bij een vervolgvraag altijd opnieuw de graaf". Met #611 vervalt die regel: eerder opgehaalde wettekst mag weer. De eis ving de echte fout (artikel 10) bovendien alleen toevallig.

De case toetst nu de inhoud: `bevat: navorderingsaanslag` en `verboden: artikel 10`. Reeks 4 draait de oude code daarom opnieuw met deze set, zodat de vergelijking op dezelfde lat staat.

## Wat dit níét zegt

- Negen gesprekken zijn een smalle set, met de Invorderingswet als zwaartepunt.
- `GesprekAnnotaties` bootst de api niet na in omvang en verificatie. Het zoeklus-effect van grote zoekresultaten (#608) is daarom met unittests aangetoond, niet met deze meting.
- Dit is geen juridisch oordeel over de antwoorden.

## Bestanden

- `1-voor-oude-set.log`
- `2-na-oude-set.log`
- `3-na-correctiefix.log`
- `4-voor-zelfde-set.log`

Het zijn de volledige rapporten van `run_eval.py --gesprek` per reeks.
