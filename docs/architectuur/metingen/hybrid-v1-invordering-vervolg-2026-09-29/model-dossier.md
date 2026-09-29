# Beoordelingsdossier van alle modeluitvoer

Elke rij is één bronspan + klasse, ook als die slechts eenmaal voorkomt. Per variant staat het aantal geaccepteerde voorstellen (a) en menselijke twijfelgevallen (m), op drie pogingen. B−A en C−B zijn waarnemingen op de unie van drie runs; geen causale of juridische score. Een andere grens/klasse staat als aparte rij. De broncodepoint-offsets zijn halfopen [start,eind).

## IW-9-1

Bron(nen):

`urn:bwb:BWBR0004770:artikel:9:lid:1` · SHA256 `fd044d7e35ad3a1eb2440ee5d485759c70efa621732d21a94714e2b656c0034d`

> Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.

Runbestanden met volledige prompts, reacties, bijdragen en besluiten:

[A_huidig ronde 1](modelruns/1-IW-9-1-A_huidig.json), [B_verbeterd ronde 1](modelruns/1-IW-9-1-B_verbeterd.json), [C_context ronde 1](modelruns/1-IW-9-1-C_context.json), [A_huidig ronde 2](modelruns/2-IW-9-1-A_huidig.json), [B_verbeterd ronde 2](modelruns/2-IW-9-1-B_verbeterd.json), [C_context ronde 2](modelruns/2-IW-9-1-C_context.json), [A_huidig ronde 3](modelruns/3-IW-9-1-A_huidig.json), [B_verbeterd ronde 3](modelruns/3-IW-9-1-B_verbeterd.json), [C_context ronde 3](modelruns/3-IW-9-1-C_context.json)

| Offset | Fragment | Klasse | A (a/m) | B (a/m) | C (a/m) | Verschil in aanwezigheid |
|---|---|---|---:|---:|---:|---|
| [0,20) | Een belastingaanslag | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [0,87) | Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet. | Rechtsfeit | 1/0 | 3/0 | 3/0 | B−A wisselend/status |
| [37,86) | zes weken na de dagtekening van het aanslagbiljet | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [69,86) | het aanslagbiljet | Rechtsobject | 1/0 | 0/0 | 0/0 | B−A verdwenen |

Gerichte herbeoordelingen en technische uitval:

Geen gerichte herbeoordeling in deze pogingen.

## IW-9-5

Bron(nen):

`urn:bwb:BWBR0004770:artikel:9:lid:5` · SHA256 `11aab4fb73f10380f88b3db884976396773f0fd9b40bcda37fe8140dadf2943d`

> In afwijking van het eerste lid is een voorlopige aanslag in de inkomstenbelasting of in de vennootschapsbelasting en een voorlopige conserverende aanslag in de inkomstenbelasting, waarvan het aanslagbiljet een dagtekening heeft die ligt in het jaar waarover deze is vastgesteld, invorderbaar in zoveel gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is vermeld, nog maanden van het jaar overblijven. De eerste termijn vervalt één maand na de dagtekening van het aanslagbiljet en elk van de volgende termijnen telkens een maand later. Indien de toepassing van de eerste volzin niet leidt tot meer dan één termijn, vindt het eerste lid toepassing.

Runbestanden met volledige prompts, reacties, bijdragen en besluiten:

[A_huidig ronde 1](modelruns/1-IW-9-5-A_huidig.json), [B_verbeterd ronde 1](modelruns/1-IW-9-5-B_verbeterd.json), [C_context ronde 1](modelruns/1-IW-9-5-C_context.json), [A_huidig ronde 2](modelruns/2-IW-9-5-A_huidig.json), [B_verbeterd ronde 2](modelruns/2-IW-9-5-B_verbeterd.json), [C_context ronde 2](modelruns/2-IW-9-5-C_context.json), [A_huidig ronde 3](modelruns/3-IW-9-5-A_huidig.json), [B_verbeterd ronde 3](modelruns/3-IW-9-5-B_verbeterd.json), [C_context ronde 3](modelruns/3-IW-9-5-C_context.json)

