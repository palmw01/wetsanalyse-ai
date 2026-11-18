# Bronselectie – de methoden van de afhankelijkheden vanuit de verwachte kern (18 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-18-afbakening/`](../bronselectie-2026-11-18-afbakening/README.md)

## Waarom

Na de afbakening stonden 11 nodige bepalingen in geen enkele lijst. Een deel daarvan is een lid dat in hetzelfde artikel
naar het kernlid verwijst ("in afwijking van het derde lid") of waarnaar het kernlid verwijst. Iw 24 lid 4 en AWR 67n lid 3
zijn voorbeelden. De graaf kent geen verwijzingen binnen een artikel, dus geen methode vond ze. #1721 voegde de methode
`lid_verwijzing` toe, standaard uit. Deze meting bepaalt of ze aan gaat. `verwijzing_in` meet mee als tweede kandidaat.

## Wat er gemeten is

Per deelvraag zijn de verwachte kernbepalingen als kern genomen, zoals de jurist ze opnam. Daarna draaien de methoden van
de fase van de afhankelijkheden. Er wordt geteld welk deel van de verwachte afhankelijkheden en aanverwante bepalingen er
gevonden is:

- precies of eronder (*gevonden*);
- of alleen via het artikel erboven (*via het artikel*: de jurist opent het artikel en neemt het lid op).

Daarnaast telt hoeveel kandidaten dat kostte. Er zit geen model en geen rangschikking in.

`azure-infra` → `eval` → `bronselectie_afhankelijkheden`:
`--afhankelijkheden standaard,standaard+lid_verwijzing,standaard+verwijzing_in`. Gedraaid op acceptatie, live tegen de graaf,
op commit `3d5dc476` (run 44310055696). Dit zijn dezelfde tien sets als bij de afbakening. De verwachtingen zijn nog concept.
`standaard` was toen verwijzing uit, definitie, opschrift en opbouw.

## Uitkomst

Gevonden + via het artikel, van het aantal nodige bepalingen (kandidaten tussen haakjes):

- Kwijtschelding: 4+0/7 (49) | **5+0/7 (50)** | 4+0/7 (58)
- Bestuurdersaansprakelijkheid: 0+0/3 (46) | 0+0/3 (50) | 0+0/3 (64)
- Invorderbaarheid: 0+1/3 (9) | 0+1/3 (13) | 0+1/3 (11)
- Bezwaar/ontvankelijkheid: 2+1/3 (41) | 2+1/3 (42) | 2+1/3 (46)
- Verrekening: 0+0/7 (52) | **1+0/7 (54)** | 0+0/7 (56)
- Rekeningafspraken: 0+0/2 (52) | 0+0/2 (54) | 0+0/2 (54)
- Termijnen: 2+0/8 (23) | 2+0/8 (25) | **5+0/8 (39)**
- LB-07: 3+2/7 (15) | 3+2/7 (18) | 4+1/7 (20)
- LB-08: 0+6/14 (135) | **2+6/14 (145)** | 0+6/14 (143)
- LB-09: 2+0/5 (43) | **3+0/5 (51)** | 2+0/5 (51)
- **Totaal: standaard 13+10/59 (465) | +lid_verwijzing 18+10/59 (502) | +verwijzing_in 17+9/59 (542)**

- `lid_verwijzing` vindt 5 nodige bepalingen meer, voor 37 kandidaten meer (+8%), en is op geen enkele set slechter.
  Erbij gevonden: BWBR0004766 artikel 9 lid 2 (kwijtschelding), Iw 1990 artikel 24 lid 4 (verrekening), BWBR0019237
  artikel 7 leden 6 en 9 (LB-08) en AWR artikel 67e lid 2 (LB-09).
- `verwijzing_in` vindt er 4 meer: drie bij termijnen en één bij LB-07, waar één via het artikel wegvalt. Dat kost 77
  kandidaten meer (+17%). Het patroon is hetzelfde als bij de meting van 15 okt 2026: winst op één set, ruis overal.

## Besluit

`lid_verwijzing` gaat standaard aan (`bronnen_vinden.STANDAARD`). `verwijzing_in` blijft uit.

## Wat nog mist

De grootste groep die geen methode vindt, zijn de beleidsregels bij een kernartikel: de Leidraad-divisies 49.3.1, 36.6.1,
26.2.1, 24.6.3, 24.3 en 9.1–9.3. Daarnaast missen leden van een ander artikel zonder verwijzing in de graaf: Awb 4:93
leden 1, 3 en 5, Iw 24 lid 5 en 8, en Awb 4:13, 4:86, 4:114, 5:41 en 5:46.
