# Vier conceptdossiers

Status: concept, niet geadjudiceerd. Geen minimale aantallen of volledige gold-set. Alle fragmenten komen uit de graaf, in [bronnen.json](bronnen.json). De 60 onderzoeksitems omvatten voorstellen, alternatieven, relaties en expliciete uitsluitingen; ze zijn geen 60 verwachte annotaties.

`voorstel` = onderbouwde werkhypothese; `open` = afzonderlijke juridische beoordeling; `samenhang` = relatie/context zonder verplicht extra label; `uitsluiten` = gemotiveerd negatief geval. Meerdere klassen zijn alternatieven tenzij de motivering verschillende functies onderscheidt. Kern/optie gaat alleen over exacte grenzen; afwezige kerngrenzen bewijzen niet dat iedere overlappende systeemmarkering onjuist is.

## IW-9-1

Bron: `urn:bwb:BWBR0004770:artikel:9:lid:1`; wet; graaftoestand 2026-07-01.

> Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.

De norm bepaalt wanneer een aanslag invorderbaar is. IW 8 lid 5 onderscheidt verschuldigdheid; IW 3 lid 1 en 2 lid 1 k dragen de abstracte partijen. Een rolverbinding is geen extra anker in dit lid.

### Elementen en functies

| ID | Bereik [start,eind) en fragment | Mogelijke klasse | Beoordeling | Functie | Exacte kandidaat/optie |
|---|---|---|---|---|---|
| E01 | [0,87) Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet. | Rechtsbetrekking, Rechtsfeit | voorstel | Dragende norm: invorderbaarheid vanaf een tijdstip; RB is werkhypothese, RF vraagt motivering. | C001; passende kernklasse: Rechtsbetrekking, Rechtsfeit |
| E02 | [0,20) Een belastingaanslag | Rechtsobject | voorstel | Voorwerp waarop de invorderbaarheid ziet. | C002; passende kernklasse: Rechtsobject |
| E03 | [37,86) zes weken na de dagtekening van het aanslagbiljet | Tijdsaanduiding | voorstel | Duur met startpunt; geen ontvangsttermijn. | C003; passende kernklasse: Tijdsaanduiding |
| E04 | [37,46) zes weken | Tijdsaanduiding | samenhang | Temporele kern van E03; geen verplichte tweede annotatie. | C004; optie: C003; passende kernklasse: Tijdsaanduiding |
| E05 | [50,86) de dagtekening van het aanslagbiljet | Tijdsaanduiding, Variabele en variabelewaarde | open | Startdatum: context bij termijn. Variabele alleen bij onderscheiden functie. | geen kern; passende kernklasse: geen |
| E06 | [69,86) het aanslagbiljet | Rechtsobject | open | Datumdrager/document; zelfstandige objectfunctie te beoordelen. | C005; passende kernklasse: Rechtsobject |
| E07 | [37,86) zes weken na de dagtekening van het aanslagbiljet | Rechtsfeit | open | Verloop met mogelijke toestandsverandering; geen automatische vervanging van Tijdsaanduiding. | C003; passende kernklasse: Rechtsfeit |
| E08 | [24,36) invorderbaar | Rechtsobject | uitsluiten | Geen object alleen wegens NOUN-tag van de parser. | geen kern; passende kernklasse: geen |

### Alle dertien klassen beoordeeld

