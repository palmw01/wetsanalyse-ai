# G1b – een lijdende vorm noemt de handelende partij niet (13 nov 2026)

Soort: *meting*, volgens het lichte regime: één set, twee runs per vorm, omdat dit precies het randgeval is. Plan:
[`../../plan-methodes-scheiden.md`](../../plan-methodes-scheiden.md), deel 2, G1b. De aanleiding staat in
[`../methodes-g1-2026-11-13/g1.md`](../methodes-g1-2026-11-13/g1.md): onder G1 zeiden vijf antwoorden ten onrechte dat
de bepaling het bestuursorgaan noemt.

Code: graph-qa op `8aa96d09` (bundel 103, met G1b), `CENTRALE_AGENT=meten`. Nulpunt: graph-qa op `e1532e29` (G1 plus
A2-3a en A2-3b, bundel 102). Daarom is het G1-verslag zelf geen nulpunt voor de centrale vorm: A2-3b haalde het
bepalingssjabloon uit de centrale agent.

## Kort

- **Inhoud: gehaald.**
  - Op de vijf partijvragen zegt het antwoord nu in 19 van de 20 gevallen dat de tekst de handelende partij niet
    noemt. In het nulpunt was dat 10 van de 20.
  - Geen enkel antwoord zegt nog dat de bepaling het bestuursorgaan noemt. In het nulpunt deden drie antwoorden dat.
  - Geen partij staat tussen aanhalingstekens als woorden uit de tekst. Waar *het bestuursorgaan* tussen aanhalingstekens
    staat, zegt dezelfde zin dat de tekst het niet noemt.
  - Geen verzonnen partij.
- **Brongetrouw: gelijk.** Faithfulness 1,0 en *gegrond* in elke beurt. Alle blokcitaten uit wettekst staan letterlijk in
  de Awb.
- **Kwaliteit: niet slechter.**
  - Supervisor: 19 → 20/20.
  - Centraal: 16 → 19/20.
  - De enige mislukking is 7:11 lid 2, op het woord *gebonden*; daarover hieronder een voorstel.
- **Routering: gelijk.** Elke beurt gaat naar *duiding* (supervisor) of *centraal*.
- **Niet duurder (gewogen warm): per vorm gehaald, per vraag niet overal.**
  - Supervisor: 464,3k → 463,1k (−0 %).
  - Centraal: 403,0k → 403,3k (+0 %).
  - Per vraag zijn drie vragen meer dan 25 % duurder: 4:35 lid 1 en 7:10 lid 1 komen door één dure run, 7:12 lid 1 bij
    de supervisor in beide runs. Zie §*Niet duurder*.
  - Koud: gelijk.
- **Verwachting bij 7:11 lid 2 is te streng.** Correctievoorstel: `expected_contains: ["herroept", "verplicht"]`.
- **Verbruik:** nulpunt 2,93M ruw, G1b 3,10M ruw.

## Wat er gemeten is

Gemeten is de partijenset (`golden_duiding_partijen`, tien Awb-bepalingen), twee runs per vorm, op beide commits. De
meting liep om en om en één beurt tegelijk, via de BFF met `eval/centrale_agent_meting.mjs vragen partijen …`, en is
gescoord met `eval.centrale_agent_sets`. golden_duiding is in het nulpunt niet gedraaid; dat valt onder het lichte
regime.

Versies in de eerste beurt:

| | Profiel *duiding* (supervisor) | `system_hash` *duiding* | Profiel *centraal* |
|---|---|---|---|
| Nulpunt `e1532e29` | `b98c251a955c` | `92a6545ea1ea` (gelijk aan G1) | `326e0e88f3db` |
| G1b `8aa96d09` | `b98c251a955c` | `22b928451b1c` | – |

De vingerafdruk van de methodetekst voor de rol *duiding* ging van `836cd79e6d08` naar `6288fec13be4`. Dat is een
andere hash dan de `system_hash`, die de hele systeemprompt dekt. Het methodeblok in de context groeide van 1.240 naar
1.313 tokens, wat past bij de extra zin.

Gegevens: [`g1b-sets.jsonl`](g1b-sets.jsonl), één regel per vraag per run. Het zijn 80 regels: 40 van het nulpunt en 40
van G1b, te onderscheiden aan het veld `commit`.

## De drempels

### Inhoud – gehaald

Gelezen zijn alle antwoorden op de vijf partijvragen: 3:46, 3:45 lid 1, 3:47 lid 1, 3:41 lid 1 en 7:12 lid 1. Dat zijn
10 antwoorden per vorm per meting. Geen van deze bepalingen noemt de handelende partij.

| | Supervisor, nulpunt | Supervisor, G1b | Centraal, nulpunt | Centraal, G1b |
|---|---|---|---|---|
| Zegt dat de tekst de handelende partij niet noemt | 3 | 10 | 7 | 9 |
| Zegt ten onrechte dat de tekst het bestuursorgaan noemt | 2 | 0 | 1 | 0 |
| Noemt het bestuursorgaan zonder te zeggen dat het een interpretatie is | 5 | 0 | 2 | 1 |

