# ADR-016: korte meting na A6 (bundel 128 en 129, 15 nov 2026)

Soort: *meting*, licht regime: alleen de opdrachten die de fixes raken, één run, plafond 2M. De gebruiker gaf akkoord met
"Geraakte opdrachten, 2M".

- **Code:** graph-qa op `45bba137` (bundel 129, #1556, met de fixes van #1555; daarvoor bundel 128, #1553). De centrale
  agent staat op acceptatie op `aan`. Het meetscript vraagt hem per run expliciet (`agentvorm: centraal`). Het model is
  `claude-sonnet-4-6`.
- **Nulpunt:** run 3 van A6 ([`../centrale-agent-2026-11-15-a6-eind/a6-eind.md`](../centrale-agent-2026-11-15-a6-eind/a6-eind.md)).
- **Gedraaid:**
  - V03, V04, F02, F03 en F05;
  - daarna S01 en F01, om de controle per stuk vaker te laten draaien.

  F01 laat in zijn opzet S01 nog eens draaien. P02 en M06 pasten niet meer binnen het plafond.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen. De graaf was gevuld.
- **Totaal:** 1.905.091 tokens. Er kwam geen `BUDGET_OP`, en de wachter (1,95M) hoefde niet in te grijpen.

## Uitkomst

| Opdracht | Nu | Account | Run 3 | Wat er gemeten is |
|---|---|---|---|---|
| V03 | **goed** | 319k | fout, 351k | per deelvraag een memorie van toelichting gelezen en samengevat |
| V04 | **niet gemeten (fout in de keten)** | 0 | deels, 193k | de beurt faalt na 259 ms met een `ValueError` |
| F02 | **deels** | 385k | fout, 121k | geen nieuwe keuzevraag meer, maar geen kern per uitspraak |
| F03 | fout | 162k | fout, 190k | nu "niets veranderd", terwijl deelvraag 1 wel gewijzigd is |
| F05 | **goed** | 107k | deels, 107k | nu met 9 citaten uit de Leidraad 24.x |
| S01 | deels | 337k | deels, 373k | citaten, maar alleen over procedure en feiten |
| F01 | goed | 595k | goed, 572k | zoals in run 3, nu met 22 citaten |

- **V03 (goed).** Eén kind `algemeen` (256k) las drie memories van toelichting en vatte ze per deelvraag samen:
  - kst-33402-3, het bodemrecht en de mededelingsplicht van het Belastingplan 2013;
  - kst-31124-3, waar artikel 24 als grondslag voor verrekening genoemd wordt;
  - kst-34786-3, de vordering op derden van het Belastingplan 2018.

  Lex zegt zelf wat ontbreekt: de oorspronkelijke MvT valt buiten de zoekdienst, en voor artikel 24 is er geen eigen
  toelichting. Er kwam geen vraag naar boven, maar die was ook niet nodig: het kind kwam niet aan de rondegrens. De
  centrale agent bleef op 64k.
- **V04 (niet gemeten).** De run (`103359ba…`) heeft route `onbekend`, 0 modelrondes en `uitkomst: fout`. De melding
  is: "Er ging iets mis bij het beantwoorden". In run 3 deel 2 ging dezelfde vraag zonder fout. De logs kon ik niet
  lezen: de Grafana-toegang ontbreekt in deze sessie. Een tweede poging paste niet binnen het plafond.
- **F02 (deels).** Op "De Invorderingswet 1990" gaat het werk nu door, zonder nieuwe keuzevraag. Eén kind las zes
  uitspraken. Maar het eindantwoord zegt "Hieronder de kern per gelezen uitspraak" en geeft daarna alleen twee
  uitspraken, met procedurezinnen als citaat ("Het middel kan niet tot cassatie leiden …"). De kern per uitspraak
  ontbreekt. Het kind markeerde zelf 7 keer `die de passages van dat stuk niet dragen`.
- **F03 (fout, maar anders).** Lex zegt nu: "geen ervan is na de bundel nog gewijzigd. Er is dus niets veranderd". In
  run 3 zei hij dat alle drie gewijzigd waren. Er is in deelvraag 1 doorgevraagd, dus beide antwoorden zijn onjuist.
  `delegatie_stand` wordt nog steeds niet aangeroepen.
- **F05 (goed).** De Leidraad 24.1–24.6, nu met 9 letterlijke citaten.
- **S01 (deels).** Vier arresten, en HR:2023:1371 is juist samengevat. De drie citaten gaan over procedure en feiten
  ("De Hoge Raad heeft partijen in kennis gesteld …", r.o. 2.1, 2.2), niet over de melding. Ook spreekt het antwoord
  zichzelf tegen: eerst "vier uitspraken die zijn gelezen", daarna drie "niet volledig gelezen".

## De controle per stuk

- **Ze draaide één keer:** bij V03 (4,9k), zonder melding. Bij S01 en F01 draaide ze niet, omdat de goedkopere toetsen
  al iets vonden.
- **Sinds de nieuwe regel** (run 3 deel 2 en deze meting) heeft ze twee keer gedraaid, met **0 meldingen
  `tegenspreekt`**: geen valse en geen terechte.
- **De bekende valse melding op PHR:2025:435** kwam niet terug. F01 noemt die conclusie deze keer niet in het
  eindantwoord.
- **De grounding van de kinderen markeert nog vals.** Bij HR:2023:1371 staat in S01 en F01 opnieuw `die de passages van
  dat stuk niet dragen`, terwijl de samenvatting klopt. Dat komt niet van de controle per stuk maar van de toets op
  dragende passages.

## `onbevestigd` bij nummers

Er staan geen dossier- of kamerstuknummers meer als `onbevestigd`. Het kind van V03 had er 0; in run 3 waren dat er 3
("1988", "33004" en "dossier 20588 in 1994-1995").

## Brongetrouw

Getoetst is elk citaat, tegen de officiële tekst van de wet en van elk genoemd stuk. kst-31124-3 kwam pas met een
tweede verzoek binnen.

- **60 citaten**, waarvan **59 letterlijk**.
- **Het ene:** bij V03 een passage uit kst-33402-3 waarin Lex het voetnootcijfer en de voetnoottekst heeft weggelaten.
  De tekst ervoor en erna is letterlijk; zo ging het ook in run 2.
- **Citaten zonder inhoud:**
  - bij V03 twee losse voetnoten ("Kamerstukken I 2011/12, 33 121, J.");
  - bij F02 twee procedurezinnen;
  - bij S01 drie zinnen over procedure en feiten.
- Er is geen onjuiste bron en geen verzonnen citaat.

## Wat er openstaat

1. **V04:** de beurt faalt met een `ValueError`. Dat is een regressie in de keten, met run-id `103359ba…`.
2. **F03:** de stand van de deelgesprekken wordt niet gelezen (geen `delegatie_stand`).
3. **Citaten zonder inhoud bij uitspraken:** S01 en F02. Daar staan procedure en feiten onder het antwoord in plaats
   van de passages die de samenvatting dragen.
4. **F02:** de kern per uitspraak komt niet in het eindantwoord.
5. **De controle per stuk:** nog maar twee keer gemeten, met 0 meldingen. Dat is te weinig om iets over het aantal
   valse meldingen te zeggen.

## Bestanden

- `na6-runs.jsonl`: de zeven opdrachten (`centrale_agent_vat.py`). `per_rol` dekt alleen de laatste beurt.
- `na6-kinderen.jsonl`: de vier kindruns (V03, F02, S01, F01) zonder tekst. De drie kinderen van de regie (F03) kostten
  0 tokens en staan er niet in.

De ruwe runs staan niet in de repo.
