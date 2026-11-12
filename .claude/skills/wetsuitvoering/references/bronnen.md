# Bronnen en beslisregister — wetsuitvoering

Broncodes van deze skill. Ze zijn uniek over de methode-skills heen (de skill wetsanalyse gebruikt M- en P-codes).

## Bronnen

| ID | Bron en vindplaats | Waarvoor gebruikt / beperking |
|---|---|---|
| J01 | [JRM 2, specificatie](https://minbzk.github.io/wetsuitvoering/), BZK, commit 4a9b584 (2025-03-21); H1 hoofdclassificaties, H2 scenario's, H3 rechtsgevolg, H4 juridisch relevant feit, H5 waarde. Lokaal: `docs/wetsanalyse/wetsuitvoering/` | De begrippen juridisch scenario, juridische akte, begin- en eindtoestand, rechtsgevolg, juridisch relevant feit (type en instantie) en waarde. W3C-licentie, mag letterlijk met de notice ([BRON.md](../BRON.md)). De specificatie kondigt verdere uitwerking aan (aktes, delegatie): wat er nog niet staat, vul je niet in alsof het methode is. |

## Projectkeuzes

| Regel | Onderdeel | Basis | Eigen keuze |
|---|---|---|---|
| JP01 | Scenario's en aktes ([scenario](scenario.md)) | J01 H2 | Het sjabloon voor een akte (begintoestand, rechtsfeit, rechtsgevolgen, eindtoestand) en de volgorde van werken zijn een uitwerking; de specificatie geeft de begrippen, niet het formaat. |
| JP02 | Juridisch relevant feit ([relevant feit](relevant-feit.md)) | J01 H4, H5 | De notatie van een feittype met `<onderdelen>` en het onderscheid bepalend/bepaald volgen het voorbeeld van H4; de controlelijst is een uitwerking. |
| JP03 | Verhouding tot het JAS ([classificaties](classificaties.md)) | J01 H1, H3, H5; skill wetsanalyse P07 | In Lex blijven de dertien JAS-klassen het annotatiecontract. Rechtsgevolg, juridisch relevant feit, scenario's en waarde leggen we vast in het dossier of de samenhang, niet als nieuwe annotatieklasse. |
| JP04 | Koppeling aan Lex | ADR-010, ADR-014 §7 | De methodesecties van deze skill zijn nog aan geen enkele rol gekoppeld: dat verandert het gedrag van Lex en volgt pas na een meting. |