De rijen tellen niet op tot 10. Twee antwoorden van de supervisor in het nulpunt maken alleen de wederpartij expliciet,
niet de plichthebbende: 3:47 run 1 en 3:46 run 2. Het tweede telt ook als onjuist.

**De onjuiste zinnen in het nulpunt:**

- 3:46, supervisor run 2: "De tekst noemt alleen het bestuursorgaan als plichthebbende."
- 3:46, centraal run 2: "De wet noemt alleen het bestuursorgaan als plichthebbende."
- 3:41 lid 1, supervisor run 1: "Het lid noemt de verplichting van het bestuursorgaan".

**Hoe G1b het zegt.** Voorbeelden:

- "De tekst noemt de handelende partij niet bij naam (*'wordt melding gemaakt'* en *'wordt vermeld'* zijn lijdende
  vormen)." (3:45 lid 1, supervisor)
- "De bepaling gebruikt de lijdende vorm en noemt geen actor bij name; uit de systematiek van afdeling 7.2 Awb volgt dat
  het bestuursorgaan de plichthebbende is." (7:12 lid 1, supervisor)
- "Lid 1 noemt zelf geen actor ... dat het bestuursorgaan de plichthebbende is, volgt uit lid 3 en de systematiek van
  afdeling 3.7, niet rechtstreeks uit lid 1." (3:47 lid 1, centraal)

  Lid 3 noemt het bestuursorgaan inderdaad. Dat is een vindplaats in de bepaling zelf, en dat is wat G1 vroeg.
- Een concrete vindplaats (een afdeling, hoofdstuk of ander lid) staat erbij in 4 van de 10 antwoorden bij de supervisor
  en in 3 van de 10 bij centraal. In het nulpunt: 3 en 4. De rest noemt "de systematiek van de Awb".

**Aanhalingstekens.** In G1b staat *het bestuursorgaan* vier keer tussen aanhalingstekens:

- drie keer in een zin die zegt dat de tekst het niet noemt;
- één keer bij 7:10 lid 1, dat het bestuursorgaan wel noemt.

In het nulpunt stond het bij 4:35 lid 1 één keer tussen aanhalingstekens als drager van de bevoegdheid: "De bevoegdheid
ligt bij 'het bestuursorgaan'". Dat lid noemt het niet.

**Overige inhoud.**

- **Geen verzonnen partij.** Genoemd worden alleen het bestuursorgaan, de belanghebbende, de aanvrager, de burger, de
  ontvanger en de derde. Alle komen ze uit de Awb.
- **De soort staat goed:**
  - *discretionair* bij 4:5, 4:35 en 4:48;
  - een plicht bij 7:10 lid 1;
  - geen vrije keuze bij 7:11 lid 2.

### Brongetrouw gelijk – gehaald

| Vorm | Nulpunt, per run: citaten / niet letterlijk | G1b, per run: citaten / niet letterlijk |
|---|---|---|
| Supervisor | 31/0 · 36/0 | 38/0 · 32/0 |
| Centraal | 30/0 · 35/0 | 34/0 · 33/0 |

- De controle meldde twee citaten die ze niet vond: 4:35 in het nulpunt en 7:11 in G1b. Dat zijn stukken lopende tekst
  tussen twee aanhalingen, geen citaat.
- Faithfulness 1,0 en *gegrond* in alle 80 beurten.

### Kwaliteit niet slechter – gehaald

| | Nulpunt | G1b |
|---|---|---|
| Supervisor | 19/20 (7:11 run 1) | 20/20 |
| Centraal | 16/20 (3:46 en 3:47 run 1, 7:11 tweemaal) | 19/20 (7:11 run 1) |

- **3:46 en 3:47 lid 1 bij centraal (nulpunt).** Beide falen op het sjabloon. `antwoord_duiding` werd twee keer
  geweigerd (`genoemd_onbekend` of `passage_niet_te_tonen`), en daarna volgde tekst.
- **Weigeringen in totaal**, beide runs samen:

  | Vorm | Nulpunt | G1b |
  |---|---|---|
  | Supervisor | 7 | 8 |
  | Centraal | 12 | 7 |

  G1b haalt bij centraal geen sjabloon meer mis.

### Routering gelijk – gehaald

Alle 40 beurten per meting gaan naar *duiding* (supervisor) of *centraal*. Nergens `meer_tools`.

### Niet duurder (gewogen warm; koud apart) – per vorm gehaald, per vraag niet overal

| | Nulpunt, som | G1b, som | Nulpunt, mediaan | G1b, mediaan |
|---|---|---|---|---|
| Supervisor | 464,3k | 463,1k | 19,0k | 20,4k |
| Centraal | 403,0k | 403,3k | 17,9k | 15,4k |

**De 25 %-regel**, per vraag en vorm, met de mediaan van twee runs. Er is geen afwijzing in deze set.