| Offset | Fragment | Klasse | A (a/m) | B (a/m) | C (a/m) | Verschil in aanwezigheid |
|---|---|---|---:|---:|---:|---|
| [0,434) | In afwijking van het eerste lid is een voorlopige aanslag in de inkomstenbelasting of in de vennootschapsbelasting en een voorlopige conserverende aanslag in de inkomstenbelasting, waarvan het aanslagbiljet een dagtekening heeft die ligt in het jaar waarover deze is vastgesteld, invorderbaar in zoveel gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is vermeld, nog maanden van het jaar overblijven. | Afleidingsregel | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [0,434) | In afwijking van het eerste lid is een voorlopige aanslag in de inkomstenbelasting of in de vennootschapsbelasting en een voorlopige conserverende aanslag in de inkomstenbelasting, waarvan het aanslagbiljet een dagtekening heeft die ligt in het jaar waarover deze is vastgesteld, invorderbaar in zoveel gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is vermeld, nog maanden van het jaar overblijven. | Rechtsbetrekking | 3/0 | 0/0 | 0/0 | B−A verdwenen |
| [3,31) | afwijking van het eerste lid | Rechtsfeit | 0/0 | 0/0 | 0/2 | C−B toegevoegd |
| [3,31) | afwijking van het eerste lid | Voorwaarde | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [35,57) | een voorlopige aanslag | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [61,82) | de inkomstenbelasting | Rechtsobject | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [61,82) | de inkomstenbelasting | Variabele en variabelewaarde | 0/0 | 3/0 | 2/0 | B−A toegevoegd; C−B wisselend/status |
| [89,114) | de vennootschapsbelasting | Rechtsobject | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [89,114) | de vennootschapsbelasting | Variabele en variabelewaarde | 0/0 | 3/0 | 2/0 | B−A toegevoegd; C−B wisselend/status |
| [118,154) | een voorlopige conserverende aanslag | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [158,179) | de inkomstenbelasting | Rechtsobject | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [158,179) | de inkomstenbelasting | Variabele en variabelewaarde | 0/0 | 3/0 | 2/0 | B−A toegevoegd; C−B wisselend/status |
| [189,206) | het aanslagbiljet | Rechtsobject | 3/0 | 0/0 | 1/0 | B−A verdwenen; C−B toegevoegd |
| [207,222) | een dagtekening | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [238,249) | in het jaar | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [241,278) | het jaar waarover deze is vastgesteld | Voorwaarde | 3/0 | 3/0 | 3/0 | behouden |
| [280,292) | invorderbaar | Variabele en variabelewaarde | 3/0 | 1/0 | 0/0 | B−A wisselend/status; C−B verdwenen |
| [296,320) | zoveel gelijke termijnen | Rechtsobject | 0/0 | 1/0 | 2/0 | B−A toegevoegd; C−B wisselend/status |
| [296,320) | zoveel gelijke termijnen | Variabele en variabelewaarde | 3/0 | 2/0 | 1/0 | B−A wisselend/status; C−B wisselend/status |
| [328,339) | na de maand | Tijdsaanduiding | 3/0 | 2/0 | 2/0 | B−A wisselend/status |
| [348,362) | de dagtekening | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [348,384) | de dagtekening van het aanslagbiljet | Rechtsfeit | 1/0 | 0/0 | 0/2 | B−A verdwenen; C−B toegevoegd |
| [348,384) | de dagtekening van het aanslagbiljet | Rechtsobject | 2/0 | 0/0 | 0/0 | B−A verdwenen |
| [348,384) | de dagtekening van het aanslagbiljet | Voorwaarde | 0/0 | 3/0 | 1/0 | B−A toegevoegd; C−B wisselend/status |
| [367,384) | het aanslagbiljet | Rechtsobject | 3/0 | 0/0 | 1/0 | B−A verdwenen; C−B toegevoegd |
| [397,408) | nog maanden | Variabele en variabelewaarde | 3/0 | 3/0 | 0/0 | C−B verdwenen |
| [413,421) | het jaar | Tijdsaanduiding | 3/0 | 3/0 | 2/0 | C−B wisselend/status |
| [435,452) | De eerste termijn | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [461,470) | één maand | Rechtsobject | 0/1 | 0/0 | 0/0 | B−A verdwenen |
| [461,510) | één maand na de dagtekening van het aanslagbiljet | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [474,488) | de dagtekening | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [474,510) | de dagtekening van het aanslagbiljet | Rechtsfeit | 0/0 | 0/0 | 0/2 | C−B toegevoegd |
| [474,510) | de dagtekening van het aanslagbiljet | Rechtsobject | 0/0 | 3/0 | 1/0 | B−A toegevoegd; C−B wisselend/status |
| [474,567) | de dagtekening van het aanslagbiljet en elk van de volgende termijnen telkens een maand later | Rechtsfeit | 2/0 | 0/0 | 0/0 | B−A verdwenen |
| [493,510) | het aanslagbiljet | Rechtsobject | 3/0 | 0/0 | 1/0 | B−A verdwenen; C−B toegevoegd |
| [522,543) | de volgende termijnen | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [544,561) | telkens een maand | Variabele en variabelewaarde | 2/0 | 3/0 | 3/0 | B−A wisselend/status |
| [544,567) | telkens een maand later | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [552,561) | een maand | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [569,646) | Indien de toepassing van de eerste volzin niet leidt tot meer dan één termijn | Voorwaarde | 3/0 | 3/0 | 3/0 | behouden |
| [569,680) | Indien de toepassing van de eerste volzin niet leidt tot meer dan één termijn, vindt het eerste lid toepassing. | Afleidingsregel | 0/0 | 0/0 | 1/0 | C−B toegevoegd |
| [576,610) | de toepassing van de eerste volzin | Rechtsfeit | 2/0 | 0/0 | 0/2 | B−A verdwenen; C−B toegevoegd |
| [576,610) | de toepassing van de eerste volzin | Voorwaarde | 0/0 | 3/0 | 1/0 | B−A toegevoegd; C−B wisselend/status |
| [611,615) | niet | Operator | 3/0 | 3/0 | 3/0 | behouden |
| [626,634) | meer dan | Operator | 3/0 | 3/0 | 3/0 | behouden |
| [626,646) | meer dan één termijn | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |

Gerichte herbeoordelingen en technische uitval:

- A_huidig ronde 1, C025: R-ONGELDIG. 
- C_context ronde 2, C002: R-ONGELDIG. 
- C_context ronde 2, C018: R-ONGELDIG. 
- C_context ronde 2, C026: R-ONGELDIG. 
- C_context ronde 2, C035: R-ONGELDIG. 
- C_context ronde 3, C002: R-ONGELDIG. 
- C_context ronde 3, C018: R-ONGELDIG. 
- C_context ronde 3, C026: R-ONGELDIG. 
- C_context ronde 3, C035: R-ONGELDIG. 

## LI-9.1

Bron(nen):

`urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.1` · SHA256 `a6d1a0d2199a83bbe664b33c0d56efcc5160490d8284efca2b01a963ac71ff7b`

> In de gevallen waarin voor voorlopige aanslagen (bedoeld in artikel 9, vijfde lid, van de wet) die zijn gedagtekend in november of eerder, toepassing van de wet er toe zou leiden dat de enige of laatste betalingstermijn eindigt voor 31 december, dan wordt de vervaldag van deze termijn op 31 december gesteld. Bij afwijkende boekjaren wordt de laatste vervaldag steeds op de laatste dag van de maand gesteld.

Runbestanden met volledige prompts, reacties, bijdragen en besluiten:

[A_huidig ronde 1](modelruns/1-LI-9.1-A_huidig.json), [B_verbeterd ronde 1](modelruns/1-LI-9.1-B_verbeterd.json), [C_context ronde 1](modelruns/1-LI-9.1-C_context.json), [A_huidig ronde 2](modelruns/2-LI-9.1-A_huidig.json), [B_verbeterd ronde 2](modelruns/2-LI-9.1-B_verbeterd.json), [C_context ronde 2](modelruns/2-LI-9.1-C_context.json), [A_huidig ronde 3](modelruns/3-LI-9.1-A_huidig.json), [B_verbeterd ronde 3](modelruns/3-LI-9.1-B_verbeterd.json), [C_context ronde 3](modelruns/3-LI-9.1-C_context.json)

| Offset | Fragment | Klasse | A (a/m) | B (a/m) | C (a/m) | Verschil in aanwezigheid |
|---|---|---|---:|---:|---:|---|
| [0,309) | In de gevallen waarin voor voorlopige aanslagen (bedoeld in artikel 9, vijfde lid, van de wet) die zijn gedagtekend in november of eerder, toepassing van de wet er toe zou leiden dat de enige of laatste betalingstermijn eindigt voor 31 december, dan wordt de vervaldag van deze termijn op 31 december gesteld. | Afleidingsregel | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [27,47) | voorlopige aanslagen | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [116,137) | in november of eerder | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [119,127) | november | Variabele en variabelewaarde | 2/0 | 3/0 | 3/0 | B−A wisselend/status |
| [139,160) | toepassing van de wet | Voorwaarde | 3/0 | 2/0 | 3/0 | B−A wisselend/status; C−B wisselend/status |
| [183,219) | de enige of laatste betalingstermijn | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [228,244) | voor 31 december | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [256,268) | de vervaldag | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [273,285) | deze termijn | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [286,300) | op 31 december | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [310,334) | Bij afwijkende boekjaren | Voorwaarde | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [310,408) | Bij afwijkende boekjaren wordt de laatste vervaldag steeds op de laatste dag van de maand gesteld. | Afleidingsregel | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [314,334) | afwijkende boekjaren | Variabele en variabelewaarde | 3/0 | 2/0 | 2/0 | B−A wisselend/status |
| [341,361) | de laatste vervaldag | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [372,386) | de laatste dag | Tijdsaanduiding | 3/0 | 0/0 | 0/0 | B−A verdwenen |
| [372,399) | de laatste dag van de maand | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [391,399) | de maand | Tijdsaanduiding | 3/0 | 0/0 | 2/0 | B−A verdwenen; C−B toegevoegd |

Gerichte herbeoordelingen en technische uitval:

Geen gerichte herbeoordeling in deze pogingen.

## LI-9.5

Bron(nen):

`urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.5` · SHA256 `726e8826e0208095b2858a1f7779faca91d7dc7aa2548cd2318fc8f2419fdfbf`

> Als de betalingstermijn van een aanslag is gesteld op één maand of is gesteld op zes weken, dan houdt dat in dat als de dagtekening van een aanslagbiljet valt op 31 oktober, de betalingstermijn van één maand vervalt op 30 november en de betalingstermijn van zes weken vervalt op 12 december. Als de dagtekening 28 februari is, dan vervalt de betalingstermijn van een maand op 31 maart en de betalingstermijn van zes weken op 11 april, tenzij het jaartal aangeeft dat het een schrikkeljaar is, in welk geval de termijn vervalt op 28 maart dan wel 10 april. Als de dagtekening van het aanslagbiljet valt op een andere dag dan de laatste dag van de kalendermaand, vervalt de termijn een maand later (bij een betalingstermijn van een maand) op de dag die hetzelfde nummer heeft als dat van de dagtekening. Als de dagtekening bijvoorbeeld 15 maart is, vervalt de termijn dus op 15 april. Is de betalingstermijn zes weken en is de dagtekening 15 maart, vervalt de termijn op 26 april.

