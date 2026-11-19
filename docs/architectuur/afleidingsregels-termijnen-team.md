# De afleidingsregels van Termijnen, opgesteld door het team (activiteit 3b)

19 nov 2026. Werkgebied Termijnen op acceptatie. Deelactiviteit 3b van de methode Wetsanalyse: afleidingsregels maken,
met begrippen als invoer en uitvoer. Wat daarbuiten valt, is niet gedaan: geen voorbeeldreeksen en geen validatie
(activiteit 4), geen uitwerking van uitvoeringsbeleid (activiteit 5, hier alleen gesignaleerd), geen RegelSpraak
(activiteit 6) en niets uit de methode wetsuitvoering.

Lex kent nog geen regel als eigen object (plan-afleidingsregels §5.1, D1). Het team deed **alsof dat wel kan**: elke regel
is opgeleverd als het object dat Lex zou opslaan, met status, en beoordeeld zoals een begrip in de werkplek. Het logboek
van de run (`afleidingsregels-termijnen-2026-11-19`, lokaal, niet in de repo) was de opslag. Alles wat de werkplek al wél
kan (markeringen, relaties, begrippen), is echt in Lex gedaan.

De eerdere reconstructie op papier ([proef-afleidingsregels-termijnen.md](proef-afleidingsregels-termijnen.md)) diende als
voorbeeld van de vorm. Het team nam er geen regel uit over zonder hem zelf tegen de bron te toetsen (§6).

## 1. Het team

- **De agent-regelspecialist** stelde de regels op: de inventaris, per regel het regelskelet uit de markeringen en
  relaties, de volledigheidstoets en de regel als regelobject. De definitie van deze rol stond nog in een open PR en is
  daarom als algemene agent met die definitie gestart.
- **De agent-jurist** was eigenaar van de betekenis. Hij herstelde de gaten in het skelet in Lex, nam de
  interpretatiekeuzes en accordeerde of wees elke regel af.
- **De agent-gegevensspecialist** was eigenaar van de begrippen. Hij toetste elke regel op eenduidigheid en voerde de
  begripswijzigingen door die de jurist goedkeurde.

Het werk liep regel voor regel, van onder naar boven in de afleidingshiërarchie. De regels kwamen in twee ronden: eerst
R1–R8 als concept, daarna een slotronde waarin de jurist de ontbrekende markeringen legde en de regelspecialist R5 en R6
opnieuw indiende.

## 2. De regels

Het formaat volgt D1 uit het plan. De regeltekst is afgeleid uit de delen, in de taalpatronen van de methode. Begrippen
staan met hun term en de eerste tekens van hun id; elementen (markeringen) staan met de eerste twaalf tekens van hun id.
Een regel met meer gevallen is een **beslistabel**: één uitvoer en één regelbegrip, met rijen die elkaar uitsluiten. Daarmee
heeft het gegeven één bron, en kan de volgende regel er eenduidig op voortbouwen.

### R1 — Bepalen aantal termijnen

- **status:** geaccordeerd (jurist, gegevensspecialist)
- **soort:** rekenregel, als beslistabel met drie rijen
- **regelbegrip:** *bepalen van het aantal termijnen* (f87474ca, revisie 8, nu met lid 7)
- **uitvoer:** *aantal termijnen* (de1bae54)
- **invoer:** 1. *jaar* (0337495b); 2. *dagtekening van het aanslagbiljet* (11c714db). Het *bedrag van de
  belastingaanslag* (c25b97af) bepaalt welke rij geldt.
- **bewerking:** het tellen van de maanden van het jaar. Er is geen operatorbegrip voor (open punt).
- **dragend:** de afleidingsregels in art. 9 IW 1990 lid 5 (1cb47880a331), lid 6 (e65b6e0f8d78) en lid 7 (747ecbc0a10e, nieuw).
- **regeltekst:**

  | geval | voorwaarden (alle) | aantal termijnen |
  |---|---|---|
  | lid 5 | de aanslag is een voorlopige aanslag in de inkomstenbelasting of de vennootschapsbelasting, een voorlopige conserverende aanslag, of via art. 72 Mbw een voorlopige aanslag winstaandeel (lezing C); de dagtekening ligt in het jaar; het bedrag van de belastingaanslag is niet negatief | het aantal maanden van het jaar dat overblijft **na** de maand van de dagtekening |
  | lid 6 | een aanslag als bedoeld in lid 5 die een uit te betalen bedrag behelst (voorwaarde 02c651028863, nieuw); de dagtekening ligt in het jaar | het aantal maanden van het jaar dat overblijft, **met inbegrip van** de maand van de dagtekening |
  | lid 7 | de dagtekening ligt vóór het jaar (elke voorlopige aanslag) | het aantal maanden van het jaar |

