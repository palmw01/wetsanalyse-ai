# De tests van graph-qa, per mechanisme

Een map per mechanisme (testplan graph-qa P1-6, `docs/architectuur/testplan/graph-qa.md` §1.1). Een test die uit een
meting kwam, staat bij het mechanisme dat de fout oploste; de meting noemt hij in zijn docstring. De testnamen zijn bij de
verhuizing gelijk gebleven, dus de historie is te volgen met `git log --follow`.

| map | mechanisme |
|---|---|
| `routes/` | de ingang en de routes in code: routering, vaste workflows, scope, methodekeuze |
| `centrale_agent/` | de centrale agent en zijn subagents: overdracht, kindgesprek, rapport, vragen naar boven, hervatten, regie, profielen |
| `sjablonen/` | de antwoordsjablonen en de vorm van wat Lex zegt |
| `grounding/` | grounding en verify: citaten, beweringen, vindplaatsen, de controle op rapporten en samenvattingen, injectie via een bron |
| `annotatieketen/` | de JAS-annotatieketen (ADR-001): detectoren, fusie, classificatie, review, de gedeelde laag, hergebruik |
| `begrippen/` | de begrippenketen (ADR-004) en de begrippen-agent |
| `werkgebied/` | het werkgebied en de bronselectie: intake, deelvragen, bronnen zoeken, zoekvragen |
| `connectors/` | de bronconnectors (ADR-013), met de live-proeven `test_*_live.py` voor `bronnenwacht.yml` |
| `denkproces/` | het denkproces en het toolspoor |
| `context/` | de contextopbouw en de modelstap: caching, trimming, verzoekopbouw, strict-grenzen, verbruik |
| `graaf/` | de graaf en de getypeerde toollaag: queries, het resultaatcontract, de MCP-client |
| `mcp_server/` | de stdio-MCP `graph-qa-mcp` |
| `runs/` | runs, de beurt-driver en de dienst: run-endpoints, runstore, config, drift tegen de bicep, de foutpaden en de naad |
| `methode/` | de methode, de skills en de catalogus: drift, methodepakket, bronpakket |
| `evals/` | het eval-harnas, de sets en de referentiesets, en het testharnas zelf (`FakeLLM`, procestoestand) |

De hulpmodules (`fakes.py`, `bron_fakes.py`, `conftest.py`) en de gegevens (`data/`, `fixtures/`) staan hier, één niveau
boven de mappen. `conftest.py` zet elke map op het importpad, zodat een test een helper uit een andere map kan lezen.

Een nieuwe test hoort in de map van zijn mechanisme. Past hij nergens, dan is dat een vraag over de indeling, niet een
reden voor een losse map per bundel of meting.