Runbestanden met volledige prompts, reacties, bijdragen en besluiten:

[A_huidig ronde 1](modelruns/1-LI-9.5-A_huidig.json), [B_verbeterd ronde 1](modelruns/1-LI-9.5-B_verbeterd.json), [C_context ronde 1](modelruns/1-LI-9.5-C_context.json), [A_huidig ronde 2](modelruns/2-LI-9.5-A_huidig.json), [B_verbeterd ronde 2](modelruns/2-LI-9.5-B_verbeterd.json), [C_context ronde 2](modelruns/2-LI-9.5-C_context.json), [A_huidig ronde 3](modelruns/3-LI-9.5-A_huidig.json), [B_verbeterd ronde 3](modelruns/3-LI-9.5-B_verbeterd.json), [C_context ronde 3](modelruns/3-LI-9.5-C_context.json)

| Offset | Fragment | Klasse | A (a/m) | B (a/m) | C (a/m) | Verschil in aanwezigheid |
|---|---|---|---:|---:|---:|---|
| [4,23) | de betalingstermijn | Rechtsobject | 1/0 | 0/0 | 2/0 | B−A verdwenen; C−B toegevoegd |
| [4,23) | de betalingstermijn | Variabele en variabelewaarde | 2/0 | 3/0 | 1/0 | B−A wisselend/status; C−B wisselend/status |
| [28,39) | een aanslag | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [54,63) | één maand | Tijdsaanduiding | 3/0 | 3/0 | 0/0 | C−B verdwenen |
| [81,90) | zes weken | Tijdsaanduiding | 3/0 | 3/0 | 0/0 | C−B verdwenen |
| [117,131) | de dagtekening | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [117,153) | de dagtekening van een aanslagbiljet | Rechtsfeit | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [117,153) | de dagtekening van een aanslagbiljet | Rechtsobject | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [117,153) | de dagtekening van een aanslagbiljet | Voorwaarde | 1/0 | 2/0 | 3/0 | B−A wisselend/status; C−B wisselend/status |
| [136,153) | een aanslagbiljet | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [159,172) | op 31 oktober | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [174,193) | de betalingstermijn | Rechtsobject | 1/0 | 0/0 | 2/0 | B−A verdwenen; C−B toegevoegd |
| [174,193) | de betalingstermijn | Variabele en variabelewaarde | 2/0 | 3/0 | 1/0 | B−A wisselend/status; C−B wisselend/status |
| [198,207) | één maand | Tijdsaanduiding | 3/0 | 3/0 | 0/0 | C−B verdwenen |
| [216,230) | op 30 november | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [234,253) | de betalingstermijn | Rechtsobject | 1/0 | 0/0 | 2/0 | B−A verdwenen; C−B toegevoegd |
| [234,253) | de betalingstermijn | Variabele en variabelewaarde | 2/0 | 3/0 | 1/0 | B−A wisselend/status; C−B wisselend/status |
| [258,267) | zes weken | Tijdsaanduiding | 3/0 | 3/0 | 0/0 | C−B verdwenen |
| [276,290) | op 12 december | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [296,310) | de dagtekening | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [311,322) | 28 februari | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [339,358) | de betalingstermijn | Rechtsobject | 1/0 | 0/0 | 2/0 | B−A verdwenen; C−B toegevoegd |
| [339,358) | de betalingstermijn | Variabele en variabelewaarde | 2/0 | 3/0 | 1/0 | B−A wisselend/status; C−B wisselend/status |
| [363,372) | een maand | Tijdsaanduiding | 3/0 | 3/0 | 0/0 | C−B verdwenen |
| [373,384) | op 31 maart | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [388,407) | de betalingstermijn | Rechtsobject | 1/0 | 0/0 | 2/0 | B−A verdwenen; C−B toegevoegd |
| [388,407) | de betalingstermijn | Variabele en variabelewaarde | 2/0 | 3/0 | 1/0 | B−A wisselend/status; C−B wisselend/status |
| [412,421) | zes weken | Tijdsaanduiding | 3/0 | 3/0 | 0/0 | C−B verdwenen |
| [422,433) | op 11 april | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [435,491) | tenzij het jaartal aangeeft dat het een schrikkeljaar is | Voorwaarde | 3/0 | 3/0 | 3/0 | behouden |
| [442,453) | het jaartal | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [471,488) | een schrikkeljaar | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [507,517) | de termijn | Rechtsobject | 2/0 | 0/0 | 3/0 | B−A verdwenen; C−B toegevoegd |
| [507,517) | de termijn | Variabele en variabelewaarde | 1/0 | 3/0 | 0/0 | B−A wisselend/status; C−B verdwenen |
| [526,537) | op 28 maart | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [538,545) | dan wel | Operator | 3/0 | 3/0 | 3/0 | behouden |
| [546,554) | 10 april | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [556,659) | Als de dagtekening van het aanslagbiljet valt op een andere dag dan de laatste dag van de kalendermaand | Voorwaarde | 3/0 | 3/0 | 3/0 | behouden |
| [556,801) | Als de dagtekening van het aanslagbiljet valt op een andere dag dan de laatste dag van de kalendermaand, vervalt de termijn een maand later (bij een betalingstermijn van een maand) op de dag die hetzelfde nummer heeft als dat van de dagtekening. | Afleidingsregel | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [560,574) | de dagtekening | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [560,596) | de dagtekening van het aanslagbiljet | Rechtsfeit | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [560,596) | de dagtekening van het aanslagbiljet | Rechtsobject | 2/0 | 0/0 | 0/0 | B−A verdwenen |
| [560,596) | de dagtekening van het aanslagbiljet | Voorwaarde | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [579,596) | het aanslagbiljet | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [605,619) | een andere dag | Variabele en variabelewaarde | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [624,638) | de laatste dag | Tijdsaanduiding | 3/0 | 0/0 | 0/0 | B−A verdwenen |
| [624,659) | de laatste dag van de kalendermaand | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [643,659) | de kalendermaand | Rechtsobject | 0/1 | 0/0 | 0/0 | B−A verdwenen |
| [643,659) | de kalendermaand | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [669,679) | de termijn | Rechtsobject | 2/0 | 0/0 | 3/0 | B−A verdwenen; C−B toegevoegd |
| [669,679) | de termijn | Variabele en variabelewaarde | 1/0 | 3/0 | 0/0 | B−A wisselend/status; C−B verdwenen |
| [680,689) | een maand | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [680,695) | een maand later | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [701,721) | een betalingstermijn | Rechtsobject | 1/0 | 0/0 | 2/0 | B−A verdwenen; C−B toegevoegd |
| [701,721) | een betalingstermijn | Variabele en variabelewaarde | 2/0 | 3/0 | 1/0 | B−A wisselend/status; C−B wisselend/status |
| [726,735) | een maand | Tijdsaanduiding | 3/0 | 3/0 | 1/0 | C−B wisselend/status |
| [740,746) | de dag | Rechtsobject | 0/2 | 0/0 | 0/0 | B−A verdwenen |
| [740,746) | de dag | Variabele en variabelewaarde | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [740,800) | de dag die hetzelfde nummer heeft als dat van de dagtekening | Rechtsobject | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [740,800) | de dag die hetzelfde nummer heeft als dat van de dagtekening | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [740,800) | de dag die hetzelfde nummer heeft als dat van de dagtekening | Voorwaarde | 0/1 | 0/0 | 0/0 | B−A verdwenen |
| [751,767) | hetzelfde nummer | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [786,800) | de dagtekening | Rechtsobject | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [786,800) | de dagtekening | Variabele en variabelewaarde | 2/0 | 3/0 | 3/0 | B−A wisselend/status |
| [802,845) | Als de dagtekening bijvoorbeeld 15 maart is | Voorwaarde | 3/0 | 0/0 | 0/0 | B−A verdwenen |
| [806,820) | de dagtekening | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [834,842) | 15 maart | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [855,865) | de termijn | Rechtsobject | 2/0 | 0/0 | 3/0 | B−A verdwenen; C−B toegevoegd |
| [855,865) | de termijn | Variabele en variabelewaarde | 1/0 | 3/0 | 0/0 | B−A wisselend/status; C−B verdwenen |
| [870,881) | op 15 april | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [886,905) | de betalingstermijn | Rechtsobject | 1/0 | 0/0 | 2/0 | B−A verdwenen; C−B toegevoegd |
| [886,905) | de betalingstermijn | Variabele en variabelewaarde | 2/0 | 3/0 | 1/0 | B−A wisselend/status; C−B wisselend/status |
| [906,915) | zes weken | Tijdsaanduiding | 3/0 | 3/0 | 0/0 | C−B verdwenen |
| [922,936) | de dagtekening | Variabele en variabelewaarde | 3/0 | 3/0 | 3/0 | behouden |
| [937,945) | 15 maart | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [955,965) | de termijn | Rechtsobject | 2/0 | 0/0 | 3/0 | B−A verdwenen; C−B toegevoegd |
| [955,965) | de termijn | Variabele en variabelewaarde | 1/0 | 3/0 | 0/0 | B−A wisselend/status; C−B verdwenen |
| [966,977) | op 26 april | Tijdsaanduiding | 0/0 | 3/0 | 3/0 | B−A toegevoegd |

