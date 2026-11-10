# Rechtspraak op acceptatie, vierde meting – 10 november 2026

Soort: *meting* · Code: master `814d46ed` (bundel 32, #1186: #1184 + #1185) · Straat: acceptatie, Rechtspraak en
Kamerstukken aan in het register · Model: `claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP, elke run in een
nieuw gesprek, één tegelijk · Akkoord: gegeven bij de eerste meting en herhaald voor deze meting.

Dit is dezelfde reeks als in [`rechtspraak-2026-11-10-derde/`](../rechtspraak-2026-11-10-derde/README.md), na #1185. De ruwe
gegevens per run staan in [`runs.jsonl`](runs.jsonl). Tokens = cache lezen + cache schrijven + uitvoer per run, uit het
`meting`-event. Volgens de verbruiksteller is het totaal **580.957** (de som per run is 580.885).

**Vraag 4 heeft twee runs, niet drie.** Voor de meting stond het account op 85% van het budget. Een derde run van vraag 4
(~200k) zou het account van de agent-jurist op acceptatie tot de reset op 11 november hebben geblokkeerd, ook voor de andere
sessies. Vraag 4 meet alleen of Rechtspraak níét geraakt wordt, en #1185 verandert daar niets aan. Na de meting staat het
account op 97%.

De hoofdsessie stelde vier vragen over de ECLI-vraag. Op alle vier is het antwoord **ja**:

- Kost ze weer ~47k? Ja: 47.473, 47.382 en 47.726.
- Zijn het 2 rondes? Ja, alle drie, met één toolaanroep.
- Komt er geen vrije samenvatting meer? Ja: 3 van 3 gebruiken het sjabloon *extern*.
- Staat de gelezen ECLI in de bronnen? Ja: 3 van 3.

## Uitkomst

| # | vraag | derde (#1182) | nu (#1185) |
|---|---|---|---|
| 1 | Wat staat er in ECLI:NL:HR:2022:50? | 2/3 sjabloon, 3 rondes, 72k ×3; 1 vrije samenvatting | **3/3 sjabloon *extern***, 2 rondes, 47,4–47,7k; de ECLI 3/3 in de bronnen |
| 2 | Welke uitspraken noemen artikel 36 Iw? | 3/3 `bron_lijst`, 0 tokens | 3/3 `bron_lijst`, 0 tokens, 0,3–4,0 s |
| 3 | De 10 nieuwste uitspraken van de HR in het belastingrecht | 3/3, 0 tokens | 3/3, 0 tokens, 0,3–1,2 s |
| 4 | Wat is een uitspraak op bezwaar? | 3/3 zonder Rechtspraak, 178–274k | 2/2 zonder Rechtspraak, 187k en 252k |
| 5 | ECLI zonder tekst | 3/3 zonder model, `leesbaar: true` | 3/3 zonder model, **`leesbaar: false`** |

Wat #1185 deed, gezien in de events:

- **Eén pagina.** `get_uitspraak` levert 28 van de 28 rijen met `volledig: true`. Daardoor is er geen tweede leesronde meer
  (was: 24 rijen en een vervolg op offset 24).
- **Het blok *Uit de rechtspraak*** draagt 11 passages met hun kop ("Uitspraak › 2 Uitgangspunten in cassatie") en
  rechtsoverweging (r.o. 2.1 tot en met 3.3). De kop staat in de rijen alleen waar hij verandert; `extern` vult hem aan.
- **De bronnen**: run 1 en 2 noemen alleen ECLI:NL:HR:2022:50. Run 3 noemt ook HR 1996 en het EHRM, omdat het antwoord
  die noemt (de verwijzing in r.o. 3.1).
- **De controle**:
  - run 1 en 3 gegrond (12 citaten en 1 verwijzing, of 3 ECLI's);
  - run 2 onbepaald met één signaal: "ruim € 2,4 miljoen" in de toelichting van Lex, waar r.o. 2.2 € 2.438.324 zegt;
  - 0 niet-letterlijk in 14 runs.

## Bevindingen

1. **Vraag 5: de lijstregel zegt "(onopgemaakt, alleen PDF)".** Dat is de tekst die `bronmodel/antwoord.py` bij elke
   `leesbaar: false` zet, en die komt van Kamerstukken. Voor een uitspraak zonder tekst in de open data klopt hij niet. Een
   tekst per connector in de beschrijving, of een algemene ("geen tekst bij de bron"), lost het generiek op.
2. **Een afgerond bedrag in de toelichting is een signaal** ("ruim € 2,4 miljoen", vraag 1, run 2). Het staat in de eigen
   woorden van Lex, niet in een citaat, en de passage met het exacte bedrag staat in het blok erboven. Dat is te meten als
   vals alarm (`onbevestigd`); er is niets mis met het antwoord.
3. **In vraag 3 zegt de slotzin "10 van de 19523 stukken"**, de statusregel "10 van 19.523". Dat is klein: het getal in
   de slotzin mist de punt voor de duizendtallen.
4. **Vraag 4 blijft de duurste vraag** (10–12 rondes, 15–18 toolaanroepen). Dat ligt niet aan Rechtspraak; die wordt in
   2 van 2 runs niet aangeroepen. De denkregel "zoekt in de wetgeving en Kamerstukken en Rechtspraak" noemt wat aanstaat.

## Wat deze meting niet zegt

Hetzelfde als in de eerdere metingen: dit is geen juridisch oordeel over de uitspraken, en de begrenzer en de versiecontrole
van de cache zijn onder deze belasting niet zichtbaar. Waarom vraag 1 twee modelrondes kost bij één toolaanroep, is hier
niet uitgezocht: de eerste ronde levert geen event op. Mogelijk is het een sjabloonaanroep die de code weigerde en die de
tweede ronde herstelde, maar de logregel is vanaf hier niet te lezen. De vorm is dezelfde als in de eerste meting
(47k, 2 rondes). Bij vraag 2 en 5 zijn de runs 2 en 3, en bij vraag 3 de runs 1 en 2, alleen op route, duur en aantal events
gelezen; hun vorm is gelijk aan die van de run die helemaal gelezen is.
