# Ongenummerde onderdelen: naamgeving en verwijzingen

Een BWB-opsommingsteken (`bwb:nummer "–"`) is geen uniek onderdeelnummer.
De XML-gebaseerde IRI identificeert het onderdeel; RDF-type en ouderrelaties
bepalen zijn type en positie. `_10` in het XML-pad is geen juridische nummering.

`bronmodel.bronlabel` levert de presentatienaam. Een expliciet
`bwb:definieertBegrip` heeft voorrang (bij meer begrippen het langste, dus specifiekste,
eerst); anders volgt een letterlijk tekstfragment van hoogstens 100 tekens.
Een dubbele punt wordt niet gebruikt om zelf een definitierelatie af te leiden.
De namen staan in `snapshot.presentatie`, buiten de gehashte bronnodes. Brontekst,
nummer, IRI, bronhash en annotatieankers blijven ongewijzigd. De bronnenlijst
gebruikt de actuele graafplaats alleen voor een selectie onder een ongenummerd
onderdeel, ook als die eerder is opgeslagen; elke andere selectie houdt haar eigen
label, met het opschrift van een structuurdeel.

Een snapshot wordt één keer bewaard. Een snapshot die vóór deze wijziging is
weggeschreven, heeft dezelfde ID maar geen `presentatie` en het oude doellabel; dat is
geen fout. De graaf en de bronnenlijst rekenen de naam uit de actuele bronboom.

Ook bij een kaal label van een lid of divisie komt het nummer erbij ("Lid 1",
"Divisie 1.1.2"), zoals de detailkop al deed. Een label dat het nummer al draagt,
krijgt het niet nog eens.

Verwijzingsknopen krijgen hun type uit RDF. Zonder bekend RDF-type blijft het
type onbekend. De verwijzingsqueries geven één rij per verwijzing: de begrippen van
het doel worden samengevoegd en de tekst gaat ingekort mee, zodat de limiet van de
samenhang verwijzingen telt en geen begrippen. De importer gebruikt voor verwijzingen vanaf een onderdeel
zonder JuriConnect dezelfde XML-identiteit als de writer voor de onderdeelnode.
Dit geldt ook voor geneste onderdelen.

## Uitrol en herimport

1. Rol de aangepaste API, frontend en importer uit via de bestaande workflows.
2. Importeer `BWBR0024096` opnieuw met de aangepaste importer in de bedoelde
   omgeving: vanuit `tools/bwb-import`, met de bestaande omgevingsconfiguratie,
   `python main.py BWBR0024096`. Gebruik hiervoor niet `--alleen-bij-verlies`:
   de bestaande graaf kan compleet zijn en toch de oude verwijzingslijnen dragen.
   De reguliere importer haalt de nieuwste toestand op. Controleer vooraf of
   dit dezelfde bronstand is die wordt onderzocht; de gemelde stand was
   `2026-07-01`. Een nieuwere toestand is een afzonderlijke bronwijziging.
3. Herstart de API-processen na de herimport. De structuur- en verwijzingscaches
   zijn proceslokaal en op toestand-URL gesleuteld; een herimport van dezelfde
   toestand verandert die sleutel niet. Herlaad daarna de browser.

Een herimport vervangt de BWB-named graph, niet de gedeelde annotatielagen.
Voor naamgeving en opmaak volstaat de nieuwe code; de herimport is nodig voor
het vertrekpunt van reeds opgeslagen verwijzingen.

## Controle van het gemelde onderdeel

De exacte IRI is:

```text
urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie1%2FCirculaire.divisie1.1%2FCirculaire.divisie1.1.2%2FTekst%2FOnderdeel._10
```

Controleer vóór en na de herimport de letterlijke tekst, IRI en bronhash. De
snapshot-hash blijft gelijk als dezelfde bronnodes en toestand worden ingelezen;
een presentatienaam of verplaatste verwijzingslijn zit daar niet in.
De bronpagina en graaf moeten een herkenbare naam tonen en de wettekst begint
met `– negatieve voorlopige aanslag:`. In de graaf blijft de knoop een onderdeel;
de verwijzing naar artikel 13 AWR vertrekt vanaf deze IRI. Controleer daarbij
ook de gepubliceerde doelprecisie van de bronverwijzing (artikel en eventueel lid).
De twee annotaties blijven gekoppeld aan hun bestaande tekstankers.

Het verschil tussen de beoordelingstellers in bronnenlijst en detailpagina is
een afzonderlijk onderzoek en wordt met deze wijziging niet aangepast.
