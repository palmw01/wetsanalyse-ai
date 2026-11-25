# Voorbeeld: de webtekst over de betalingsregeling

Een uitgewerkte toets van een echte webtekst over de betalingsregeling voor particulieren (geplakt in Lex op 25 nov 2026).
De bron is de Leidraad Invordering 2008 (BWBR0024096), toestand 1 juli 2026, en artikel 25 van de Invorderingswet 1990
(BWBR0004770). Alle citaten zijn letterlijk uit de kennisgraaf. Dit voorbeeld illustreert de criteria; het is geen
referentieset (die staat in `evals/`, met andere teksten).

De mockup van dit rapport staat als schermafbeeldingen in `docs/architectuur/media/mockup-contenttoets-*.png`.

## Mogelijk onjuist

**"U kunt uw belastingschuld betalen in maximaal 24 maanden."** · J1, J3, J6

- Bron: "De ontvanger kan op verzoek van de belastingschuldige een standaardbetalingsregeling verlenen met een looptijd
  van maximaal twaalf maanden, gerekend vanaf de datum waarop de ontvanger de betalingsregeling bij beschikking verleent."
  (Leidraad art. 25.3a.1)
- En: "De periode waarover de regeling zich uitstrekt is maximaal 24 maanden te rekenen vanaf de vervaldag van de
  terugvorderingsbeschikking of de datum van de beschikking waarbij de Dienst Toeslagen de betalingsregeling toestaat."
  (Leidraad art. 79.7)
- Toelichting: voor belastingschulden is het twaalf maanden; 24 maanden is de regeling voor toeslagschulden. De tekst
  noemt bovenaan zelf 12 maanden, dus hij spreekt zichzelf ook tegen.
- Voorstel: "U kunt uw belastingschuld betalen in maximaal 12 maanden."

**"Uw belastingschuld is niet hoger dan € 90.000."** · J2

- Bron: "In aanvulling hierop kan de ontvanger niet instemmen met het verzoek om toepassing van de
  standaardbetalingsregeling als: … c. sprake is van een aanzienlijk fiscaal belang; de belastingschuld waarvoor de
  standaardbetalingsregeling wordt gevraagd bedraagt ten tijde van indiening van het verzoek ten minste € 100.000."
  (Leidraad art. 25.3a.3)
- Toelichting: een schuld tussen € 90.000 en € 100.000 valt volgens de Leidraad wel onder de regeling.
- Aanname: € 90.000 kan een grens van het online formulier zijn; die staat niet in de graaf. Daarom *mogelijk*.
- Voorstel (vraag): "Is € 90.000 de grens van het online formulier? Zeg dat dan in de tekst."

**"U wilt een betalingsregeling voor 1 of meer openstaande belastingaanslagen inkomstenbelasting, bijdrage
Zorgverzekeringswet en/of naheffingsaanslagen motorrijtuigenbelasting."** · J3

- Bron: "De ontvanger verleent de betalingsregeling voor alle belastingaanslagen van de belastingschuldige die ten tijde
  van het verzoek openstaan, met uitzondering van:" (Leidraad art. 25.3a.1)
- Toelichting: "1 of meer" suggereert dat je kiest; de Leidraad neemt alle openstaande aanslagen mee, op drie
  uitzonderingen na. De beperking tot drie soorten aanslagen staat niet in art. 25.3a.

## Onvolledig

**"Of misschien kunt u 4 maanden kort uitstel van betaling krijgen."** · V1, J5

- Bron: "Op schriftelijk of telefonisch verzoek kan zonder nader onderzoek een betalingsregeling worden getroffen met een
  looptijd tot maximaal vier maanden na de laatste vervaldag van de (oudste) aanslag, als aan de volgende cumulatieve
  voorwaarden is voldaan:" en "De totale openstaande schuld van de belastingschuldige bedraagt minder dan € 20.000."
  (Leidraad art. 25.5.3)
- Toelichting: de vier maanden tellen vanaf de laatste vervaldag van de oudste aanslag, en alleen bij een schuld onder
  € 20.000, zonder betekend dwangbevel en zonder eerder uitstel wegens betalingsproblemen.

**"Kunt u niet binnen 12 maanden betalen of wilt u dat wij rekening houden met uw betalingscapaciteit? Dan kunt u een
betalingsregeling aanvragen waarbij wij rekening houden met uw betalingscapaciteit en bijzondere omstandigheden."** · V2

- Bron: "Slechts als er volgens de ontvanger bijzondere omstandigheden zijn, kan hij de belastingschuldige een langere
  termijn gunnen dan twaalf maanden." en "Indien uit het verzoek om uitstel blijkt dat de belastingschuldige over
  onvoldoende betalingscapaciteit beschikt om binnen twaalf maanden zijn schuld te betalen, dan neemt de ontvanger dat
  verzoek ambtshalve in behandeling als een verzoek om kwijtschelding." (Leidraad art. 25.5.1)
- Toelichting: ook de reguliere regeling is in beginsel ten hoogste twaalf maanden; het gevolg van te weinig
  betalingscapaciteit noemt de tekst niet.

## Niet in de bron

- **"Bij de standaardbetalingsregeling houden wij geen rekening met uw betalingscapaciteit."** Art. 25.3a zegt niets
  over de betalingscapaciteit. Waarschijnlijk juist, maar niet aan een passage te koppelen.
- **"Inclusief eventuele invorderingsrente en aanmaning- en dwangbevelkosten."** Niet in de gelezen passages; de regels
  over invorderingsrente en kosten zijn niet gelezen.

## Juist

- "standaardbetalingsregeling van maximaal 12 maanden" – Leidraad art. 25.3a.1.
- "gelijke termijnen van minimaal € 20 per maand" – "De belastingschuldige betaalt de belastingschuld in gelijke
  maandelijkse termijnen van ten minste € 20." (art. 25.3a.1)
- De drie uitzonderingen (voorlopige aanslag over het lopende jaar, conserverende aanslag, uitstel wegens bezwaar of
  beroep) – art. 25.3a.1, onderdelen 1° tot en met 3°.
- "Ook als de uiterste betaaldatum al is verstreken." – "De ontvanger neemt een verzoek om uitstel van betaling altijd in
  behandeling, ongeacht het tijdstip van indiening en het stadium van de invordering." (art. 25.1.14)

## Ontbreekt

- Verrekening tijdens de standaardregeling: "Gedurende de looptijd van de standaardbetalingsregeling verrekent de
  ontvanger belastingteruggaven en andere teruggaven met de openstaande belastingschuld." (art. 25.3a.2)

## Niet getoetst

- Het formulier, DigiD en eIDAS, en het versturen per post: procesinformatie.