| Vraag | Vorm | Nulpunt, runs | G1b, runs | Mediaan |
|---|---|---|---|---|
| 4:35 lid 1 | centraal | 14,6 / 14,6k | 36,9 / 14,2k | +75 % |
| 7:10 lid 1 | supervisor | 11,5 / 17,3k | 17,5 / 24,8k | +47 % |
| 7:12 lid 1 | supervisor | 14,3 / 29,8k | 46,4 / 39,8k | +96 % |

- **4:35 en 7:10:** de stijging komt door één dure run. 4:35 had zes rondes in plaats van twee. Bij twee runs valt dat
  niet van spreiding te onderscheiden.
- **7:12 lid 1 (supervisor):** beide runs zijn duurder, met 11 en 9 rondes tegen 5 en 7. Elke run kreeg twee weigeringen
  van `antwoord_duiding` (`passage_niet_te_tonen`, één keer `genoemd_onbekend`). Het antwoord zelf is goed en noemt
  afdeling 7.2 als vindplaats. Dit is de enige vraag waar de meerkosten in beide runs terugkomen.
- Daartegenover zijn andere vragen goedkoper:
  - 3:45 lid 1, supervisor: −42 %;
  - 4:48 lid 1, supervisor: −40 %;
  - 3:47 lid 1, centraal: −35 %;
  - 3:46, centraal: −28 %.

**Koud.** Het eerste begin per vorm schreef het uurvoorvoegsel:

| Vorm | Nulpunt, koud − warm | G1b, koud − warm |
|---|---|---|
| Supervisor | +26,3k | +26,5k |
| Centraal | +25,0k | +25,1k |

## 7:11 lid 2: de verwachting in de set

De bron (Awb, toestand 2026-08-15): "Voor zover de heroverweging daartoe aanleiding geeft, herroept het bestuursorgaan
het bestreden besluit en neemt het voor zover nodig in de plaats daarvan een nieuw besluit."

De set verwacht `expected_contains: ["gebonden"]`. `contains_ok` toetst of het woord letterlijk in het antwoord staat.

| | G1 en nulpunten (16 antwoorden) | G1b (4 antwoorden) |
|---|---|---|
| Bevat *gebonden* | 1 | 3 |
| Bevat *herroept* | 16 | 4 |
| Bevat *verplicht* (ook *verplichting*) | 15 | 4 |
| Zegt geen vrije keuze, verplicht of dwingend | 16 | 4 |

- **Inhoudelijk klopt elk antwoord.** Het lid legt een gebonden plicht op: zodra de heroverweging aanleiding geeft, moet
  het bestuursorgaan herroepen. Voorbeelden: "geen vrije keuze", "herroeping is verplicht", "gebiedende wijs, geen
  'kan'".
- **Alleen de woordkeus faalt.** *Gebonden* is vakjargon dat de antwoorden zelden gebruiken. De toets meet dus de
  woordkeus, niet de duiding.

**Voorstel:** `"expected_contains": ["herroept", "verplicht"]`, met als `beoordeling`: "'herroept' in de tegenwoordige
tijd: een gebonden plicht zodra de heroverweging daartoe aanleiding geeft; het antwoord zegt dat het bestuursorgaan
moet herroepen (geen vrije keuze)."

- *herroept* toetst dat het lid gelezen en aangehaald is.
- *verplicht* toetst de soort.
- Met deze verwachting slagen 19 van de 20 antwoorden. Het ene dat niet slaagt (centraal, nulpunt e1532e29) zegt "geen
  vrije keuze … dwingend" en is inhoudelijk ook goed.

Wil je ook dat laatste antwoord laten slagen, dan heeft de scorer een veld nodig met alternatieven, bijvoorbeeld
*verplicht* óf *geen vrije keuze*. Dat bestaat nu niet; `contains_ok` eist alle termen.

De set is in deze PR niet gewijzigd: een andere verwachting verandert de vergelijking met de eerdere metingen.

## Open

1. **7:11 lid 2:** de verwachting aanpassen zoals hierboven voorgesteld, bij de volgende meting die de partijenset
   gebruikt.
2. **7:12 lid 1 bij de supervisor:** in beide runs duurder (+96 %), door weigeringen van het sjabloon. Bij de eindmeting
   A6 met drie runs nog eens bekijken.
3. **De vindplaats:** die blijft vaak algemeen ("de systematiek van de Awb"). Een concreet artikel of lid, zoals 1:1 of
   3:47 lid 3, staat er in 3 à 4 van de 10. G1b vroeg daar niet om. Mocht het een eis worden, dan hoort dat in een eigen
   stap.

## Verbruik

| | Ruw |
|---|---|
| Nulpunt `e1532e29`, partijenset, beide vormen | 2,93M |
| G1b `8aa96d09`, partijenset, beide vormen | 3,10M |

Bron: de delta van het accountverbruik. Het budget is voor beide metingen gereset.