- **volgt op:** geen (onderste regel)
- **open:** het operatorbegrip voor de telling; lezing C is niet getoetst aan de memorie van toelichting of aan rechtspraak.

### R2 — Bepalen vervaldag bij betaling ineens

- **status:** geaccordeerd
- **soort:** rekenregel (uitvoer een datum)
- **regelbegrip:** *bepalen van de vervaldag bij betaling ineens* (6bce8f07, opvolger van 3b10bef1)
- **uitvoer:** *vervaldag* (08ffc11c, opvolger van d9d0e191: nu de vervaldag van een aanslag **of** een termijn)
- **invoer:** 1. *dagtekening van het aanslagbiljet* (11c714db); 2. *wettelijke betalingstermijn* (855cd256, revisie 5)
- **bewerking:** tijdsduur na tijdstip. Er is geen operatorbegrip voor (open punt).
- **voorwaarden:** de aanslag valt niet onder R1, of R1 levert niet meer dan één termijn op (lid 5 volzin 3, met een
  `toepassing`-relatie naar lid 1).
- **parameter:** *wettelijke betalingstermijn* = zes weken, vastgesteld in de toestanden van 1 jan 2025 en 1 okt 2026 van
  art. 9 lid 1 IW 1990. De toestanden daartussen zijn niet gelezen.
- **dragend:** de afleidingsregel in art. 9 lid 1 (8263fa226caa, nieuw) en lid 5 volzin 3 (1d46b64dc6aa).
- **regeltekst:** De vervaldag moet berekend worden als het tijdstip dat de wettelijke betalingstermijn **na** de
  dagtekening van het aanslagbiljet ligt, indien de aanslag niet in termijnen invorderbaar is of de termijnregeling niet tot meer dan één termijn
  leidt.
- **volgt op:** R1
- **keuze jurist:** een aanslag van lid 6 met één termijn valt níét terug op lid 1.

### R3 — Bepalen vervaldag een maand na de dagtekening (beleidsregel)

- **status:** geaccordeerd als beleidsregel
- **soort:** rekenregel (uitvoer een datum)
- **regelbegrip:** *bepalen van de vervaldag een maand na de dagtekening* (a9afb082)
- **uitvoer:** *vervaldag* (08ffc11c)
- **invoer:** 1. *dagtekening van het aanslagbiljet* (11c714db); 2. *betalingstermijn* (e48826ff, nieuw), met de waarde
  één maand
- **voorwaarde:** de dagtekening valt niet op de laatste dag van de kalendermaand.
- **dragend:** de afleidingsregel in Leidraad Invordering 2008, 9.5 (398711121c90).
- **regeltekst:** De vervaldag van de eerste termijn moet berekend worden als het tijdstip dat de betalingstermijn (een
  maand) **na** de dagtekening van het aanslagbiljet ligt, indien de dagtekening niet op de laatste dag van de kalendermaand valt.
- **volgt op:** geen; levert de eerste vervaldag voor de rij lid 5 van R4.
- **open:** de laatste dag van de maand staat alleen in de rekenvoorbeelden van de Leidraad; voor een dagtekening op de
  29e tot en met de 31e geeft de bron geen uitkomst; het citaat is niet getoetst aan de officiële tekst, omdat de
  bronlezer geen Leidraad-onderdelen leest.

### R4 — Bepalen vervaldagen van de termijnen

