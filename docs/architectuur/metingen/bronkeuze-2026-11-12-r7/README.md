# Bronkeuze robuust (#1273) – B18, K16 en een steekproef (12 november 2026)

Soort: *meting* · Code: master `a120e579` (bundel 55, met #1273: de reden `niet_nodig`, filterwaarden die connectors
meenemen, `aanwijzingen` die herkennen zonder te noemen, en #1270 `van_route`) · Straat: acceptatie, **alle vier de
connectors aan** · Model: `claude-sonnet-4-6` · Uitvoering: de acceptatie-MCP, één run per vraag in een eigen gesprek
("Ronde 7 bronkeuze – …"). Vergeleken met de meting van #1261 ([`../bronkeuze-2026-11-12/`](../bronkeuze-2026-11-12/README.md),
"ronde 6"). Tokens = invoer + uitvoer + cache lezen + cache schrijven uit het `meting`-event. Ruwe gegevens in
[`runs.jsonl`](runs.jsonl).

**Onvolledig**: na K16 was het tokenbudget op. De vijf Kamerstukken-vragen (K11, K13, K14, K19, K29) gaven een 429
`budget_op`; hun vraag staat als user-bericht in het gesprek, er liep geen run. Ze volgen na een reset.

## Uitkomst

| vraag | ronde 6 | nu | bronstand nu |
|---|---|---|---|
| B18 "Welke publicaties horen bij Kamerdossier 36602?" | fout, 1 ronde, 21.545 | **goed**, 0 rondes, 0 tokens | Kamerstukken en Staatsblad aan; Rechtspraak, Wetgeving buiten de graaf `niet_nodig` |
| K16 "Wat bedoelde de wetgever met artikel 36 van de Invorderingswet 1990?" | deels, 15 rondes, 448.370 | **goed**, 16 rondes, 638.235 | alle vier aan |

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

## Andere bevindingen

1. **`id_herkomst` werkt**: de zoekvraag op dossier 20588 (uit het geheugen van het model) ging niet naar de bron, maar
   kwam terug als `id_niet_uit_gesprek`.
2. **De grens van KOOP staat in de toelichting, maar remt het zoeken niet**: na de eerste lege zoekvraag zocht het model
   nog tien rondes door. Een kandidaat voor de prompt of de toolbeschrijving.
3. `tekst_ernaast` bij K16: 93 tekens (ronde 6: niet gemeten bij K16).

## Wat deze meting niet zegt

Twee vragen, één run per vraag. De steekproef van vijf Kamerstukken-vragen (genoemd stuk, verwacht: alleen Kamerstukken,
~26k) moet nog.
