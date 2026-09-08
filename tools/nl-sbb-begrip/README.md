# nl-sbb-begrip

Een agent-workflow die voor één wettelijk begrip een **NL-SBB-conforme definitie** opstelt en die
wegschrijft als Markdown en Turtle (SKOS). Hij haalt zijn wettekst uit dezelfde BWB-kennisgraaf als
de rest van dit platform.

Dit is een **side project**: het draait niet mee in de dienst, wordt niet meegebouwd in een image en
heeft geen eigen CI. Het staat hier omdat het dezelfde graaf en dezelfde toollaag gebruikt, en dus
mee hoort te bewegen als die veranderen.

## Aanroepen

```js
{ begrip: "belastingschuldige",
  artikelen: ["2 lid 1 IW 1990", "4:89 Awb"],   // informele verwijzingen
  begrippenkader: "Invordering",                 // optioneel, default "Algemeen"
  uitvoermap: "nlsbb-begrippen" }                // optioneel, relatief pad
```

`wetteksten: [...]` mag in plaats van `artikelen`: dan slaat hij het ophalen over en analyseert hij
de meegegeven teksten. Uitvoer: `<Begrip>.md` en `<Begrip>.ttl` in de uitvoermap, plus een
samenvatting met de gebruikte vindplaatsen.

## Hij schrijft geen SPARQL — en dat is het punt

De workflow gebruikt de **getypeerde graaftools** van graph-qa via de MCP-server
`wetsanalyse-graaf` (`tools/graph-qa/agent/mcp_server.py`): `list_regelingen`, `get_artikel`,
`get_lid`, `get_bepaling`, `zoek_definitie`. Dezelfde tools die Lex gebruikt, om dezelfde reden.

Hij schreef die SPARQL eerst zelf, en liep daarmee in precies de valkuilen die `graph/queries.py`
al had opgelost:

- een **handgeschreven BWBR-tabel** die AWR naar `BWBR0002405` wees (moet `BWBR0002320`) en
  "Leidraad Inv" naar `BWBR0019237` — dat ís de Uitvoeringsregeling Awir. Een fout nummer geeft geen
  foutmelding maar de tekst van een ándere wet;
- artikelnummers **met een dubbele punt**: `4:89` moet als `artikel:4%3A89` de graaf in, en dat was
  nota bene het eigen voorbeeld uit de aanroepbeschrijving;
- `bwb:tekst` als **harde eis**, waardoor zeven Leidraad-bepalingen die alleen onderdelen hebben stil
  nul rijen gaven;
- definities alleen zoeken in `soort == "wet"`, waardoor artikel 1ca van de Uitvoeringsregeling IW
  ("betalingsvordering", "overheidsvordering") structureel werd gemist.

De regelingenlijst komt nu uit de graaf zelf (`list_regelingen` geeft citeertitel, soort én de
officiële afkortingen), zodat er niets meer is dat kan verouderen. Staat een genoemde wet niet in de
graaf, dan meldt de workflow dat — hij verzint geen BWB-nummer.

## Opzetten

De MCP-server draait naast de workflow en praat met de graaf:

```bash
cd tools/graph-qa
uv sync --extra mcp
GRAPHDB_MCP_URL=… GRAPHDB_TOKEN=… uv run --extra mcp graph-qa-mcp
```

Registreren doe je **machine-lokaal** (`claude mcp add`), niet in deze repo — die is publiek, en de
URL en het token van de omgeving horen er niet in.

## Wat hier niet getest is

De workflow draait in een agent-runtime die dit project niet meelevert; er is dus geen
end-to-end-test. Wat wél bewaakt is: de tools en hun queries hebben tests en een retrieval-smoke in
`tools/graph-qa`, en de MCP-server heeft tests die borgen dat hij exact die toollaag doorgeeft. Wat
in dit bestand zelf zit — de prompts, de Turtle-opmaak — is met de hand nagelopen.