- **status:** geaccordeerd
- **soort:** rekenregel (uitvoer een reeks datums), als beslistabel met drie rijen
- **regelbegrip:** *bepalen van de vervaldagen van de termijnen* (225d18a3)
- **uitvoer:** *vervaldag* (08ffc11c), als kenmerk van de *termijn* (e6aed82a, revisie 21)
- **invoer:** *dagtekening van het aanslagbiljet* of *jaar*, het interval, en *aantal termijnen* (uit R1)
- **dragend:** de afleidingsregels in art. 9 lid 5 (e9f2f0428ec5), lid 6 (c8429eaa55cb) en lid 7 (8cfe37e92e8d), met de
  invoer- en intervalrelaties die de jurist legde.
- **regeltekst:**

  | geval | eerste vervaldag | volgende vervaldagen |
  |---|---|---|
  | lid 5 | volgens R3 (een maand na de dagtekening) | telkens een maand later |
  | lid 6 | de laatste dag van de maand van de dagtekening | telkens een maand later |
  | lid 7 | de laatste dag van de eerste maand van het jaar | telkens een maand later |

  De reeks loopt door totdat er evenveel vervaldagen zijn als het aantal termijnen (R1). Een termijn heeft in de wet geen
  volgnummer; de regel gebruikt er ook geen.
- **volgt op:** R1, R3
- **keuze jurist:** "eind van de maand" is de *laatste dag van de kalendermaand* (f0a7053f); "telkens een maand later"
  vanaf een laatste dag valt weer op de laatste dag van de volgende maand. Beleid moet dat bevestigen (§4).

### R5 — Bepalen termijnbedrag

- **status:** geaccordeerd (na herindiening)
- **soort:** rekenregel, als beslistabel met drie rijen
- **regelbegrip:** *bepalen van het termijnbedrag* (27426263, nieuw)
- **uitvoer:** *termijnbedrag* (cbc694db, revisie 6: **zonder teken**)
- **invoer:** 1. het *bedrag van de belastingaanslag* (c25b97af), zonder teken; 2. *aantal termijnen* (de1bae54, uit R1)
- **bewerking:** gedeeld door. Er is geen operatorbegrip voor (open punt).
- **dragend:** de nieuwe afleidingsregels op "gelijke termijnen" in art. 9 lid 5 (52525d2b22c8), lid 6 (264c4001bc2d) en
  lid 7 (d963056fc488). De uitvoer rust op het termijnbedrag in Leidraad 9.3 (70ca61bc3d45): de wet noemt het bedrag per
  termijn zelf niet.
- **regeltekst:** Het termijnbedrag moet berekend worden als het bedrag van de belastingaanslag zonder teken **gedeeld
  door** het aantal termijnen. Bij lid 5 is het bedrag een positief bedrag (art. 13 lid 1 AWR, dc43143ba8c4), bij lid 6
  een uit te betalen bedrag (6eec78b767f3). Of het om betalen of uitbetalen gaat, volgt uit de rij van R1.
- **volgt op:** R1
- **waarom zonder teken:** met teken wordt het termijnbedrag van een teruggaaf negatief. R6 vergelijkt het met "ten hoogste
  € 49", en een negatief bedrag voldoet daar altijd aan, zodat elke teruggaaf in één keer zou worden uitbetaald. De
  gegevensspecialist vond dit; de jurist ging akkoord.
- **open:** rij lid 7 heeft voor het bedrag geen markering, omdat de tekst er geen formulering voor heeft; afronding en
  restant (§4).

### R6 — Bepalen wijze van uitbetaling (beleidsregel)

- **status:** geaccordeerd als beleidsregel (na herindiening)
- **soort:** beslisregel
- **regelbegrip:** *bepalen van de wijze van uitbetaling* (d23d063b, nieuw)
- **uitvoer:** *wijze van uitbetaling* (ef13d661), met twee waarden: in maandelijkse termijnen (f6df5e32bb29) en in één
  keer (3f1c4b922310). Volgens Leidraad 9.3 is die lijst volledig.
- **invoer:** *termijnbedrag* (uit R5)
- **operator:** *ten hoogste* (ca0b687b)
- **voorwaarden:** het termijnbedrag is niet groter dan € 49 per maand (d7d4d9913a3d); uitzondering: er ligt derdenbeslag
  (*derdenbeslag* 420c5e40, element 9735579d6282).
