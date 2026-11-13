# Bronnen en beslisregister — wetsuitvoering

Broncodes van deze skill. Ze zijn uniek over de methode-skills heen (de skill wetsanalyse gebruikt M- en P-codes).

## Bronnen

| ID | Bron en vindplaats | Waarvoor gebruikt / beperking |
|---|---|---|
| J01 | [JRM 2, specificatie](https://minbzk.github.io/wetsuitvoering/), BZK, commit 4a9b584 (2025-03-21); H1 hoofdclassificaties, H2 scenario's, H3 rechtsgevolg, H4 juridisch relevant feit, H5 waarde. Lokaal: `docs/wetsanalyse/wetsuitvoering/` | De begrippen juridisch scenario, juridische akte, begin- en eindtoestand, rechtsgevolg, juridisch relevant feit (type en instantie) en waarde. W3C-licentie, mag letterlijk met de notice ([BRON.md](../BRON.md)). De specificatie kondigt verdere uitwerking aan (aktes, delegatie): wat er nog niet staat, vul je niet in alsof het methode is. |
| J02 | Bulles & Van der Hoven, *Doorontwikkelingen en voortschrijdend inzicht in Wetsanalyse*, werkversie 2024-11-18: §1.4 stappen, §2.1 scenario's, §3.2.3 rechtsbetrekking, §3.2.8 juridische toestand. Lokaal bewaard, zie `docs/wetsanalyse/bronnen/manifest.json` | Vult aan waar de specificatie zwijgt: de inhoud van een juridische toestand, de lege begintoestand, de drie soorten rechtsbetrekkingen. Een werkversie; waar zij en J01 verschillen, gaat J01 voor. Alleen in eigen woorden. |
| J03 | Ausems, Bulles & Lokin (2021), *Wetsanalyse*, hoofdstuk 3, stap 4 (valideren met juridische scenario's). Lokaal bewaard, niet in de repo | De plaats van het scenario in de methode Wetsanalyse: toetsen van de analyseresultaten. Alleen in eigen woorden. |
| J04 | Expertisecentrum BRM Belastingdienst, Handleiding Wetsanalyse 1.0 (2023): activiteit 1, deelactiviteiten 1c en 1e; activiteit 2, deelactiviteit c; activiteit 4, deelactiviteit a. Lokaal bewaard, niet in de repo | Het scenario bij het werkgebied (één pad, gebeurtenissen op volgorde, het gangbare geval eerst), als vertrekpunt bij het markeren en bij het valideren. Alleen in eigen woorden; niet herpubliceren. |

## Projectkeuzes

| Regel | Onderdeel | Basis | Eigen keuze |
|---|---|---|---|
| JP01 | Scenario's en aktes ([scenario](scenario.md)) | J01 H2 | Het sjabloon voor een akte (begintoestand, rechtsfeit, rechtsgevolgen, eindtoestand) en de volgorde van werken zijn een uitwerking; de specificatie geeft de begrippen, niet het formaat. |
| JP02 | Juridisch relevant feit ([relevant feit](relevant-feit.md)) | J01 H4, H5 | De notatie van een feittype met `<onderdelen>` en het onderscheid bepalend/bepaald volgen het voorbeeld van H4; de controlelijst is een uitwerking. |
| JP03 | Verhouding tot het JAS ([classificaties](classificaties.md)) | J01 H1, H3, H5; JP05 | In Lex blijven de dertien JAS-klassen het annotatiecontract. Rechtsgevolg, juridisch relevant feit, scenario's en waarde leggen we vast in het dossier of de samenhang, niet als nieuwe annotatieklasse. |
| JP04 | Koppeling aan Lex | ADR-010, ADR-014 §7 | De methodesecties van deze skill zijn nog aan geen enkele rol gekoppeld: dat verandert het gedrag van Lex en volgt pas na een meting. |
| JP05 | De JAS-klassen blijven; verschillen benoemen ([classificaties](classificaties.md)) | J01 H1; J02 §3.2.3; het JAS-boek (skill wetsanalyse, M01 h.4) | De dertien JAS-labels blijven het annotatiecontract; wat het JRM toevoegt, staat in het scenario. Een immuniteit die de wetsanalyse onderbouwd vaststelde, blijft staan, ook al kent de werkversie haar niet. Tot 13 nov 2026 stond deze keuze als P07 in de skill wetsanalyse. |
| JP06 | Vier gevallen per beslispunt ([scenario](scenario.md)) | J02 §1.4, §2.1; J04 activiteit 4 | Per beslispunt het normale geval, een niet vervulde voorwaarde, de uitzondering en de grens. De gevallen toetsen de analyse van de gekozen bepalingen; geen claim dat de scenarioruimte uitputtend is bekeken. Tot 13 nov 2026 stond deze keuze als P08 in de skill wetsanalyse. |
| JP07 | De juridische toestand ([juridische toestand](juridische-toestand.md)) | J01 H2; J02 §3.2.8 | De inhoud van een toestand volgt de bronnen. Het onderscheid bekend, aangenomen en onbekend per deel van een toestand is een eigen uitwerking. |
| JP08 | De koppeling met een wetsanalyse ([koppeling](koppeling-wetsanalyse.md)) | J02 §1.4; J03; J04; plan methodes scheiden (13 nov 2026) | Een scenario verwijst naar bronnen, elementen en relaties van een JAS-dossier (B, E, R) en legt ze niet opnieuw vast. Het maakt geen markeringen. Het scenario dat de methode Wetsanalyse bij het werkgebied en het valideren noemt, werk je met deze skill uit. |

## Voorrang van de bronnen

De specificatie van BZK (J01) gaat voor. De werkversie (J02) vult aan waar de specificatie zwijgt, en het boek en de
Handleiding (J03, J04) zeggen alleen waar de methode Wetsanalyse het scenario gebruikt. Materiaal van J02, J03 en J04
staat alleen in eigen woorden in deze skill.
