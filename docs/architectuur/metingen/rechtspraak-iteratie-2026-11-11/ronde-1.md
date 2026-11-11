# Rechtspraak, iteratie – ronde 1 – 11 november 2026

Soort: *meting*, de eerste van hoogstens vier rondes · Code: acceptatie op master `bb6b46a5` (bundel 40) · Straat: acceptatie,
alle vier connectors aan · Model: `claude-sonnet-4-6` · Uitvoering: de client van de acceptatie-MCP in een script, elke vraag één
run in een eigen gesprek (een vervolgvraag in hetzelfde gesprek), drie tegelijk · Vragen:
[`rechtspraak_vragenset_30.json`](../../../../tools/graph-qa/tests/data/rechtspraak_vragenset_30.json), 30 vragen in 32 beurten.

De ruwe gegevens per run staan in [`runs-1.jsonl`](runs-1.jsonl). Tokens = invoer + uitvoer + cache lezen + cache schrijven uit
het `meting`-event: samen **2.700.587**. De feiten zijn nagekeken bij de bron (de zoekfeed van de Rechtspraak, LiDO en de
BWB-repository), niet geraden.

## Score

**15 goed, 11 deels, 4 fout**, en 2 niet beoordeeld:

- R03 is niet gedraaid. De eerste poging viel op het inloggen (drie werkers tegelijk), de tweede op het tokenbudget van het
  account (429 `budget_op`).
- R19 is niet beoordeeld. Het meetwerkgebied met peildatum 2015 was die ochtend verwijderd; de run liep zonder werkgebied.

| # | vraag (kort) | oordeel | tokens | rondes |
|---|---|---|---|---|
| R01 | uitspraken bij art. 9 Iw | goed | 0 | 0 |
| R02 | de 5 nieuwste bij art. 36 Iw | goed | 0 | 0 |
| R03 | nieuwste HR in het belastingrecht | niet gedraaid | – | – |
| R04 | CRvB in maart 2025 | deels | 177.672 | 6 |
| R05 | 10 oudste conclusies bij art. 25 Iw | deels | 62.870 | 3 |
| R06 | hoven bij art. 67f AWR | deels | 127.995 | 5 |
| R07 | RvS bij art. 6:7 Awb | **fout** | 0 | 0 |
| R08 | art. 26 Awir | goed | 0 | 0 |
| R09 | art. 3.111 Wet IB 2001 | **fout** | 104.850 | 3 |
| R10 | HR bij art. 15 Wet OB 1968 | **fout** | 101.721 | 3 |
| R11 | wat staat er in HR:2023:1371 | deels | 356.502 | 9 |
| R12 | r.o. 3.1 van HR:2023:1371 | goed | 29.951 | 1 |
| R13 | conclusie PHR:2015:354 | goed | 62.071 | 2 |
| R14 | ECLI:NL:HR:2099:1 | deels | 54.167 | 2 |
| R15 | ECLI:EU:C:2019:123 | goed | 88.868 | 4 |
| R16 | "ecli nl rbgel 2026 7933" | goed | 171.642 | 5 |
| R17 | huidige tekst art. 36 Iw | deels | 127.965 | 5 |
| R18 | art. 25 Iw op peildatum 2015 | deels | 126.250 | 5 |
| R19 | art. 25 Iw in een werkgebied | niet beoordeeld | 0 | 0 |
| R20 | eerdere tekst art. 9 Iw | goed | 87.651 | 4 |
| R21 | hoeveel bij art. 36 Iw | goed | 0 | 0 |
| R22 | verdeling per instantie art. 36 Iw | deels | 96.338 | 4 |
| R23 | alle bij art. 2 Uitvoeringsregeling Iw | deels | 126.167 | 5 |
| R24 | belastingrecht bij art. 36 Iw | deels | 93.206 | 3 |
| R25 | CBb bij art. 9 Iw (niets) | goed | 0 | 0 |
| R26 | de Leidraad Invordering 2008 | goed | 127.082 | 5 |
| R27 | art. 36 Iw en de Hoge Raad | goed | 346.646 | 9 |
| R28a | HR bij art. 36 Iw | goed | 0 | 0 |
| R28b | "wat zegt de nieuwste daarvan?" | **fout** | 4.675 | 2 |
| R29a | 5 nieuwste bij art. 9 Iw | goed | 0 | 0 |
| R29b | "en de volgende 5?" | goed | 67.487 | 3 |
| R30 | uitspraken en Kamerstukken bij art. 25 lid 2 Iw | deels | 158.811 | 5 |

Wat goed gaat:

