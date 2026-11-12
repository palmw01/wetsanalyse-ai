# Kamerstukken, iteratieve verbeterrondes – ronde 6 en eindverslag (12 november 2026)

Soort: *meting* · Code: master `66e73f75` (bundels 52 en 53) · Straat: acceptatie · Model: `claude-sonnet-4-6` (Foundry)
· Uitvoering: de acceptatie-MCP, elke vraag in een eigen gesprek; de vervolgvragen K21–K22 en K23–K24 staan elk in één
gesprek. Bronstand als in ronde 5: alle connectors aan, geen beperking per gesprek.

**Vragenset.** Dezelfde 30 vragen als in ronde 1–5, plus L-K2 uit de iteratie van wetgeving_live: "Welke memories van
toelichting gaan over de bestuurdersaansprakelijkheid in de Invorderingswet 1990?".

**Wat er nieuw is in de bundels:**
- #1259: de PR van ronde 5;
- #1260: de zoekvraag bij Staatsblad en Staatscourant;
- #1261: per vraag alleen de connectortools die de vraag of het gesprek noemt;
- #1262: een lijst in tekst zet de code om naar het sjabloon.

**Gegevens en herhaling.** De ruwe gegevens staan in [`runs.jsonl`](runs.jsonl) (`"ronde": 6`), met per vraag de connectors
die aanstonden. K02 kreeg eerst een inlogfout van de MCP-sessie, nog voor Lex de vraag zag, en is één keer opnieuw
gedraaid. Er zijn in deze ronde geen fixes gebouwd; wat open is, staat hieronder benoemd.

## Uitkomst

**De 30 vragen: 28 goed, 2 deels, 0 fout. Samen 1,83M tokens en 63 modelrondes** (ronde 5: 28 goed, 2 deels, 0 fout,
1,95M tokens, 59 modelrondes).

**L-K2: deels.** In ronde 5 bij wetgeving_live was het ook deels, met 0 gevonden.

Hieronder staan alleen de vragen met een model. De zestien andere geven hetzelfde als in ronde 5: elk 0 tokens, en alle
goed. Daaronder vallen de telvragen K25 (16) en K26 (72), en K17 (211, de kanttekening met "in de titel" nu één keer).

| vraag | oordeel (ronde 5 → 6) | modelrondes | tokens |
|---|---|---|---|
| K07 | goed → **goed** | 7 → 6 | 230k → 123k |
| K10 | deels → **deels** | 11 → 10 | 397k → 359k |
| K11 | goed → **goed** | 1 → 1 | 35k → 26k |
| K13 | goed → **goed** | 1 → 1 | 35k → 26k |
| K14 | goed → **goed** | 1 → 1 | 35k → 26k |
| K15 | goed → **goed** | 5 → 9 | 182k → 295k |
| K16 | deels → **deels** | 13 → 16 | 466k → 531k |
| K18 | goed → **goed** | 6 → 6 | 206k → 173k |
| K19 | goed → **goed** | 2 → 1 | 64k → 22k |
| K20 | goed → **goed** | 4 → 4 | 99k → 99k |
| K22 | goed → **goed** | 2 → 2 | 34k → 26k |
| K24 | goed → **goed** | 3 → 3 | 63k → 46k |
| K28 | goed → **goed** | 2 → 2 | 69k → 52k |
| K29 | goed → **goed** | 1 → 1 | 34k → 26k |
| L-K2 | deels (0 gevonden) → **deels** | 0 → 0 | 0 → 0 |

**De correctierondes en de sjablonen** (`meting.sjabloon`, over de 30 vragen):
- Gevuld: `antwoord_extern` 15 keer, `antwoord_duiding` 1 keer.
- Geweigerd: twee keer, dus twee correctierondes. Dat waren K10 (`antwoord_extern:extern.lijsten`) en K15
  (`antwoord_extern:extern.blokken`), net als in ronde 5.
- `gevraagd`, `omgezet`, `lijst_aangenomen`, `gemist`, `als_tekst` en `uitgesteld`: 0. #1262 sloeg in deze set dus niet aan.
- `tekst_ernaast`: 2.661 tekens over 13 vragen (ronde 5: 1.494 over 8). K22 draagt er 706 van, K10 337 en K19 333.

## Wat de bundels opleverden

