# ADR-016 A6: slotmeting (bundel 130 en 131, 15 nov 2026)

Soort: *meting*, licht regime. Alleen de opdrachten die de laatste fixes raken, één run, plafond 1,5M. De gebruiker gaf
akkoord met "1,5M". Hiermee sluit A6 af; wat nog niet goed is, staat in de slotlijst onderaan.

- **Code:** graph-qa op `81bee0d1`:
  - bundel 130 (#1559): de crash bij V04;
  - bundel 131 (#1561): F03, regiekinderen die hun delegatie onthouden, en citaten die bij uitspraken de dragende
    passage tonen.

  De centrale agent staat op `aan`. Het meetscript vraagt hem per run expliciet (`agentvorm: centraal`). Het model is
  `claude-sonnet-4-6`.
- **Nulpunt:** de korte meting na A6 ([`../centrale-agent-2026-11-15-na-a6/na-a6.md`](../centrale-agent-2026-11-15-na-a6/na-a6.md), #1557).
- **Gedraaid:** V04, F03, F02 en S01.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen. De graaf was gevuld.
- **Totaal:** 918.611 tokens. Er kwam geen `BUDGET_OP`, en de wachter (1,45M) hoefde niet in te grijpen.

## Uitkomst

| Opdracht | Nu | Account | Na A6 (#1557) |
|---|---|---|---|
| V04 | **goed** | 0 | crash (`ValueError`) |
| F03 | **goed** | 161k | fout ("niets veranderd") |
| F02 | **goed** | 425k | deels (geen kern per uitspraak) |
| S01 | **fout** | 332k | deels (citaten over procedure) |

- **V04 (goed).** Hij crasht niet meer. In code, voor 0 tokens, vraagt Lex: "Artikel 36 van de Invorderingswet 1990 kan
  meer dan eens gewijzigd zijn. Welke wijziging bedoel je?" Als opties geeft hij de laatste wijziging (Stb. 2009, 610, in
  werking 2010-07-04) of zelf een datum of wijzigingswet noemen.
- **F03 (goed).** "Alleen deelvraag 1 is veranderd", met per deelgesprek de stand: in 1 is doorgevraagd, 2 en 3 zijn
  ongewijzigd. Dat klopt. Lex start niets opnieuw en kost 37k. `delegatie_stand` wordt nog steeds niet aangeroepen; de
  stand komt uit de context van de beurt.
- **F02 (goed).** Zes arresten van de Hoge Raad, elk met de kern over de rente:
  - HR:2005:AS5040;
  - HR:2009:BI2929;
  - HR:2017:341;
  - HR:2018:1789;
  - HR:2023:1271;
  - en HR:2017:530, waarvan Lex zegt dat hij niet volledig gelezen is.

  Er komt geen nieuwe keuzevraag. Lex zegt ook wat niet gelezen is (de rondegrens) en wat met art. 81 RO is afgedaan.
  De vier citaten:
  - twee dragen het oordeel: HR:2005:AS5040 r.o. 3.3, en de kern van HR:2009:BI2929;
  - één is een inhoudsindicatie;
  - één beschrijft de feiten (r.o. 3.1.1).
- **S01 (fout, en een regressie).** Het kind las zes uitspraken en twee conclusies. Zijn rapport (40k tekens) vat ze per
  stuk samen over de melding, en wat het over HR:2023:1371 zegt, klopt.
  - Het eindantwoord zegt "Hieronder een overzicht per gelezen stuk", maar geeft dat overzicht niet.
  - Er staan alleen vier citaten onder, en dat zijn alle vier trefwoordregels uit de inhoudsindicatie, zoals
    "Artikel 36 IW 1990; bestuurdersaansprakelijkheid; bewijspositie bestuurder; …".
  - Volgens de meting stond er 4.345 tekens tekst naast het sjabloon (`tekst_ernaast`), en die tekst toont de werkplek
    niet. Daar zaten de samenvattingen waarschijnlijk in.

  Na A6 had S01 wel samenvattingen per arrest.

## De citaten bij uitspraken

Gevraagd was of de citaten nu de passage tonen die de samenvatting draagt, en niet de procedure, de feiten of een losse
voetnoot.

- **F02: 2 van de 4 dragen het oordeel.** Na A6 was dat 0 van de 4; toen waren het alleen procedurezinnen.
- **S01: 0 van de 4.** Na A6 waren het procedure- en feitenzinnen, nu trefwoordregels.
- **Losse voetnoten:** geen; daar ging het in deze opdrachten ook niet om.
- **Letterlijk:** alle 8 citaten staan in de uitspraak.

## De controle per stuk

- **Ze draaide twee keer:** bij F02 en bij S01 (2,7k). Ze meldde **geen enkele keer `tegenspreekt`**: geen valse en geen
  terechte.
- **Sinds de nieuwe regel** heeft ze in totaal vier keer gedraaid (run 3 deel 2, de meting na A6 en hier), met **0
  meldingen `tegenspreekt`**. Of dat komt doordat de regel strenger is, of doordat er niets te melden viel, valt uit
  vier keer niet te zeggen. De valse meldingen uit run 3 deel 1 zijn in elk geval niet teruggekomen.
- **Bij S01** staan twee andere markeringen:
  - "die de passages van dat stuk niet dragen" bij PHR:2025:435;
  - "zonder passage van dat stuk in het rapport" bij PHR:2025:426.

  Die komen van de toets op dragende passages, niet van de controle per stuk. In het eindantwoord staat geen duiding van
  die twee stukken, dus beoordelen kan ik ze niet. De tweede klopt wel met wat het antwoord zelf zegt: "geen passages
  van dat stuk in het rapport".
- **Het kind van S01** heeft er 12, waarvan 4 keer: "met 'melding' uit de vraag, dat niet in dat stuk staat". Dat is een
  nieuwe vorm van de toets, en bij uitspraken die zijdelings over de melding gaan, is hij terecht.

## Slotlijst: wat na A6 openstaat

Kort en concreet, om over te nemen in `docs/PLAN.md`.

1. **S01: de samenvattingen per uitspraak vallen weg.** De tekst die het model naast het sjabloon `antwoord_extern`
   schrijft (`tekst_ernaast`, hier 4,3k tekens), toont de werkplek niet. Het antwoord belooft een overzicht per stuk en
   geeft het niet. Een regressie na #1561.
2. **Citaten bij uitspraken tonen vaak nog geen dragende passage.** Het gaat om trefwoordregels uit de inhoudsindicatie
   (S01, P01), feiten en procedure (F02 deels, P02). De aanwijzing moet de passage kiezen waarop de samenvatting rust.
3. **Vragen naar boven: 2 van 4 in de eindmeting.** Een kind dat tegen zijn rondegrens loopt, stopt in plaats van te
   vragen (V03 in run 3). V04 vraagt nu wel, maar dat is pas na de eindmeting gemeten.
4. **De controle per stuk is te weinig gemeten.** Vier keer met de nieuwe regel, 0 meldingen. Er is een gerichte set
   nodig met bekende tegenspraken, om te weten of ze nog iets vindt.
5. **De toets op dragende passages markeert juiste samenvattingen.** HR:2023:1371 kreeg in S01 en F01 steeds "die de
   passages van dat stuk niet dragen", terwijl de samenvatting klopt.
6. **`delegatie_stand` wordt niet aangeroepen.** F03 klopt nu dankzij de context van de beurt, maar het gereedschap
   blijft onbenut. Bepaal of de set het nog moet eisen.
7. **De kinderen lopen tegen hun rondegrens aan.** Stukken blijven daardoor ongelezen: S04 (Leidraad 22.8.9 en verder),
   F02 en P01. Ze kosten 200–300k per kind.
8. **P01: het eindantwoord maakt van een rijk rapport één alinea.** De vier arresten uit het rapport over de rechtspraak
   worden niet per uitspraak samengevat.
9. **Kleine dingen:**
   - E05 gaat nog via `duiding`;
   - bij E08 staat een kale IRI als vindplaats;
   - E03 krijgt twee sjabloonweigeringen (`genoemd_in_tekst`);
   - K18 heeft 61 keer `onbevestigd` op artikelnummers.
10. **De set (na A6):**
    - K03 en K09 verwachten "14 dagen" waar "veertien dagen" juist is;
    - S02 meet geen delegatie (vervang hem door een opdracht die een subagent nodig heeft);
    - F05 en S04 eisen een citaat of elk onderdeel gelezen, en dat staat niet in alle "goed"-teksten even scherp.

## Bestanden

- `slot-runs.jsonl`: de vier opdrachten (`centrale_agent_vat.py`). `per_rol` dekt alleen de laatste beurt.
- `slot-kinderen.jsonl`: de twee kindruns (F02, S01) zonder tekst. De drie kinderen van de regie (F03) kostten 0 tokens
  en staan er niet in.

De ruwe runs staan niet in de repo.
