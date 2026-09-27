# Pre-baseline fixvoorstel hybrid_v1

Uitgangspunt: master `9de992226e18514f40d96dd29ed98498e747ffe6`. Opgesteld vóór de
productieaanpassingen. De diagnostische fixtures komen uit de bestaande exports T3/T4;
zij zijn geen uitbreiding van de provisional of adjudicated referentieset.

| ID / prioriteit | Probleem en bewijs | Root cause | Bestanden | Gedrag / risico | Verwachte metric-impact | Regressie / besluit |
|---|---|---|---|---|---|---|
| F01 / P1 | T3 C024 loopt op huidige master door in `en elk van de volgende termijnen telkens een maand later`; te brede deterministisch geaccepteerde termijn | Rechtse uitbreiding stopt alleen op interpunctie; het profiel verlangt de startgebeurtenis | `detectoren/regels/tijd.yaml`, detectortests | Begrens uitsluitend de aantoonbare distributieve vervolgbepaling `en elk/ieder van`; andere nevenschikking blijft intact. Klein bereik, geen algemene spanherziening | Devset naar verwachting gelijk; gewijzigde kandidaat-ID en grens in IW-D2; classifierroute kan door fusie veranderen | Volledige historische tekst + positieve nevenschikking binnen startgebeurtenis. **FIX_BEFORE_BASELINE**, A/B |
| F02 / P1 | T4 C037 `als dat van de dagtekening` wordt ook op master een Voorwaarde; profiel sluit vergelijkend als uit | `mark` + `advcl` is onvoldoende; een elliptische vergelijking kan dezelfde parse krijgen | `detectoren/syntactisch.py`, syntactische tests | Sluit de aangetoonde elliptische vergelijking met hetzelfde/dezelfde uit, met behoud van conditionele clauses met eigen predicaat. Geen algemene connectiefclassifier | Eén ongefundeerde conditionele kandidaat minder in LI-D3; geen verwachte devsetwijziging | Historische bron; conditioneel, vergelijkend, hoedanigheid en verwijzing; conditioneel met `hetzelfde`. **FIX_BEFORE_BASELINE**, A/B |
| F03 / P2 | Ruwe detector-/regelbijdragen verliezen bij interne samenvoeging en fusie hun klassenkoppeling; V4 bewaart alleen de vlakke unie | Geen diagnostische opslag vóór fusie | kandidaat-/fusie-/regelresultaat, beslisregister, annotatie-emitter, additief API-contract | Bewaar oorspronkelijke bijdragen inclusief versie, bewijs, klassen en opties; uitsluitend meetdata, geen nieuwe hypotheses of beslisbeleid. Risico: gegevensverlies bij API-roundtrip | Geen wijzigingen in kandidaatruimte, prompts of routing | Twee regels met dezelfde span en verschillende klassen; oude registers; afgewezen kandidaten; API-opslag/export; promptvergelijking. **FIX_BEFORE_BASELINE**, D |

Alle overige voorstellen worden in de volledige audit geclassificeerd. Generic NP,
Rechtsfeit-alternatieven, bewijssterkte, relationele frames en geplande detectorregels worden
niet op basis van theoretisch nut ingevoerd. Er worden geen verse modelruns gedaan.

Reproductie F02: ook het reeds bestaande negatieve profielvoorbeeld `Hij treedt op als
bestuurder van het lichaam` krijgt met spaCy `mark` + `advcl`. Daarom wordt de minimale
correctie een predicaatvereiste voor de als-bijzin: de eigen subboom moet VERB/AUX bevatten
(inclusief een koppelwerkwoord bij een nominale kop). Dit sluit beide aangetoonde nominale
fragmenten uit, zonder een contextuele vergelijkingsclassifier te introduceren. Vergelijkingen
met een eigen werkwoord en elliptische voorwaarden blijven een expliciete beperking.
