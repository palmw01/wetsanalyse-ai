# LiDO-dump: zijn de versies van een artikel volledig? (10 nov 2026)

Soort: *meting*. Het vervolg op de [LiDO-spike van dezelfde dag](../lido-spike-2026-11-10/README.md). Daar bleef één
vraag open: geeft de maandelijkse dump van Linked Data Overheid de koppelingen artikel → uitspraak over de versies van
een artikel wél volledig, waar de services dat niet doen?

Alles is alleen lezend gedaan, op publieke bronnen:

- de dump zelf;
- ter controle de LiDO-services (164 aanroepen);
- de BWB-repository (77 toestanden van de Iw);
- de Rechtspraak (6 metadata-aanroepen).

Er zijn geen modelcalls en geen productcode. De gebruiker keurde de download goed.

## De aanname die getoetst is

In de dump zijn alle versies van een artikel te vinden zonder te zoeken. Daarmee is de vereniging over versies
aantoonbaar volledig, in elk geval ten opzichte van wat LiDO zelf heeft.

## Opzet

- **De dump.**
  - Bron: `https://linkeddata.overheid.nl/export/lido-export.nt.gz`, de enige downloadlocatie die data.overheid.nl noemt
    (dataset *linked-data-overheid*, CC0 1.0, frequentie maandelijks).
  - Omvang: 5.662.706.901 bytes, `Last-Modified` 1 nov 2026.
  - Formaat: N-Triples in gzip. Het is een export van een Blazegraph, met de afgeleide triples erin (`…_TC`).
  - Opslag: gedownload in 260 s (≈ 22 MB/s), naar een eigen map buiten de repo. Hij is niet uitgepakt opgeslagen.
- **`filter_dump.py`:** één doorgang, `zcat | python -I filter_dump.py`.
  - Per BWB-id schrijft hij de regels waarin dat id voorkomt naar een eigen `.nt.gz`, als onderwerp, als object of in
    een literal.
  - Dat vangt ook de link-knopen. Hun IRI bevat beide uiteinden URL-gecodeerd
    (`…/Regellinks/rvr-jurisprudentie-<ecli>-<artikelversie>`), dus er is geen tweede doorgang nodig.
  - Daarnaast telt hij de predicaten over de hele dump.
- **`analyse_dump.py`:** per regeling.
  - Een *artikelversie* is elk onderwerp `…/bwb/id/<BWB>/<label-id>/<geldig>/<zicht>` met `dcterms:type "Artikel"`.
  - Een *uitspraak bij een artikel* is een `LinkAct` met `linktVan` een `…/jurisprudentie/id/ECLI…` en `linktNaar` een
    versie van dat artikel. Dat is dezelfde telling als `samenvat.py` van de spike: inkomend, groep Jurisprudentie,
    elk linktype.
  - De vergelijking met de spike loopt per label-id tegen `uitkomst.json`.
- **`vergelijk_live.py`:** voor 7 Iw-artikelen (2, 7c, 7d, 9, 25, 36, 49).
  - De ECLI's die de services nu geven, via route *ref* met de code van de spike, naast de ECLI's uit de dump.
  - Sequentieel, met de pauze van de spike.
- **`toestand_controle.py`:** de toets op volledigheid, onafhankelijk van LiDO.
  - Voor elke Iw-toestand in de BWB (77, van 2002-01-01 tot 2026-10-01) per artikel een hash van tekst en status, naast
    de vorige toestand.
  - Elk gewijzigd artikel moet een LiDO-versie met die begindatum hebben, en omgekeerd.
  - 0,5 s pauze per download.
- **Regelingen.**
  - In de eerste doorgang: Iw 1990 (BWBR0004770), Awb (BWBR0005537) en de Leidraad Invordering 2008 (BWBR0024096).
  - In een tweede doorgang de andere vier uit de graaf: AWR, Uitvoeringsregeling Iw 1990, Awir en Uitvoeringsregeling Awir. Die
    waren er voor de kostenschatting.

## Uitkomst

**Doorgang en kosten:**

