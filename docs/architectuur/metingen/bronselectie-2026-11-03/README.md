# Zoeken en rangschikken per deelvraag – ontwikkelset en blind op een held-out set (3 nov 2026)

Soort: *meting* · Hoort bij: PLAN spoor J (*de rangschikking van `bepaling_opties`*) · Code: PR #788
(`0cd5939d`) · Sets:
[`bezwaar-ontvankelijkheid-concept`](../../../wetsanalyse/referentieset-bronselectie/bezwaar-ontvankelijkheid-concept/README.md)
(ontwikkelset) en
[`invorderbaarheid-deelvragen-concept`](../../../wetsanalyse/referentieset-bronselectie/invorderbaarheid-deelvragen-concept/README.md)
(held-out)

> **Geen juridisch oordeel.** Beide sets zijn concepten die de agent uit de letterlijke graaftekst opstelde;
> geen jurist heeft ze vastgesteld. Vier deelvragen per set, 19 en 18 verwachte bepalingen: de cijfers
> zeggen iets over het mechanisme, en bij zulke aantallen is één bepaling meer of minder al 0,05.

## Wat er gemeten is

`tools/graph-qa/eval/bronselectie_eval.py --intake`, zonder model, per deelvraag:

- **`bepaling_opties`**: de nieuwe standaard (`Zoekprofiel`): per term zoeken, samenstellingsdelen en de
  ellips, divisies van een beleidsregel, de kop van het deel voor de hele pool, RRF (k=60).
- **F3f (21 okt)**: de oude rangschikking, als profiel in dezelfde code; reproduceert de meting van 21 okt
  exact (0,211 op de opname van toen).
- **Ablatie**: de standaard met telkens één ingreep uit (het lemma, standaard uit, erbij).
- **`recall_pool`**: wat de index vindt vóór de rangschikking. Ligt `recall` daar ver onder, dan laat de
  rangschikking het vallen; ligt de pool zelf laag, dan mist het zoeken het.

De ontwikkelset is op de opname van 21 okt aangevuld (`--aanvullen`: alleen de queries van de nieuwe code
zijn live opgehaald, de oude antwoorden zijn bewijs en bleven staan). De held-out set is **één keer live**
gedraaid (`--opnemen`), na de merge en een herimport van acceptatie (`vul-graaf`, met `bwb:vindplaats` en
`bwb:inBepaling`). Offline afspelen geeft hetzelfde rapport.

## Uitkomst

**Ontwikkelset** (bezwaar, Awb + AWR), volledig: [`ontwikkel.md`](ontwikkel.md):

| route | recall | recall nodig | precisie | uitgesloten | recall pool |
|---|---|---|---|---|---|
| F3f (21 okt) | 0,21 | 0,20 | 0,12 | 1 | 0,58 |
| standaard | **0,42** | **0,47** | **0,22** | 0 | **0,84** |
| zonder samenstelling | 0,16 | 0,13 | 0,09 | 1 | 0,63 |
| zonder per term / kop overal / fusie | 0,32 | 0,27–0,33 | 0,12–0,19 | 0–1 | 0,84 |

**Held-out** (invorderbaarheid, Iw 1990 + Leidraad), blind, met de **gecorrigeerde telling** (zie onder),
volledig: [`heldout-gecorrigeerd.md`](heldout-gecorrigeerd.md); de ruwe uitkomst: [`heldout.md`](heldout.md):

| route | recall | recall nodig | precisie | uitgesloten | recall pool |
|---|---|---|---|---|---|
| F3f (21 okt) | 0,28 | **0,36** | 0,16 | 0 | 0,56 |
| standaard | **0,33** | 0,27 | **0,28** | 0 | **0,94** |
| zonder divisies | 0,28 | 0,46 | 0,16 | 0 | 0,67 |
| zonder fusie | 0,22 | 0,18 | 0,16 | 0 | 0,94 |
| zonder per term | 0,11 | 0,00 | 0,12 | 0 | 0,89 |

## Wat dit zegt

- **Het zoeken generaliseert.** De pool gaat op de held-out set van 0,56 naar 0,94: 17 van de 18 verwachte
  bepalingen staan erin, ook de Leidraad-divisies die F3f niet kon vinden (het zocht niet in divisies).
- **De rangschikking generaliseert maar half.** Recall en precisie in de top 8 gaan omhoog (0,28 → 0,33;
  0,16 → 0,28), "recall nodig" omlaag (0,36 → 0,27). De winst op de ontwikkelset (0,21 → 0,42) is
  daarmee voor een deel aan die set gebonden. Niets is op de held-out set bijgesteld.
- **Diagnose (niet bijgesteld):** de Leidraad overstroomt de top 8. Bij "Schort een bezwaarschrift tegen
  de aanslag de verplichting tot betaling op?" staan zeven Leidraad-divisies 25.x (uitstel) bovenaan en
  valt Iw art. 9 lid 12 eruit, dat F3f wel had. Lange beleidsteksten raken veel termen tegelijk, en RRF
  over de lijsten per term beloont dat. De ablatie wijst dezelfde kant op: zonder divisies is recall
  nodig 0,46. Een kandidaat-vervolg is een rangsignaal voor de soort regeling (wet vóór beleidsregel,
  zoals `overzicht.RANG`) of een lengtecorrectie – te meten op een **nieuwe** set, want deze is na
  vandaag ook een ontwikkelset.
- **Het lemma** hielp op geen van beide sets.

## Correctie van de telling

De eval telt een optie als treffer als ze gelijk is aan, binnen of rond een verwachte bepaling
(`bronnen_vinden.in_selectie`). Voor een `id:`-knoop van een beleidsregel gold alleen gelijkheid, dus
divisie 25.2.1 telde niet bij een verwachte 25.2, terwijl `…divisie25.2%2FCirculaire.divisie25.2.1` die
nesting gewoon draagt. `_binnen` kent die vorm nu (deze PR). De **opties zijn identiek**; alleen de telling
verandert, en voor beide profielen op dezelfde manier. Wat de IRI niet zegt – een hoofddivisie heet
`…:artikel:25` en bevat `…id:…divisie25%2F…` – blijft open: dat weet alleen de boom.

## Bestanden

- `ontwikkel.md`/`.json`: de ontwikkelset, offline op de aangevulde opname.
- `heldout.md`/`.json`: de blinde run, zoals hij live uitkwam (oude telling).
- `heldout-gecorrigeerd.md`/`.json`: dezelfde opname, met de gecorrigeerde telling.
- De opname van de held-out set: `referentieset-bronselectie/invorderbaarheid-deelvragen-concept/graafantwoorden.json`.
