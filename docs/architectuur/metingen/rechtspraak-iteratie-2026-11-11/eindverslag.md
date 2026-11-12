# Rechtspraak, iteratie – eindverslag – 12 november 2026

Soort: *eindverslag* van de iteratierondes voor de connector Rechtspraak (opdracht van de gebruiker, 11 nov 2026: hoogstens
vier rondes, stoppen als alles klopt). Vragen: [`rechtspraak_vragenset_30.json`](../../../../tools/graph-qa/tests/data/rechtspraak_vragenset_30.json),
30 vragen in 32 beurten, met de routetoets `tools/graph-qa/tests/test_rechtspraak_vragenset.py`.

## Per ronde

| ronde | code | goed | deels | fout | n.b. | zonder model | tokens | verslag |
|---|---|---|---|---|---|---|---|---|
| 1 | `bb6b46a5` (bundel 40) | 16 | 11 | 4 | 1 | 10 | 2.700.587 | [ronde-1.md](ronde-1.md) |
| 2 | `80ca14f4` (bundel 43, #1229) | 26 | 6 | 0 | – | 16 | 1.934.419 | [ronde-2.md](ronde-2.md) |
| 3 | `a0eeb8de` (bundel 45, #1235) | 31 | 1 | 0 | – | 16 | 1.997.147 | [ronde-3.md](ronde-3.md) |

Na ronde 3 is er één vraag deels (R22: het model duidt een telling) en geen enkele fout. Vier rondes zijn niet nodig voor de
connector zelf. Een vierde ronde zou alleen de fixes van ronde 3 op acceptatie toetsen (de label van een stuk zonder tekst,
regelingen uit een zoekresultaat, het boeknummer, de grens per bron); die horen grotendeels bij andere connectors en worden
daar ook gemeten.

## Wat er veranderde

**In de connector** (`tools/graph-qa/agent/tools/rechtspraak_tools.py`, `adapters/lido_rechtspraak.py`):
- LiDO `get-links` vraagt alleen jurisprudentie; een veelgebruikt artikel (Awb 6:7, 6.772 uitspraken) brak anders af.
- Een regeling buiten de kennisgraaf (Wet IB 2001, Wet OB 1968) zoekt LiDO op bwb-id en nummer, met haar titel uit de
  BWB-zoekdienst.
- Een regeling zonder artikel geeft de uitspraken bij de regeling als geheel (de Leidraad Invordering 2008: 204).
- Tellingen per instantie en per tekststand tellen binnen de andere filters; `bij_het_artikel` zonder filters.
- Een rechtsgebied naast een artikel wordt niet toegepast, en dat staat erbij; het meervoud van een instantiesoort werkt.
- Een buitenlandse ECLI is een stuk zonder tekst; een onvolledige lijst noemt wat LiDO zelf telt.

**Gedeeld, met Rechtspraak als eigenaar** (aangewezen door de hoofdsessie):
- `bron_lijst`: een maand, een werkwoord achter het onderwerp, "kamerdossier", "alle", "Zoek …", een naam binnen een
  langere regelingnaam, en een begripsvraag is geen lijst.
- `sjablonen/extern`: de `kanttekening` van een zoektool in het blok en de leemte, pagina's van één zoekvraag als één lijst, een
  gelezen stuk bij zijn zoekvraag, het lidwoord, de maand, geen volgorde bij niets gevonden, de grens per bron.
- `provenance` en `grounding`: een fout zonder stuk is geen bron, een stuk in een fout houdt zijn label, een regeling uit een
  zoekresultaat is geen bron, een citeervorm ("Stb. 2013, 568") houdt een gelezen stuk in de bronnenlijst, en een artikel met
  boeknummer is bekend.

## Wat open blijft

- **R22**: het model duidt een telling ("past bij het civiel- en belastingrechtelijke karakter"), ondanks de regel in de
  toolbeschrijving.
- **De kosten van lezen**: een vraag die vier arresten leest (R27) kost 235–335k tokens; een samenvatting van één lang arrest
  (R11) leest nog alle pagina's, maar nu in één ronde (96k).
- **De duur bij LiDO**: een artikel met veel uitspraken kost bij een koude cache 15–40 s (R01, R05–R07).
