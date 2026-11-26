---
name: contenttoets
metadata:
  methode_versie: "0.1"
  lex_soort: "methode"
  lex_label: "Contenttoets: content toetsen op juistheid en volledigheid"
  lex_herkomst: "Eigen werk van het project (plan docs/architectuur/plan-contenttoets.md); de bronnen staan in references/bronnen.md"
  lex_licentie: "eigen tekst in deze repo"
  lex_letterlijk: "nee"
description: >-
  Toetst een stuk content, zoals een webtekst, brief of FAQ, op juistheid en volledigheid tegen de bron: de geldende
  wet- en regelgeving en de beleidsregels. Haalt de toetsbare beweringen uit de tekst (bedragen, termijnen, voorwaarden,
  uitzonderingen, rechtsgevolgen, bevoegdheden), legt elke bewering naast de letterlijke brontekst, geeft per bewering
  een oordeel (juist, mogelijk onjuist, onvolledig, niet in de bron) met criterium, vindplaats, toelichting, twijfels
  en een voorstel voor een betere zin, en noemt wat de bron zegt en de tekst weglaat. Gebruik deze skill zodra iemand
  content wil valideren, controleren, checken of toetsen tegen de wet, vraagt of een tekst klopt, of /contenttoets
  gebruikt. Niet voor een wetsanalyse of het annoteren van wettekst, en niet voor juridisch advies.
---

# Contenttoets

Een contenttoets legt een tekst voor het publiek of de uitvoering naast de bron en zegt per bewering of die klopt en of
er iets wezenlijks ontbreekt. Het resultaat is een **toetsrapport** voor twee lezers: de redacteur, die wil weten wat er
moet veranderen, en de jurist, die het oordeel wil kunnen nalopen.

De contenttoets staat los van de wetsanalyse. Hij maakt geen markeringen in wettekst, gebruikt geen werkgebied en geen
JAS-klassen. Hij deelt alleen de brondata: de wet- en regelgeving zoals die in de kennisgraaf staat.

## Drie dingen die altijd gelden

1. **Alleen letterlijke brontekst.** Elk oordeel over juistheid rust op een letterlijk citaat uit een opgehaalde bron,
   met de vindplaats. Zonder citaat geen *mogelijk onjuist*: dan is het *niet in de bron*.
2. **Lex stelt voor, de mens beslist.** Het oordeel heet *mogelijk onjuist*, niet *onjuist*. Twijfel en aannames staan
   apart en zichtbaar, en een voorstel voor een betere zin is een voorstel.
3. **Vereenvoudigen is geen fout.** Een publiekstekst mag korter en eenvoudiger zijn dan de bron. Weglaten is pas
   *onvolledig* als de lezer er anders door zou handelen. Zie [eenvoud is geen fout](references/eenvoud-is-geen-fout.md).

## Wat ga je doen?

| Vraag of opdracht | Werkstroom | Lees |
|---|---|---|
| "Toets deze tekst", "klopt dit?", "valideer deze content", `/contenttoets <tekst>` | **A. Volledige toets** | alles hieronder, [rapport](references/rapport.md) |
| "Klopt deze ene zin?", "is dit bedrag juist?" | **B. Eén bewering** | [beweringen](references/beweringen.md), [criteria](references/criteria.md) |
| "Hoe moet het dan wel?", een betere formulering | **Bij A en B: herschrijven** | [herschrijven](references/herschrijven.md) |

Een uitgewerkte toets van een echte webtekst staat in [voorbeelden](references/voorbeelden.md).

## A. Volledige toets

```
Contenttoets – voortgang
- [ ] Peildatum vastgesteld: vandaag, of de publicatiedatum die is meegegeven
- [ ] De tekst opgedeeld in toetsbare beweringen; procesinformatie apart gezet als niet getoetst
- [ ] Per bewering de bron gezocht en letterlijk gelezen (geldend op de peildatum)
- [ ] Per bewering een oordeel met criterium (J1–J7, V1–V3), citaat en vindplaats
- [ ] Elke "mogelijk onjuist" nog een keer gelezen: spreekt de bron de bewering echt tegen?
- [ ] De tekst als geheel: spreekt hij zichzelf tegen (J6), ontbreekt er iets wezenlijks (ontbreekt)?
- [ ] Twijfels en aannames apart benoemd
- [ ] Per bevinding die niet juist is: een voorstel voor een betere zin
- [ ] Het rapport in twee lagen: voor de redacteur, en de juridische kern
```