| Klasse | Beoordeling |
|---|---|
| Rechtssubject | Niet letterlijk aanwezig; ontvanger en belastingschuldige alleen uit graafcontext afleiden. |
| Rechtsobject | Beoordeel het object van de centrale norm, niet iedere zelfstandige naamwoordgroep. |
| Rechtsbetrekking | Centrale invorderbaarheids- of termijnnorm expliciteren; type rechtsbetrekking vraagt context. |
| Rechtsfeit | Tijdsverloop met rechtsgevolg onderzoeken; dagtekening is niet automatisch een rechtshandeling. |
| Voorwaarde | Temporele toepasselijkheid aanwezig; niet automatisch een extra Voorwaarde op dezelfde termijn. |
| Afleidingsregel | De berekening dagtekening + zes weken is een analytische reconstructie, geen letterlijk uitgeschreven rekenregel. |
| Variabele en variabelewaarde | Datum/aantal kunnen analytische invoergegevens zijn; geen dubbel label bij dezelfde temporele functie. |
| Parameter en parameterwaarde | Geen extra parameter uitsluitend omdat een termijn een vaste duur heeft (JAS-PRIORITY-001). |
| Operator | Na legt een temporele relatie; geen zelfstandig operatorlabel zonder ander vergelijkingsbereik. |
| Tijdsaanduiding | Duur/startpunt/vervalmoment met de dragende context. |
| Plaatsaanduiding | Geen plaatsbepaling in eigen tekst. |
| Delegatiebevoegdheid en delegatie-invulling | Geen delegatieformule; een verwijzing naar de wet is geen delegatie. |
| Brondefinitie | Geen expliciete begripsdefinitie in eigen tekst; eventuele definities staan in contextnodes. |

### Open beoordelingsvragen

- Draagt de volledige zin primair een rechtsbetrekking of de temporele eigenschap ervan?
- Rechtvaardigt hetzelfde tijdfragment een zelfstandig rechtsfeit, of legt het dossier dat als relatie vast?
- Heeft het aanslagbiljet naast zijn functie als datumdrager een zelfstandige juridische objectfunctie?

## IW-9-5

Bron: `urn:bwb:BWBR0004770:artikel:9:lid:5`; wet; graaftoestand 2026-07-01.

> In afwijking van het eerste lid is een voorlopige aanslag in de inkomstenbelasting of in de vennootschapsbelasting en een voorlopige conserverende aanslag in de inkomstenbelasting, waarvan het aanslagbiljet een dagtekening heeft die ligt in het jaar waarover deze is vastgesteld, invorderbaar in zoveel gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is vermeld, nog maanden van het jaar overblijven. De eerste termijn vervalt één maand na de dagtekening van het aanslagbiljet en elk van de volgende termijnen telkens een maand later. Indien de toepassing van de eerste volzin niet leidt tot meer dan één termijn, vindt het eerste lid toepassing.

De eerste zin koppelt soort aanslag en dagtekeningsjaar aan gelijke termijnen. De tweede regelt eerste en volgende vervalmomenten. De derde laat bij hoogstens één termijn lid 1 gelden. De berekening en de toepassingsvoorwaarden horen aan deze drie regels verbonden.

### Elementen en functies

