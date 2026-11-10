# Rechtspraak op acceptatie, nameting – 10 november 2026

Soort: *meting* · Code: master `9d5a56a0` (bundel 30, #1180: #1178 + #1179) · Straat: acceptatie, Rechtspraak en
Kamerstukken aan in het register · Model: `claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP, elke run in een
nieuw gesprek, één tegelijk · Akkoord: gegeven bij de eerste meting en herhaald voor deze nameting.

Dit is dezelfde 5×3 als in [`rechtspraak-2026-11-10/`](../rechtspraak-2026-11-10/README.md), na de oplossingen in #1179.
De ruwe gegevens per run staan in [`runs.jsonl`](runs.jsonl). Tokens = cache lezen + cache schrijven + uitvoer per run,
uit het `meting`-event. Het totaal volgens de verbruiksteller is **824.677**; dat was 1.019.997.

## Uitkomst

| # | vraag | vóór (#1178) | na (#1179) |
|---|---|---|---|
| 1 | Wat staat er in ECLI:NL:HR:2022:50? | 3/3 sjabloon, 2 rondes, 47k, gegrond ×3 | **2/3** sjabloon, 3–4 rondes, 72–97k; run 1 een vrije samenvatting met 2 signalen |
| 2 | Welke uitspraken noemen artikel 36 Iw? | **1/3** met lijstblok, 5–8 rondes, 93–178k | **3/3** `bron_lijst`, 0 rondes, 0 tokens, 0,3–6,4 s |
| 3 | De 10 nieuwste uitspraken van de HR in het belastingrecht | 3/3 `bron_lijst`, 0 tokens | 3/3 `bron_lijst`, 0 tokens, 0,3–1,2 s |
| 4 | Wat is een uitspraak op bezwaar? | 3/3 zonder Rechtspraak, 134–178k | 3/3 zonder Rechtspraak (run 1 per bron gelezen), 153–206k |
| 5 | ECLI zonder tekst | 3/3 eerlijk | 3/3 eerlijk, met de denkregel "… heeft geen tekst om te lezen" |

Wat de oplossingen in #1179 deden:

- **Vraag 2 haalt het nu.** Het blok *Gevonden Rechtspraak* staat er elke keer: 10 van 623, met de zin "Gezocht bij
  artikel 36 van Invorderingswet 1990. Nieuwste eerst." Er is geen supervisor en geen model, dus de 93–178k tokens per
  run zijn weg.
- **Labels**: "Hoge Raad 10 april 2026, ECLI:NL:HR:2026:586" en "Parket bij de Hoge Raad 23 juni 2026, …", in vraag 2 en 3.
- **De spatie bij een regelafbreking**: "bankrekeningen. In bezwaar" (was "bankrekeningen.In").
- **r.o. in het blok**: elke passage onder een genummerde rechtsoverweging draagt "(r.o. 2.1)" tot "(r.o. 3.3)".
- **Geen soortfilter uit "uitspraken"**: de zoekvraag zegt het niet meer. Het totaal blijft 19.523, want de conclusies
  vallen onder het Parket en niet onder de Hoge Raad.
- **De denkregel** bij een uitspraak zonder tekst staat er in alle drie de runs.
- **De controle**: 0 niet-letterlijk in 15 runs. Onbevestigd: 2 signalen, beide in vraag 1, run 1 (zie hieronder).

## Bevindingen

1. **Vraag 1 werd duurder en is één keer uit het sjabloon gevallen.**
   - De eerste pagina van `get_uitspraak` heeft nu 23 rijen in plaats van 25: het veld `plek` kost ruimte binnen de
     begroting. Daardoor haalt het model in alle drie de runs het tweede deel op (offset 23), met een ronde en een
     toolaanroep extra (72–97k tegen 47k).
   - In run 1 schreef het model daarna een vrije samenvatting in plaats van het sjabloon *extern*. Die samenvatting noemt de
     r.o.-nummers goed, maar geeft 2 onbevestigde signalen: "ruim € 2,4 miljoen" (de bron zegt € 2.438.324) en een eigen
     blokcitaat "Let op: …".
   - Mogelijke oplossing: `ro` en `plek` dubbelen elkaar ("2.1" en "r.o. 2.1"). Eén veld scheelt per rij en houdt de
     uitspraak van 28 alinea's waarschijnlijk op één pagina.
2. **De denkregel noemt het BWB-id** ("Lex · zoekt uitspraken bij artikel 36 van BWBR0004770"). Het werkwoord van
   `zoek_uitspraken` vult `{bwb_id}` in; de naam van de regeling staat pas in het resultaat.
3. **De zoekvraagzin van vraag 3 loopt niet**: "Gezocht op van de Hoge Raad en rechtsgebied belastingrecht." De vorm voor
   een orgaan ("van de …") past niet achter "Gezocht op".
4. **De bronnenlijst van vraag 1 noemt ook `ECLI:CE:ECHR:2002:…`**, een uitspraak waar de HR-uitspraak naar verwijst, maar
   die het antwoord niet noemt.
5. **Vraag 5**: Lex voegt in run 1 een eigen duiding toe ("WAHV-zaak, dus een verkeersboete"), en zegt nog "Het systeem
   meldt" (systeemtaal).

Los van Rechtspraak blijft vraag 4 de duurste (9–10 rondes, 153–206k): een definitievraag zonder wettelijke definitie. Dat
is gemeten, niet onderzocht.

## Wat deze meting niet zegt

Hetzelfde als in de eerste meting: geen juridisch oordeel over de uitspraken, en de begrenzer en de versiecontrole van de
cache zijn onder deze belasting niet zichtbaar. In vraag 4, runs 2 en 3, zijn de tools niet per stuk gelezen; de vorm van
die runs is gelijk aan die van run 1.
