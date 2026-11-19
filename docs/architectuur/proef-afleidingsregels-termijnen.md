# Proef: de afleidingsregels van Termijnen, opgesteld buiten Lex

> 19 nov 2026. Concept bij [plan-afleidingsregels.md](plan-afleidingsregels.md) §4. Opgesteld in een gewone sessie, met
> de wettekst en de Leidraad letterlijk opgehaald via de acceptatie-MCP (`bron_lezen`, `graaf_lezen`; IW 1990 en Awb in
> de toestand van oktober en november 2026). **Niets is beoordeeld door een jurist**: elke regel is een voorstel, en waar
> ik iets lees dat de tekst niet zegt, staat *lezing* erbij.

Dit document doet activiteit 3b uit de methode op papier: regels in natuurlijke taal, met begrippen als invoer en uitvoer,
een afleidingshiërarchie en een voorbeeldreeks die de regels toetst (M01 h.3 stap 3b en 4b; M02 §3.5.2b en §3.5.5; plan
§2.3). Het vervangt §4.1 en §4.2 van het plan niet. Het werkt ze uit met de bepalingen die daar nog ongelezen waren:
art. 9 lid 1 en 7 IW 1990, art. 24 lid 8, Awb 4:93 lid 3 en 4, en Leidraad 9.1, 9.3, 9.5 en 24.3.

## 1. Wat het lezen opleverde

Vier dingen veranderen ten opzichte van de proef in het plan:

- **Er is een regel nodig die het termijnregime kiest.** Lid 5, 6 en 7 sluiten elkaar uit en vallen alle drie terug op
  lid 1. Zonder één beslisregel die zegt welk lid geldt, herhaalt elke regel de voorwaarden van de andere. Die regel is
  R5 hieronder; AR2 uit het plan gaat erin op.
- **Lid 7 geldt voor elke voorlopige aanslag**, niet alleen voor de inkomsten- en vennootschapsbelasting: de tekst noemt
  geen belasting ("een voorlopige aanslag waarvan het aanslagbiljet een dagtekening heeft die ligt voor het jaar …"). Lid 6
  geldt alleen voor "een belastingaanslag als bedoeld in het vijfde lid", dus met de belastingen en de dagtekening van
  lid 5.
- **Leidraad 9.1 verschuift de laatste vervaldag, en raakt ook lid 1.** De Leidraad spreekt van de "enige of laatste
  betalingstermijn" van een aanslag "bedoeld in artikel 9, vijfde lid" die "in november of eerder" is gedagtekend. Bij een
  dagtekening in november geeft lid 5 één termijn, dus geldt lid 1 (zes weken), en die termijn eindigt vóór 31 december.
  *Lezing*: 9.1 zet die ene termijn dan op 31 december.
- **Leidraad 9.5 lost het datumrekenen maar half op.** Een dagtekening op de laatste dag van de maand vervalt op de laatste
  dag van de volgende maand; elke andere dag op "de dag die hetzelfde nummer heeft". Voor de 29e, 30e of 31e januari bij
  een maand zonder die dag zegt de Leidraad niets. Dat is **ontbrekend beleid** (activiteit 5), geen gat in de bron.

En voor het praktijkvoorbeeld (art. 69, 70 en 72 Mijnbouwwet, gelezen in de toestand van juni 2026):

- **Art. 72 Mbw is de enige brug, en die is ruim.** "Onverminderd het overigens bij of krachtens deze paragraaf bepaalde
  geschieden de heffing en de invordering van oppervlakterecht, cijns en winstaandeel met overeenkomstige toepassing van de
  Algemene wet inzake rijksbelastingen, de Invorderingswet 1990 en de Kostenwet invordering rijksbelastingen en de op die
  wetten berustende bepalingen." Het artikel zegt niet onder welke belasting van art. 9 lid 5 het winstaandeel valt. De
  graaf van acceptatie heeft buiten de Mijnbouwwet geen bepaling die het winstaandeel noemt, ook niet in de Leidraad.
- **Het winstaandeel volgt het boekjaar van de vennootschapsbelasting.** Art. 70 lid 2 laat de houder de stukken indienen
  "gelijktijdig met de aangifte voor de vennootschapsbelasting over een boekjaar"; art. 69 rekent "over een boekjaar". Dat
  maakt de tweede volzin van Leidraad 9.1 (afwijkende boekjaren) en de lezing bij R1 relevant voor de casus.