| ID | Bereik [start,eind) en fragment | Mogelijke klasse | Beoordeling | Functie | Exacte kandidaat/optie |
|---|---|---|---|---|---|
| E01 | [0,434) In afwijking van het eerste lid is een voorlopige aanslag in de inkomstenbelasting of in de vennootschapsbelasting en een voorlopige conserverende aanslag in de inkomstenbelasting, waarvan het aanslagbiljet een dagtekening heeft die ligt in het jaar waarover deze is vastgesteld, invorderbaar in zoveel gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is vermeld, nog maanden van het jaar overblijven. | Rechtsbetrekking, Afleidingsregel | voorstel | Centrale bijzondere norm plus termijnberekening; mogelijke dubbele functie expliciet beoordelen. | C001; passende kernklasse: Afleidingsregel, Rechtsbetrekking |
| E02 | [35,114) een voorlopige aanslag in de inkomstenbelasting of in de vennootschapsbelasting | Rechtsobject | voorstel | Eerste categorie aanslagen; geen rechtssubject. | geen kern; passende kernklasse: geen |
| E03 | [118,179) een voorlopige conserverende aanslag in de inkomstenbelasting | Rechtsobject | voorstel | Tweede categorie in opsomming. | geen kern; optie: C007; passende kernklasse: geen |
| E04 | [181,278) waarvan het aanslagbiljet een dagtekening heeft die ligt in het jaar waarover deze is vastgesteld | Voorwaarde | voorstel | Toepassingsvoorwaarde: dagtekening in betrokken jaar. | geen kern; passende kernklasse: geen |
| E05 | [296,433) zoveel gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is vermeld, nog maanden van het jaar overblijven | Afleidingsregel | voorstel | Aantal termijnen uit resterende maanden; gelijkheid van termijnbedragen als afzonderlijke eigenschap. | geen kern; passende kernklasse: geen |
| E06 | [296,320) zoveel gelijke termijnen | Variabele en variabelewaarde | open | Uitkomst aantal/verdeling; onderscheiden van duur van één termijn. | C015; passende kernklasse: Variabele en variabelewaarde |
| E07 | [321,433) als er na de maand, die in de dagtekening van het aanslagbiljet is vermeld, nog maanden van het jaar overblijven | Operator, Afleidingsregel | open | Vergelijkend zoveel ... als; geen zelfstandige als-voorwaarde uitsluitend op voegwoord. | geen kern; passende kernklasse: geen |
| E08 | [435,568) De eerste termijn vervalt één maand na de dagtekening van het aanslagbiljet en elk van de volgende termijnen telkens een maand later. | Rechtsfeit, Rechtsbetrekking | voorstel | Twee gekoppelde vervalmomenten; beoordelen als tijdsverloop/gevolg bij norm. | geen kern; passende kernklasse: geen |
| E09 | [461,510) één maand na de dagtekening van het aanslagbiljet | Tijdsaanduiding | voorstel | Eerste vervalmoment; stop voor de volgende termijnregel. | C024; passende kernklasse: Tijdsaanduiding |
| E10 | [544,567) telkens een maand later | Tijdsaanduiding | voorstel | Distributieve vervolgmomenten, gerelateerd aan de vorige termijn. | C030; passende kernklasse: Tijdsaanduiding |
| E11 | [435,510) De eerste termijn vervalt één maand na de dagtekening van het aanslagbiljet | Rechtsfeit | open | Vervallen eerste termijn als tijdsverloop met gevolg. | geen kern; passende kernklasse: geen |
| E12 | [514,567) elk van de volgende termijnen telkens een maand later | Rechtsfeit | open | Elliptisch vervolg deelt vervalt; geen werkwoord verzinnen in anker. | geen kern; passende kernklasse: geen |
| E13 | [569,646) Indien de toepassing van de eerste volzin niet leidt tot meer dan één termijn | Voorwaarde | voorstel | Terugvalconditie inclusief negatie. | C034; passende kernklasse: Voorwaarde |
| E14 | [626,634) meer dan | Operator | voorstel | Vergelijking van berekend aantal met één; negatie zit in de omvattende voorwaarde. | C040; passende kernklasse: Operator |
| E15 | [635,646) één termijn | Parameter en parameterwaarde, Variabele en variabelewaarde | open | Drempelwaarde van aantal, niet zonder meer een tijdsduur. | geen kern; passende kernklasse: geen |
| E16 | [569,680) Indien de toepassing van de eerste volzin niet leidt tot meer dan één termijn, vindt het eerste lid toepassing. | Afleidingsregel, Rechtsbetrekking | voorstel | Terugvalregel verwijst naar hoofdregel lid 1; anker blijft in lid 5. | C033; passende kernklasse: Afleidingsregel |
| E17 | [0,31) In afwijking van het eerste lid | bronrelatie | samenhang | Bronrelatie: wijkt af van IW-9-1; geen nieuwe JAS-klasse. | geen kern; passende kernklasse: geen |

### Alle dertien klassen beoordeeld

