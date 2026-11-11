# Staatsblad en Staatscourant, iteratie – ronde 2 (11 november 2026)

Soort: *meting* · Code: master `73569621` (bundel 42, #1226, met #1225: versies, "wetten", grens, G1 en G2) · Straat:
acceptatie · Model: `claude-sonnet-4-6` · Uitvoering: zoals [ronde 1](ronde-1.md), dezelfde 30 vragen, elk één keer,
drie tegelijk. Ruwe gegevens in [`runs.jsonl`](runs.jsonl) (`ronde: 2`). Tokens = invoer + uitvoer + cache lezen + cache
schrijven, uit het `meting`-event.

## Uitkomst

**26 goed, 4 deels, 0 fout** (ronde 1: 21, 8, 1). **Samen 1.626.011 tokens** (ronde 1: 1.518.494). Tien vragen gaan
zonder model (ronde 1: negen); B20 is erbij gekomen.

| # | oordeel (r1 → r2) | tokens (r1 → r2) | rondes |
|---|---|---|---|
| B03 | deels → goed | 105.457 → 152.339 | 6 |
| B05 | deels → goed | 72.921 → 48.031 | 3 |
| B12 | deels → deels | 66.960 → 67.261 | 3 |
| B16 | goed → goed | 184.674 → 129.210 | 5 |
| B18 | deels → goed | 44.667 → 66.515 | 4 |
| B20 | deels → goed | 44.604 → 0 | 0 |
| B21 | deels → deels | 286.700 → 327.195 | 10 |
| B22 | deels → deels | 35.738 → 41.480 | 2 |
| B23 | goed → goed | 87.501 → 111.620 | 6 |
| B24 | goed → goed | 88.955 → 144.468 | 7 |
| B25 | **fout → goed** | 21.710 → 21.489 | 1 |
| B26 | goed → goed | 105.279 → 140.089 | 5 |
| B27 | deels → deels | 19.104 → 19.109 | 1 |

De overige zeventien vragen zijn gelijk gebleven: dezelfde vorm, tokens binnen 1%. Lijstroutes kosten 0 tokens.

**Garanties:** geen run ongegrond, 0 niet-letterlijk, geen naam van een particulier.

## Wat de fixes van ronde 1 deden

- **Versies** (B25): Lex noemt nu `stcrt-2024-20015-n1`. Was fout, nu goed.
- **"wetten" als soort** (B20): de vraag is nu een lijstvraag, voor 0 tokens, met zoekvraag en totaal.
- **G2, één keer om het sjabloon vragen** (B03, B05, B18): de lijsten komen nu met het blok `stukken` en links. Het kost
  een ronde extra (B03 +47k, B18 +22k). B05 werd goedkoper, omdat het model meteen het sjabloon nam.
- **G1, één weigering met alle fouten** (B16): 185k → 129k, met alle 17 regelingen. Toch nog drie sjabloonrondes.
- **De grens bij personen** (B15): de tekst klopt nu ("staan wel in de Staatscourant"). Het model zegt er alleen
  systeemtaal bij ("de regels van deze werkplek … mag opvragen").

## Bevindingen

1. **Een geweigerd sjabloon kost nog rondes bij veel passages** (B21: drie rondes van ~1.700 tokens, 327k; B16: drie;
   B26: twee). G1 noemt nu alle fouten tegelijk. De herhaling komt dus vermoedelijk van de grens van zes alinea's per
   aanwijzing: B21 citeert ~30 passages. Kamerstukken zag hetzelfde (K15: vijf weigeringen, 450k). Opgelost in
   `c67171f5` (de code splitst een reeks zelf, met een totaal van 48 alinea's), maar dat stond nog niet op acceptatie.
   *Gedeeld*, `sjablonen/extern.blokken` (eigenaar: deze sessie, G1).
2. **De versies staan in het stuk, maar het model noemt ze niet** (B12). In B25 werd naar de versies gevraagd, en dan
   gebruikt Lex het veld. In B12 werd gevraagd wat er in het stuk staat, en dan leest het model `stuk.versies` niet.
   *Deze connector.*
3. **Tekst na het lezen van een stuk** (B22): een markdown-tabel zonder sjabloon en zonder citaat, met twee nummers die
   het model zelf afleidde. D heet daar "25.2.10 (nieuw)", terwijl de bron "na artikel 25.2.9 een nieuw artikel" zegt.
   J heet "25.5a.1–25.5a.3", maar die nummers staan nergens. G2 vraagt alleen om het sjabloon na een *zoek*resultaat,
   niet na een gelezen stuk. *Gedeeld*, `nodes/antwoord.py` (G2, eigenaar: deze sessie).
4. **Een stuk lezen kost een ronde per pagina** (B21: zes rondes bladeren, pagina's van 9 tot 30 rijen). Elke ronde
   leest de hele context opnieuw uit de cache, zodat zes rondes ~180k cache-lezen kosten. *Gedeeld:* de voorlezing
   (`nodes/bron_lezen.py`) zou meer pagina's in één keer kunnen ophalen. Ik meld dit eerst bij de hoofdsessie.
5. **Bekend en gedeeld:** B27 (het oude Sdu-formaat, G3, eigenaar Kamerstukken, nog niet op acceptatie). Lex zegt
   daar nog "staat in de kennisgraaf" en "waarschijnlijk alleen PDF".
6. **Spreiding:** B23, B24 en B26 kostten 25–60% meer dan in ronde 1, met een of twee rondes meer, bij een gelijk
   oordeel. Eén run per vraag is te weinig om dat aan een fix toe te schrijven.

## Wat deze ronde niet zegt

Eén run per vraag. De tekst van de antwoorden is gelezen waar het oordeel ervan afhangt (B03, B05, B12, B15, B16, B18,
B22, B25, B27, B30). Bij de vragen met dezelfde vorm als in ronde 1 zijn alleen route, tokens, bronnen en grounding
nagelopen.