| | doorgang 1 (3 regelingen) | doorgang 2 (4 regelingen) |
|---|---|---|
| regels | 385.213.623 | idem |
| uitgepakt | **127,7 GB** (data.overheid zegt "enkele tientallen GB") | idem |
| duur filter | 890 s (≈ 143 MB/s, één kern, `zcat` is de rem) | 787 s |
| piekgeheugen filter | **16 MB** | 18 MB |
| uitsnede (gz) | Iw 2,8 MB · Awb 288 MB · Leidraad 0,4 MB | AWR 13,8 MB · overige < 2 MB |
| analyse | Iw 0,9 s / 44 MB · Awb 56 s / 2,4 GB (naïef: alle link-knopen in het geheugen) | AWR 195 MB |

**Iw, de 128 artikelen van de spike:**

| | spike, *ref* | spike, *jci* | dump |
|---|---|---|---|
| versies | 394 | 240 | **396** (7c en 7d: elk één versie van 1 okt 2026 extra) |
| paren (artikel, uitspraak), alle versies | 5.332 | 4.388 | **5.370** |
| paren, alleen huidige versie | 2.813 | 2.813 | 2.845 |
| artikelen met minder versies of paren dan de spike | – | – | **0** |
| artikelen met meer paren | – | – | 20 (+1 tot +4, samen +38) |

- **De hele Iw in de dump:** 132 label-id's, 412 versies, 5.449 paren en 3.095 ECLI's. Daarbij zitten 5 vervallen
  artikelen die de spike oversloeg, zoals art. 50 met 60 uitspraken.
- **Awb, de steekproef van 30 artikelen tegen spike *jci*:**
  - versies: 53 in de spike, 66 in de dump;
  - paren: 26.169 in de spike, 29.298 in de dump (+12 %), waarvan 23.976 op de huidige versie;
  - grote verschillen: art. 5:32 heeft er 660 tegen 2.114, en 5:15 heeft er 0 tegen 182. Dat zijn de versies die bij de
    spike ook in RDF afbraken, plus de versies die de jci-route mist (3:24: 1 versie tegen 4).
- **Awb geheel:** 570 label-id's, 1.050 versies, **666.015 paren** (483.363 op de huidige versie) en 281.560 ECLI's.
  - Art. 8:75 heeft er 53.328, 8:54 heeft er 45.342 en 8:81 heeft er 32.671.
  - De mediaan per artikel is 99.
- **Leidraad:** 125 label-id's en 201 versies, maar 295 paren. Er zijn een paar later toegevoegde decimale artikelen
  (22bis.1, 25a.1), maar geen divisies zoals 9.4 of 26.5. "Artikel 9" heeft versies tot 2009.
- **De zeven regelingen uit de graaf samen:** ≈ 727.000 paren. De Awb is daar 92 % van. Zonder de Awb blijven er
  ≈ 61.500 over: AWR 49.536, Awir 5.683, Iw 5.449, Uitvoeringsregeling Iw 370, Leidraad 295 en Uitvoeringsregeling Awir 146.

**Live controle (7 Iw-artikelen, 164 aanroepen):** de dump bevat elke ECLI die de services geven (**0 alleen live**).

- Bij art. 9 heeft de dump er 2 meer, bij art. 36 4 meer.
- Het facet van de services zelf telt bij die versies ook minder: art. 9, versie 2016-05-01 heeft 132 in het facet,
  131 in de lijst en 133 in de dump.
- De uitspraken bestaan bij de Rechtspraak (HTTP 200).
- De links zijn op 12 jul en 14 nov 2025 geïmporteerd. Waarom de services ze niet tonen, is niet vastgesteld.
- Versies: dump en live gelijk. Live vindt nu ook 7d en de versie van 7c van 1 okt.

**Toets op volledigheid tegen de BWB (Iw, 76 overgangen tussen toestanden):**

- 344 artikelwijzigingen, 329 LiDO-versies.
- **Elke wijziging heeft een LiDO-versie, op 15 na. Die 15 zijn allemaal `status="nogniet"`**: een artikel dat al in de
  toestand staat, maar nog niet in werking is (35a/35b in 2003, 57a sinds 2013, 7c in 2015, 7d in juli 2026).