| Klasse | Beoordeling |
|---|---|
| Rechtssubject | Belastingsoorten en aanslagen zijn geen personen; abstracte partijen volgen uit context. |
| Rechtsobject | Beoordeel het object van de centrale norm, niet iedere zelfstandige naamwoordgroep. |
| Rechtsbetrekking | Centrale invorderbaarheids- of termijnnorm expliciteren; type rechtsbetrekking vraagt context. |
| Rechtsfeit | Tijdsverloop met rechtsgevolg onderzoeken; dagtekening is niet automatisch een rechtshandeling. |
| Voorwaarde | Toepassingsvoorwaarden inclusief uitzonderingen en ontkenning onderzoeken. |
| Afleidingsregel | De eerste zin bevat een algemene berekening van aantal en gelijke verdeling van termijnen; derde zin selecteert terugvalregel. |
| Variabele en variabelewaarde | Datum/aantal kunnen analytische invoergegevens zijn; geen dubbel label bij dezelfde temporele functie. |
| Parameter en parameterwaarde | Geen extra parameter uitsluitend omdat een termijn een vaste duur heeft (JAS-PRIORITY-001). |
| Operator | Alleen met benoemde operanden en bereik; geen los of/en/als zonder functie. |
| Tijdsaanduiding | Duur/startpunt/vervalmoment met de dragende context. |
| Plaatsaanduiding | Geen plaatsbepaling in eigen tekst. |
| Delegatiebevoegdheid en delegatie-invulling | Geen delegatieformule; een verwijzing naar de wet is geen delegatie. |
| Brondefinitie | Geen expliciete begripsdefinitie in eigen tekst; eventuele definities staan in contextnodes. |

### Open beoordelingsvragen

- Welke grens draagt de volledige afleiding zonder het bereik en de verwijzing te verliezen?
- Hoe moeten de opsomming van aanslagsoorten en de relatieve bijzin samen worden gelezen?
- Welke onderscheiden functies verdienen overlappende markeringen en welke alleen relaties?

## LI-9.1

Bron: `urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.1`; beleidsregel; graaftoestand 2026-07-01.

> In de gevallen waarin voor voorlopige aanslagen (bedoeld in artikel 9, vijfde lid, van de wet) die zijn gedagtekend in november of eerder, toepassing van de wet er toe zou leiden dat de enige of laatste betalingstermijn eindigt voor 31 december, dan wordt de vervaldag van deze termijn op 31 december gesteld. Bij afwijkende boekjaren wordt de laatste vervaldag steeds op de laatste dag van de maand gesteld.

De eerste zin verplaatst onder genoemde voorwaarden de enige of laatste vervaldag naar 31 december. De tweede bepaalt een maandultimo bij afwijkende boekjaren. De wettelijke berekening moet eerst bekend zijn. Beleid vervangt de wet niet als bronstatus.

### Elementen en functies