Gerichte herbeoordelingen en technische uitval:

- A_huidig ronde 1, C003: R-ABSTAIN-CHANGE. 
- A_huidig ronde 1, C004: R-ABSTAIN-CHANGE. 
- A_huidig ronde 1, C005: R-ABSTAIN-CHANGE. 
- A_huidig ronde 1, C009: R-ABSTAIN-CHANGE. 
- A_huidig ronde 1, C011: R-ABSTAIN-CHANGE. 
- A_huidig ronde 1, C014: R-ABSTAIN-CHANGE. 
- A_huidig ronde 1, C016: R-ABSTAIN-CHANGE. 
- A_huidig ronde 1, C024: R-ABSTAIN-CHANGE. 
- A_huidig ronde 1, C029: R-ONGELDIG. 
- A_huidig ronde 1, C033: R-ABSTAIN-CHANGE. 
- A_huidig ronde 1, C035: R-ABSTAIN-HUMAN. 
- A_huidig ronde 1, C042: R-ABSTAIN-CHANGE. 
- A_huidig ronde 2, C003: R-ABSTAIN-CHANGE. 
- A_huidig ronde 2, C004: R-ABSTAIN-CHANGE. 
- A_huidig ronde 2, C009: R-ABSTAIN-CHANGE. 
- A_huidig ronde 2, C011: R-ABSTAIN-CHANGE. 
- A_huidig ronde 2, C014: R-ABSTAIN-CHANGE. 
- A_huidig ronde 2, C016: R-ABSTAIN-CHANGE. 
- A_huidig ronde 2, C031: R-ABSTAIN-CHANGE. 
- A_huidig ronde 2, C033: R-ABSTAIN-CHANGE. 
- A_huidig ronde 2, C034: R-ABSTAIN-HUMAN. 
- A_huidig ronde 2, C035: R-ABSTAIN-HUMAN. 
- A_huidig ronde 2, C042: R-ABSTAIN-CHANGE. 