1. **Beweringen vinden.** Haal uit de tekst wat een lezer als regel opvat: bedragen, termijnen, voorwaarden,
   uitzonderingen, rechtsgevolgen, bevoegdheden, voor wie het geldt. Citeer elke bewering letterlijk uit de tekst. Wat
   geen regel is (hoe je een formulier invult, waar je inlogt), toets je niet; noem het onder *niet getoetst*. Zie
   [beweringen](references/beweringen.md).
2. **De bron zoeken en lezen.** Zoek per bewering de bepaling die haar draagt en lees de tekst zelf, niet een
   samenvatting. Kijk welke bronnen er zijn: de wet, de uitvoeringsregeling, de beleidsregel (zoals de Leidraad
   Invordering), alles uit de kennisgraaf. Een bron buiten de graaf telt niet. Zie [bronnen](references/bronkeuze.md).
3. **Oordelen.** Kies één oordeel uit de vaste lijst en noem het criterium. Zie [criteria](references/criteria.md).
4. **Tweede lezing.** Lees elke *mogelijk onjuist* opnieuw met de tekst rond het citaat. Gaat de bepaling wel over
   dezelfde groep, dezelfde belasting, dezelfde regeling? Bij twijfel wordt het *niet in de bron*, met de twijfel erbij.
5. **Het geheel.** Kijk of de tekst zichzelf tegenspreekt en of de bron iets wezenlijks zegt dat de tekst weglaat. Loop
   daarvoor elke gelezen bepaling na, ook de onderdelen van een opsomming: welke voorwaarden, uitzonderingen en gevolgen
   staan er, en noemt de tekst ze? Wat ontbreekt en de lezer nodig heeft, zet je onder *ontbreekt*. De code noemt daarna
   wat het rapport en de tekst allebei missen, als *na te lopen*.
6. **Herschrijven.** Stel per bevinding een betere zin voor. Zie [herschrijven](references/herschrijven.md).
7. **Rapporteren** in het [sjabloon](assets/toetsrapport.md). Zie [rapport](references/rapport.md).

## B. Eén bewering

Dezelfde stappen voor één zin: de bron, het oordeel met criterium, het citaat, de toelichting en zo nodig een voorstel.
Het rapport is dan één bevinding, zonder de samenvatting.

## De oordelen

| Oordeel | Wanneer | Vereist |
|---|---|---|
| **juist** | de bron draagt de bewering | citaat en vindplaats |
| **mogelijk onjuist** | de bron zegt iets anders (J1–J7) | citaat en vindplaats, na de tweede lezing |
| **onvolledig** | de bewering klopt, maar laat iets wezenlijks weg (V1–V3) | citaat van wat ontbreekt |
| **niet in de bron** | Lex vond geen bepaling die de bewering draagt of tegenspreekt | wat er gezocht is |
| **ontbreekt** | voor de tekst als geheel: de bron zegt iets wezenlijks dat de tekst nergens noemt | citaat en vindplaats |

*Niet in de bron* is geen verkapt *onjuist*. Het zegt alleen dat de bewering niet te toetsen was met wat Lex kan lezen.
Een werkinstructie of formuliervoorwaarde staat vaak niet in de wet; noem dat als aanname.

## Veelgemaakte fouten

- **Een regel van een andere groep toepassen.** De standaardregeling voor toeslagschulden is niet die voor
  belastingschulden. Lees de kop en de context van de bepaling (J3).
- **Een termijn op het verkeerde moment laten ingaan.** "Vier maanden" kan vanaf de vervaldag lopen, niet vanaf het
  verzoek (J5).
- **Elke vereenvoudiging onvolledig noemen.** Pas de materialiteitstoets toe (V).
- **Een bewering onjuist noemen zonder citaat.** Dan is het *niet in de bron*.
- **Uit het hoofd citeren.** Elk citaat komt letterlijk uit wat deze beurt is opgehaald.
- **Procesinformatie toetsen.** Een formulier, een inlogmiddel of een postadres is geen regel uit de wet.
- **Het voorstel laten zeggen wat de bron niet zegt.** Een betere zin voegt geen nieuwe bewering toe.

## Grenzen

Een toetsrapport is geen juridisch advies en stelt niets vast: een jurist beoordeelt. Op termijn hoort RegelSpraak de
basis van de toets te zijn; tot die er is, toetst Lex tegen de tekst van de wet- en regelgeving.
