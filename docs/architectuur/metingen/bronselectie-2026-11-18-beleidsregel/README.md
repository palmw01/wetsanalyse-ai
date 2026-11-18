# Bronselectie – de beleidsregel bij het artikel van de kern (18 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-18-afhankelijkheden/`](../bronselectie-2026-11-18-afhankelijkheden/README.md)

## Waarom

Na de vorige meting bleven de beleidsregels bij een kernartikel de grootste groep nodige bepalingen die geen methode vond.
Het gaat om Leidraad 9.1–9.3, 24.3, 24.6.3, 26.2.1, 36.6.1 en 49.3.1.

Zo'n beleidsregel hangt in de graaf niet aan het kernlid. Ze hangt aan het artikel: Leidraad-artikel 49 ("In aansluiting op
artikel 49 van de wet beschrijft dit artikel het beleid over:") verwijst naar Iw artikel 49, en de subdivisies staan
eronder. `verwijzing_in` vond een deel daarvan, maar bracht ook de rest van de Leidraad mee.

#1723 voegde de methode `beleidsregel` toe, standaard uit. Ze zoekt de beleidsregel die naar het artikel van de kern
verwijst en onderdelen heeft, of het Leidraad-artikel waarin de kern zelf staat. Daaruit neemt ze twee soorten onderdelen:

- onderdelen die een kernbepaling noemen;
- onderdelen waarvan de kop van het opschrift in de tekst van de kern staat.

Per beleidsregel stelt ze hoogstens zes onderdelen voor, en van een onderdeel met een passend onderdeel daarbinnen het binnenste.

## Wat er gemeten is

`azure-infra` → `eval` → `bronselectie_afhankelijkheden`:
`--afhankelijkheden standaard,standaard+beleidsregel,standaard+verwijzing_in`. Gedraaid op acceptatie, live tegen de graaf,
op commit `1dba1c1d` (run 44318153777).

- `standaard` = verwijzing uit, definitie, opschrift, `lid_verwijzing` en opbouw.
- De vorm is die van de vorige meting: de verwachte kern per deelvraag, zonder model.
- Het gaat om dezelfde tien sets. De verwachtingen zijn nog concept.

## Uitkomst

Gevonden + via het artikel, van het aantal nodige bepalingen (kandidaten tussen haakjes):

- Bezwaar/ontvankelijkheid: 2+1/3 (42) | 2+1/3 (42) | 2+1/3 (47)
- Bestuurdersaansprakelijkheid: 0+0/3 (50) | **1+0/3 (61)** | 0+0/3 (68)
- Invorderbaarheid: 0+1/3 (13) | 0+1/3 (15) | 0+1/3 (15)
- Kwijtschelding: 5+0/7 (50) | **6+0/7 (69)** | 5+0/7 (59)
- Verrekening: 1+0/7 (54) | **2+0/7 (61)** | 1+0/7 (58)
- Rekeningafspraken: 0+0/2 (54) | 0+0/2 (54) | 0+0/2 (56)
- Termijnen: 2+0/8 (25) | **5+0/8 (32)** | 5+0/8 (41)
- LB-07: 3+2/7 (18) | 3+2/7 (18) | 4+1/7 (23)
- LB-08: 2+6/14 (145) | 2+6/14 (145) | 2+6/14 (153)
- LB-09: 3+0/5 (51) | 3+0/5 (51) | 3+0/5 (59)
- **Totaal: standaard 18+10/59 (502) | +beleidsregel 24+10/59 (548) | +verwijzing_in 22+9/59 (579)**

`beleidsregel` vindt 6 nodige bepalingen meer, voor 46 kandidaten meer (+9%), en is op geen enkele set slechter:

- **Leidraad 9.1, 9.2 en 9.3** (termijnen): ze noemen artikel 9, vijfde, zesde en zevende lid.
- **Leidraad 49.3.1** "Wanneer in gebreke" (bestuurdersaansprakelijkheid): Iw 49 lid 1 noemt "in gebreke".
- **Leidraad 26.2.1** "Vermogen en kwijtschelding particulieren": een onderdeel naast de kern 26.2.3 en 26.2.4.
- **Leidraad 24.6.3** "Instemming of weigering met een cessie of verpanding" (verrekening): naast de kern 24.6.1.

`verwijzing_in` vindt er 4 meer, voor 77 kandidaten meer.

## Besluit

`beleidsregel` gaat standaard aan (`bronnen_vinden.STANDAARD`). `verwijzing_in` blijft uit.

## Wat nog mist

- **Twee beleidsregels.** Leidraad 24.3 "Reikwijdte van de verrekening" en 36.6.1 "Bewijslastverdeling en
  bestuurdersaansprakelijkheid" noemen geen kernbepaling, en de kop van hun opschrift staat niet in de kern.
- **Leden van een ander artikel zonder verwijzing in de graaf:** Awb 4:93 leden 1, 3 en 5; Iw 24 leden 5 en 8; Awb 4:13,
  4:86, 4:114, 5:41 en 5:46; en Awir 16 en 28.
