# JRM-classificaties en het Juridisch Analyseschema

Grondslag: [bronnen](bronnen.md) — J01 H1, H3, H4, H5, J02 §3.2.3, JP03, JP05.

Het JRM 2 ordent de classificaties anders dan het JAS. Deze tabel zegt hoe ze zich verhouden, en waar je ze in Lex
vastlegt. De dertien JAS-klassen blijven het annotatiecontract (zie de skill wetsanalyse).

## Hoofd- en ondersteunende classificaties

| JRM 2 | Soort in JRM | In het JAS (dertien labels) | Waar vastleggen in Lex |
|---|---|---|---|
| Rechtssubject | hoofd | Rechtssubject | markering |
| Rechtsbetrekking | hoofd | Rechtsbetrekking | markering |
| Rechtsfeit | hoofd | Rechtsfeit | markering |
| **Rechtsgevolg** | hoofd (nieuw) | zat in Rechtsfeit | samenhang en scenario (akte), niet als label |
| Afleidingsregel | hoofd | Afleidingsregel | markering |
| **Juridisch relevant feit** | hoofd (nieuw) | — | dossier: feittype, gekoppeld aan markeringen |
| Voorwaarde | ondersteunend (bij subject, betrekking, feit, afleidingsregel) | Voorwaarde | markering |
| Rechtsobject | ondersteunend (bij betrekking en feit) | Rechtsobject | markering |
| Variabele | ondersteunend (bij juridisch relevant feit) | Variabele en variabelewaarde | markering |
| Parameter | ondersteunend (bij juridisch relevant feit) | Parameter en parameterwaarde | markering |
| **Waarde** | vervangt parameter- en variabelewaarde | de helft *waarde* van de paren | markering (het paarlabel), toelichting zegt *waarde* |

Delegatieverlening en delegatie-invulling komen volgens de specificatie in een volgende publicatie aan de orde. Tot
dan blijft de JAS-klasse *Delegatiebevoegdheid en delegatie-invulling* van toepassing. Tijdsaanduiding,
plaatsaanduiding, operator en brondefinitie werkt de specificatie niet apart uit; ook die blijven uit het JAS.

## Hoofd en ondersteunend

De zes hoofdclassificaties beschrijf je elk op zichzelf, maar ze hangen samen. Ze zijn ook de bouwblokken van de
aktes van een scenario. De ondersteunende classificaties hangen aan een hoofdclassificatie: een voorwaarde zonder
subject, betrekking, feit of afleidingsregel waarop zij werkt, is onvolledig.

## Soorten rechtsbetrekkingen: JAS en JRM delen anders in

De twee bronnen verdelen de rechtsbetrekking niet hetzelfde. Zeg welke indeling je gebruikt.

- **Het JAS** (het boek Wetsanalyse) kent vier soorten: aanspraak tegenover verplichting, bevoegdheid tegenover
  gehoudenheid, immuniteit tegenover geen bevoegdheid, en vrijheid tegenover geen aanspraak.
- **De werkversie van het JRM** (J02 §3.2.3) kent er drie: aanspraak tegenover verplichting, verlof tegenover geen
  aanspraak, en bevoegdheid tegenover gehoudenheid. Zij noemt de twee kanten de voordeel- en de nadeelkant, en wijst
  per soort aan welke partij handelt.
- **De specificatie van BZK** (J01) werkt de soorten niet uit.

Het verlof van het JRM komt overeen met de vrijheid van het JAS. De immuniteit heeft in de werkversie geen eigen
soort. Laat een immuniteit die de wetsanalyse onderbouwd heeft vastgesteld, daarom staan, en noteer in het scenario
dat de werkversie haar niet kent (JP05).

## Wat je níét doet

- Rechtsgevolg of juridisch relevant feit als nieuwe JAS-klasse op een markering zetten. In Lex zijn dat geen labels;
  een annotatie met zo'n klasse wordt geweigerd.
- Een rechtsgevolg als afleidingsregel markeren omdat er geen eigen label is. De JAS-klasse volgt uit haar eigen
  omschrijving; het rechtsgevolg leg je vast in de akte.
- Een immuniteit of onbevoegdheid weglaten omdat het JRM die niet uitwerkt: het JAS-boek kent ze wel.