| ID | Bereik [start,eind) en fragment | Mogelijke klasse | Beoordeling | Functie | Exacte kandidaat/optie |
|---|---|---|---|---|---|
| E01 | [0,309) In de gevallen waarin voor voorlopige aanslagen (bedoeld in artikel 9, vijfde lid, van de wet) die zijn gedagtekend in november of eerder, toepassing van de wet er toe zou leiden dat de enige of laatste betalingstermijn eindigt voor 31 december, dan wordt de vervaldag van deze termijn op 31 december gesteld. | Afleidingsregel, Rechtsbetrekking | voorstel | Gehele voorwaardelijke beleidsregel inclusief nieuwe vervaldag. | C001; passende kernklasse: Afleidingsregel |
| E02 | [27,47) voorlopige aanslagen | Rechtsobject | voorstel | Objectcategorie, nader bepaald door verwijzing en relatieve bijzin. | C003; passende kernklasse: Rechtsobject |
| E03 | [60,93) artikel 9, vijfde lid, van de wet | bronrelatie | samenhang | Expliciete verwijzing naar IW-9-5, resolveer via LI-def-wet. | geen kern; passende kernklasse: geen |
| E04 | [95,137) die zijn gedagtekend in november of eerder | Voorwaarde | voorstel | Beperking aanslagen; maand/jaarfunctie behouden. | geen kern; passende kernklasse: geen |
| E05 | [116,137) in november of eerder | Tijdsaanduiding | voorstel | Temporele bovengrens; eerder heeft november als referentie. | C005; passende kernklasse: Tijdsaanduiding |
| E06 | [183,244) de enige of laatste betalingstermijn eindigt voor 31 december | Voorwaarde | voorstel | Voorwaarde op berekend wettelijk resultaat. | geen kern; passende kernklasse: geen |
| E07 | [228,244) voor 31 december | Tijdsaanduiding | voorstel | Bovengrens in de voorwaarde; niet de nieuwe vervaldag. | C011; passende kernklasse: Tijdsaanduiding |
| E08 | [246,308) dan wordt de vervaldag van deze termijn op 31 december gesteld | Afleidingsregel, Rechtsbetrekking | voorstel | Gevolg/toewijzing bij de hoofdvoorwaarde; alleen samen met E01 interpreteren. | geen kern; passende kernklasse: geen |
| E09 | [286,300) op 31 december | Tijdsaanduiding | voorstel | Nieuwe vervaldag in het gevolg, ander voorkomen dan E07. | C014; passende kernklasse: Tijdsaanduiding |
| E10 | [310,408) Bij afwijkende boekjaren wordt de laatste vervaldag steeds op de laatste dag van de maand gesteld. | Afleidingsregel, Rechtsbetrekking | voorstel | Tweede beleidsregel; volledige voorwaarde en uitkomst. | C015; passende kernklasse: Afleidingsregel |
| E11 | [310,334) Bij afwijkende boekjaren | Voorwaarde | voorstel | Voorwaarde zonder indien/als. | C016; passende kernklasse: Voorwaarde |
| E12 | [369,399) op de laatste dag van de maand | Tijdsaanduiding | voorstel | Relatieve datumomschrijving. | geen kern; passende kernklasse: geen |
| E13 | [256,285) de vervaldag van deze termijn | Tijdsaanduiding, Variabele en variabelewaarde | open | Berekende tijdswaarde met coreferentie naar enige/laatste termijn. | geen kern; optie: C012; passende kernklasse: geen |

### Alle dertien klassen beoordeeld

| Klasse | Beoordeling |
|---|---|
| Rechtssubject | Niet letterlijk aanwezig; ontvanger en belastingschuldige alleen uit graafcontext afleiden. |
| Rechtsobject | Beoordeel het object van de centrale norm, niet iedere zelfstandige naamwoordgroep. |
| Rechtsbetrekking | Centrale invorderbaarheids- of termijnnorm expliciteren; type rechtsbetrekking vraagt context. |
| Rechtsfeit | Stellen van vervaldag kan een gevolg beschrijven; passief wordt gesteld bewijst op zichzelf geen norm of rechtsfeit. |
| Voorwaarde | Toepassingsvoorwaarden inclusief uitzonderingen en ontkenning onderzoeken. |
| Afleidingsregel | De beleidsbepaling bepaalt een vervaldatum uit de wettelijke uitkomst en aanvullende voorwaarden. |
| Variabele en variabelewaarde | Datum/aantal kunnen analytische invoergegevens zijn; geen dubbel label bij dezelfde temporele functie. |
| Parameter en parameterwaarde | Geen extra parameter uitsluitend omdat een termijn een vaste duur heeft (JAS-PRIORITY-001). |
| Operator | Alleen met benoemde operanden en bereik; geen los of/en/als zonder functie. |
| Tijdsaanduiding | Duur/startpunt/vervalmoment met de dragende context. |
| Plaatsaanduiding | Geen plaatsbepaling in eigen tekst. |
| Delegatiebevoegdheid en delegatie-invulling | Geen delegatieformule; een verwijzing naar de wet is geen delegatie. |
| Brondefinitie | Kop benoemt afwijking; geen brondefinitie. |

