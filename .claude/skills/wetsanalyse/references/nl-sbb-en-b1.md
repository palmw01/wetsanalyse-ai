# NL-SBB en B1

Hoe Lex de velden van een begrip vult volgens de standaard NL-SBB, en hoe de uitleg op taalniveau B1
komt. In eigen woorden. Dit hoort bij de agentrol `begrippen` (`../agentrollen.json`) en vult
[begrippen](begrippen.md) aan. Broncodes verwijzen naar [bronnen en beslisregister](bronnen.md).

## NL-SBB en B1

Grondslag: M11, M12, M13, P16.

<!-- methode:nl-sbb-taalniveau:begin -->
Een begrip volgt NL-SBB, met vier velden die elk iets anders doen. De definitie (skos:definition) onderscheidt het begrip van andere: bij voorkeur het soortbegrip plus het kenmerk dat het onderscheidt, in één zin. De uitleg (rdfs:comment) helpt een lezer het begrip te begrijpen, in eenvoudige taal en zonder verdere context. De toelichting (skos:scopeNote) zegt waar de grens van het begrip ligt of hoe het gebruikt wordt. Een voorbeeld (skos:example) is een concreet geval. De bron gaat via de passages die het begrip dragen.
Een uitleg is op taalniveau B1: één alinea van hoogstens vijf zinnen; zinnen van hoogstens twintig woorden; de actieve vorm, zodat de lezer ziet wie iets doet; woorden die bijna iedereen kent. Een vakterm of de naam van een wet laat je staan, maar je legt hem uit. Een kort voorbeeld maakt het concreet. Herhaal de definitie niet, en zeg niets wat niet uit de definitie of de bronnen volgt.
Een uitleg komt pas als er een definitie is: ze legt de definitie uit. Lex stelt haar voor met aandachtspunten uit vaste toetsen; de analist neemt over, past aan of wijst af.
TOOI (Thesauri en Ontologieën voor Overheidsinformatie) geeft overheidsorganisaties en thema's een vaste URI op identifier.overheid.nl. Een ministerie heeft de vorm https://identifier.overheid.nl/tooi/id/ministerie/mnre gevolgd door vier cijfers (Financiën: mnre1090); een thema komt uit de thesaurus tooitop. In de kennisgraaf staat het eerstverantwoordelijke ministerie van een regeling zo (bwb:eerstverantwoordelijkeOrganisatie), en een werkgebied kan een thema hebben. Noem TOOI als methode en standaard, nooit als wettekst.
Een vraag over NL-SBB, SKOS, TOOI of B1 beantwoord je uit deze methode, niet uit de graaf, en je zegt dat erbij: "uit de methode, geen wettekst". Citeer dan geen wettekst en noem geen vindplaats.
<!-- methode:nl-sbb-taalniveau:end -->

## Wat de toetsen meten

De toetsen staan in code (`tools/graph-qa/agent/begrippen_pipeline/begrip_b1.py`), niet alleen in de
prompt: een zin langer dan twintig woorden, meer dan vijf zinnen, een lijdende vorm, een woord met een
gewoner alternatief (`b1_woorden.yaml` ernaast), een vakterm uit de definitie die de uitleg niet
uitlegt, en een uitleg die de definitie herhaalt. Een treffer is een aandachtspunt, geen weigering:
soms is het moeilijke woord het juiste.
