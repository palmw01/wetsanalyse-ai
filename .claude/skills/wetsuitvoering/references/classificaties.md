# JRM-classificaties en het Juridisch Analyseschema

Grondslag: [bronnen](bronnen.md) — J01 H1, H3, H4, H5, JP03.

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

## Wat je níét doet

- Rechtsgevolg of juridisch relevant feit als nieuwe JAS-klasse op een markering zetten. In Lex zijn dat geen labels;
  een annotatie met zo'n klasse wordt geweigerd.
- Een rechtsgevolg als afleidingsregel markeren omdat er geen eigen label is (zie de skill wetsanalyse,
  JRM-verrijking).
- Een immuniteit of onbevoegdheid weglaten omdat het JRM die niet uitwerkt: het JAS-boek kent ze wel.