- **Homoniem: het verrekenbare bedrag.** Art. 69 lid 2 en 3 Mbw kent een "verrekenbare bedrag" dat het winstaandeel
  vermindert, berekend met het tarief van de vennootschapsbelasting. Dat is heffing, geen verrekening in de zin van art. 24
  IW 1990. In 3a horen dat twee begrippen te zijn; met dezelfde naam liggen ze in één groep.

Twee kleinere vondsten:

- Art. 24 lid 8 wijkt af van Awb 4:93 **lid 4** (verrekening is niet bevoegd voor zover beslag nietig zou zijn), niet van
  lid 3. De slottekst van art. 24 lid 1, volzin 6, wijkt af van **lid 3** (de verrekening werkt terug). Het zijn dus twee
  verschillende `uitzondering_op`-relaties naar twee leden van dezelfde Awb-bepaling.
- Volzin 7 van de slottekst van art. 24 lid 1 noemt "artikel 9, zesde en zevende lid". Daaronder valt ook een **positieve**
  aanslag met termijnen volgens lid 7. Het tijdstip van verrekening is dan ook de vervaldag, niet de dagtekening.

## 2. De begrippen

Per begrip de soort (zoals in plan §2.4) en of het in Termijnen al bestaat. *Bestaand* is een van de negen geaccordeerde
begrippen van Termijnen; *nieuw* is een voorstel voor een naam. De formulering waarop het begrip rust staat erbij.

**Rechtsobjecten en hun kenmerken (bepalend)**

- *voorlopige aanslag* — bestaand. Rechtsobject.
- *belasting waarin de aanslag is opgelegd* — nieuw. Kenmerk met de waarden inkomstenbelasting, vennootschapsbelasting,
  conserverende inkomstenbelasting en overige. Rust op "een voorlopige aanslag in de inkomstenbelasting of in de
  vennootschapsbelasting en een voorlopige conserverende aanslag in de inkomstenbelasting" (art. 9 lid 5). Het winstaandeel
  krijgt een waarde via R0.
- *voorlopige aanslag winstaandeel* — nieuw. Rechtsobject; een voorlopige aanslag die het winstaandeel van art. 70 Mbw
  heft (art. 70 lid 1: "Winstaandeel wordt geheven bij wege van aanslag", met art. 72 voor de voorlopige aanslag uit de
  AWR).
- *verrekenbaar bedrag (Mijnbouwwet)* — nieuw, en uitdrukkelijk **niet** *verrekening*. Variabele van de heffing
  (art. 69 lid 2 en 3 Mbw). Buiten de regels van dit document; het staat hier om het homoniem.
- *aanslag met een uit te betalen bedrag* — bestaand als *negatieve voorlopige aanslag*. Kenmerk ja/nee. Rust op "die een
  uit te betalen bedrag behelst" (lid 6) en "voorlopige aanslag tot een negatief bedrag" (art. 24 lid 8). Of beide
  formuleringen hetzelfde begrip dragen, is een keuze in 3a.
- *bedrag van de aanslag* — nieuw. Variabele, een bedrag in euro, bij een negatieve aanslag het uit te betalen bedrag.
- *derdenbeslag op de teruggaaf* — nieuw. Kenmerk ja/nee. Rust op "indien een derde aanspraak maakt op een voorlopige
  teruggaaf ingevolge een gelegd derdenbeslag" (Leidraad 9.3).

**Tijdsaanduidingen (bepalend)**

- *dagtekening van het aanslagbiljet* — bestaand. Een datum.
- *jaar waarover de aanslag is vastgesteld* — nieuw. Een tijdvak; bij een afwijkend boekjaar het boekjaar (Leidraad 9.1,
  tweede volzin). De afgewezen groep "het jaar" in Termijnen heroverwegen.
- *tijdvak waarop de aanslag betrekking heeft* — nieuw. Rust op "hetzelfde tijdvak" (art. 24 lid 2). *Lezing*: voor een
  voorlopige aanslag valt het samen met het vorige begrip. Dat moet de jurist bevestigen voor je de twee samenvoegt.

**Parameters**

- *aantal maanden van een jaar* — nieuw. Waarde 12. Rust op "nog maanden van het jaar" (lid 5, 6) en "als er maanden van
  het jaar zijn" (lid 7).
- *grensbedrag termijnuitbetaling* — nieuw. Waarde € 49 per maand (Leidraad 9.3).
- *wettelijke betalingstermijn* — nieuw. Waarde zes weken (art. 9 lid 1).

**Tussenresultaten en uitvoer (bepaald)**

