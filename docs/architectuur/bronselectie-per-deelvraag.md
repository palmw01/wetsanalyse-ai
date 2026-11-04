# Bronselectie per deelvraag (spoor J)

Soort: *specificatie, beweegt mee met de code* · Hoort bij: PLAN spoor J · Code: `api/app/bronselectie.py`,
`tools/graph-qa/agent/bronselectie.py`, `frontend/components/werkgebieden/BronnenBijDeelvraag.tsx`

Lex begeleidt de bronselectie van een werkgebied in het gesprek, deelvraag voor deelvraag. Het model kiest
daarbij niets: de stand en de volgorde zijn van de applicatie, de zoekmethoden zijn deterministisch, en de
analist besluit.

## Drie dingen, drie plekken

| wat | waar | levensduur |
|---|---|---|
| de stand van het werk per deelvraag (voortgang, fase, onderzoekspunten) | api, `bronselectie_voortgang` | duurzaam, gedeeld |
| de besluiten: een bron opgenomen bij een deelvraag (met rol), of *uitgesloten* bij een deelvraag | api, `werkgebied_deelvraag_koppelingen.rol` en `bron_kandidaat_deelvragen`; werkgebiedbreed `bron_kandidaten` | duurzaam, gedeeld, geaudit |
| het gesprek: welke kaartjes er zijn gesteld en beantwoord | api, `gesprek_berichten` (`vraagkaart`, `intake_antwoord`) | per gebruiker, een verslag |

De gesprek-checkpointer van graph-qa draagt **niets** van de bronselectie. Daardoor is hervatten gewoon een
nieuwe beurt die de stand leest: na herladen, in een ander gesprek in hetzelfde werkgebied, of bij een collega.

## De cyclus per deelvraag

```
bs_kies ──► bs_bepalingen (fase A/B: kern) ──► bs_afhankelijkheden (fase C) ──► bs_afronden (fase D) ──► bs_verder
   ▲                │ niets gevonden: één zin, door              │ niets: door                    │            │
   └────────────────┴──────────── "Naar het overzicht" ◄─────────┴────────────────────────────────┘◄───────────┘
```

- **Eerst de gebeurtenis** (`bs_gebeurtenis`, zoekvragen a–d, skill `references/zoekvragen-bronselectie.md`):
  heeft het werkgebied nog geen gebeurtenis en is de analist nog niet begonnen, of vraagt hij er zelf om ("bepaal
  de gebeurtenis"), dan vraagt Lex om welke gebeurtenis het gaat, in de term van de wet. De voorstellen komen
  zonder model uit de koppen van de regelingen (`zoekvragen.gebeurtenis_opties`); de keuze staat op het werkgebied
  (`gebeurtenis`) en laat de bronnenrun ook de grondslag zoeken (methode `grondslag`, zoekvraag a). Overslaan mag.
- **Een kaartje per stap**, in het vraagkaartcontract van de intake (`modus: "bronselectie"`, `intake_id`
  `bs-<werkgebied>`, `deelvraag_id`). Eén kaart per deelvraag met meerkeuze voor *opnemen*. **Kiezen is het
  besluit**: wat niet aangevinkt is, is *niet gekozen* (afgeleid uit de fase, niet bewaard). Er is geen *later*.
- **Zelf toevoegen**: een eigen tekst op een bepalingenkaartje ("artikel 25 lid 2 Invorderingswet 1990") is een
  bepaling die de analist als keuze toevoegt; de api toetst haar in de graaf. Een eigen tekst op het
  afrondkaartje is een onderzoekspunt. Later iets toevoegen = de vragen van de deelvraag opnieuw doorlopen; dan
  is wat niet gekozen was weer kiesbaar.
- **Zoeken** is de bestaande bronnenrun (`bronnen_run.bronnen_kern`), idempotent op de selectie: na het opnemen
  verandert de invoer, en de volgende stap vindt wat aan de nieuwe bron hangt (verwijzing, definitie, opbouw).
- **De volgende deelvraag** rekent de api (`volgende`): de eerste niet-klare na de huidige, dan vooraan verder.
- **Een tussenvraag** gaat langs de supervisor naar de antwoord-worker, met het werkgebied als context. Het
  kaartje blijft openstaan in de werkplek (`openVraag`), de stand verandert niet.

## Statussen

- `niet_gestart` (geen rij) → `in_behandeling` (openen, of het eerste besluit) → `voorlopig_afgerond` (de
  analist sluit af; open punten mogen) → `beoordeeld` (alleen door een poort: de vragen zijn doorlopen, er
  staat geen onderzoekspunt open en er is een bron opgenomen – een deelvraag zonder bron is nog open, volgens de
  dekkingsregel van de skill; sinds 4 nov 2026). `heropenen` gaat terug naar `in_behandeling`.
- Los daarvan staan de deelvraagstatus (`actief`, `vervangen`, …) en de dekkingscheck (`met_bron`, `geen_bron`;
  sinds spoor K zonder begrippen: die horen bij het werkgebied). Die worden niet vermengd. De rijen van de
  deelvragen in de werkplek tonen de voortgang hierboven, met het aantal bronnen.
- **Wat er ligt, is wat de laatste zoekopdracht vond.** Na een wijziging van het dossier of de selectie zoekt Lex
  eerst opnieuw (ook als alles al af was); een voorstel dat de nieuwe zoekopdracht niet meer vindt, verdwijnt.
  Besluiten (opgenomen, uitgesloten) blijven staan.
- **Een afronding staat op een scope** (`scope_stand`: analysevraag, afbakening, deelvraagtekst en de kandidaten
  bij de deelvraag). Verandert die,
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


## Compact kaartje, het paneel beslist (3 nov 2026)

Besluit van de gebruiker: het gesprek blijft rustig, zoals een artefact bij Claude. Het kaartje van de kernbepalingen
en van wat eraan hangt heeft geen vinkjes meer (`weergave: paneel`). Het noemt wat er ligt en verwijst naar het
paneel. Daar lees je de wettekst (uitklappen) en neem je per bepaling op of sluit je uit; die besluiten gaan
rechtstreeks naar de api. *Klaar* (`actie: klaar`, op het kaartje of onderaan het paneel) schuift de fase door
zonder een besluit te raken; wat dan nog onbeslist is, is niet gekozen. *+ Bepaling toevoegen* is hetzelfde onderdeel
als op de tab Bronnen: een regeling, een vindplaats uit de echte boom en de deelvraag. Een oud kaartje met vinkjes
wordt nog verwerkt.