- **parameter:** *drempel voor uitbetaling in één keer* (82165e28) = € 49 per maand. Het tijdvak waarin die waarde geldt,
  is niet vastgesteld.
- **dragend:** de nieuwe afleidingsregel in Leidraad 9.3 (0fb9888eeb85).
- **regeltekst:** De wijze van uitbetaling is *in één keer* indien aan alle volgende voorwaarden is voldaan: het gaat om
  een voorlopige teruggaaf; het termijnbedrag is ten hoogste de drempel voor uitbetaling in één keer; er ligt geen
  derdenbeslag. Anders is de wijze van uitbetaling *in maandelijkse termijnen*.
- **volgt op:** R5
- **open:** het tijdvak van de drempel; het citaat niet getoetst aan de officiële tekst (zie R3).

### R7 — Bepalen tijdstip van verrekening

- **status:** geaccordeerd
- **soort:** rekenregel (uitvoer een datum), als beslistabel met twee rijen
- **regelbegrip:** *bepalen van het tijdstip van verrekening* (ef9a1c46, één opvolger voor 18875a3a en 8d54e463)
- **uitvoer:** *tijdstip van verrekening* (6334736f)
- **dragend:** de afleidingsregels in de slottekst van art. 24 lid 1 IW 1990, volzin 6 (43f4f3f1798d) en volzin 7
  (c5d1c19d1503), met de bestaande `uitzondering_op` van volzin 7 op volzin 6.
- **regeltekst:**

  | geval | tijdstip van verrekening |
  |---|---|
  | rij 2 (gaat voor): een termijn van een voorlopige aanslag als bedoeld in art. 9 lid 6 of 7, ook een positieve aanslag van lid 7 | de vervaldag van die termijn (uit R4) |
  | rij 1 (anders) | de dagtekening van het aanslagbiljet van de aanslag waaruit het te betalen bedrag blijkt (e41c96f34c84, nu een Variabele) |

- **volgt op:** R1, R4
- **open:** de voorwaarde voor lid 6 en lid 7 is niet als eigen markering gelegd; een `uitzondering_op` naar Awb 4:93 lid 3
  kan niet, omdat dat lid als context in de selectie staat en geen elementen heeft; het tijdstip bij uitbetaling in één
  keer (§4).

### R8 — Verrekening vóór het verstrijken van de termijn (art. 24 lid 2): geen afleidingsregel

Afgewezen als afleidingsregel. Art. 24 lid 2 IW 1990 geeft een bevoegdheid onder voorwaarden: er wordt geen waarde
afgeleid. De bepaling staat in de inventaris als rechtsbetrekking (0f01cda739e9) met haar voorwaarden en met het begrip
*bevoegdheid tot verrekening vóór het verstrijken van de betalingstermijn* (fb9f3866). Dat is samenhang uit activiteit 2.
De keuzes die erbij horen, nam de jurist wel: "dezelfde belasting" is winstaandeel met winstaandeel (lezing C); een
aanslag van lid 6 valt onder "het vijfde lid"; het tijdvak is het jaar waarover de aanslag is vastgesteld.

## 3. De afleidingshiërarchie

Afgeleid, niet opgeslagen (D2): een regel volgt op een andere als haar invoer de uitvoer van die ander is.

```
R1 aantal termijnen ──┬─> R2 vervaldag bij betaling ineens   (sluit R4 uit)
                      ├─> R4 vervaldagen van de termijnen ──> R7 tijdstip van verrekening
R3 vervaldag 9.5 ─────┘        ^ (rij lid 5)                     ^
R1 ───────────────────> R5 termijnbedrag ──> R6 wijze van uitbetaling   (§4: tijdstip bij één keer)
```

R7 draagt het eerste deel van de analysevraag van Termijnen (wanneer mag worden verrekend), R5 en R6 het tweede (de
doorwerking in de termijnbedragen). Twee regels met dezelfde uitvoer zonder elkaar uitsluitende voorwaarden zijn er
niet: R2 en R4 leveren beide een *vervaldag*, maar sluiten elkaar uit via R1.

## 4. Open punten