## IW02

Bron(nen):

`urn:bwb:BWBR0004770:artikel:36:lid:1` · SHA256 `a0723a3330cdbb0c3770fadd06c2ca1ba8df14188726dff9a46dcc7acea2ba25`

> Hoofdelijk aansprakelijk is voor de loonbelasting, de omzetbelasting, de accijns, de verbruiksbelastingen van alcoholvrije dranken en van pruimtabak en snuiftabak, de in artikel 1 van de Wet belastingen op milieugrondslag genoemde belastingen en de kansspelbelasting verschuldigd door een rechtspersoonlijkheid bezittend lichaam in de zin van de Algemene wet inzake rijksbelastingen dat volledig rechtsbevoegd is, voor zover het aan de heffing van vennootschapsbelasting is onderworpen: ieder van de bestuurders overeenkomstig het bepaalde in de volgende leden.

Runbestanden met volledige prompts, reacties, bijdragen en besluiten:

[A_huidig ronde 1](modelruns/snapshot-herstel/1-IW02-A_huidig.json), [B_verbeterd ronde 1](modelruns/snapshot-herstel/1-IW02-B_verbeterd.json), [C_context ronde 1](modelruns/snapshot-herstel/1-IW02-C_context.json), [A_huidig ronde 2](modelruns/2-IW02-A_huidig.json), [B_verbeterd ronde 2](modelruns/2-IW02-B_verbeterd.json), [C_context ronde 2](modelruns/2-IW02-C_context.json), [A_huidig ronde 3](modelruns/3-IW02-A_huidig.json), [B_verbeterd ronde 3](modelruns/3-IW02-B_verbeterd.json), [C_context ronde 3](modelruns/3-IW02-C_context.json)

| Offset | Fragment | Klasse | A (a/m) | B (a/m) | C (a/m) | Verschil in aanwezigheid |
|---|---|---|---:|---:|---:|---|
| [0,485) | Hoofdelijk aansprakelijk is voor de loonbelasting, de omzetbelasting, de accijns, de verbruiksbelastingen van alcoholvrije dranken en van pruimtabak en snuiftabak, de in artikel 1 van de Wet belastingen op milieugrondslag genoemde belastingen en de kansspelbelasting verschuldigd door een rechtspersoonlijkheid bezittend lichaam in de zin van de Algemene wet inzake rijksbelastingen dat volledig rechtsbevoegd is, voor zover het aan de heffing van vennootschapsbelasting is onderworpen | Rechtsbetrekking | 3/0 | 3/0 | 3/0 | behouden |
| [33,49) | de loonbelasting | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [51,68) | de omzetbelasting | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [70,80) | de accijns | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [82,105) | de verbruiksbelastingen | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [164,242) | de in artikel 1 van de Wet belastingen op milieugrondslag genoemde belastingen | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [246,266) | de kansspelbelasting | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [311,328) | bezittend lichaam | Rechtssubject | 3/0 | 0/0 | 0/0 | B−A verdwenen |
| [321,328) | lichaam | Rechtsobject | 0/0 | 1/0 | 0/0 | B−A toegevoegd; C−B verdwenen |
| [321,328) | lichaam | Rechtssubject | 3/0 | 2/0 | 3/0 | B−A wisselend/status; C−B wisselend/status |
| [366,412) | rijksbelastingen dat volledig rechtsbevoegd is | Voorwaarde | 3/0 | 3/0 | 3/0 | behouden |
| [414,485) | voor zover het aan de heffing van vennootschapsbelasting is onderworpen | Voorwaarde | 3/0 | 3/0 | 3/0 | behouden |
| [433,470) | de heffing van vennootschapsbelasting | Rechtsfeit | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [433,470) | de heffing van vennootschapsbelasting | Voorwaarde | 0/0 | 3/0 | 3/0 | B−A toegevoegd |
| [448,470) | vennootschapsbelasting | Variabele en variabelewaarde | 0/0 | 0/0 | 1/0 | C−B toegevoegd |
| [487,492) | ieder | Rechtssubject | 0/0 | 2/0 | 3/0 | B−A toegevoegd; C−B wisselend/status |
| [487,511) | ieder van de bestuurders | Rechtssubject | 3/0 | 3/0 | 3/0 | behouden |
| [497,511) | de bestuurders | Rechtssubject | 2/0 | 0/0 | 0/0 | B−A verdwenen |