### Open beoordelingsvragen

- Is de centrale klasse hier Afleidingsregel, Rechtsbetrekking of beide met verschillende functie?
- Welk precies toepassingsbereik heeft de slotzin over afwijkende boekjaren?
- Hoe wordt enige of laatste betalingstermijn gekoppeld aan het resultaat van lid 5 en diens terugval?

## LI-9.5

Bron: `urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.5`; beleidsregel; graaftoestand 2026-07-01.

> Als de betalingstermijn van een aanslag is gesteld op één maand of is gesteld op zes weken, dan houdt dat in dat als de dagtekening van een aanslagbiljet valt op 31 oktober, de betalingstermijn van één maand vervalt op 30 november en de betalingstermijn van zes weken vervalt op 12 december. Als de dagtekening 28 februari is, dan vervalt de betalingstermijn van een maand op 31 maart en de betalingstermijn van zes weken op 11 april, tenzij het jaartal aangeeft dat het een schrikkeljaar is, in welk geval de termijn vervalt op 28 maart dan wel 10 april. Als de dagtekening van het aanslagbiljet valt op een andere dag dan de laatste dag van de kalendermaand, vervalt de termijn een maand later (bij een betalingstermijn van een maand) op de dag die hetzelfde nummer heeft als dat van de dagtekening. Als de dagtekening bijvoorbeeld 15 maart is, vervalt de termijn dus op 15 april. Is de betalingstermijn zes weken en is de dagtekening 15 maart, vervalt de termijn op 26 april.

Scheid de kalenderuitwerking en haar concrete illustraties. Eén maand en zes weken worden niet gelijkgesteld. Het laatste-dag-onderscheid verklaart de februarivoorbeelden. Bronstatus blijft beleidsregel, ook voor de rekenvoorbeelden daarin.

### Elementen en functies

