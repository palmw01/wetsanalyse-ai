# Verwijzingen inventariseren en volgen

Wetsformuleringen verwijzen voortdurend naar andere bepalingen: naar het definitieartikel
vooraan ("in deze wet wordt verstaan onder…"), naar andere leden ("in afwijking van het
eerste lid"), naar schakelbepalingen ("van overeenkomstige toepassing"), en naar
gedelegeerde regelingen (amvb / ministeriële regeling). Die verwijzingen bepalen mede de
*betekenis* en *werking* van de bepaling die je analyseert. Deze stap maakt ze expliciet,
volgt de relevante, en legt ze traceerbaar vast als `verwijzingen`-array **op de bron**
(elke verwijzing draagt het `bron_id` van haar bron).

`verwijzingen` is een **aparte as** náást de markeringen: het zijn uitgaande pointers van de
bepaling, géén tweede plek om JAS-klassen te registreren. Een delegatie blijft óók een
markering met klasse *Delegatiebevoegdheid en delegatie-invulling*, en is daarnaast een
verwijzing met functie *delegatie*. Een verwijzing naar een definitieartikel legt de
brondefinitie vast die de betekenis van de bepaling bepaalt.

## Twee herkomsten

1. **Getagde verwijzingen** – de graaf levert per lid de verwijzingen (intref/extref) met
   doel, label en het BWB-id van de doelregeling. Deze staan óók als inline-link in de
   tekst. Neem ze over.
2. **Natuurlijke-taalverwijzingen** – verwijzingen zonder XML-tag die de bron niet vangt, bv.
   "in afwijking van het eerste lid", "van overeenkomstige toepassing", "de in artikel 5
   bedoelde termijn". Herken die zelf in de letterlijke tekst en noteer ze met `soort:
   "natuurlijk"` (vaak alleen een `doel.label`, geen `target`).

## Classificeer naar functie

| Functie | Wat het is | Herken aan |
| --- | --- | --- |
| **definitie** | Verwijst naar een begripsomschrijving die de betekenis bepaalt | "in deze wet wordt verstaan onder", verwijzing naar het definitieartikel |
| **schakel** | Maakt een andere bepaling (deels) van toepassing of wijkt ervan af | "van overeenkomstige toepassing", "in afwijking van", "onverminderd" |
| **delegatie** | Verwijst naar een lagere regeling die nadere regels stelt | "bij of krachtens algemene maatregel van bestuur", "bij ministeriële regeling" |
| **intra-artikel** | Verwijst naar een ander lid van hetzelfde artikel | "het eerste lid", "het bepaalde in het tweede lid" |
| **informatief** | Verwijst zonder de betekenis/werking te raken | losse signalering, "zie ook" |

## Volg-beleid (default)

| Functie | Default actie | Diepte | Tool |
| --- | --- | --- | --- |
| **definitie** | Ophalen; de brondefinitie legt de betekenis van de bepaling vast | 1 | begrip opzoeken / artikel ophalen |
| **schakel** | Ophalen voor zover het de focus-bepaling betekenis geeft | 1 | artikel ophalen |
| **delegatie** | *Bounded:* vindplaats + relevante bepaling identificeren, de betekenis verwerken. Wordt de gedelegeerde regeling relevant genoeg, **promoveer haar tot een eigen bron** in het werkgebied (het werkgebied mag groeien); anders signaleer je een volledige JAS-analyse als validatiepunt | 1 (identificatie) | structuur van de regeling |
| **intra-artikel** | Als relatie vastleggen; de tekst staat al in scope | 0 | – |
| **informatief** | Signaleren, niet volgen | – | – |

## Grenzen tegen scope-explosie

Omdat alle soorten in beginsel gevolgd worden, gelden twee harde grenzen:

- **Diepte-cap = 1.** Volg verwijzingen één niveau vanaf de focus-bepaling. Een verwijzing
  *ván* een verwezen artikel volg je niet automatisch verder: noteer haar met status
  `buiten-scope-diepte`. De jurist kan vragen alsnog dieper te gaan.
- **Relevantie-gate.** Haal een verwijzing alleen daadwerkelijk op als ze de *betekenis of
  werking van de focus-bepaling* raakt. Louter informatieve verwijzingen krijgen status
  `gesignaleerd`. Elke gevolgde verwijzing is bovendien een extra bevraging van de kennisgraaf —
  houd het gericht.

## Status per verwijzing

- `opgehaald` – gevolgd én de tekst opgehaald (de betekenis is in de analyse verwerkt).
- `gevolgd` – gevolgd zonder aparte fetch (bv. intra-artikel: de tekst is al in scope).
- `gesignaleerd` – herkend maar bewust niet gevolgd (informatief of niet-relevant).
- `buiten-scope-diepte` – buiten de diepte-cap gelaten; kandidaat om als bron toe te voegen.

## Registreren

Schrijf de verwijzingen als `verwijzingen`-array **op de betreffende bron**, met
**werkgebied-breed stabiele id's** (`v1`, `v2`, …) en het `bron_id` van de bron. Let op de
functie- en status-waarden, een ingevulde `doel.label`, id-uniciteit over bronnen, en de
koppeling bij een delegatie.

**Houd deze stap licht:** het is inventariseren + gericht ophalen, niet al classificeren in
JAS-klassen – dat blijft activiteit 2. De verwijzing-inventaris is er zodat de jurist de scope van
het werkgebied kan bijsturen.

---

**Waar dit wel en niet geldt.** Dit beleid hoort bij het afbakenen van een **werkgebied** over
meerdere bronnen. De annotatiestroom in de werkplek annoteert één opgehaalde bepaling en volgt
zelf geen verwijzingen; wat je hier leest is dus geen stap in die keten. Twee dingen blijven wél
gelden bij het annoteren van één bepaling: een **delegatiebevoegdheid** markeer je als klasse (zie
`jas-klassen-referentie.md` §12), en een **brondefinitie** waarnaar de bepaling verwijst staat vaak
in de moederwet en niet in de gedelegeerde regeling (§13).