- *maandnummer van de dagtekening* — nieuw (R1).
- *termijnregime* — nieuw (R5). Waarden: lid 1, lid 5, lid 6, lid 7.
- *aantal termijnen* — nieuw (R2–R4, R6).
- *vervaldag van een termijn* — nieuw (R7, R8), met *volgnummer van de termijn* (nieuw, 1 tot en met het aantal) als
  invoer.
- *termijnbedrag* — nieuw (R9).
- *uitbetaling in één keer* — nieuw (R10). Kenmerk ja/nee.
- *tijdstip van verrekening* — nieuw (R11). Nu opgenomen in de definitie van het bestaande *verrekening*: maak er een eigen
  begrip van.
- *verrekening mogelijk vóór het verstrijken van de termijn* — nieuw (R12). Kenmerk ja/nee.

**Operatoren** (generieke begrippen, plan §2.4): *min*, *plus*, *gedeeld door*, *groter dan*, *ten hoogste*, *gelijk aan*,
*ligt vóór*, *ligt in*, *en*, *of*, *niet*, *plus n maanden* (datumrekenen volgens Leidraad 9.5), *plus zes weken*, *laatste
dag van de maand*.

## 3. De regels

In het patroon van de methode: een rekenregel "X moet berekend worden als …", een beslisregel "X is waar indien aan alle
volgende voorwaarden is voldaan". Elke regel heeft precies één uitvoer.

### R0 — Bepalen belasting voor de invordering van een voorlopige aanslag winstaandeel (specialisatie; nieuw)

- Bron: art. 72 Mbw (§1), met art. 69 lid 3 onderdeel c en art. 70 lid 2 Mbw als steun voor de keuze.
- Regel: Voor de toepassing van de Invorderingswet 1990 geldt een *voorlopige aanslag winstaandeel* als een voorlopige
  aanslag waarvan de *belasting waarin de aanslag is opgelegd* de **vennootschapsbelasting** is.
- **Dit is een lezing (A), en de belangrijkste van het document.** Art. 72 zegt "overeenkomstige toepassing" van de hele
  Invorderingswet, niet dat het winstaandeel als vennootschapsbelasting geldt. Er zijn twee andere lezingen:
  - (B) lid 5 noemt het winstaandeel niet, en bij overeenkomstige toepassing van art. 9 vallen alleen de leden zonder
    belasting erin: lid 1 en lid 7 (R5 dan zonder deze regel);
  - (C) "overeenkomstig" leest de opsomming in lid 5 als "de belasting waarop de aanslag rust", en dan valt het winstaandeel
    onder lid 5 en 6 zonder dat het vennootschapsbelasting heet.
  A en C geven dezelfde termijnen; ze verschillen alleen bij R12, waar "dezelfde belasting" bij C winstaandeel met
  winstaandeel is in plaats van met de vennootschapsbelasting. B geeft het praktijkvoorbeeld geen termijnen.
- Soort: een specialisatie (plan §2.3): het rechtsobject wordt ingedeeld bij een groep, met als gevolg de regels van die
  groep. Relatie: `toepassing` van art. 72 Mbw naar de Invorderingswet 1990.

### R1 — Bepalen maandnummer van de dagtekening (rekenregel)

- Bron: "de maand, die in de dagtekening van het aanslagbiljet is vermeld" (art. 9 lid 5); "met inbegrip van de maand die
  in de dagtekening van het aanslagbiljet is vermeld" (lid 6).
- Regel: Het *maandnummer van de dagtekening* moet berekend worden als het rangnummer van de maand van de *dagtekening van
  het aanslagbiljet* binnen het *jaar waarover de aanslag is vastgesteld*.
- *Lezing*: bij een afwijkend boekjaar telt het rangnummer vanaf de eerste maand van het boekjaar. Leidraad 9.1 gaat uit
  van afwijkende boekjaren, maar de wet zegt alleen "het jaar".

### R2 — Bepalen aantal termijnen volgens lid 5 (rekenregel; was AR1)

- Bron: "invorderbaar in zoveel gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is
  vermeld, nog maanden van het jaar overblijven" (art. 9 lid 5, eerste volzin).
- Regel: Het *aantal termijnen volgens lid 5* moet berekend worden als het *aantal maanden van een jaar* **min** het
  *maandnummer van de dagtekening*.

### R3 — Bepalen aantal termijnen volgens lid 6 (rekenregel; was AR5a)

- Bron: "zoveel gelijke termijnen als er met inbegrip van de maand die in de dagtekening van het aanslagbiljet is vermeld,
  nog maanden van het jaar overblijven" (art. 9 lid 6, eerste volzin).