| ID | Bereik [start,eind) en fragment | Mogelijke klasse | Beoordeling | Functie | Exacte kandidaat/optie |
|---|---|---|---|---|---|
| E01 | [0,291) Als de betalingstermijn van een aanslag is gesteld op één maand of is gesteld op zes weken, dan houdt dat in dat als de dagtekening van een aanslagbiljet valt op 31 oktober, de betalingstermijn van één maand vervalt op 30 november en de betalingstermijn van zes weken vervalt op 12 december. | Afleidingsregel | open | Conditionele uitwerking met oktobervoorbeeld; voorbeeldstatus behouden. | geen kern; passende kernklasse: geen |
| E02 | [292,555) Als de dagtekening 28 februari is, dan vervalt de betalingstermijn van een maand op 31 maart en de betalingstermijn van zes weken op 11 april, tenzij het jaartal aangeeft dat het een schrikkeljaar is, in welk geval de termijn vervalt op 28 maart dan wel 10 april. | Afleidingsregel | open | Februarivoorbeeld met tenzij-vertakking; geen contextloze kalenderregel. | geen kern; passende kernklasse: geen |
| E03 | [556,801) Als de dagtekening van het aanslagbiljet valt op een andere dag dan de laatste dag van de kalendermaand, vervalt de termijn een maand later (bij een betalingstermijn van een maand) op de dag die hetzelfde nummer heeft als dat van de dagtekening. | Afleidingsregel | voorstel | Algemene kalenderregel voor dagtekening anders dan maandultimo. | C031; passende kernklasse: Afleidingsregel |
| E04 | [0,90) Als de betalingstermijn van een aanslag is gesteld op één maand of is gesteld op zes weken | Voorwaarde | voorstel | Alternatieve termijnen in bereik van uitleg. | geen kern; passende kernklasse: geen |
| E05 | [113,172) als de dagtekening van een aanslagbiljet valt op 31 oktober | Voorwaarde | voorstel | Voorwaarde binnen voorbeeld. | geen kern; passende kernklasse: geen |
| E06 | [292,325) Als de dagtekening 28 februari is | Voorwaarde | voorstel | Voorbeeldvoorwaarde, schrikkeljaar bepaalt gevolg. | geen kern; passende kernklasse: geen |
| E07 | [435,491) tenzij het jaartal aangeeft dat het een schrikkeljaar is | Voorwaarde | voorstel | Uitzondering met afzonderlijke vervalmomenten. | C023; passende kernklasse: Voorwaarde |
| E08 | [556,659) Als de dagtekening van het aanslagbiljet valt op een andere dag dan de laatste dag van de kalendermaand | Voorwaarde | voorstel | Algemene voorwaarde; vergelijkingsbereik behouden. | C032; passende kernklasse: Voorwaarde |
| E09 | [737,800) op de dag die hetzelfde nummer heeft als dat van de dagtekening | Tijdsaanduiding | voorstel | Relatieve datumomschrijving; vergelijking is geen losse als-voorwaarde. | geen kern; passende kernklasse: geen |
| E10 | [774,800) als dat van de dagtekening | Voorwaarde | uitsluiten | Vergelijkende aanvulling zonder eigen predicatie; uitsluiten als zelfstandige voorwaarde. | geen kern; passende kernklasse: geen |
| E11 | [751,767) hetzelfde nummer | Operator | open | Gelijkheidsvergelijking tussen dagnummers; operanden in samenhang. | C047; passende kernklasse: geen |
| E12 | [54,63) één maand | Tijdsaanduiding | voorstel | Duur: behoud verschil met zes weken. | C003; passende kernklasse: Tijdsaanduiding |
| E13 | [81,90) zes weken | Tijdsaanduiding | voorstel | Duur: niet gelijkstellen aan maand of parameter voor dezelfde functie. | C004; passende kernklasse: Tijdsaanduiding |
| E14 | [162,172) 31 oktober | Tijdsaanduiding | open | Datum in voorbeeld; geen generieke uiterste betaaldatum. | geen kern; optie: C008; passende kernklasse: geen |
| E15 | [219,230) 30 november | Tijdsaanduiding | open | Resultaat van maandvoorbeeld. | geen kern; optie: C011; passende kernklasse: geen |
| E16 | [279,290) 12 december | Tijdsaanduiding | open | Resultaat van zeswekenvoorbeeld. | geen kern; optie: C014; passende kernklasse: geen |
| E17 | [376,384) 31 maart | Tijdsaanduiding | open | Maandultimo-uitkomst bij 28 februari buiten schrikkeljaar. | geen kern; optie: C019; passende kernklasse: geen |
| E18 | [529,537) 28 maart | Tijdsaanduiding | open | Maanduitkomst bij 28 februari in schrikkeljaar. | geen kern; optie: C028; passende kernklasse: geen |
| E19 | [802,882) Als de dagtekening bijvoorbeeld 15 maart is, vervalt de termijn dus op 15 april. | Afleidingsregel | open | Expliciet maartvoorbeeld van de maandregel. | geen kern; passende kernklasse: geen |
| E20 | [883,978) Is de betalingstermijn zes weken en is de dagtekening 15 maart, vervalt de termijn op 26 april. | Afleidingsregel | open | Zeswekenvoorbeeld naast het maandvoorbeeld. | geen kern; passende kernklasse: geen |
| E21 | [643,659) de kalendermaand | Tijdsaanduiding | open | Temporeel referentiekader; afbakening met laatste dag beoordelen. | C039; passende kernklasse: Tijdsaanduiding |
| E22 | [4,23) de betalingstermijn | Rechtsobject | uitsluiten | Een naamwoordgroep is niet vanzelf een rechtsobject; primair temporele eigenschap. | C001; passende kernklasse: Rechtsobject |

### Alle dertien klassen beoordeeld