- **0 LiDO-versies zonder wijziging.**

## Bevindingen

1. **In de dump zijn alle versies van een artikel te vinden zonder te zoeken.** Alle versies dragen het label-id in hun
   IRI (`…/bwb/id/<BWB>/<label-id>/<geldig>/<zicht>`, plus `heeftBWBLabelId`). "Alle versies van art. 9" is dus een
   groepering, geen keten van `get-id`-aanroepen met datums zoals bij de services.
   - Een relatie "vorige versie" bestaat ook in de dump niet: `dcterms:replaces`/`isReplacedBy` komen voor, maar 0 keer
     op een Iw-artikel.
   - Zo'n relatie is ook niet nodig.
2. **Volledigheid is hiermee aan te tonen**, en dat is nieuw ten opzichte van de spike.
   - De versies sluiten één op één aan op de BWB-toestanden: elke artikelwijziging sinds 2002 heeft een versie, en er
     zijn geen versies zonder wijziging.
   - De enige uitzondering is systematisch en verklaard: LiDO maakt pas een versie als een artikel in werking treedt.
     Daarmee is ook **art. 57a verklaard**: het staat sinds 2013 als `nogniet` in de Iw en heeft daarom geen LiDO-id.
     Dat was in de spike "om een onbekende reden".
   - Tegenover de services is de dump een **bovenverzameling**:
     - geen enkel artikel heeft minder versies of paren;
     - in de live controle is geen enkele ECLI alleen live te vinden;
     - de services missen een klein deel: Iw 0,7 %, Awb-steekproef 11 %, via de *jci*-route en afgebroken versies.

   **De grens:** volledigheid geldt ten opzichte van wat LiDO heeft gelinkt, niet ten opzichte van alle uitspraken die
   een artikel noemen. De LinkExtractor herkent niet elke vermelding (zie de 3 gemiste patronen in de precisiemeting van
   de spike).
3. **De dump is actueler dan de spike meende.**
   - De laatste BWB-import van de Iw is van 7–8 okt 2026; de toestand van 1 okt 2026 zit erin (7c en 7d).
   - Link-imports lopen door tot ten minste 29 okt 2026 (`links-2026-10-*`). Na 2 jul kwamen er bij de Iw 118 paren bij.
   - De conclusie "laatste link-import 2 jul 2026" uit de spike klopt dus niet als stand van LiDO. Op 10 nov 's middags
     kenden ook de services 7d.
   - De dump zelf loopt maximaal een maand achter (1 nov). Een uitspraak van deze week staat er pas in december in.
4. **Linktypen** (Iw, inkomend op artikelversies, in de dump):
   - 5.309 `lx-referentie` (LinkExtractor) en 560 `rvr-referentie` (redactioneel) vanuit jurisprudentie;
   - 2.213 `bwb-externe-referentie` vanuit wetten;
   - uitgaand: 1.501 `bwb-externe-referentie`, 414 `bwb-ontstaansbron` en 411 `bwb-inwerkingtredingsbron`.

   Bij de Awb komen daar `uwv-referentie`, `svb-grondslag` en `puc-opendata-referentie` bij.
5. **Lid-niveau, deels.** Een `LinkAct` draagt in `prov:wasDerivedFrom` de herkende verwijzing met `opschrift`
   ("artikel 2, lid 2, letter d, van de Invorderingswet 1990") en de datum van de uitspraak (`g=`).
   - Bij de Iw noemt **38 %** van de lx-links een lid in die tekst.
   - Het is vrije tekst, geen gestructureerde lid-id. De services gaven alleen artikelniveau.
6. **Omvang.** De dump is 128 GB uitgepakt, niet "enkele tientallen".
   - Eén streamende doorgang kost ≈ 13–15 min en vrijwel geen geheugen.
   - Een doorgang voor zeven regelingen kost evenveel als een doorgang voor één.
   - Het gewicht zit in de Awb: 666k paren, 92 % van het totaal.

## Go/no-go