1. **Minder tools per vraag** (#1261). De meeste vragen hadden alleen Kamerstukken aan, en een vraag met één leesronde kost
   nu 26k tokens in plaats van 35k (K11, K13, K14, K22, K29). K07 halveerde (230k → 123k), maar dat is ook spreiding:
   het model koos andere woorden in `get_kamerstuk`.
2. **L-K2 vindt nu iets.**
   - De lijstroute zocht eerst de woordgroep "bestuurdersaansprakelijkheid Invorderingswet 1990", die nergens zo
     voorkomt, en daarna de losse woorden.
   - Dat gaf 7 memories van toelichting, met erbij: "Als woordgroep staat „…” in geen stuk; dit zijn de stukken met elk
     van de woorden."
   - Dit ging zonder model.
3. **K17**: de kanttekening zegt "in de titel" één keer.

## Bevindingen, alleen benoemd

### Code

1. **K16 leest de uitspraak niet meer, en noemt het dossier weer zonder bron.**
   - De vraag ("Wat bedoelde de wetgever met artikel 36 van de Invorderingswet 1990?") noemt geen rechtspraak. Daarom stond
     Rechtspraak in deze beurt uit (#1261).
   - In ronde 5 las het model nog ECLI:NL:HR:2023:1371, en daaruit kwam het dossier 20 588. Nu noemt de toelichting weer
     "dossier 20588, 1988-1989" zonder dat een gelezen stuk het draagt. Het nummer klopt, het jaar niet: de uitspraak
     zegt 1987/88.
   - De controle meldde het niet: de grounding staat op gegrond. Waarom niet, is niet nagegaan. Misschien staat het
     nummer ergens in een gelezen Kamerstuk, misschien vangt de beweringentoets deze vorm niet.
   - Twee open punten:
     - de bronkeuze bij een vraag naar de bedoeling van de wetgever (alleen Kamerstukken is juist, maar dan mist de
       memorie van vóór 1994);
     - waarom de controle het dossiernummer niet meldde.
2. **L-K2 mist één stuk, en niemand zegt dat.**
   - De SRU geeft met dezelfde woorden en `dt.type==Kamerstuk` 42 stukken. Daarvan hebben er 8 "memorie van toelichting"
     in de titel.
   - De connector toont er 7. Kst-24172-3 ("Wet op de omzetbelasting 1968; wijz. … ; Memorie van toelichting")
     ontbreekt, ook bij een lokale aanroep van `zoek_kamerstukken`.
   - De oorzaak is niet vastgesteld. Het zit waarschijnlijk in het soortfilter voor stukken zonder rubriek
     (`_soort_cql`).
   - Een stuk dat stil wegvalt, is de faalmodus die de toollaag juist wil voorkomen.
3. **K15 kostte 9 rondes** (ronde 5: 5). Het model bladerde vier pagina's van `woorden: "Belastingdienst"` door (223
   alinea's) en kreeg één weigering van `extern.blokken`. Het oordeel blijft goed.

### Model

4. **K10 telt de amendementen zelf, en weer fout.** Het noemt 92 bij 36602; de bron telt er 88 (SRU, `w.subrubriek==
   Amendement`). Bij 36604 noemt het 3, en dat klopt. Het model bladert alles door: 10 rondes en 359k tokens, de duurste
   vraag na K16.
5. **Tekst naast een sjabloon**: 2.661 tekens over 13 vragen. Sinds #1257 ziet de jurist die tekst niet, maar het model
   schrijft hem wel.

## Eindverslag over zes rondes

| ronde | code | goed | deels | fout | tokens | modelrondes | grootste kostenpost |
|---|---|---|---|---|---|---|---|
| 1 | `1ba00b8f` | 16 | 12 | 2 | 3,62M | – | K07 en K16 samen 1,47M (oud schema zonder koppen) |
| 2 | `80ca14f4` | 23 | 7 | 0 | 2,33M | – | K07 359k, K16 342k |
| 3 | `a0eeb8de` | 26 | 3 | 1 | 2,51M | – | K07 779k (offsets in drie stukken) |
| 4 | `229b9063` | 27 | 3 | 0 | 2,36M | – | K16 504k, K07 392k |
| 5 | `e7e2ab8a` | 28 | 2 | 0 | 1,95M | 59 | K16 466k, K10 397k |
| 6 | `66e73f75` | 28 | 2 | 0 | 1,83M | 63 | K16 531k, K10 359k |

(De modelrondes per ronde zijn pas vanaf ronde 5 opgeteld; ze staan wel per vraag in `runs.jsonl`.)

**De uitkomst over zes rondes:**
- Van 16 naar 28 goed, en sinds ronde 4 geen fout meer.
- De tokens halveerden: 3,62M → 1,83M.
- Zestien van de 30 vragen gaan nu zonder model, met 0 tokens:
  - de lijstvragen, ook de telvragen en "horen bij";
  - een genoemd stuk zonder tekst;
  - een storing van de bron.
- Wat er nog kost, zit in drie vragen waarin het model zelf zoekt en bladert: K16, K10 en K15, samen 1,19M van de 1,83M.

**Wat de iteratie in code opleverde:**

*Gedeeld:*
- de lijstroute voor zoeken, tellen en verdelen, "horen bij", een bronfout en een woordgroep;
- vaste meldingen bij een stuk zonder tekst en bij een storing;
- de zoekvraag in woorden;
- `get_kamerstuk(woorden=)` met `per_woord`;
- de lettercode in de reeks;
- de inhoudpagina.

*Voor Kamerstukken:*
- het oude schema;
- het soortfilter;
- een onopgemaakt stuk en een herdruk;
- de grens van KOOP (vanaf 1994-1995).

**De twee die deels blijven:**
- **K10 (de amendementen bij het Belastingplan).** Een vraag naar "de amendementen bij X" kan pas zonder model als de
  code het dossier van een wetsvoorstel uit zijn naam kan halen. Dat is een nieuw mechanisme. Tot die tijd telt het model
  zelf, en elke ronde anders (90, 92).
- **K16 (de bedoeling van de wetgever bij artikel 36 Iw).** De memorie van de Invorderingswet 1990 staat niet bij KOOP;
  de bron gaat terug tot 1994-1995. Het antwoord rust op de wettekst en op latere stukken, en dat zegt het eerlijk. Het
  dossiernummer en het jaar daarnaast komen niet uit een gelezen bron.

**Open vervolgwerk, voor andere sessies:**
- K16: de bronkeuze bij "wat bedoelde de wetgever", en waarom de controle het dossiernummer niet meldde;
- L-K2: het stuk dat wegvalt in het soortfilter (`_soort_cql`);
- K10: het dossier van een wetsvoorstel uit zijn naam;
- Rechtspraak, uit ronde 5: de LiDO-weigering na 92 s en ~60 s per telvraag.

## Wat deze meting niet zegt

- Dit is één run per vraag. K07 (230k → 123k) en K15 (182k → 295k) laten zien hoe groot de spreiding is bij hetzelfde
  oordeel.
- Bij L-K2 is de oorzaak van het ontbrekende stuk niet vastgesteld.
- Het oordeel is van deze sessie, getoetst tegen de bron. Het is geen juridisch oordeel over de stukken.