Gerichte herbeoordelingen en technische uitval:

Geen gerichte herbeoordeling in deze pogingen.

## AWB04

Bron(nen):

`urn:bwb:BWBR0005537:artikel:4%3A17:lid:2` · SHA256 `0fead802bb963eeceaeea7fe06028f48cb725b1ebbb802e4f3ed20337ef25ac2`

> De dwangsom bedraagt de eerste veertien dagen € 23 per dag, de daaropvolgende veertien dagen € 35 per dag en de overige dagen € 45 per dag.

Runbestanden met volledige prompts, reacties, bijdragen en besluiten:

[A_huidig ronde 1](modelruns/snapshot-herstel/1-AWB04-A_huidig.json), [B_verbeterd ronde 1](modelruns/snapshot-herstel/1-AWB04-B_verbeterd.json), [C_context ronde 1](modelruns/snapshot-herstel/1-AWB04-C_context.json), [A_huidig ronde 2](modelruns/2-AWB04-A_huidig.json), [B_verbeterd ronde 2](modelruns/2-AWB04-B_verbeterd.json), [C_context ronde 2](modelruns/2-AWB04-C_context.json), [A_huidig ronde 3](modelruns/3-AWB04-A_huidig.json), [B_verbeterd ronde 3](modelruns/3-AWB04-B_verbeterd.json), [C_context ronde 3](modelruns/3-AWB04-C_context.json)

| Offset | Fragment | Klasse | A (a/m) | B (a/m) | C (a/m) | Verschil in aanwezigheid |
|---|---|---|---:|---:|---:|---|
| [0,11) | De dwangsom | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [0,139) | De dwangsom bedraagt de eerste veertien dagen € 23 per dag, de daaropvolgende veertien dagen € 35 per dag en de overige dagen € 45 per dag. | Afleidingsregel | 3/0 | 1/1 | 1/0 | B−A wisselend/status; C−B wisselend/status |
| [0,139) | De dwangsom bedraagt de eerste veertien dagen € 23 per dag, de daaropvolgende veertien dagen € 35 per dag en de overige dagen € 45 per dag. | Parameter en parameterwaarde | 0/0 | 1/0 | 2/0 | B−A toegevoegd; C−B wisselend/status |
| [21,45) | de eerste veertien dagen | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [31,45) | veertien dagen | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [46,47) | € | Variabele en variabelewaarde | 0/0 | 0/0 | 3/0 | C−B toegevoegd |
| [46,58) | € 23 per dag | Parameter en parameterwaarde | 3/0 | 3/0 | 3/0 | behouden |
| [55,58) | dag | Variabele en variabelewaarde | 0/0 | 0/0 | 2/0 | C−B toegevoegd |
| [60,92) | de daaropvolgende veertien dagen | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [78,92) | veertien dagen | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [93,94) | € | Variabele en variabelewaarde | 0/0 | 0/0 | 3/0 | C−B toegevoegd |
| [93,105) | € 35 per dag | Parameter en parameterwaarde | 3/0 | 3/0 | 3/0 | behouden |
| [102,105) | dag | Variabele en variabelewaarde | 0/0 | 0/0 | 2/0 | C−B toegevoegd |
| [109,125) | de overige dagen | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [126,127) | € | Variabele en variabelewaarde | 0/0 | 0/0 | 3/0 | C−B toegevoegd |
| [126,138) | € 45 per dag | Parameter en parameterwaarde | 3/0 | 3/0 | 3/0 | behouden |
| [135,138) | dag | Variabele en variabelewaarde | 0/0 | 0/0 | 2/0 | C−B toegevoegd |

Gerichte herbeoordelingen en technische uitval:

- B_verbeterd ronde 2, C001: R-ONGELDIG. 

## AWB-4:17-1

Bron(nen):

`urn:bwb:BWBR0005537:artikel:4%3A17:lid:1` · SHA256 `6be09c14c2bde6a4838945fc60ec5efdb2f4d08d3902c9e95d306841d85780c1`

> Indien een beschikking op aanvraag niet tijdig wordt gegeven, verbeurt het bestuursorgaan aan de aanvrager een dwangsom voor elke dag dat het in gebreke is, doch voor ten hoogste 42 dagen. De Algemene termijnenwet is op laatstgenoemde termijn niet van toepassing.

Runbestanden met volledige prompts, reacties, bijdragen en besluiten:

[A_huidig ronde 1](modelruns/snapshot-herstel/1-AWB-4_17-1-A_huidig.json), [B_verbeterd ronde 1](modelruns/snapshot-herstel/1-AWB-4_17-1-B_verbeterd.json), [C_context ronde 1](modelruns/1-AWB-4_17-1-C_context.json), [A_huidig ronde 2](modelruns/2-AWB-4_17-1-A_huidig.json), [B_verbeterd ronde 2](modelruns/2-AWB-4_17-1-B_verbeterd.json), [C_context ronde 2](modelruns/2-AWB-4_17-1-C_context.json), [A_huidig ronde 3](modelruns/3-AWB-4_17-1-A_huidig.json), [B_verbeterd ronde 3](modelruns/3-AWB-4_17-1-B_verbeterd.json), [C_context ronde 3](modelruns/3-AWB-4_17-1-C_context.json)

| Offset | Fragment | Klasse | A (a/m) | B (a/m) | C (a/m) | Verschil in aanwezigheid |
|---|---|---|---:|---:|---:|---|
| [0,60) | Indien een beschikking op aanvraag niet tijdig wordt gegeven | Voorwaarde | 3/0 | 3/0 | 3/0 | behouden |
| [7,22) | een beschikking | Rechtsobject | 1/0 | 3/0 | 3/0 | B−A wisselend/status |
| [7,34) | een beschikking op aanvraag | Rechtsfeit | 0/0 | 0/1 | 0/0 | B−A toegevoegd; C−B verdwenen |
| [7,34) | een beschikking op aanvraag | Rechtsobject | 1/0 | 2/0 | 3/0 | B−A wisselend/status; C−B wisselend/status |
| [26,34) | aanvraag | Variabele en variabelewaarde | 0/0 | 2/0 | 1/0 | B−A toegevoegd; C−B wisselend/status |
| [40,46) | tijdig | Tijdsaanduiding | 1/0 | 0/0 | 1/0 | B−A verdwenen; C−B toegevoegd |
| [71,89) | het bestuursorgaan | Rechtssubject | 3/0 | 3/0 | 3/0 | behouden |
| [94,106) | de aanvrager | Rechtssubject | 3/0 | 3/0 | 3/0 | behouden |
| [107,119) | een dwangsom | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [125,133) | elke dag | Variabele en variabelewaarde | 1/0 | 3/0 | 3/0 | B−A wisselend/status |
| [167,178) | ten hoogste | Operator | 3/0 | 3/0 | 3/0 | behouden |
| [167,187) | ten hoogste 42 dagen | Tijdsaanduiding | 3/0 | 3/0 | 3/0 | behouden |
| [189,213) | De Algemene termijnenwet | Rechtsobject | 0/0 | 0/0 | 1/0 | C−B toegevoegd |

Gerichte herbeoordelingen en technische uitval:

- B_verbeterd ronde 3, C002: R-ONGELDIG. 

## IW04

Bron(nen):

`urn:bwb:BWBR0004770:artikel:34:lid:6` · SHA256 `c0ad8c5227c159f4650da09b8e380d69a549f4f96b9a7ed641512133cb60a941`

> Bij ministeriële regeling worden nadere regels gesteld met betrekking tot de toepassing van het derde lid.

Runbestanden met volledige prompts, reacties, bijdragen en besluiten:

[A_huidig ronde 1](modelruns/snapshot-herstel/1-IW04-A_huidig.json), [B_verbeterd ronde 1](modelruns/snapshot-herstel/1-IW04-B_verbeterd.json), [C_context ronde 1](modelruns/snapshot-herstel/1-IW04-C_context.json), [A_huidig ronde 2](modelruns/2-IW04-A_huidig.json), [B_verbeterd ronde 2](modelruns/2-IW04-B_verbeterd.json), [C_context ronde 2](modelruns/2-IW04-C_context.json), [A_huidig ronde 3](modelruns/3-IW04-A_huidig.json), [B_verbeterd ronde 3](modelruns/3-IW04-B_verbeterd.json), [C_context ronde 3](modelruns/3-IW04-C_context.json)

| Offset | Fragment | Klasse | A (a/m) | B (a/m) | C (a/m) | Verschil in aanwezigheid |
|---|---|---|---:|---:|---:|---|
| [0,106) | Bij ministeriële regeling worden nadere regels gesteld met betrekking tot de toepassing van het derde lid. | Delegatiebevoegdheid en delegatie-invulling | 3/0 | 3/0 | 3/0 | behouden |
| [33,46) | nadere regels | Rechtsobject | 3/0 | 3/0 | 3/0 | behouden |
| [59,105) | betrekking tot de toepassing van het derde lid | Rechtsobject | 0/0 | 3/0 | 2/0 | B−A toegevoegd; C−B wisselend/status |
| [74,87) | de toepassing | Rechtsobject | 1/0 | 0/0 | 0/0 | B−A verdwenen |
| [74,87) | de toepassing | Variabele en variabelewaarde | 0/0 | 1/0 | 0/0 | B−A toegevoegd; C−B verdwenen |

Gerichte herbeoordelingen en technische uitval:

Geen gerichte herbeoordeling in deze pogingen.