| Klasse | Beoordeling |
|---|---|
| Rechtssubject | Geen expliciete drager van rechten/plichten; tijdseenheden zijn geen rechtssubjecten. |
| Rechtsobject | Beoordeel het object van de centrale norm, niet iedere zelfstandige naamwoordgroep. |
| Rechtsbetrekking | Hoofdzakelijk temporele uitwerking; niet elke voorbeeldzin is een zelfstandige bevoegdheid of verplichting. |
| Rechtsfeit | Tijdsverloop met rechtsgevolg onderzoeken; dagtekening is niet automatisch een rechtshandeling. |
| Voorwaarde | Toepassingsvoorwaarden inclusief uitzonderingen en ontkenning onderzoeken. |
| Afleidingsregel | Algemene kalenderregel in derde zin; overige zinnen bevatten conditionele uitleg en concrete voorbeelden. |
| Variabele en variabelewaarde | Datum/aantal kunnen analytische invoergegevens zijn; geen dubbel label bij dezelfde temporele functie. |
| Parameter en parameterwaarde | Geen extra parameter uitsluitend omdat een termijn een vaste duur heeft (JAS-PRIORITY-001). |
| Operator | Alleen met benoemde operanden en bereik; geen los of/en/als zonder functie. |
| Tijdsaanduiding | Duur/startpunt/vervalmoment met de dragende context. |
| Plaatsaanduiding | Geen plaatsbepaling in eigen tekst. |
| Delegatiebevoegdheid en delegatie-invulling | Geen delegatieformule; een verwijzing naar de wet is geen delegatie. |
| Brondefinitie | Titel Begrip maand bij betalingstermijn is op zichzelf geen definitie-aanhef; inhoud onderzoeken als uitleg/afleiding. |

### Open beoordelingsvragen

- Welke zinnen dragen algemene uitleg en welke illustreren die met concrete data?
- Moeten voorbeelddata markeringen krijgen als illustratie, en hoe blijft dat zichtbaar in de huidige uitvoer?
- Hoe worden de schrikkeljaarvertakking en het verschil tussen maand en zes weken verbonden?

## Geraadpleegde contextpassages

Deze vijftien passages zijn uit dezelfde graafophaling geselecteerd; de technische ophaalquery haalt de bronboom op, maar de inhoudelijke selectie blijft hieronder expliciet. Alle teksten en hashes staan in bronnen.json. Niet-gebruikte bronboomnodes zijn geen onderdeel van de analysetekst of de meting.

| ID | Reden |
|---|---|
| IW-2-1-i | Definitie ontvanger. |
| IW-2-1-k | Definitie belastingschuldige. |
| IW-2-1-m | Reikwijdte belastingaanslag. |
| IW-3-1 | Taak ontvanger. |
| IW-8-1 | Bekendmaking; partijen en functie aanslagbiljet. |
| IW-8-5 | Verschuldigdheid onderscheiden van invorderbaarheid. |
| IW-9-2 | Afwijkende termijnen. |
| IW-9-6 | Uit te betalen bedrag: andere termijnberekening. |
| IW-9-7 | Dagtekening vóór belastingjaar. |
| IW-9-10 | Uitsluiting Algemene termijnenwet. |
| IW-9-12 | Bezwaar/beroep schorst betalingsverplichting niet. |
| LI-1.1 | Status van de Leidraad: beleidsregels. |
| LI-9 | Aanhef voor context van bronnode. |
| LI-9.4 | Dagtekening is niet ontvangst; versnelde invordering. |
| LI-def-wet | Resolveert de wet in §9.1. |

Open bronvragen:

- IW art.10 lid1: versnelde invordering; relevant bij toepassing, niet uitputtend onderzocht.
- Concrete aanwijzing ontvanger: niet nodig voor abstracte rol, wel bij uitvoering.
- Afwijkende boekjaren §9.1: toepassingsbereik en concrete kalender vragen deskundige beoordeling.
