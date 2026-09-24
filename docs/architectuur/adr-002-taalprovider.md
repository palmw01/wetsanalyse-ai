# ADR-002 — Taalanalyse-provider voor de hybride JAS-pijplijn

Status: **aangenomen** · Datum: 2026-09-24 · Hoort bij: [ADR-001](adr-001-hybride-jas-pijplijn.md), PR 3

## Besluit

De linguïstische laag (`tools/graph-qa/agent/jas_pipeline/taal/`) gebruikt standaard **spaCy 3.8
met `nl_core_news_md` 3.8.0**, als optionele extra `nlp` van graph-qa. `nl_core_news_lg` en Stanza
blijven als provider beschikbaar (`maak_provider("spacy:nl_core_news_lg")`, `"stanza:nl"`), zonder
dat er JAS-code verandert: detectoren lezen alleen het UD-model uit `taal/model.py`.

## Wat er gemeten is

`tools/graph-qa/eval/taal_benchmark.py`, op de 16 ontwikkelcasussen van de referentieset (83
conceptmarkeringen, status `provisional`). De held-out families (BW6, Omgevingswet) zijn uitgesloten
en een test bewaakt dat. Er bestaat geen treebank van Nederlandse wetstekst, dus de vraag is niet
"welke parser ontleedt het best", maar **welke parser levert grenzen waarop kandidaten te bouwen
zijn**:

- *tokengrens*: de span begint en eindigt op een tokengrens;
- *subboom*: de span is exact het bereik van een UD-subboom;
- *spanoptie*: de span zit in `spanopties()`, dat wil zeggen subbomen, kern- en volle
  naamwoordgroepen, bijzinnen, predicaten en zinnen;
- *voegwoord als mark*: 'indien', 'tenzij', 'mits', 'als' (niet in "als bedoeld in") en 'voor
  zover' worden als bijzin-inleider herkend (H2:64).

| provider | tokengrens | subboom | spanoptie | voegwoord als mark | deterministisch | ms / 1000 tekens | omvang |
|---|---:|---:|---:|---:|---|---:|---:|
| null (regex) | 96% | 2% | 14% | 0/6 | ja | 0,5 | – |
| spaCy `nl_core_news_sm` | 96% | 40% | 54% | 2/6 | ja | ~25 | 15 MB |
| **spaCy `nl_core_news_md`** | 96% | 36% | 54% | **6/6** | ja | ~22 | **53 MB** |
| spaCy `nl_core_news_lg` | 96% | 44% | 58% | 2/6 | ja | ~23 | 603 MB |
| Stanza 1.14 (`nl`, UD Alpino) | 96% | 42% | 63% | 2/6 | ja | ~4000 | ~1,7 GB (incl. torch) |

Spanoptie-dekking per klasse (spaCy md): Rechtsobject 88%, Tijdsaanduiding 89%, Variabele 75%,
Afleidingsregel 62%, Rechtsbetrekking 56%, Parameter 40%, Voorwaarde 36%, Rechtssubject 25%,
Operator 33%, Brondefinitie 0%, Delegatie 100% (n = 2).

De voegwoordcijfers van de eerste run zagen "voor zover" als gemist omdat 'zover' niet als `mark`
hangt. Dat was de meting, niet de parser: 'voor' is de inleider. Na correctie haalt md 6/6. Met
n = 6 is dat een aanwijzing, geen maat.

## Afweging

- **Kwaliteit:** lg en Stanza liggen 4 à 9 punten hoger op spanoptie. Dat is minder dan het gat dat
  de parse sowieso laat. Brondefinitie, Voorwaarde en Rechtssubject vallen grotendeels buiten
  élke parse. Die grenzen horen bij de regeldetectoren (PR 6/7: 'indien … ,', 'wordt verstaan
  onder', rollexicon), niet bij een grotere parser.
- **Determinisme:** alle vijf leveren bij dezelfde invoer dezelfde analyse. Het model wordt in de
  provenance vastgelegd (`LinguisticAnalysis.model`, bv. `nl_core_news_md-3.8.0`).
- **Omvang en latentie:** md kost 53 MB tegen 603 MB (lg) of ~1,7 GB (Stanza met torch). Stanza is
  op CPU ~180× trager, en een annotatiebeurt analyseert elke bronnode.
- **Licentie:** de spaCy-modellen zijn CC BY-SA 4.0 (getraind op UD Dutch Alpino en LassySmall). We
  verspreiden het model niet als onderdeel van onze broncode. De wheel wordt bij installatie
  opgehaald. Stanza's Nederlandse modellen komen uit dezelfde treebanks. UDPipe 2 viel af op de
  licentie van zijn modellen (CC BY-NC-SA). Alpino (de sterkste Nederlandse parser) viel af op
  integratie: een los binair Prolog-pakket, niet als Python-afhankelijkheid te beheren.
- **Python 3.14:** spaCy 3.8.16 en Stanza 1.14 installeren beide op de versie van het image.

## Gevolgen

- Zonder de `nlp`-extra draait alles door: de provider levert een analyse op niveau `TOKENS` met de
  reden in `fout`, en zinsdetectoren slaan zich zichtbaar over. Er is geen stille terugval naar een
  LLM.
- Het productie-image krijgt de extra pas als de hybride route (PR 9) hem nodig heeft. Tot dan
  draait hij alleen in CI (`poort`, `--extra nlp`).
- De benchmark wordt opnieuw gedraaid wanneer de referentieset van status verandert of het model
  wordt bijgewerkt.