- Regel: Het *aantal termijnen volgens lid 6* moet berekend worden als het *aantal maanden van een jaar* **min** het
  *maandnummer van de dagtekening* **plus** 1.

### R4 — Bepalen aantal termijnen volgens lid 7 (rekenregel; nieuw)

- Bron: "invorderbaar in zoveel gelijke termijnen als er maanden van het jaar zijn" (art. 9 lid 7, eerste volzin).
- Regel: Het *aantal termijnen volgens lid 7* is het *aantal maanden van een jaar*.

### R5 — Bepalen termijnregime (beslisregel; was AR2, uitgebreid)

- Bronnen: art. 9 lid 1; lid 5, eerste en derde volzin; lid 6, eerste volzin; lid 7, eerste volzin.
- Regel, in volgorde (de eerste die geldt, wint):
  1. Het *termijnregime* is **lid 7** indien de *dagtekening van het aanslagbiljet* **ligt vóór** het *jaar waarover de
     aanslag is vastgesteld*.
  2. Het *termijnregime* is **lid 6** indien aan alle volgende voorwaarden is voldaan:
     - de *belasting waarin de aanslag is opgelegd* is inkomstenbelasting, vennootschapsbelasting of conserverende
       inkomstenbelasting;
     - de *dagtekening van het aanslagbiljet* **ligt in** het *jaar waarover de aanslag is vastgesteld*;
     - het is een *aanslag met een uit te betalen bedrag*.
  3. Het *termijnregime* is **lid 5** indien aan alle volgende voorwaarden is voldaan:
     - de *belasting waarin de aanslag is opgelegd* is een van de drie hierboven;
     - de *dagtekening van het aanslagbiljet* **ligt in** het *jaar waarover de aanslag is vastgesteld*;
     - het is **niet** een *aanslag met een uit te betalen bedrag*;
     - het *aantal termijnen volgens lid 5* is **groter dan** 1.
  4. Anders is het *termijnregime* **lid 1**.
