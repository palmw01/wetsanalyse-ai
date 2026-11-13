---
name: wetsuitvoering
metadata:
  methode_versie: "JRM 2 (2025-03)"
  skill_versie: "1.1"
  lex_soort: "methode"
  lex_label: "Wetsuitvoering: juridische scenario's (JRM 2)"
  lex_herkomst: "Juridisch Referentiemodel (JRM 2), specificatie van BZK (minbzk/wetsuitvoering, commit 4a9b584); zie BRON.md"
  lex_licentie: "W3C Software and Document License"
  lex_letterlijk: "ja"
description: >-
  Beschrijft hoe wet- en regelgeving in de uitvoering uitpakt volgens het Juridisch Referentiemodel (JRM 2), de
  methode wetsuitvoering: juridische scenario's en aktes opstellen (begintoestand, rechtsfeit, rechtsgevolgen,
  eindtoestand), rechtsgevolgen expliciet vastleggen, juridisch relevante feiten en feittypen formuleren als opmaat
  naar een gegevensmodel, en de JRM-classificaties verbinden met het Juridisch Analyseschema. Gebruik deze skill
  zodra iemand een scenario, tijdlijn of testgeval uit wetgeving wil afleiden, vraagt wat er juridisch verandert
  door een gebeurtenis, de happy flow en afwijkende gevallen wil uitwerken, rechtsgevolgen of juridisch relevante
  feiten wil vastleggen, of de stap van wettekst naar gegevens of uitvoering wil zetten, ook als JRM niet genoemd wordt.
---

# Wetsuitvoering (JRM 2)

Het Juridisch Referentiemodel kijkt naar wetgeving **zoals een burger of bedrijf haar doorloopt in de uitvoering**.
De eenheid daarvan is het juridisch scenario: een reeks juridische aktes, elk van een begintoestand via een rechtsfeit
naar een eindtoestand. Zo wordt zichtbaar wat er juridisch verandert, en welke gegevens daarvoor nodig zijn.

Deze skill hoort naast de skill **wetsanalyse**. Gebruik wetsanalyse om bepalingen te ontleden en in de dertien
JAS-klassen te markeren; gebruik deze skill om met die bepalingen scenario's, rechtsgevolgen en juridisch relevante
feiten op te bouwen. De twee zijn gescheiden: een scenario verwijst naar een wetsanalyse en maakt zelf geen
markeringen (zie [koppeling](references/koppeling-wetsanalyse.md)). De herkomst en licentie staan in [BRON.md](BRON.md).

## Drie dingen die altijd gelden

1. **Elk element is herleidbaar.** Een rechtsgevolg, feit of akte verwijst naar de bepaling waarop het rust, of staat
   als toevoeging van het team gemarkeerd. Een scenario dat de wet niet draagt, is een aanname.
2. **Instantie en type uit elkaar.** Een scenario met een concrete burger en concrete bedragen is een instantie; de
   regel erachter is een type. Schrijf allebei, en meng ze niet in één zin.
3. **Hypothetische feiten zijn geen bron.** Een scenario test de lezing van de wet; het bewijst haar niet.

## Wat ga je doen?

| Vraag of opdracht | Werkstroom | Lees |
|---|---|---|
| "Werk een scenario uit", "wat gebeurt er als …", happy flow en afwijkingen, testgevallen | **A. Juridisch scenario** | [scenario](references/scenario.md), [sjabloon](assets/scenario.md) |
| "Wat is het rechtsgevolg", wat ontstaat, wijzigt of eindigt | **B. Rechtsgevolgen** | [scenario §Rechtsgevolg](references/scenario.md) |
| Welke gegevens zijn nodig, feittypen, de stap naar een gegevensmodel | **C. Juridisch relevante feiten** | [relevant feit](references/relevant-feit.md) |
| Hoe verhouden JRM en JAS zich, welke classificatie is dit | **D. Classificeren** | [classificaties](references/classificaties.md) |
| Wat geldt er vóór en na een gebeurtenis, wat is onbekend | **Bij A en B: de juridische toestand** | [juridische toestand](references/juridische-toestand.md) |
| Er ligt al een wetsanalyse (JAS); hoe sluit het scenario daarop aan | **Bij A: de koppeling** | [koppeling met een wetsanalyse](references/koppeling-wetsanalyse.md) |

Een uitgewerkt scenario op een echte bepaling staat in [voorbeelden](references/voorbeelden.md).

## A. Juridisch scenario

```
Scenario – voortgang
- [ ] Praktijkvoorbeeld in gewone tekst: wie, wat, wanneer
- [ ] Tijdlijn: de gebeurtenissen in volgorde
- [ ] Per gebeurtenis een akte: begintoestand → rechtsfeit → rechtsgevolgen → eindtoestand
- [ ] De eindtoestand van een akte is de begintoestand van de volgende
- [ ] Per element de bepaling (artikel, lid) of "toevoeging team"
- [ ] Bewust gekozen: welke andere scenario's (niet alleen de happy flow) en welke niet
- [ ] Per beslispunt dat ertoe doet: het normale geval, een niet vervulde voorwaarde, de uitzondering en de grens
- [ ] Per deel van een toestand: bekend uit de bepaling, aangenomen of onbekend
- [ ] Het type achter de instantie: dezelfde akte zonder concrete namen en waarden
```

Werk één scenario volledig uit voor je het volgende begint: zo blijft het voor het hele team te volgen.

## B. Rechtsgevolgen

Een rechtsgevolg beschrijft dat een rechtsbetrekking of juridisch relevant feit **ontstaat, wijzigt of eindigt**. Leg
het apart vast, met het rechtsfeit dat het veroorzaakt. Verstop het niet in het rechtsfeit, zoals in het JAS
gebruikelijk was. Rechtsgevolgen zijn de receptuur van wat applicaties en registers moeten doen.

## C. Juridisch relevante feiten

Een juridisch relevant feit verbindt een waarde met de elementen waar zij bij hoort: *de natuurlijk persoon met BSN
<BSN> heeft een jaarinkomen van <jaarinkomen> in kalenderjaar <kalenderjaar>*. Het komt voor in een voorwaarde, is
een onderdeel van een rechtsobject, of is invoer of uitvoer van een afleidingsregel. Een losse variabele zonder zo'n
verbinding is onvoldoende. Zie [relevant feit](references/relevant-feit.md).

## D. Classificeren

Het JRM kent zes hoofdclassificaties (rechtssubject, rechtsbetrekking, rechtsfeit, rechtsgevolg, afleidingsregel,
juridisch relevant feit) en vier ondersteunende (voorwaarde, rechtsobject, variabele, parameter); parameter- en
variabelewaarde zijn samen *waarde*. In Lex blijven de dertien JAS-klassen het annotatiecontract; de JRM-laag hoort in
het dossier en de samenhang. Zie [classificaties](references/classificaties.md).

## Grenzen

De specificatie kondigt verdere uitwerking aan, onder meer van de juridische akte en van delegatie. Vul niet in alsof
het methode is wat er nog niet staat; zeg dat het een eigen uitwerking is. Een antwoord van deze skill is nooit
juridisch advies, en een scenario stelt niets vast: een jurist beoordeelt.

In Lex zijn de methodesecties van deze skill nog aan geen rol gekoppeld (JP04): dat volgt na een meting.