- **Go voor de dump als toets op en aanvulling van de live connector.**
  - Een maandelijkse run kan per artikel het aantal uitspraken uit de dump naast de connector leggen (het facet
    `totaal_lido` en de lijst). Zo wordt de regel "ten minste deze" van de connector meetbaar: de connector mist bij de
    Iw 0,7 %.
  - De run kan ook het lijstje versie-id's per artikel leveren. De connector hoeft de versies dan niet meer te zoeken:
    de zwakke ref/jci-route vervalt, net als de stille afbraak bij versies die hij niet vond.
  - Dat past bij "de tool haalt wat" (ADR-013): de dump levert alleen de index, de tekst blijft live bij de Rechtspraak.
- **Een graafimport uit de dump is haalbaar, maar alleen zinvol zonder de Awb, of met de Awb begrensd.**
  - Een maandelijkse job (in bwb-import of ernaast):
    - streamt de dump direct van de URL door het filter (`curl | zcat | filter`, 0 bytes schijf);
    - duurt ≈ 20 min: 4–5 min download plus ≈ 15 min filter;
    - gebruikt minder dan 100 MB geheugen als de aggregatie per artikel streamend gebeurt (de analyse hier hield alle
      link-knopen vast: 2,4 GB bij de Awb).
  - **Omvang in GraphDB.** Bij ≈ 3 triples per paar (artikel-label, ECLI, linktype) plus ≈ 4 per ECLI (titel, datum,
    instantie, rechtsgebied):
    - zonder de Awb: ≈ 61k paren, ≈ 30k ECLI's, ≈ 0,3 M triples;
    - met de Awb: ≈ 727k paren, ≈ 300k ECLI's, ≈ 3–3,5 M triples.
  - **Graafwacht.** De graaf is niet-persistent, en een herstart zou elke keer de hele dump opnieuw lezen (≈ 20 min
    verkeer bij KOOP). Dat verdraagt de graafwacht slecht, die elk kwartier peilt.
    - Dan moet de uitsnede (Iw+AWR+Awir: ≈ 20 MB gz) als artefact bewaard worden, bijvoorbeeld als bijlage van de
      job-run of in blob-opslag.
    - Dat vraagt opslag die er nu niet is (zie de grens van de SP in `deploy/azure/README.md`).
- **Waarom live per bepaling genoeg blijft voor wat de jurist ziet:**
  - een vraag gaat over één bepaling;
  - de connector kost 2–5 s en geeft 99 % van wat de dump heeft;
  - de rest van het verschil is meetbaar en klein (Iw), of zit in artikelen waar zo'n lijst weinig zegt (Awb 8:75 met
    53k uitspraken).

  Een graafimport loont pas als Lex over uitspraken heen moet *rekenen*, bijvoorbeeld "welke artikelen van de Iw worden
  het vaakst genoemd sinds 2024", of als een uitspraak als knoop in de graaf moet staan. Dat staat nu niet op het plan.
- **Advies:**
  1. Live houden.
  2. De dump maandelijks gebruiken als **toets**: een eval-achtige job die per artikel connector en dump vergelijkt en
     een afwijking boven een drempel meldt.
  3. Optioneel als **versie-index** voor de connector.
  4. Een graafimport alleen voor de fiscale wetten (zonder de Awb), en pas als er een vraag is die erom rekent.
- **De Leidraad:** ook in de dump niet bruikbaar (bevinding 5 van de spike blijft staan).

## Bestanden

- `filter_dump.py`, `analyse_dump.py`, `vergelijk_live.py` en `toestand_controle.py`: de scripts zoals ze gedraaid
  hebben. `vergelijk_live.py` gebruikt `lido_spike.py` uit de map van de spike.
- `aggregaten.json`: de cijfers.
  - De doorgangen (duur, geheugen, omvang) en de top van de predicaten.
  - De samenvatting per regeling.
  - Per Iw-artikel de spike naast de dump.
  - De Awb-steekproef naast de spike, en de Awb-top 10.
  - De live controle en de toestandcontrole per toestand.

De dump zelf, de uitsneden (≈ 310 MB), de ECLI-lijsten per artikel en de gedownloade toestanden zijn niet bewaard. Ze zijn
opnieuw te maken met de scripts. De dump van december zal andere getallen geven.
