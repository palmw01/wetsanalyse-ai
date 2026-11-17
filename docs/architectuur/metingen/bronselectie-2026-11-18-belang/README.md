# Bronselectie – het belang van verwijzingen in de woordenroute (18 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-17-grens-120/`](../bronselectie-2026-11-17-grens-120/README.md)

## Waarom

In de rangdiagnose stonden 27 van de 49 nodige bepalingen die de 80 kandidaten niet haalden wel in de woordenroute, maar pas op
plaats 81–400. Een langere lijst helpt het model niet (`bronselectie-2026-11-17-grens-120`), dus de volgorde binnen de lijst
moet beter. In de signalenmeting was het belang van verwijzingen, licht gedoseerd, de sterkste knop na de vertaling.

## Wat er gemeten is

`Zoekprofiel.belang` (#1712, standaard uit) voegt een lijst toe aan de fusie van de woordenroute. Die lijst rangschikt de
bepalingen op hoeveel tekstdelen van buiten het artikel ernaar verwijzen; bij een lid tellen de verwijzingen naar het hele
artikel. Het is één RRF-lijst, geen gewicht, berekend over de voorlopige top (3 × de grens).

`azure-infra` → `eval` → `bronselectie_belang`: `--kandidaten 80,80+belang --rangen`, op acceptatie, live tegen de graaf,
op commit `7501e73a` (run 44201164093). Het model kiest hier niet. De wetstermen kostten 47,5k invoertokens en werden één
keer per deelvraag gevraagd voor beide routes, dus de vergelijking is gepaard. Het gaat om dezelfde tien sets en 38
deelvragen. De verwachtingen zijn nog concept.

## Uitkomst

Nodige bepalingen op de kandidatenlijst bij 80, zonder en met belang:

- Bestuurdersaansprakelijkheid 0,78 → 0,78
- Bezwaar/ontvankelijkheid 0,73 → 0,80
- Invorderbaarheid 0,73 → 0,73
- Kwijtschelding 0,81 → 0,86
- Rekeningafspraken 0,86 → 1,00
- Termijnen 0,50 → 0,56
- Verrekening 0,61 → 0,61
- LB-07 0,60 → 0,65
- LB-08 0,70 → 0,70
- LB-09 0,75 → 0,75
- **Totaal 120 → 125 van 172**, beter op 5 sets en op geen enkele slechter

Zonder belang staan er nu 120 op de lijst, tegen 123 in de vorige meting. De wetstermen verschillen per run, want het model
vertaalt elke keer opnieuw. Daarom staan beide routes in dezelfde run.

## Besluit

Het belang levert op de lijst een kleine, gelijkmatige winst op, zonder verlies. Of het model die extra bepalingen ook
kiest, meet `bronselectie_belang_model`: een gepaarde ronde met dezelfde wetstermen per deelvraag, met en zonder belang.
Daarna besluit ik over de vlag.
