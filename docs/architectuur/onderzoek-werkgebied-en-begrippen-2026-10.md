# Onderzoek — bronselectie, taalpatronen en begrippen voor spoor D

Soort: *onderzoek* · Datum: 14 oktober 2026 · Hoort bij: [PLAN spoor D](../PLAN.md#d-activiteit-3-werkgebieden-en-begrippen), [ADR-003](adr-003-nl-sbb-begrippencontract.md)

Deze notitie legt vast wat er is onderzocht voor activiteit 3: hoe Lex de bepalingen van een
werkgebied vindt, welke taalpatronen begripsrelaties aanwijzen, en hoe we meten of dat werkt. Ze
zegt ook wat we níét overnemen. Het startpunt was een verkennend gesprek met een taalmodel (13 okt
2026). Alleen wat tegen de code en de bronnen is gecontroleerd staat hier. Waar een bron niet
geverifieerd is, staat dat erbij.

Wat al vastligt wordt hier niet herhaald:
- het begrippenmodel staat in [PLAN spoor D](../PLAN.md#d-activiteit-3-werkgebieden-en-begrippen);
- de taalkundige tussenlaag (operatorbereik, dependency-relaties, `AnalyseFrame`) staat in het
  [verbeterplan](verbeterplan-jas-pipeline-2026-10-08.md);
- het volg-beleid voor verwijzingen staat in de skill
  ([`verwijzingen-volgen.md`](../../.claude/skills/wetsanalyse/references/verwijzingen-volgen.md));
- TermWerk, BlackLab en de INT-hulpmiddelen staan in het
  [INT-terminologieonderzoek](../wetsanalyse/onderzoek-int-terminologie-2026-10-08/README.md).

## 1. Bronselectie: relevant is "nodig voor de vraag", niet "gaat over hetzelfde"

| Bron | Wat we eruit halen |
|---|---|
| Colombo, Bernasconi, Bellomarini e.a., *LegisSearch: navigating legislation with graphs and large language models*, Artificial Intelligence and Law (2025), [doi:10.1007/s10506-025-09482-6](https://doi.org/10.1007/s10506-025-09482-6), [code](https://github.com/andreac0/LegisSearch) | Graafcontext helpt bij het vinden van bepalingen. De ranking combineert de score van de wet met die van het best passende artikel. LLM-queryexpansie helpt per onderwerp wisselend. Ze meten met ablatie wat elk onderdeel bijdraagt. |
| Van Opijnen & Santos, *On the concept of relevance in legal information retrieval*, Artificial Intelligence and Law (2017), [doi:10.1007/s10506-017-9195-8](https://doi.org/10.1007/s10506-017-9195-8) | Juridische relevantie hangt af van de taak van de jurist, niet alleen van het onderwerp. |
| COLIEE, statute retrieval (o.a. editie 2025) | Volledigheid weegt zwaar: een gemiste bepaling maakt de redenering erna onbetrouwbaar. BM25 is een sterke baseline. |
| UTwente-scriptie "Citation graphs don't help" (2026, essay.utwente.nl 110874) | **Niet geverifieerd** (de pagina was niet leesbaar). Volgens de samenvatting levert blind uitbreiden langs verwijzingen geen winst op ten opzichte van een sterke semantische baseline, soms zelfs verlies. Eerst lezen vóór we het citeren. |

Gevolgen voor het ontwerp (opgenomen in PLAN D, *Bronnen vinden voor een werkgebied*):

1. **Vraag eerst, artikelen daarna.** Een werkgebied begint bij een analysevraag, eventueel
   opgedeeld in deelvragen. Elke opgenomen bepaling heeft een rol en een reden. Zo ook een
   rechter: welke regels heb ik nodig om deze vraag te beoordelen, niet welke artikelen het woord
   bevatten.
2. **Gericht volgen, niet blind.** Diepte 1 vanaf de kern, verder alleen langs een concrete
   afhankelijkheid. Dat is het skillbeleid. De studies hierboven onderbouwen waarom.
3. **Bewijs per methode, geen gecombineerde score.** Semantische gelijkenis is het zwakste signaal.
4. **Afbakening telt even zwaar als volledigheid.** Daarom meten we beide (§3).

**Wat in de code ontbreekt** (inventaris 14 okt 2026):
- `overzicht_bouwen` (`tools/graph-qa/agent/overzicht.py`) is deterministisch, maar volgt geen
  verwijzingen en gebruikt geen semantiek.
- Verwijzingen (`bwb:Verwijzing`, `tools/bwb-import/app/ontology.py`) zijn alleen getypeerd als
  INTERN, EXTERN of TEKSTUEEL, niet naar hun functie (definitie, uitzondering, termijn,
  procedure). Die functie moet uit de context van het anker worden afgeleid.
- `bwb_similarity` indexeert alleen `bwb:tekst` per node, zonder context.

LegisSearch-achtige graafverrijkte embeddings zijn een latere optie: eerst meten of de
deterministische methoden tekortschieten.

## 2. Taalpatronen voor begripsrelaties

De detectoren herkennen al brondefinities ("wordt verstaan onder", "betekent",
`detectoren/structuur.py`) en signalen voor uitzonderingen en voorwaarden ("in afwijking van",
"met uitzondering van", "indien/tenzij/mits", `detectoren/regels/voorwaarde.yaml`). Die dienen
activiteit 2. Voor activiteit 3 zijn er patronen nodig die een **relatie tussen begrippen**
voorstellen. Die ontbreken nog:

| Patroonfamilie | Voorbeelden | Voorstel aan de analist | Valkuil |
|---|---|---|---|
| Kwalificatie / fictie | "X geldt als Y", "X wordt aangemerkt als Y" | kwalificatierelatie, beperkt tot het rechtsgevolg | is **geen** synoniem; nooit één begrip maken |
| Inclusie | "onder X wordt mede verstaan Y", "daaronder begrepen" | Y valt binnen het bereik van X | verruiming van het bereik, niet per se hiërarchie |
| Uitsluiting | "onder X wordt niet verstaan Y", "uitgezonderd" | negatief bewijs tegen samenvoegen | — |
| Hiërarchie (Hearst) | "X, zoals Y en Z", "X, waaronder Y" | Y en Z als onderbegrip van X | geheel-deel is geen `skos:broader` |

Bronnen:
- Hearst, *Automatic acquisition of hyponyms from large text corpora* (COLING 1992),
  [C92-2082](https://aclanthology.org/C92-2082/);
- Nederlandse hyperoniemdetectie (RANLP 2013), [R13-1078](https://aclanthology.org/R13-1078/);
- Walter, definitie-extractie uit Duitse rechtspraak (LREC 2008),
  [L08-1608](https://aclanthology.org/L08-1608/);
- *LexDrafter* (LREC-COLING 2024), [2024.lrec-main.913](https://aclanthology.org/2024.lrec-main.913/):
  terminologische consistentie en definities in wetgeving.

Uitgangspunten:
- **Een patroon stelt voor, het besluit niet.** Elk voorstel draagt een patroon-ID met versie en
  het exacte bronfragment, en heeft altijd menselijke beoordeling nodig.
- **Hetzelfde registerformaat.** De patronen komen in hetzelfde YAML-formaat als
  `detectoren/regels/`, op de bestaande taalprovider ([ADR-002](adr-002-taalprovider.md)).
- **Termkandidaten** (naamwoordgroepen op UPOS-patronen, zoals TermWerk ze gebruikt) vullen de
  JAS-elementen aan. Ze worden nooit vanzelf een annotatie of een begrip. Termhood/keyness vraagt
  een algemeen referentiecorpus en is geparkeerd.
- Termhood mag nooit bepalen wat juridisch telt: "indien", "na" en "niet" zijn statistisch
  alledaags en juridisch beslissend.

## 3. Meten: een retrieval-benchmark naast de annotatie-eval

Er bestaat nu alleen `eval/retrieval_smoke.py` (komt er iets terug?) en de end-to-end bronrecall
per antwoord (`eval/run_eval.py`). Voor bronselectie is nodig:

- **Referentieset van werkgebieden**: per analysevraag stelt een jurist de kernbepalingen en de
  afhankelijkheden vast. Eerst *Invorderbaarheid van belastingaanslagen*, uitgaande van art. 9
  IW 1990. Dit is hetzelfde soort mensenwerk als V7 in spoor A, dus plan het samen.
- **Ablatie**, elke stap apart gemeten:

  | Variant | Methoden |
  |---|---|
  | A | tekst en opbouw (`overzicht_bouwen`-queries) — nulmeting |
  | B | A + verwijzingen (diepte 1, gericht) |
  | C | B + definities |
  | D | C + `bwb_similarity` |
  | E | D + LLM-queryexpansie |

- **Maten**: recall@k van de benodigde bepalingen, **en** het aandeel overbodige bepalingen in de
  selectie. Daarnaast de beoordeeltijd van de analist en, bij E, de modelkosten.
- Wat niet aantoonbaar helpt, gaat niet standaard aan. De meetbestanden komen onder
  [`metingen/`](metingen/README.md), volgens het meetlogboek.

## 4. Niet overgenomen

- **De LegisSearch-architectuur** (Neo4j property graph, eigen rankingmodel): we hebben een
  RDF-graaf met verwijzingen en een api als waarheid.
- **Verplichte LLM-queryexpansie**: hooguit variant E, en alleen als hij meetbaar helpt.
- **BlackLab naast GraphDB**: een tweede index naast `bwb_tekst`, zonder aangetoonde behoefte.
- **Overstappen naar Apache Jena/Fuseki of een ander triplestore**: graph-qa leunt op de
  ingebouwde MCP-server, de Lucene-connector en de similarity-plugin van GraphDB. De
  licentievraag staat bij de open keuzes van het plan.
- **Een generiek AI-platform** naar het voorbeeld van Scrydon. Zie §4a.

### 4a. Scrydon (Tweakers, 14 okt 2026)

"Dev Summit 2026: AI binnen Europese muren: hoe Scrydon een sovereign AI OS bouwt" is
partnercontent: een aankondiging van een talk, zonder technische uitwerking. De punten en hoe ze
zich verhouden tot het platform:

| Punt uit het artikel | Stand bij ons |
|---|---|
| Een ontologie geeft agents context ("AI is zo goed als de data en context"). | Dat is de kennisgraaf plus de JAS-lagen. Begrippen volgens NL-SBB maken die laag rijker (ADR-003). |
| Een copilot verandert geen proces; de winst zit in het werkproces. | Dat is de werkplek met review, en straks het werkgebied. Lex is daar een onderdeel van, geen chatbot erbovenop. |
| "AI neemt geen accountability": de agent stelt voor, een bevoegd persoon besluit. | Dat staat al als eerste leidend principe in het plan. |
| Het "saaie" deel: authenticatie, autorisatie, logging, modelbeheer, observability, audittrails en grenzen aan agentacties. | Dat bestaat al: login met rollen en 2FA, auditlog, OTel en Grafana, modelprofielen, tokenbudget, en geen graafmutaties door het model. |
| Pragmatische soevereiniteit: zelf bepalen waar data staat en welk model draait, tot on-premises of air-gapped. Zero trust ook voor agents. | **Niet uitgewerkt.** Het platform draait op Azure met modellen via profielen. De observability is bewust provider-neutraal (OTLP), maar er is geen besluit over soevereiniteit voor een inzet bij een overheidsorganisatie. Dat is een kandidaat voor een eigen open keuze zodra die inzet aan de orde is. |

Lessen voor spoor D levert het artikel niet op. Het bevestigt vooral de richting.

## 5. Volgorde

Eerst één verticale proef, zoals PLAN D al voorschrijft (levering 1 + 2): van art. 9 IW 1990, via
beoordeelde JAS-annotaties, naar een klein NL-SBB-begrippenkader van ongeveer vijf begrippen. Dat
kader bevat ten minste één betekenisconflict, één hiërarchische relatie, één juridische relatie
(bijv. een kwalificatie) en een gevalideerde export. Leg daarbij per voorstel vast welke techniek
het opleverde en welke correctie nodig was. Pas daarna de patronen (§2) en de ontdekmethoden
voorbij verwijzingen en definities (§1) automatiseren, met de benchmark (§3) als toets.
