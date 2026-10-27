# Bronselectie per deelvraag (spoor J)

Soort: *specificatie, beweegt mee met de code* · Hoort bij: PLAN spoor J · Code: `api/app/bronselectie.py`,
`tools/graph-qa/agent/bronselectie.py`, `frontend/components/werkgebieden/BronselectieOverzicht.tsx`

Lex begeleidt de bronselectie van een werkgebied in het gesprek, deelvraag voor deelvraag. Het model kiest
daarbij niets: de stand en de volgorde zijn van de applicatie, de zoekmethoden zijn deterministisch, en de
analist besluit.

## Drie dingen, drie plekken

| wat | waar | levensduur |
|---|---|---|
| de stand van het werk per deelvraag (voortgang, fase, onderzoekspunten) | api, `bronselectie_voortgang` | duurzaam, gedeeld |
| de besluiten: een bron opgenomen bij een deelvraag (met rol), *later* of *uitgesloten* bij een deelvraag | api, `werkgebied_deelvraag_koppelingen.rol` en `bron_kandidaat_deelvragen`; werkgebiedbreed `bron_kandidaten` | duurzaam, gedeeld, geaudit |
| het gesprek: welke kaartjes er zijn gesteld en beantwoord | api, `gesprek_berichten` (`vraagkaart`, `intake_antwoord`) | per gebruiker, een verslag |

De gesprek-checkpointer van graph-qa draagt **niets** van de bronselectie. Daardoor is hervatten gewoon een
nieuwe beurt die de stand leest: na herladen, in een ander gesprek in hetzelfde werkgebied, of bij een collega.

## De cyclus per deelvraag

```
bs_kies ──► bs_bepalingen (fase A/B: kern) ──► bs_afhankelijkheden (fase C) ──► bs_afronden (fase D) ──► bs_verder
   ▲                │ niets gevonden: één zin, door              │ niets: door                    │            │
   └────────────────┴──────────── "Naar het overzicht" ◄─────────┴────────────────────────────────┘◄───────────┘
```

- **Een kaartje per stap**, in het vraagkaartcontract van de intake (`modus: "bronselectie"`, `intake_id`
  `bs-<werkgebied>`, `deelvraag_id`). Eén kaart per deelvraag met meerkeuze voor *opnemen*; uitsluiten, later
  en context zijn besluiten in het paneel of op de pagina. Een eigen tekst op een kaartje wordt een
  onderzoekspunt.
- **Zoeken** is de bestaande bronnenrun (`bronnen_run.bronnen_kern`), idempotent op de selectie: na het opnemen
  verandert de invoer, en de volgende stap vindt wat aan de nieuwe bron hangt (verwijzing, definitie, opbouw).
- **De volgende deelvraag** rekent de api (`volgende`): de eerste niet-klare na de huidige, dan vooraan verder.
- **Een tussenvraag** gaat langs de supervisor naar de antwoord-worker, met het werkgebied als context. Het
  kaartje blijft openstaan in de werkplek (`openVraag`), de stand verandert niet.

## Statussen

- `niet_gestart` (geen rij) → `in_behandeling` (openen, of het eerste besluit) → `voorlopig_afgerond` (de
  analist sluit af; open punten mogen) → `beoordeeld` (alleen door een poort: geen open voorstel en geen
  onderzoekspunt). `heropenen` gaat terug naar `in_behandeling`.
- Los daarvan staan de deelvraagstatus (`actief`, `vervangen`, …) en de dekkingscheck met begrippen
  (`gedekt`, `geen_begrip`, `geen_bron`). Die worden niet vermengd.
- **Een afronding staat op een scope** (`scope_stand`: analysevraag, afbakening, deelvraagtekst). Verandert die,
  dan is de deelvraag `opnieuw_bekijken` en niet meer klaar; de besluiten blijven staan. Een verbeterde
  deelvraag erft voortgang en besluiten, en staat daardoor op *opnieuw bekijken*.

## Wat Lex niet zegt

- Een tekstuele overeenkomst heet zo (`bewijs_soorten`: verwijzing, definitie, structuur, tekst, gelijkenis).
- Een afgekapte of mislukte zoekmethode is een open punt (`zoekdekking`), nooit een stil kleinere lijst; wat
  bij geen deelvraag hoort staat apart (`zonder_deelvraag`).
- De controle onderscheidt zoekdekking, juridische dekking en beoordelingsdekking, en eindigt met "beoordeeld
  binnen de vastgestelde afbakening en de beschikbare bronnen" – nooit met "volledig".

## Bekende beperkingen

- De functie van een verwijzing (uitzondering, delegatie, voorwaarde) wordt niet afgeleid; Lex noemt alleen de
  relatie in de graaf.
- De rangschikking van `bepaling_opties` is ongewijzigd (meting 21 okt 2026: recall 0,21 in de top 8). Een
  betere rangschikking is de volgende stap, gemeten op een nieuwe held-out set.
