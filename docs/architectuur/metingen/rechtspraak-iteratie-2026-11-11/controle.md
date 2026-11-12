# Rechtspraak, iteratie – controle na ronde 3 – 12 november 2026

Soort: *controle*, de korte toets van de fixes uit ronde 3 in plaats van een volledige ronde 4 (besluit van de hoofdsessie) ·
Code: acceptatie op master `a995b0c0` (bundel 46, met #1240 tot en met `932548cc`) · Uitvoering: zoals de rondes, vijf vragen,
één run elk, elk in een eigen gesprek.

De ruwe gegevens staan in [`controle-runs.jsonl`](controle-runs.jsonl). Tokens uit het `meting`-event: samen **475.529**.

## Uitkomst: 5 van 5 goed

| # | wat het toetst | vraag | uitkomst | tokens |
|---|---|---|---|---|
| C1 | de grens van het blok per bron (R30) | uitspraken en Kamerstukken bij art. 25 lid 2 Iw | 15 uitspraken en 21 Kamerstukken, elk een eigen blok met zoekvraag en totaal (223 en 46): samen meer dan de oude grens van 25 | 106.487 |
| C2 | een stuk zonder tekst houdt zijn label (K12) | Wat staat er in Kamerstuk 32140, nr. 342? | `alleen_pdf`, zonder model; de bronnenlijst noemt "Kamerstukken 32140, nr. 342", niet "kst-1278484" | 0 |
| C3 | de titel van de nieuwste toestand (I02) | uitspraken bij art. 43 Participatiewet | "Gezocht bij artikel 43 van Participatiewet", niet "Wet werk en bijstand"; 637 uitspraken | 96.405 |
| C4 | een voetnoot is geen bron (B12) | Wat staat er in stcrt-2024-20015-n1? | de bronnenlijst noemt alleen het gelezen stuk, niet de stukken uit de voetnoten | 29.981 |
| C5 | een regeling uit een zoekresultaat is geen bron (I03/I20) | rechtspraak bij art. 3.111 Wet IB 2001 | de kale bron "BWBR0011353" is weg; de lijst arresten van de Hoge Raad over twee pagina's draagt haar zoekvraag en het totaal (36) | 242.656 |

## Opvallend

- **LiDO is traag**: de zoektool deed er in C1 116 s over en in C5 80 s, tegen 1–40 s in de rondes. Dezelfde avond meldden
  Kamerstukken en Staatsblad time-outs bij KOOP. De connector wacht en geeft daarna het goede antwoord; een time-out op die
  schaal zou de lijst onvolledig maken, en dat zegt hij dan.
- **C5 leest de arresten van de Hoge Raad in twee pagina's** en toont er 25 van 36, met de zin dat er nog 11 op te halen zijn:
  begrensd, niet stil.

## Wat deze controle niet zegt

- K17 (een lijst uit meer zoekvragen noemt elke zoekvraag) staat in #1244 en is nog niet uitgerold; die toets volgt.
- Eén run per vraag.

Voor deze controle zijn vijf gesprekken aangemaakt. Er is niets gewijzigd of gewist.
