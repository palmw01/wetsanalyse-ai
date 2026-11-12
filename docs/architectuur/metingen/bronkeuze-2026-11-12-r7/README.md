# Bronkeuze robuust (#1273) – B18, K16 en vijf Kamerstukken-vragen (12 november 2026)

Soort: *meting* · Code: master `a120e579` (bundel 55, met #1273: de reden `niet_nodig`, filterwaarden die connectors
meenemen, `aanwijzingen` die herkennen zonder te noemen, en #1270 `van_route`) · Straat: acceptatie, **alle vier de
connectors aan** · Model: `claude-sonnet-4-6` · Uitvoering: de acceptatie-MCP, één run per vraag in een eigen gesprek
("Ronde 7 bronkeuze – …"). Vergeleken met de meting van #1261 ([`../bronkeuze-2026-11-12/`](../bronkeuze-2026-11-12/README.md),
"ronde 6"). Tokens = invoer + uitvoer + cache lezen + cache schrijven uit het `meting`-event. Ruwe gegevens in
[`runs.jsonl`](runs.jsonl).

Na K16 was het tokenbudget op; na een reset (12:31 UTC) liepen de vijf Kamerstukken-vragen (K11, K13, K14, K19, K29) in
hun bestaande gesprekken, zonder het user-bericht opnieuw.

## Uitkomst

| vraag | ronde 6 | nu | bronstand nu |
|---|---|---|---|
| B18 "Welke publicaties horen bij Kamerdossier 36602?" | fout, 1 ronde, 21.545 | **goed**, 0 rondes, 0 tokens | Kamerstukken en Staatsblad aan; Rechtspraak, Wetgeving buiten de graaf `niet_nodig` |
| K16 "Wat bedoelde de wetgever met artikel 36 van de Invorderingswet 1990?" | deels, 15 rondes, 448.370 | **goed**, 16 rondes, 638.235 | alle vier aan |
| K11 "Wat staat er in kst-33755-3?" | goed, 1 ronde, 25.879 | goed, 1 ronde, 25.919 | Kamerstukken |
| K13 doel van het voorstel in kst-33755-3 | goed, 1 ronde, 25.849 | goed, 1 ronde, 25.879 | Kamerstukken |
| K14 kst-33755-3 over artikel 29 Iw 1990 | goed, 1 ronde, 26.004 | goed, 1 ronde, 25.863 | Kamerstukken |
| K19 "Wat staat er in Kamerstuk 32740, nr. 1?" | goed, 2 rondes, 45.487 | goed, 1 ronde, 22.206 | Kamerstukken (gelezen: de andere drie `niet_nodig`) |
| K29 verwijzing naar het regeerakkoord in kst-33755-3 | goed, 1 ronde, 25.715 | goed, 1 ronde, 25.742 | Kamerstukken |

- **B18 is opgelost.** De filterwaarde (dossier) neemt Kamerstukken en Staatsblad mee, en de lijstroute zoekt in code
  `zoek_kamerstukken {dossier: 36602}`: 19 van de 206 stukken, op nummer, zonder model. De bronstand zegt bij de twee
  andere bronnen `niet_nodig`, niet "uit".
- **K16 houdt alles aan**, zoals bedoeld: "bedoelde de wetgever" is een aanwijzing, geen genoemde bron. Het antwoord is
  gegrond (2 verwijzingen en 12 citaten): de leden van artikel 36 met uitleg, en twee passages uit de parlementaire
  geschiedenis (het verslag van het AO over de evaluatie, kst-25600-IXB-22, dat het preventieve doel noemt; en de memorie
  van antwoord bij 30322, die minder op de vraag ingaat). Het sjabloon is één keer geweigerd (ronde 6: twee keer).
- **K16 kost meer**, maar niet door de bronkeuze. Alle 21 toolaanroepen gaan naar de wetgeving of Kamerstukken; de drie
  andere connectors kosten alleen hun schema's. Het model zocht 13 keer in Kamerstukken naar de oorspronkelijke memorie
  van toelichting (1988–1990), die vóór de grens van KOOP valt (vanaf 1994–1995). Per modelronde: 39,9k (ronde 6: 29,9k).
  Bij één run per vraag spreidt het aantal rondes sterk (vergelijk K07 in ronde 6).

- **De steekproef verandert niet**: de vijf genoemde stukken blijven beperkt tot Kamerstukken, gegrond en in één ronde met
  `antwoord_extern`. Samen 125.609 tegen 148.934 (−16 %), en zonder K19 (ronde 6 twee rondes, nu één: spreiding)
  103.403 tegen 103.447. De reden `niet_nodig` kost niets: het promptblok is even groot als bij "uit".

## Andere bevindingen

1. **`id_herkomst` werkt**: de zoekvraag op dossier 20588 (uit het geheugen van het model) ging niet naar de bron, maar
   kwam terug als `id_niet_uit_gesprek`.
2. **De grens van KOOP staat in de toelichting, maar remt het zoeken niet**: na de eerste lege zoekvraag zocht het model
   nog tien rondes door. Open punt voor later (besluit hoofdsessie: nu geen fix).
3. `tekst_ernaast`: K16 93 tekens, K11 215, K14 66, K19 194, K29 183, K13 0.

## Wat deze meting niet zegt

Zeven vragen, één run per vraag. De antwoorden van K11, K13, K14 en K29 zijn niet opnieuw gelezen: route, rondes,
grounding en sjabloon zijn gelijk aan ronde 6, en dat oordeel is overgenomen.