**Interpretatiekeuzes**, genomen door de jurist:
1. Art. 72 Mbw: lezing C. "Met overeenkomstige toepassing van … de Invorderingswet 1990" leest het winstaandeel als de
   belasting waarop de aanslag rust. Lezing A (het winstaandeel geldt als vennootschapsbelasting) en B (lid 5 en 6 gelden
   niet) zijn verworpen. **Niet getoetst aan de memorie van toelichting of aan rechtspraak.**
2. Een aanslag van lid 6 valt onder art. 24 lid 2.
3. Het tijdvak is het jaar waarover de aanslag is vastgesteld; *jaar* is een soort van *tijdvak*.
4. R7 rij 2 geldt ook voor een positieve aanslag van lid 7.
5. "Te betalen bedrag" in art. 24 lid 1 wijst de aanslag met het te innen bedrag aan.
6. Lid 6 met één termijn valt niet terug op lid 1.
7. "Eind van de maand" is de laatste kalenderdag, ook bij "telkens een maand later".

**Ontbrekende begrippen:** de operatoren *tellen van maanden* (R1), *tijdsduur na tijdstip* (R2, R3, R4) en *gedeeld
door* (R5). Er is geen gemarkeerde formulering die ze aanduidt, dus ze worden geen begrip; de regeltekst noemt de
bewerking. Dit hoort bij gat A2 uit het plan: een vaste set generieke operatorbegrippen.

**Gaten in het skelet die bleven:** rij lid 7 van R5 heeft geen invoer voor het bedrag; de voorwaarde van R7 rij 2 is
niet gemarkeerd; een `uitzondering_op` naar een contextbron kan niet.

**Te signaleren uitvoeringsbeleid** (activiteit 5, niet uitgewerkt):
- Leidraad 9.1 staat als context en is niet geannoteerd. Ze legt de enige of laatste termijn op 31 december; in het
  praktijkvoorbeeld schuift de laatste termijn dan van 15 naar 31 december.
- Het tijdstip van verrekening bij uitbetaling in één keer (R6 → R7).
- De afronding van het termijnbedrag en waar het restant landt (R5).
- Vervaldagen bij een dagtekening op de 29e tot en met de 31e, en de laatste dag bij "telkens een maand later" (R3, R4).
- Het tijdvak waarin de drempel van € 49 geldt (R6).
- Leidraad 24.3 (verrekening), niet gelezen.

## 5. Wat er in Lex is gewijzigd

Door de jurist (lagen heropend en weer geaccordeerd: art. 9 lid 1, 5, 6 en 7, Leidraad 9.3 en art. 24 lid 1 slottekst):
- **Vijf nieuwe afleidingsregels**:
  - art. 9 lid 1;
  - lid 7 volzin 1 (aantal termijnen);
  - "gelijke termijnen" in lid 5, 6 en 7 (één markering per lid);
  - Leidraad 9.3.
- **Een nieuwe voorwaarde** in lid 6 ("die een uit te betalen bedrag behelst").
- **Nieuwe relaties**:
  - uitvoer, en invoer met volgorde;
  - de voorwaarde aan de afleidingsregel in plaats van alleen aan de rechtsbetrekking;
  - `uitzondering_op`: lid 5, 6 en 7 → lid 1, en lid 6 → lid 5;
  - `toepassing`: lid 5 volzin 3 → lid 1;
  - `kenmerk`: dagtekening → aanslagbiljet;
  - het interval "telkens een maand later";
  - de operanden van "meer dan" en "niet".
- **Een klassewissel**: de dagtekening in art. 24 lid 1 is van Rechtsfeit naar Variabele gegaan.
- **Afgewezen relaties**, met reden; ze blijven als historie staan:
  - een rechtsobject als invoer ("het aanslagbiljet", "de voorlopige aanslag");
  - "nog maanden" en "na de maand" als invoer.

Door de gegevensspecialist (alles op minstens één aanduidende passage en geaccordeerd):
- **Opvolgers**:
  - *vervaldag* (08ffc11c), voor een aanslag of een termijn;
  - *bepalen van de vervaldag bij betaling ineens* (6bce8f07);
  - *bepalen van het tijdstip van verrekening* (ef9a1c46), een samenvoeging van twee begrippen.