- De lijstroute zonder model (R01, R02, R08, R21, R25, R28a, R29a) levert 0 tokens, het juiste totaal en de tekststand per rij.
- Het lezen van een ECLI en een rechtsoverweging (R12, R13, R16, R27) citeert letterlijk en is gegrond.
- De grenzen van LiDO staan er eerlijk bij: per artikel, niet per lid; ten minste; de tekst die de rechter toepaste.

## Bevindingen, oorzaak en wat ermee gebeurt

1. **LiDO breekt het antwoord af bij een veelgebruikt artikel** (R07, fout). Bij Awb 6:7 gaf `get-links` HTTP 200 met een
   JSON-fout halverwege de XML, ook bij tien rijen. De terugval op RDF faalde ook. De versie stond in `onvolledig`, maar het blok
   zei alleen "Geen jurisprudentie gevonden". LiDO noemt bij dit artikel zelf 6.772 uitspraken. Oorzaak: zonder filter geeft LiDO
   ook de wetten en regelingen die het artikel noemen, met per toestand een identifier, en daarop breekt het antwoord.
   **Opgelost in deze ronde**: `get-links` vraagt alleen jurisprudentie (`fq=obj_type:Jurisprudentie`). Live geeft Awb 6:7 nu
   990 uitspraken binnen het plafond, en de toelichting noemt de 6.772 die LiDO zelf telt.
2. **Een regeling buiten de kennisgraaf gaf "staat niet in de graaf"** (R09, R10, fout). `zoek_uitspraken` leest het artikel uit
   de graaf; de Wet IB 2001 en de Wet OB 1968 staan er niet in. LiDO kent ze wel. **Opgelost**: staat de regeling niet in de
   graaf (`graaftoestanden`, een haperende graaf telt niet), dan zoekt LiDO op bwb-id en nummer, met de zin dat de tekststand niet
   vast te stellen is. Live: art. 3.111 Wet IB 627 uitspraken, art. 15 Wet OB 1.178.
3. **De tellingen spraken het totaal tegen** (R06, R17, deels). `per_tekststand`, `per_instantie` en `tekstversies` telden alle
   uitspraken bij het artikel, `totaal` alleen de gefilterde. Zo stond "487 van de hoven" naast "26 bij de huidige, 869 bij een
   eerdere tekst". **Opgelost**: elke telling telt binnen de andere filters, zoals een facet, en `bij_het_artikel` noemt het
   aantal zonder filters.
4. **De lijstroute las "gerechtshoven" en "van de advocaat-generaal" niet** (R05, R06: 60–130k in plaats van 0).
   **Opgelost** in de beschrijving van Rechtspraak: het meervoud van een soort gerecht (`INSTANTIE_MEERVOUD`), en "conclusies van
   de advocaat-generaal" als één soort.
5. **Een vervolgvraag over een uitspraak werd een wettekstvraag** (R28b, fout). "Wat zegt de nieuwste daarvan?" werd herschreven
   met "wat zegt", artikel 36 en een datum. De bepalingsroute las dat als de tekst van artikel 36 op die datum. Gedeelde code
   (`bepaling_workflow`): **gemeld aan de hoofdsessie**.
6. **Een foutmelding met een voorbeeld wordt een bron** (R14). Het voorbeeld `{"bwb_id": "BWBR0004770", …}` in een foutresultaat
   zet de Invorderingswet in de bronnenlijst. Gedeelde code (`provenance`): **gemeld**.
7. **Het blok verzwijgt de toelichting van de tool** (R07). Een onvolledige lijst of "LiDO kent dit artikel niet" kwam niet in het
   blok; ook "die … voldoen" en "van de College". Gedeelde code (`sjablonen/extern`): **gemeld**.
8. **Platte tekst met een markdown-tabel in plaats van het blok stukken** (R06, R17, R18, R22, R23), en een blok stukken in een
   modelantwoord zonder zoekvraag en totaal (R04, R27, R30). Gedeelde code (sjabloon): **gemeld**.
9. **De lijstroute leest geen maand en geeft een rechtsgebied mee naast een artikel** (R04, R24), en ziet in "Uitvoeringsregeling
   Invorderingswet 1990" twee regelingen (R23). Gedeelde code (`agent/bron_lijst.py`, `regelingen_in_vraag`): **gemeld**.
10. **Een samenvatting van een lang arrest leest alle pagina's** (R11: 8 pagina's, 357k). Nog niet aangepakt: eerst zien of het in
    ronde 2 terugkomt.

## Wat deze ronde niet zegt

- Eén run per vraag: over de spreiding zegt dit niets.
- R03 en R19 zijn niet gemeten; ze komen in ronde 2 terug, R19 in een nieuw eigen werkgebied.
- De fixes zijn lokaal en live tegen LiDO getoetst, nog niet op acceptatie. Dat doet ronde 2.

Voor deze ronde zijn 31 gesprekken aangemaakt. Er is niets gewijzigd of gewist.
