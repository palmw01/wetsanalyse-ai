# Nulmeting bronselectie (stap 0 van het plan Termijnen, 16 nov 2026)

Soort: *meting* · Code: master `7859d2eb` (zoekversie `z4ec70aab4a55`) · Hoort bij:
[onderzoek-bronselectie-termijnen-2026-11.md](../../onderzoek-bronselectie-termijnen-2026-11.md), stap 0

Dit is de stand van de zoekcode, gemeten vóór de ingrepen van het plan. Ze is offline gedraaid tegen opnames van de graaf
van acceptatie, zonder model. Het is een trendmeting: de sets zijn concepten, ze zijn niet geadjudiceerd en ze zijn
allemaal ontwikkelsets. De held-out set `verrekening-concept` is bewust niet gedraaid en heeft nog geen opname.

**Opnames.** `termijnen-deelvragen-concept` en `rekeningafspraken-deelvragen-concept` kregen hun eerste opname
(`--opnemen`, daarna `--aanvullen` voor `--zoekvragen`). De vier oudere sets werden aangevuld met alleen de nieuwe vragen
van `--b2` (6 tot 8 regels per set). Hun bestaande antwoorden bleven ongewijzigd.

## Per deelvraag (`--intake --b2`), recall nodig

Per set de recall nodig, met daarachter de precisie tussen haakjes.

- **Termijnen**: woordenroute 0,00 (0,04), zoekvragen 0,06 (0,08), met verwijzingen 0,19 (0,15), met onderscheidend 0,12 (0,12). De pool van de woordenroute is 1,00.
- **Rekeningafspraken**: woordenroute 0,14 (0,03), zoekvragen 0,29 (0,05), met verwijzingen 0,43 (0,06), met onderscheidend 0,14 (0,03). Pool 1,00.
- **Bestuurdersaansprakelijkheid**: woordenroute 0,22 (0,09), zoekvragen 0,44 (0,22), met verwijzingen 0,28 (0,12), met onderscheidend 0,22 (0,09). Pool 0,91.
- **Bezwaar/ontvankelijkheid**: woordenroute 0,53 (0,25), zoekvragen 0,40 (0,19), met verwijzingen 0,60 (0,25), met onderscheidend 0,53 (0,25). Pool 0,84.
- **Invorderbaarheid (deelvragen)**: woordenroute 0,36 (0,28), zoekvragen 0,46 (0,19), met verwijzingen 0,36 (0,30), met onderscheidend 0,36 (0,28). Pool 0,94.
- **Kwijtschelding**: woordenroute 0,10 (0,06), zoekvragen 0,33 (0,22), met verwijzingen 0,10 (0,04), met onderscheidend 0,10 (0,06). Pool 0,33.

De zoekvragenroute (PR 5) is wat de bronnenrun met een gekozen gebeurtenis doet. De woordenroute (`bepaling_opties`) is
de route zonder gebeurtenis. De vlaggen `verwijzingen` en `onderscheidend` werken alleen op de woordenroute.

## Wat opvalt

- **Op vijf van de zes sets vindt de woordenroute vrijwel alles, maar ze rangschikt het slecht.** Haar pool haalt 0,84 tot
  1,00 (behalve Kwijtschelding, waar de woordenkloof speelt). De top 8 haalt daar 0,00 tot 0,53 van. De verliezen zitten
  dus in de rangschikking, niet in het zoeken.
- **Bij Termijnen kiest de woordenroute per deelvraag ongeveer één bepaling per regeling** (Awb 8:80b, AWR 30fa, Iw 16,
  Awir 30, Uitv.reg. 8, Leidraad 26.1.9 …). Zes regelingen in het zoekbereik krijgen om de beurt een plaats
  (`per_regeling`), ook als ze geen sterke treffer hebben. Zonder `per_regeling` gaat Termijnen van 0,00 naar 0,06.
- **De zoektermen van DV3 missen het onderscheidende woord.** Een deelvraag zoekt op hoogstens zes termen
  (`MAX_TERMEN`), in de volgorde van de zin: "werkt, verrekening, negatieve, voorlopige, aanslag, bedragen". Het woord
  "betalingstermijnen" valt erbuiten, terwijl een vulwoord als "werkt" blijft.
- **`verwijzingen` helpt op vier van de zes sets** (Termijnen, Rekeningafspraken, Bestuurdersaansprakelijkheid, Bezwaar)
  en verandert niets op Invorderbaarheid en Kwijtschelding. Dat geldt op de woordenroute; in de bronnenrun met een gekozen
  gebeurtenis heeft de vlag geen effect (O1 in het onderzoek). `onderscheidend` verandert alleen Termijnen, en daar
  licht.
- **Zoekvragen bij Termijnen**: de gebeurtenis *invordering* staat bij Lex op plek 4 van de voorstellen. De grondslag
  (zoekvraag a) vindt niets van de set. De pool vindt 0,29 en raakt 6 van de uitgesloten bepalingen.

De bestanden in deze map zijn de rapporten van `eval/bronselectie_eval.py`, ongewijzigd.
