# Rechtspraak, iteratie – ronde 4 – 12 november 2026

Soort: *meting* · Code: acceptatie op master `e7e2ab8a` (bundels 49–51: het sjabloon in één ronde #1251, telvragen via de
lijstroute #1252, de id-controle #1253, de toets op beweringen en K16 #1255, het antwoord niet in het denkproces #1257) ·
Straat: acceptatie, alle vier connectors aan · Model: `claude-sonnet-4-6` · Uitvoering: zoals [ronde 3](ronde-3.md), één run
per vraag · Vragen: dezelfde 30 in 32 beurten, plus vijf extra op de punten van deze ronde.

De ruwe gegevens per run staan in [`runs-4.jsonl`](runs-4.jsonl), met de tellers uit `meting.sjabloon`. Tokens uit het
`meting`-event:
- de 30 vragen: **1.816.452** (ronde 3: 1.997.147); 15 van de 32 beurten zonder model;
- de vijf extra: 893.321.

Het tokenbudget raakte halverwege op (R16 en verder kregen een 429). Na de reset zijn alleen de ontbrekende vragen gedraaid.

## LiDO was traag

`zoek_uitspraken` bij een artikel duurde 35 tot 211 s, tegen 4 tot 24 s in ronde 3. Lokaal, rechtstreeks gemeten, kwam elk
verzoek met 200 terug en zonder herhaling, maar elk tweede verzoek duurde 2,5 s. Het lag dus aan LiDO, niet aan de
herhaallus van K16. Lees de duur en de tokens van deze ronde daarom niet als een trend: R06 (190 s), R08 (284 s) en R26
(245 s) wachtten het grootste deel op LiDO.

De traagheid bracht wel vier zwakke plekken in onze afhandeling aan het licht. Daar komt het verlies van deze ronde
vandaan (zie *Bevindingen*).

## Score

**De 30 vragen: 28 goed, 1 deels, 3 fout** (ronde 3: 31/1/0).

| # | vraag (kort) | ronde 3 | ronde 4 | wat er gebeurde |
|---|---|---|---|---|
| R06 | gerechtshoven bij art. 67f AWR | goed | deels | 358 waar ronde 3 er 487 telde, zonder kanttekening: de keten van versies brak af |
| R08 | art. 26 Awir | goed | fout | drie keer een 400 van LiDO heette "zoekvraag geweigerd"; geen lijst |
| R09 | art. 3.111 Wet IB 2001 | goed | fout | 0 uitspraken waar LiDO er 633 kent: `get-id` gaf geen id, en de lege uitkomst werd bewaard |
| R22 | verdeling per instantie art. 36 Iw | deels | **goed** | via de lijstroute (#1252): de verdeling als telling, zonder model en zonder duiding |
| R26 | de Leidraad Invordering 2008 | goed | fout | na 211 s dezelfde 400 als R08: "zoekvraag geweigerd" |

De andere 27 zijn goed, net als in ronde 3. Steekproef tegen LiDO zelf: R10 (168 uitspraken van de Hoge Raad bij art. 15
Wet OB 1968) klopt. R22 laat 75, 91, 222, 232, 2 en 1 zien, samen 623, zoals in ronde 3.

**De vijf extra: 3 goed, 2 deels.**

| # | vraag | oordeel | opmerking |
|---|---|---|---|
| X1-K16 | wat zegt de HR in ECLI:NL:HR:2023:563 | goed | `get_uitspraak` las de uitspraak in drie pagina's; K16 kwam niet terug |
| X2-K16 | HR:2023:1371 en HR:2023:563 over bestuurdersaansprakelijkheid | goed | beide gelezen |
| X3-pct | welk deel van de uitspraken bij art. 36 Iw komt van de HR | deels | de correctieronde vuurde op het percentage; daarna liet het model het gevraagde aandeel weg ("wordt hier niet berekend") |
| X4-som | HR en Parket samen | goed | 166 = 75 + 91 klopt, maar staat na de correctie als onbevestigd: een vals signaal |
| X5-kst | MvT bij de Invorderingswet 1990, en het dossier | deels | "bekendgemaakt in Staatsblad 1990, nr." zonder nummer (zo schreef het model het). Dat het dossier buiten de zoekdienst valt, zegt het eerlijk. De id-controle (#1253) hield de gok op dossier 20588 tegen |

## De correctieronde (de toets op beweringen)

- **3 van de 37 beurten** kregen een correctieronde op feiten zonder bron: R15, X3 en X4. Bij de 30 vragen was R15 de enige.
- **2 daarvan op een afgeleid getal**: het percentage in X3 en de som in X4, allebei op een vraag die er expliciet om vroeg.
- **R15** (ECLI:EU:C:2019:123) kreeg een correctie op een feit dat de events niet noemen. Na de correctie was het antwoord
  gegrond. Ronde 3 kostte 60.652 tokens, deze ronde 86.408.
- **Kosten**: ten minste één extra modelronde van 37.000 tot 40.000 tokens per keer, de herschrijving met het hele dossier.
  X3 kostte 277.316 tokens in 9 rondes, X4 246.188 in 8. Hoeveel daarvan precies op de correctie valt, staat niet in de
  meting. De sjabloonweigeringen (`extern.vul`, twee keer in elk) kostten er ook rondes bij.
- **Het effect** was bij X3 slechter (het aandeel verdween) en bij X4 een vals signaal.

Elke vraag naar een aandeel of een totaal laat de correctieronde dus vuren. Daarom is de generieke route uit het voorstel
van de hoofdsessie in ronde 5 gebouwd: een som, verschil of percentage van getallen die de tekst noemt én die in de bron
staan, is geen bewering.

## De tellers uit `meting.sjabloon`

Over alle 37 beurten:

- gevuld: `antwoord_extern` 20, `antwoord_duiding` 1;
- geweigerd: `antwoord_extern:extern.vul` 7 (R08, R09, X3 2×, X4 2×, X5), `antwoord_extern:extern.lijsten` 2 (R20, R30);
- gevraagd (het herhaalverzoek) 6, gemist 3 (R08, R09, R15);
- `tekst_ernaast` 4.234 tekens, verdeeld over 12 beurten. R28b alleen al schreef 1.582 tekens naast het sjabloon.

## Wat een gelezen stuk kost

Staatsblad zag sinds bundel 50/51 zo'n 8.000 tokens per beurt meer bij een stuk dat in één ronde gelezen wordt. In deze
ronde is dat niet te zien:

- de invoer per modelaanroep is in ronde 4 zo'n 700 tokens groter dan in ronde 3: R11 47.029 → 47.726, R13 29.616 →
  30.313, R12 47.046 → 47.743. De eerste aanroep van de supervisor is gelijk (2.229). Het verschil zit dus in het vaste deel
  van het antwoordverzoek (de toolbeschrijvingen en de prompt), niet in een extra ronde;
- de toets op beweringen kost alleen tokens als hij een correctieronde laat vuren. Dat gebeurde 3 keer in 37 beurten, en
  nooit bij een beurt die alleen een stuk las;
- een uitspraak lezen werd goedkoper: R11 kostte 95.968 tokens in 2 rondes, nu 48.369 in 1; R16 ging ook van 2 naar 1 ronde.

Een verschil van 8.000 per beurt komt dus waarschijnlijk uit het resultaat van de leestool van Staatsblad zelf. Of dat zo
is, zie je door de invoer van de eerste antwoordaanroep in `meting.aanroepen` tussen de twee rondes te vergelijken.

## Bevindingen

1. **Een tijdelijke 400 van LiDO werd een geweigerde vraag** (R08, R26, en de eerste poging van R06). De herhaallus van K16
   probeerde een 400 van LiDO wel opnieuw, maar na de laatste poging gold de standaardindeling: een 4xx is
   `verzoek_geweigerd`. Het model las daaruit dat de vraag fout was. **Ronde 5:** elke adapter declareert welke statussen bij
   die bron tijdelijk zijn (`http_beleid.Statusbeleid`), en een status die tijdelijk blijft is `bron_onbereikbaar`.
2. **Een lege tussenstap werd een "geen"** (R09, R06). Onder belasting gaf `get-id` een antwoord zonder bruikbaar id. Bij
   R09 bleef er daardoor geen versie over: "geen uitspraken", en dat bleef een dag bewaard. Bij R06 brak de keten van versies
   halverwege af, en de telling miste 129 uitspraken. **Ronde 5:** een lege `get-id` gaat één keer opnieuw, en een uitkomst
   zonder versie of met een afgebroken antwoord wordt niet bewaard. Hetzelfde voor lege metadata en een lege titel.
3. **De afgeleide getallen** (X3, X4): zie hierboven. **Ronde 5:** de route voor een som, verschil of percentage.
4. **KOOP noemde elke 4xx "niet bereikbaar" en herhaalde niets**, de BWB-zoekdienst herhaalde alleen een 5xx en maar één
   keer. Gezien bij het bouwen van punt 1, niet in deze meting. **Ronde 5:** hetzelfde beleid voor alle adapters.

## Wat deze ronde niet zegt

- Eén run per vraag. De verliezen kwamen door de traagheid van LiDO op dat moment; een rustige dag had ze waarschijnlijk niet
  laten zien.
- De extra vragen zijn nieuw, dus er is geen vergelijking met eerdere rondes.

Voor deze ronde zijn 37 gesprekken aangemaakt, plus 20 lege door de budgetfout. Er is niets gewijzigd of gewist.
