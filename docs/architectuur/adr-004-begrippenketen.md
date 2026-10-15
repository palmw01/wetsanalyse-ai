# ADR-004 — Begrippenketen: van geannoteerde formuleringen naar betekenisgroepen

Status: **aangenomen, in uitvoering** · Datum: 2026-10-14 · Hoort bij: [PLAN spoor D](../PLAN.md#d-activiteit-3-werkgebieden-en-begrippen), [ADR-001](adr-001-hybride-jas-pijplijn.md), [ADR-003](adr-003-nl-sbb-begrippencontract.md)

## Context

Spoor D zegt dat Lex betekenisgroepen en begrippen *voorstelt* (levering 3), maar niet hoe. De
voor de hand liggende route is een model alle formuleringen te laten groeperen en definities te
laten schrijven. Dat is precies wat ADR-001 voor de JAS-annotatie heeft verlaten: dezelfde invoer
gaf dan verschillende uitkomsten, en per voorstel was niet na te gaan waarom het er stond.

De begrippenstap is daar nog gevoeliger voor. Twee gelijke woorden kunnen verschillende begrippen
zijn, en twee verschillende woorden hetzelfde begrip. Een fout voorstel dat er overtuigend uitziet,
kost de jurist meer dan een ontbrekend voorstel.

## Besluit

Betekenisgroepen worden voorgesteld door een **hybride keten in de vorm van `hybrid_v1`**:
deterministische signalen met bewijs, een vaste beslistabel, en een klein model alleen voor
twijfelparen. De keten is een zuiver pakket `tools/graph-qa/agent/begrippen_pipeline/` zonder
LangGraph-afhankelijkheid, en wordt later aangeroepen vanuit een node, zoals
`jas_pipeline/keten.py::analyseer`.

```
manifest (vaste set elementen + bronstand)
 └ taal: lemma, kern van de naamwoordgroep, samenstelling, aanwijzende verwijzing
 └ signalen: per formulering en per paar Bewijs{code, polariteit, sterkte, regel@versie, fragment}
 └ kandidaten: paar-hypothesen (zelfde betekenis | kwalificatie | inclusie | uitsluiting | hiërarchie)
 └ groeperen: union-find op sterk steunbewijs, cannot-link-controle per groep
 └ besluit: link / non-link / possible link (beslistabel)
 └ [classifier: alleen possible link, enum-keuze op kandidaat-ID]          (later)
 └ [definitievoorstel: letterlijk uit brondefinitie; model optioneel]     (later)
 └ validatie, resolver → aandacht 🟢/🟡, uitleg + trace zonder model
```

Kernkeuzes:

- **Een woord is geen begrip.** Een signaal stelt een *vergelijking* voor. Alleen een expliciete
  bron (een gedeelde brondefinitie binnen haar bereik, een aanwijzende verwijzing binnen dezelfde
  bepaling) geldt als sterke steun. Lemma- of kerngelijkheid is zwakke steun, net als semantische
  gelijkenis.
- **Bewijs heeft een richting.** Elk signaal is *steun*, *tegen* of *onbeslist*, met een
  ordinale sterkte (sterk / middel / zwak). Er is geen numerieke score en geen gecombineerd cijfer
  in beeld; dat volgt het principe "geen schijnzekerheid" uit het plan.
- **Drie uitkomsten** (naar Fellegi–Sunter): *link* (sterke steun, geen tegenbewijs) → voorstel
  🟢; *non-link* (sterk tegenbewijs) → geen groep, wel zichtbaar als bewust gescheiden; *possible
  link* (al het andere) → 🟡, en later naar de classifier. De jurist beslist in alle gevallen.
- **Relaties worden geen groepen.** "Geldt als" en "wordt aangemerkt als" (kwalificatie, fictie),
  "wordt mede verstaan" (inclusie), "wordt niet verstaan" (uitsluiting) en "zoals / waaronder"
  (hiërarchie) leveren een getypeerde relatie op, nooit een samenvoeging.
- **Conflicten worden gemarkeerd, niet opgelost.** Groeperen gebeurt met union-find op sterke
  steun. Daarna wordt per groep gecontroleerd of er een tegenpaar in zit. Is dat zo, dan wordt de
  groep niet stil geknipt maar als conflict 🟡 voorgelegd. Een optimale verdeling onder must- en
  cannot-links zoeken is in het algemeen NP-volledig en zou bovendien een keuze verbergen die bij de
  jurist hoort.
- **Bereik van definities.** Een brondefinitie geldt binnen het bereik dat haar aanhef noemt ("in
  deze wet", "in dit hoofdstuk", "voor de toepassing van artikel X", "en de daarop berustende
  bepalingen"). Het bereik wordt deterministisch uit die formules afgeleid. Past geen formule, dan
  is het bereik *onbekend* en wordt het signaal onbeslist. Binnen één bereik geldt als standaard:
  zelfde lemma = zelfde begrip, totdat tegenbewijs dat doorbreekt.
- **Reproduceerbaar.** Dezelfde invoer levert bitgelijke kandidaten, groepen en uitleg op. ID's
  zijn hashes van de gesorteerde element-ID's en de hypothese. Elke regel draagt een versie.
- **Kennis in regels en tests, niet in prompts.** Patronen staan in YAML in het formaat van
  `jas_pipeline/detectoren/regels/`, met een positieve, negatieve, rand- en overlaptest per regel.
  Elke code heeft een leesbare verklaring.
- **De keten beslist niets definitief.** Ze levert voorstellen. De opslag, de beoordeling en het
  vastleggen als NL-SBB-begrip (ADR-003) horen bij de api en de werkplek.

## Verantwoordelijkheidskaart

| Stap | Deterministisch | NLP | Graaf | Model | Mens |
|---|---|---|---|---|---|
| Manifest, ankers, hashes | ● | | ○ | | |
| Lemma, kern, samenstelling | | ● | | | |
| Aanwijzende verwijzing → antecedent | ● (regel) | ● | | | |
| Brondefinitie + bereik | ● | | ● | | |
| Kwalificatie, inclusie, uitsluiting, hiërarchie | ● (patronen) | ○ | | | |
| Groeperen, conflictcontrole | ● | | | | |
| Besluit link / non-link | ● (tabel) | | | | |
| Possible link | | | | ○ (later, enum) | ● |
| Definitie | ● (letterlijk) | | | ○ (later, optioneel) | ● |
| Begrip vastleggen en accorderen | | | | | ● |

## Fouttaxonomie

Elke fout krijgt één primaire code, bij de eerste stap waar het misging:

| Code | Stap | Voorbeeld |
|---|---|---|
| `MANIFEST_ERROR` | invoer | element ontbreekt, hash wijkt af van de bronstand |
| `NORMALISATIE_ERROR` | taal | verkeerd lemma of verkeerde kern, samenstelling fout gesplitst |
| `ANTECEDENT_ERROR` | taal | "deze aanslag" aan de verkeerde naamwoordgroep gekoppeld |
| `BEREIK_ERROR` | signalen | bereik van een definitie verkeerd afgeleid |
| `PATROON_ERROR` | signalen | patroon matcht ten onrechte of mist een bedoelde vorm |
| `PAAR_GEMIST` | kandidaten | echt verband zonder enige kandidaat |
| `SAMENVOEG_ERROR` | groeperen | homoniem of relatie in één groep terechtgekomen |
| `SPLITS_ERROR` | groeperen | synoniemen ten onrechte gescheiden |
| `BESLUIT_ERROR` | besluit | uitkomst in strijd met de beslistabel |
| `UITLEG_ERROR` | uitleg | uitleg noemt een signaal dat niet in de trace staat |

## Technieken en bronnen

Uit het onderzoek van 14 okt 2026. Het INT-dossier van 8 okt dekt de terminologiesite al:
[`onderzoek-int-terminologie-2026-10-08/`](../wetsanalyse/onderzoek-int-terminologie-2026-10-08/README.md).

| Stap | Techniek | Wat we overnemen |
|---|---|---|
| Taal | Nederlandse samenstellingssplitsing (Macken & Tezcan 2018; woordenboekgebaseerd) | kernlemma van samenstellingen, met een eigen uitzonderingslijst |
| Signalen | Winkels & Hoekstra, *Automatic extraction of legal concepts and definitions*, JURIX 2012 | precedent voor begrippen en definities uit Nederlandse belastingwetten |
| Signalen | Bereik en overerving van wettelijke definities (*statutory definitions*, arXiv 2504.16353, 2025); Aanwijzingen voor de regelgeving | bereikregels uit de aanhef |
| Signalen | Termvariatie: FASTR (Jacquemin), Daille, *Term Variation in Specialised Corpora* (2017) | typologie van varianten als catalogus van regels |
| Signalen | Hearst 1992; Lefever, Van de Kauter & Hoste, LREC 2014 (Nederlandse hyperoniemen) | hiërarchiepatronen en kop-van-samenstelling |
| Signalen | dutchcoref (van Cranenburgh; sieve-architectuur) | eigen hoog-precieze regels voor aanwijzende verwijzingen |
| Besluit | Fellegi & Sunter, *A theory for record linkage* (1969) | drie uitkomsten |
| Groeperen | Davidson & Ravi, SDM 2005; Gale, Church & Yarowsky 1992 (*one sense per discourse*) | conflict markeren; standaardaanname binnen een bereik |
| Model | ISO 704 / ISO 1087, TBX (ISO 30042), IATE | formulering en begrip gescheiden; definitiecriteria |
| Eval | Amigó e.a., *A comparison of extrinsic clustering evaluation metrics* (2009) | BCubed voor groepen, paarsgewijze P/R per relatietype |

Niet overgenomen: neurale coreferentie en neurale termextractie als detector (niet
deterministisch), LKIF Core (te zwaar voor deze stap), BlackLab (tweede index).

## Gevolgen

- Spoor D levering 3 (*Voorstellen van Lex*) wordt door deze keten ingevuld. De rest van spoor D
  verandert niet.
- De keten kan beginnen vóór levering 1. Zolang er geen werkgebied bestaat, is het manifest een
  vaste lijst elementen. Het `Analysemanifest` van levering 1 vervangt die lijst zonder dat de
  keten verandert.
- Er komt een eigen referentieset met paren (synoniem, homoniem, kwalificatie, inclusie en
  uitsluiting, hiërarchie, aanwijzende verwijzing, samenhang zonder synoniem). Status
  `provisional` totdat een jurist haar adjudiceert, net als bij spoor A.
- `jas_pipeline` verandert niet. De begrippenketen leest de taallaag en het regelformaat, maar
  schrijft er niet in.

## Uitvoering

| PR | Inhoud |
|---|---|
| 1 | Dit besluit |
| 2 | Datamodel (`model.py`): manifest, formulering, bewijs, kandidaat, groep, beslissing |
| 3 | Referentieset begrippen + `eval/begrippen_eval.py` (paarsgewijze P/R, BCubed, determinisme) |
| 4 | Taal: kern, lemma, samenstelling, aanwijzende verwijzing |
| 5 | Definitiesignalen met bereik, verwijzingssignalen |
| 6 | Patroonregister (kwalificatie, inclusie, uitsluiting, hiërarchie, tegenbewijs) |
| 7 | Groeperen, besluit, resolver, uitleg, trace; eerste meting |
| L3a | Api-domein (manifest, runs, groepen, besluiten), de run in graph-qa en de werkplek; letterlijk definitievoorstel (spoor D, levering 3a) |
| later (L3b) | Classifier voor possible link; geformuleerd definitievoorstel; hervatbare batches |