- **Nieuwe begrippen**:
  - *betalingstermijn* (e48826ff), op de Variabele in Leidraad 9.5;
  - *bepalen van het termijnbedrag* (27426263);
  - *bepalen van de wijze van uitbetaling* (d23d063b).
- **Revisies**:
  - *wettelijke betalingstermijn*: de zes weken staan nu in de toelichting, de waarde per tijdvak in de regel;
  - *termijn*: de alternatieve term "betalingstermijn" is weg, zodat het woord niet twee begrippen aanduidt;
  - *termijnbedrag*: zonder teken;
  - *bepalen van het aantal termijnen*: met lid 7.
- **Relaties**:
  - *jaar* is een soort van *tijdvak*;
  - *wettelijke betalingstermijn* is een soort van *betalingstermijn*.

Er is niets verwijderd.

## 6. Waar het team afweek van de proef op papier

- **Geen beslisregel *termijnregime*, en geen tussenbegrip *maandnummer van de dagtekening*** (proef R1 en R5). Een
  tussenresultaat zonder eigen formulering wordt geen begrip (besluit 7 in de proef; nu ook een harde regel in de api).
  De voorwaarden die het termijnregime droeg, staan nu als rijen in R1, R4 en R7.
- **Eén beslistabel per uitvoer in plaats van een regel per lid** (proef R2, R3 en R4). Drie regelbegrippen voor dezelfde
  uitvoer geven drie identiteiten voor één gegeven, en dan heeft de vervolgregel geen eenduidige bron.
- **Geen specialisatie R0 voor art. 72 Mbw.** Art. 72 is niet als afleidingsregel gemarkeerd; de doorwerking is een
  interpretatiekeuze (lezing C), verwerkt in de voorwaarden van R1.
- **Art. 24 lid 2 is geen afleidingsregel** (proef R12), maar een rechtsbetrekking met voorwaarden.
- **Geen regel voor Leidraad 9.1** (proef R8): die is niet geannoteerd, dus kan ze geen regel dragen. Alleen gesignaleerd.
- **Het termijnbedrag zonder teken**: nieuw, en nodig voor R6.
- **Geen voorbeeldreeksen**: dat is activiteit 4.

## 7. Wat dit van Lex vraagt

Bovenop de gaten uit het plan (§5), en ze bevestigend:

- **D1, de regel als eigen object, is de grootste ontbrekende stap.** Alle regels, beslistabellen en parameterwaarden per
  tijdvak staan nu in een logboek buiten de werkplek. Een beslistabel (één uitvoer, rijen die elkaar uitsluiten) moet een
  vorm van D1 zijn, niet alleen een losse regel.
- **Een compacte skeletweergave per afleidingsregel** (U1, A1): uitvoer, invoer op volgorde, operator met operanden,
  voorwaarden en uitzonderingen. Nu geeft het lezen van één lid ongeveer 62.000 tekens, het lezen van een bron in een
  werkgebied herhaalt het hele dossier, en de lijst van begrippen zonder id is ruim 300.000 tekens.
- **De keten legt een rechtsobject als invoer** ("het aanslagbiljet") en geeft de invoer geen volgorde (A1).
- **Een afgewezen relatie houdt haar volgordeplek bezet** (409 `volgorde_bezet`), zodat een hersteld skelet relaties zonder
  nummer krijgt. Een afgewezen of vervangen relatie hoort haar plek vrij te geven.
- **Een `uitzondering_op` naar een contextbron kan niet**, omdat zo'n bron geen elementen heeft.
- **Een regel die op een heropende laag rust**: de werkplek laat bij een regel niet zien dat de laag eronder weer open is.
- **Begrippen**: een opvolger neemt de koppelingen over als open, zodat ze eerst apart beoordeeld moeten worden; twee
  begrippen samenvoegen tot één nieuw begrip vraagt twee stappen; samenvoegen zet de oude naam als alternatieve term, ook
  waar dat geen synoniem is.
- **De bronlezer leest geen Leidraad-onderdelen**, dus R3 en R6 zijn alleen tegen de graaf getoetst.
- **Het logboek van de acceptatie-MCP kent de rol regelspecialist nog niet** (volgt met de PR van die agent).
