# Staatsblad en Staatscourant, iteratie – ronde 3 (11 november 2026)

Soort: *meting* · Code: master `80ca14f4` (bundel 43, #1232, met #1230: K15, versies in de toelichting, G2 na een gelezen
stuk; en #1227 van Kamerstukken: het Sdu-formaat, een stuk zonder tekst zonder model) · Straat: acceptatie · Model:
`claude-sonnet-4-6` · Uitvoering: zoals [ronde 1](ronde-1.md), dezelfde 30 vragen, elk één keer, drie of vier tegelijk.
Ruwe gegevens in [`runs.jsonl`](runs.jsonl) (`ronde: 3`). Tokens = invoer + uitvoer + cache lezen + cache schrijven, uit
het `meting`-event. B01–B03 liepen vóór, en B04–B30 na de reset van het tokenbudget (19:47 UTC). B04–B06 zijn opnieuw
gestart in hun eigen gesprek (`vraag_bewaren: false`).

De voorlezing van een kort stuk (`04ba8bc4`, bevinding 4 van ronde 2) staat nog niet op acceptatie. Deze ronde meet haar dus niet.

## Uitkomst

**27 goed, 3 deels, 0 fout** (ronde 2: 26, 4, 0; ronde 1: 21, 8, 1). **Samen 1.435.498 tokens** (ronde 2: 1.626.011;
ronde 1: 1.518.494). Dertien vragen gaan zonder model (ronde 2: tien). B07, B13 en B18 zijn erbij gekomen.

| # | oordeel (r2 → r3) | tokens (r2 → r3) | rondes |
|---|---|---|---|
| B03 | goed → goed | 152.339 → 161.192 | 7 |
| B04 | goed → goed | 168.380 → 202.476 | 9 |
| B06 | goed → goed | 41.987 → 20.725 | 1 |
| B07 | goed → goed | 19.395 → 0 | 0 |
| B12 | **deels → goed** | 67.261 → 22.461 | 1 |
| B13 | goed → goed | 19.131 → 0 | 0 |
| B16 | goed → **deels** | 129.210 → 186.930 | 7 |
| B18 | goed → goed | 66.515 → 0 | 0 |
| B21 | deels → deels | 327.195 → 328.450 | 10 |
| B22 | deels → deels | 41.480 → 39.677 | 2 |
| B23 | goed → goed | 111.620 → 87.641 | 5 |
| B24 | goed → goed | 144.468 → 84.582 | 5 |
| B26 | goed → goed | 140.089 → 101.995 | 4 |
| B27 | **deels → goed** | 19.109 → 21.858 | 1 |

De overige zestien vragen zijn gelijk gebleven: dezelfde vorm, en de tokens binnen 5%.

**Garanties:** geen run ongegrond, 0 niet-letterlijk, geen naam van een particulier (B15, B30).

## Wat de fixes van ronde 2 deden

- **De versies in de toelichting** (B12): Lex noemt nu de eerdere versie (stcrt-2024-20015 van 28 juni 2024) en zet
  beide in de bronnen. Dat was deels en is nu goed, voor 22k in plaats van 67k.
- **G2 na een gelezen stuk** (B22): het antwoord komt nu met het sjabloon en citaten, en niet meer als markdown-tabel.
  Twee nummers leidt het model nog zelf af (zie bevinding 3).
- **Het Sdu-formaat** (B27, #1227): Stb. 1995, 1 is leesbaar. Lex citeert de Rijkswet tot wijziging van het Statuut
  letterlijk, met de vindplaats van de Kamerstukken.
- **Een stuk zonder tekst zonder model** (B07, B13, #1227): een PDF-stuk of een onbekend id beantwoordt de code nu zelf,
  voor 0 tokens. Alleen B07 zegt het dubbel: "alleen als PDF (alleen als PDF)" (zie bevinding 4).
- **"Kamerdossier"** (B18): dit is nu een lijstvraag, voor 0 tokens.
- **K15, een lange reeks in één aanwijzing**: dit hielp niet bij B21 en B16. Daar zit de grens elders (bevinding 1).

## Bevindingen

1. **Het sjabloon weigert meer dan acht aanwijzingen** (B16: zes sjabloonrondes, 187k; B21: drie, 328k). `extern.blokken`
   staat hoogstens `MAX_STUKKEN * 2` = 8 aanwijzingen toe.
   - B16 wil de aanhef van 17 artikelen van een verzamelwet aanwijzen: dat zijn 17 losse alinea's, dus 17 aanwijzingen.
     Het model gaf het na zes rondes op. Zijn twijfel zegt het zelf: de aanhefteksten "konden niet alle in de acht
     aanwijzingen worden opgenomen". Daarbij noemt het antwoord "achttien" regelingen en somt het er zeventien op.
   - B21 citeert 46 alinea's in reeksen met gaten, en dat zijn ook meer dan acht aanwijzingen.

   Sinds K15 begrenst `MAX_ALINEAS` (48) het totaal. Een aanwijzing draagt minstens één alinea, dus die grens begrenst
   het aantal aanwijzingen al. **Opgelost in deze PR:** het aantal aanwijzingen heeft geen eigen grens meer (hoogstens
   `MAX_ALINEAS`), met een test voor 17 losse alinea's. *Gedeeld*, `sjablonen/extern.blokken` (eigenaar: deze sessie, G1).
2. **Een stuk lezen kost nog een ronde per pagina** (B21: zes rondes bladeren). Dit is ongewijzigd, want de voorlezing
   (`04ba8bc4`) staat nog niet op acceptatie. Ze zit in deze PR en wordt in ronde 4 gemeten.
3. **Zelf afgeleide nummers** (B21, B22): "nieuw art. 25.2.10" voor "na artikel 25.2.9 een nieuw artikel", en
   "25.5a.3" (25.5a.1 en 25.5a.2 staan wel in de bron). B22 zet "(na art. 25.2.9)" er nu bij. Het blijft een fout van het
   model, en een generieke fix zie ik niet: de code weet niet welke nummers het model in zijn eigen woorden noemt.
4. **Klein, gedeeld:** de melding bij een stuk zonder tekst zegt "staat bij de bron alleen als PDF (alleen als PDF)" (B07). De
   staart komt uit het label van het stuk. *Gedeeld*, `bron_lezen._zonder_tekst` (Kamerstukken); gemeld aan de hoofdsessie.
5. **Spreiding:** B03 en B04 kostten 6–20% meer dan in ronde 2, met één ronde meer, bij hetzelfde oordeel. B23, B24 en
   B26 kostten 20–40% minder. Bij één run per vraag zegt dat niets over een fix.

## Wat deze ronde niet zegt

Eén run per vraag. De tekst is gelezen bij B07–B09, B12–B16, B18, B21–B27 en B30. Bij de andere vragen zijn alleen de
route, de tokens, de bronnen en de grounding nagelopen.