- Relaties: lid 5, 6 en 7 dragen elk `uitzondering_op` naar lid 1, lid 6 ook naar lid 5. De derde volzin van lid 5 ("vindt
  het eerste lid toepassing") is een `toepassing` naar lid 1. Dat is voorwaarde 3.4 plus stap 4 van deze regel, geen eigen
  afleidingsregel.
- *Lezing*: lid 6 kent geen terugval op lid 1. Een negatieve aanslag die in de laatste maand van het jaar is gedagtekend,
  krijgt dus één termijn aan het eind van die maand. De terugval in lid 5 noemt "de toepassing van de eerste volzin", en lid
  6 wijkt juist van lid 5 af.
- *Lezing*: lid 7 noemt geen uit te betalen bedrag, maar Leidraad 9.3 leest het ook voor teruggaven ("Ingevolge artikel 9,
  zesde en zevende lid, van de wet worden voorlopige teruggaven in maandelijkse termijnen uitbetaald").

### R6 — Bepalen aantal termijnen (rekenregel)

- Regel: Het *aantal termijnen* is het *aantal termijnen volgens lid 5* indien het *termijnregime* lid 5 is, het *aantal
  termijnen volgens lid 6* bij lid 6, het *aantal termijnen volgens lid 7* bij lid 7, en 1 bij lid 1.
- *Lezing*: bij lid 1 is er geen termijn maar één betaling. Het getal 1 maakt R7–R9 gelijk voor alle regimes.

### R7 — Bepalen vervaldag van een termijn (rekenregel, uitvoer een datum; was AR3 en AR5b)

- Bronnen: art. 9 lid 1; lid 5, tweede volzin ("De eerste termijn vervalt één maand na de dagtekening van het
  aanslagbiljet en elk van de volgende termijnen telkens een maand later"); lid 6, tweede volzin ("De eerste termijn vervalt
  aan het eind van de maand van de dagtekening van het aanslagbiljet en elk van de volgende termijnen telkens een maand
  later"); lid 7, tweede volzin ("De eerste termijn vervalt aan het eind van de eerste maand van het jaar waarover de
  voorlopige aanslag is vastgesteld en elk van de volgende termijnen telkens een maand later").
- Regel, met *n* het *volgnummer van de termijn*:
  - bij **lid 1**: de *vervaldag* moet berekend worden als de *dagtekening van het aanslagbiljet* **plus zes weken**;
  - bij **lid 5**: de *dagtekening van het aanslagbiljet* **plus n maanden**;
  - bij **lid 6**: de **laatste dag van de maand** van de *dagtekening van het aanslagbiljet* **plus n − 1 maanden**;
  - bij **lid 7**: de **laatste dag van de maand** van de eerste maand van het *jaar waarover de aanslag is vastgesteld*
    **plus n − 1 maanden**.
- *plus n maanden* volgt Leidraad 9.5: de laatste dag van een maand wordt de laatste dag van de doelmaand, elke andere dag
  de dag met hetzelfde nummer. Bestaat dat nummer in de doelmaand niet, dan zegt de Leidraad niets (§1).
- *Lezing*: bij lid 6 en 7 is "telkens een maand later" vanaf een laatste dag weer een laatste dag. Dat volgt uit Leidraad
  9.5, niet uit de wet.

### R8 — Bepalen laatste vervaldag bij een dagtekening tot en met november (rekenregel, beleid; nieuw)

- Bron: Leidraad 9.1 ("… toepassing van de wet er toe zou leiden dat de enige of laatste betalingstermijn eindigt voor 31
  december, dan wordt de vervaldag van deze termijn op 31 december gesteld. Bij afwijkende boekjaren wordt de laatste
  vervaldag steeds op de laatste dag van de maand gesteld.").
- Regel: De *vervaldag van de laatste termijn* is de laatste dag van het *jaar waarover de aanslag is vastgesteld* indien
  aan alle volgende voorwaarden is voldaan:
  - de aanslag valt onder de belastingen en de dagtekening van lid 5 (voorwaarden 3.1 en 3.2 van R5);
  - het *maandnummer van de dagtekening* is ten hoogste 11;
  - de *vervaldag van een termijn* volgens R7 voor de laatste termijn **ligt vóór** die dag.
- *Lezing*: dit geldt ook bij termijnregime lid 1 ("enige … betalingstermijn") en bij lid 6, omdat de aanslag van lid 6 een
  aanslag "als bedoeld in het vijfde lid" is. Bij lid 6 valt de laatste termijn al aan het eind van het jaar, dus verandert
  er niets.
- *Lezing*: bij een afwijkend boekjaar is het "de laatste dag van de maand" van de laatste termijn, niet die van het
  boekjaar. Dat leest de tweede volzin letterlijk zo.
- Relatie: R8 overschrijft R7 voor één termijn. In de JAS-relaties is dat een `uitzondering_op` vanuit de beleidsregel
  naar lid 5, tweede volzin.

### R9 — Bepalen termijnbedrag (rekenregel; was AR4)

- Bron: "in zoveel gelijke termijnen" (lid 5, 6 en 7).
- Regel: Het *termijnbedrag* moet berekend worden als het *bedrag van de aanslag* **gedeeld door** het *aantal termijnen*.
- Ontbrekend beleid: de afronding en waar het restant landt. Niet in de gelezen Leidraad 9.

### R10 — Bepalen uitbetaling in één keer (beslisregel, beleid; was AR6)

- Bron: Leidraad 9.3 ("Hiervan wordt afgeweken als het maandelijks termijnbedrag niet groter is dan € 49 per maand. In dat
  geval worden de voorlopige teruggaven in één keer uitbetaald. Dit laatste lijdt uitzondering indien een derde aanspraak
  maakt op een voorlopige teruggaaf ingevolge een gelegd derdenbeslag.").
- Regel: Een voorlopige teruggaaf wordt *in één keer uitbetaald* indien aan alle volgende voorwaarden is voldaan:
  - het *termijnregime* is lid 6 of lid 7;
  - het is een *aanslag met een uit te betalen bedrag*;
  - het *termijnbedrag* is **ten hoogste** het *grensbedrag termijnuitbetaling*;
  - er is **geen** *derdenbeslag op de teruggaaf*.
- Gevolg dat de regel niet uitrekent: bij uitbetaling in één keer zijn er geen termijnen meer. Wat dan het *tijdstip van
  verrekening* is (R11), zegt de Leidraad niet. Een vraag voor de jurist.

### R11 — Bepalen tijdstip van verrekening (rekenregel met uitzondering; was AR7)

- Bron, art. 24 lid 1 slottekst, volzin 6: "In afwijking van artikel 4:93, derde lid, van de Algemene wet bestuursrecht
  geldt als tijdstip van verrekening de dagtekening van het aanslagbiljet waaruit van het te betalen bedrag blijkt."
- Volzin 7: "In afwijking van de vorige volzin geldt met betrekking tot een verrekening van een termijn van een voorlopige
  aanslag als bedoeld in artikel 9, zesde en zevende lid, als tijdstip van verrekening het tijdstip waarop de
  desbetreffende termijn vervalt."
- Afwijking: Awb 4:93 lid 3, "De verrekening werkt terug overeenkomstig artikel 129, eerste en tweede lid, van Boek 6 van
  het Burgerlijk Wetboek."
- Regel: Het *tijdstip van verrekening* moet bepaald worden als:
  - de *vervaldag van een termijn* (R7, R8) van de termijn die verrekend wordt, indien het *termijnregime* lid 6 of lid 7 is;
  - anders de *dagtekening van het aanslagbiljet* waaruit het te betalen bedrag blijkt.
- Relaties: volzin 6 `uitzondering_op` Awb 4:93 lid 3; volzin 7 `uitzondering_op` volzin 6. Op volzin 7: `uitvoer` naar
  "tijdstip van verrekening", `invoer` naar "het tijdstip waarop de desbetreffende termijn vervalt", `voorwaarde` naar "een
  termijn van een voorlopige aanslag als bedoeld in artikel 9, zesde en zevende lid".
- *Lezing*: "de dagtekening van het aanslagbiljet waaruit van het te betalen bedrag blijkt" is de dagtekening van de
  aanslag met het te betalen bedrag. Bij een verrekening tussen twee aanslagen kan dat een andere aanslag zijn dan die met
  de termijnen. Het begrip *dagtekening van het aanslagbiljet* is dus per aanslag, en de regel moet zeggen welke.

### R12 — Bepalen verrekening mogelijk vóór het verstrijken van de termijn (beslisregel; was AR8)

- Bron, art. 24 lid 2: "De verrekening is ook mogelijk ingeval de termijn, bedoeld in artikel 9, nog niet is verstreken,
  met dien verstande dat indien het betreft belastingaanslagen als bedoeld in artikel 9, vijfde en zevende lid, verrekening
  alleen mogelijk is met belastingaanslagen die op dezelfde belasting en hetzelfde tijdvak betrekking hebben."
- Regel: *Verrekening mogelijk vóór het verstrijken van de termijn* is waar voor een aanslag waarvan de termijn nog niet is
  verstreken, indien aan één van de volgende voorwaarden is voldaan:
  - het *termijnregime* is **niet** lid 5 en **niet** lid 7;
  - de andere aanslag heeft **dezelfde** *belasting waarin de aanslag is opgelegd* **en hetzelfde** *tijdvak waarop de
    aanslag betrekking heeft*.
- Art. 24 lid 8 is geen voorwaarde maar een verruiming: "In afwijking van artikel 4:93, vierde lid, van de Algemene wet
  bestuursrecht is verrekening ook mogelijk van een voorlopige aanslag tot een negatief bedrag als bedoeld in artikel 13,
  tweede lid, van de Algemene wet inzake rijksbelastingen." Relatie `uitzondering_op` naar Awb 4:93 lid 4.
- *Lezing*: een aanslag met termijnregime lid 6 is "een belastingaanslag als bedoeld in het vijfde lid" (lid 6, eerste
  volzin). Of lid 2 met "artikel 9, vijfde … lid" ook lid 6 bedoelt, beslist de tekst niet. In de regel hierboven valt lid 6
  erbuiten; dat is een keuze voor de jurist.
- Beleid (Leidraad 24.3): "Bij een voorlopige belastingaanslag in de inkomstenbelasting en de vennootschapsbelasting die is
  gedagtekend in het jaar waarover deze is vastgesteld, kan de ontvanger alleen verrekenen voor zover de betalingstermijnen
  zijn verstreken." De uitzondering daarop, de situaties van art. 10 lid 1 onderdeel b–d, valt buiten de afbakening van
  Termijnen. Als beleidsregel: R12 is **onwaar** voor een termijn die nog niet is vervallen, indien het termijnregime lid 5
  of lid 6 is en er geen situatie van art. 10 lid 1 b–d is. Dat begrip (*situatie van versnelde invordering*) blijft buiten
  Termijnen; de regel noemt het als grens.

### De afleidingshiërarchie

Van onder naar boven; elke pijl is "is invoer van".

- R0 → R5, R12 (alleen voor het winstaandeel).
- R1 → R2, R3.
- R2 → R5 (voorwaarde 3.4).
- R2, R3, R4, R5 → R6.
- R5, R6 → R7 → R8.
- R6 → R9 → R10.
- R5, R7, R8 → R11.
- R5 → R12.

R11 en R12 zijn de regels waarop de analysevraag van Termijnen rust. Ze hebben alle andere nodig, behalve R9 en R10.

## 4. De voorbeeldreeks

Met de regels hierboven. "Klopt" betekent: de uitkomst volgt uit de regels en strijdt niet met de gelezen tekst. Het is mijn
toets, geen oordeel van de jurist.

1. **Positieve voorlopige aanslag vennootschapsbelasting, € 1.000.000, dagtekening 15 februari 2025, jaar 2025.**
   R1 = 2; R2 = 10; R5 = lid 5; R6 = 10; R7: 15 maart tot en met 15 december; R8: de tiende termijn op 31 december; R9 =
   € 100.000; R11 = de dagtekening van het aanslagbiljet met het te betalen bedrag. Klopt.
2. **Negatieve voorlopige aanslag vennootschapsbelasting, € 300.000, dagtekening 20 juni 2025.**
   R1 = 6; R3 = 7; R5 = lid 6; R7: 30 juni, 31 juli, 31 augustus, 30 september, 31 oktober, 30 november en 31 december; R8
   verandert niets; R9 = € 42.857,142…; R10 = onwaar; R11 = elke vervaldag. Klopt, op de afronding na (ontbrekend beleid).
3. **Positief, dagtekening 10 november 2025.**
   R2 = 1; R5 = lid 1; R7 = 22 december 2025; R8 = 31 december 2025. Klopt met de lezing van R8 ("enige
   betalingstermijn").
4. **Positief, dagtekening 5 december 2025.**
   R2 = 0; R5 = lid 1; R7 = 16 januari 2026; R8 geldt niet (maandnummer 12). Klopt.
5. **Negatief, dagtekening 5 december 2025.**
   R3 = 1; R5 = lid 6; R7 = 31 december 2025; R11 = 31 december 2025. Klopt met de lezing van R5 (geen terugval).
6. **Positief, dagtekening 30 januari 2025.**
   R2 = 11; R5 = lid 5; R7 voor de eerste termijn: 30 februari bestaat niet. **De regels geven geen uitkomst.** Ontbrekend
   beleid: Leidraad 9.5 regelt alleen de laatste dag van de maand en "een andere dag"; voor deze dag in een kortere maand
   zegt hij niets.
7. **Voorlopige aanslag inkomstenbelasting, positief, dagtekening 15 december 2024, jaar 2025.**
   R5 = lid 7; R4 = 12; R7: 31 januari tot en met 31 december 2025; R11 = elke vervaldag (volzin 7 noemt lid 7); R12 =
   alleen met aanslagen inkomstenbelasting over 2025. Klopt.
8. **Dezelfde aanslag als 7, maar een voorlopige aanslag in een belasting die lid 5 niet noemt.**
   R5 = lid 7, want lid 7 noemt geen belasting. Klopt met de tekst; of dat de bedoeling is, is een vraag voor de jurist.
9. **Negatieve aanslag van € 300 in zeven termijnen, zonder beslag.**
   R9 = € 42,86; R10 = waar; R11 is dan niet bepaald (§3, R10). Met derdenbeslag: R10 = onwaar, en R11 = elke vervaldag.
10. **Verrekening van een negatieve voorlopige aanslag inkomstenbelasting 2025 met een positieve voorlopige aanslag
    vennootschapsbelasting 2025 (lid 5) waarvan de termijnen nog niet zijn verstreken.**
    R12 = onwaar: niet dezelfde belasting. Met een positieve voorlopige aanslag inkomstenbelasting 2025 laat de wet het wel
    toe, maar verrekent de ontvanger volgens Leidraad 24.3 alleen de termijnen die al verstreken zijn. Klopt.
11. **Bedrag van de aanslag onbekend.**
    R9 is onbekend, niet nul; R10 is dan niet te bepalen. Klopt.
12. **Voorlopige aanslag winstaandeel, positief, dagtekening 15 februari 2025, boekjaar gelijk aan het kalenderjaar**, het
    praktijkvoorbeeld van Termijnen.
    R0 = vennootschapsbelasting; R5 = lid 5; verder als voorbeeld 1. Met lezing B bij R0: R5 = lid 1, één
    betaling zes weken na 15 februari, op 29 maart 2025, en geen termijnen. Klopt alleen met lezing A of C; welke geldt, beslist
    de jurist.
13. **Hetzelfde, negatief, dagtekening 20 juni 2025, verrekend met een positieve voorlopige aanslag vennootschapsbelasting
    2025 waarvan de termijnen nog niet zijn verstreken.**
    R0 en R5 = lid 6, termijnen als voorbeeld 2; R11 = elke vervaldag. R12 = waar met lezing A (dezelfde belasting, hetzelfde
    tijdvak), onwaar met lezing C (winstaandeel is niet de vennootschapsbelasting). Leidraad 24.3 beperkt het
    hoe dan ook tot de verstreken termijnen. **Dit is de vraag van Termijnen, en het antwoord hangt aan R0.**
14. **Voorlopige aanslag winstaandeel met een afwijkend boekjaar van 1 juli 2024 tot en met 30 juni 2025, dagtekening
    15 augustus 2024, positief.**
    R1 = 2 (augustus is de tweede maand van het boekjaar, volgens de lezing bij R1); R2 = 10; R7: 15 september 2024 tot en met
    15 juni 2025; R8: de laatste termijn op 30 juni 2025 (laatste dag van de maand). Klopt met beide lezingen bij R1 en R8;
    zonder die lezing telt R1 augustus als maand 8 en geeft R2 4 termijnen die midden in het boekjaar eindigen.

## 5. Wat open blijft

**Vragen voor de jurist** (de *lezingen* hierboven):

0. Hoe werkt art. 72 Mbw door in art. 9 lid 5 en art. 24 lid 2: als vennootschapsbelasting, als eigen belasting, of niet
   (R0, voorbeelden 12–14)? Van alle vragen bepaalt deze het antwoord op de analysevraag. Als er een bron is die het beslist
   (memorie van toelichting, rechtspraak, beleid), zit die niet in de graaf van acceptatie.
1. Valt een negatieve aanslag die in de laatste maand is gedagtekend onder lid 6 met één termijn, of terug op lid 1 (R5)?
2. Geldt Leidraad 9.1 ook als lid 5 terugvalt op lid 1 (R8, voorbeeld 3)?
3. Bedoelt art. 24 lid 2 met "vijfde … lid" ook de aanslag van lid 6 (R12)?
4. Geldt lid 7 voor elke voorlopige aanslag (voorbeeld 8)?
5. Zijn *jaar waarover de aanslag is vastgesteld* en *tijdvak waarop de aanslag betrekking heeft* één begrip (§2)?
6. Wat is het tijdstip van verrekening van een teruggaaf die in één keer wordt uitbetaald (R10)?

**Ontbrekend beleid** (activiteit 5):

- het datumrekenen bij de 29e, 30e en 31e van een maand die langer is dan de volgende (voorbeeld 6);
- de afronding van het termijnbedrag en waar het restant landt (R9);
- het bedrag dat op elke vervaldag wordt verrekend (plan §4.1, slot).

**Wat nog gezocht moet worden**: een bron buiten de wet die vraag 0 beslist. De Kamerstukken-connector en de
rechtspraakconnector van Lex zijn de weg daarheen; dat is werk voor Lex, niet voor dit document.

## 6. Wat dit vraagt van Termijnen in Lex

Aanvullend op plan §4.4, die hiermee voor de bronnen achterhaald is:

- **Opnemen bij de nieuwe deelvraag** (hoe de termijnen ontstaan): art. 9 lid 1 en lid 7, Leidraad 9.1, 9.3 en 9.5. Bij DV2:
  art. 24 lid 8. Bij beide: art. 72 Mbw, met rol *analyseren*, want R0 rust erop. Als context: Awb 4:93 lid 3 en lid 4,
  Leidraad 24.3, art. 69 en 70 Mbw.
- **Begrippen**: de lijst in §2. Nieuw ten opzichte van §4.4 zijn *termijnregime*, *belasting waarin de aanslag is
  opgelegd*, *wettelijke betalingstermijn*, *tijdvak waarop de aanslag betrekking heeft*, *voorlopige aanslag winstaandeel*
  en, om het homoniem te scheiden, *verrekenbaar bedrag (Mijnbouwwet)*.
- **Relaties** (ADR-011): de `uitzondering_op` per regel, in R5, R8, R11 en R12. Twee wijzen naar Awb 4:93: lid 3 vanuit
  art. 24 lid 1 volzin 6, lid 4 vanuit art. 24 lid 8.
- **Voor het platform**: R5 en R8 laten zien dat een regel kan steunen op meer bepalingen en op beleid. Het regelskelet van
  één markering (ADR-011) draagt dat niet. Een regel die over bepalingen heen gaat, hoort bij het werkgebied, niet bij één
  laag. Zie het gat D1 in plan §5.1.
