# ADR-016: het hervatten met de eerdere resultaten (bundel 119, 14 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`, alleen D01, met akkoord van de gebruiker.

- **Code:** graph-qa op `4e2e57a3` (bundel 119, #1506), `CENTRALE_AGENT=meten`. Daarin zit **#1505**, de hervatfix:
  - een hervat kind dat de code afsluit, krijgt `afgesloten`;
  - het plafond geldt per deel;
  - het hervatte deel krijgt de eerdere resultaten mee;
  - het eindantwoord houdt de juiste samenvattingen uit het eerste rapport.
- **Nulpunt:** D01 in de meting van #1504 op `d7bcc889`
  ([`../centrale-agent-2026-11-14-bundel118/bundel118.md`](../centrale-agent-2026-11-14-bundel118/bundel118.md)): 626k.
  Bij bundel 117 (#1501) was het 342k.
- **Hoe gemeten:** dezelfde vraag en dezelfde drie antwoorden als bij bundel 118, in een lokale kopie van de set die
  niet in de repo staat. Het kind stelde twee vragen, dus het derde antwoord is niet gebruikt.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen: de graaf was gevuld.
- **Bewaking:** een kind stopt in de code bij 300k. Het verbruik wordt pas aan het eind van een run geboekt, dus een
  peiler van buitenaf kan een run niet op tijd stoppen. Er stond maar één run op het programma, en bundel 118 kostte
  626k.
- **Totaal:** 635.851 tokens op het account; plafond 1M.

## Kort

| Punt uit #1505 | Uitkomst |
|---|---|
| 1. Een hervat kind dat de code afsluit, krijgt `afgesloten` | **Niet te toetsen.** Het hervatte kind rondde zelf af met een gevuld rapport (`klaar`). De code hoefde niet af te sluiten |
| 2. Het plafond geldt per deel | **Gehaald.** Deel 1 kostte 261k en deel 2 318k, samen 579k. Deel 2 stopte bij het eigen plafond en leverde in de laatste ronde een rapport |
| 3. Het hervatte deel krijgt de eerdere resultaten mee en leest niets opnieuw | **Gehaald.** Deel 2 begint met een context van 69k (bundel 118: 30k). Het haalt zes nieuwe uitspraken op en geen enkele uit deel 1 |
| 4. Het eindantwoord houdt de juiste samenvattingen, zonder "zie toelichting bij" | **Gehaald voor de vorm, deels voor de inhoud.** Geen "zie toelichting bij". Er zijn vijf blokken met inhoud, en HR:2023:1371, :563 en :176 komen terug uit het eerste rapport. Twee samenvattingen bevatten een fout (§*Brongetrouw*) |

| Ook gemeten | Uitkomst |
|---|---|
| De beurt met de vraag eindigt met alleen de kaart | **Gehaald.** Geen modelronde van de centrale agent |
| De vragen komen in één keer | **Gehaald.** Twee vragen in het rapport. Kaart 2 kwam zonder modelronde (0 tokens, < 1 s) |
| Citaten | **10 van 10 letterlijk.** Het zijn wel kopregels van HR:2023:1371 ("HOGE RAAD DER NEDERLANDEN", "tegen") |
| `verify` | *gegrond*, `onbevestigd` 0. De twee fouten hieronder ziet hij niet |
| Kosten | **636k**, tegen 626k bij #1504 (+2 %) en 342k bij #1501 |

**Wat naar T1/A1 gaat:**

1. **Het tweede rapport voegt een melding toe die niet in de uitspraak staat.** Bij HR:2023:563 staat "Bestuurder van
   twee bv's heeft tijdig betalingsonmacht gemeld", en het eindantwoord neemt dat over ("de tijdige melding stond vast").
   In de volledige tekst van de uitspraak komen "betalingsonmacht" en "mededeling" niet voor. Het eerste rapport zei
   alleen dat de zaak "niet primair over de meldingsplicht" gaat, en dat klopte.
2. **Bij HR:2023:181/184 is de bewijslast omgedraaid.** Lex zegt: voor twee tijdvakken was tijdig gemeld, en "voor de
   overige tijdvakken was de bewijslast verlegd naar de ontvanger (art. 36 lid 3)". Volgens de uitspraak deed de BV
   voor twee tijdvakken tijdig en rechtsgeldig mededeling. Artikel 36 lid 3, waarbij de ontvanger kennelijk onbehoorlijk
   bestuur bewijst, hoort bij een tijdige melding, niet bij de overige tijdvakken. De rest van de samenvatting klopt:
   betalingen aan gelieerde schuldeisers, activiteiten overgedragen zonder vergoeding voor goodwill, en de Hoge Raad
   verwijst.
3. **`verify` vangt geen van beide.** Elk stuk is gelezen en heeft een passage, maar de fout zit in een detail van de
   samenvatting, niet in de vraag of er een passage is.
4. **Het veld `stukken` in het tweede rapport is niet bijgewerkt.** Het noemt dezelfde vier stukken als het eerste
   rapport, terwijl deel 2 zes andere las (waaronder HR:2023:181, :183, :184 en PHR:2024:936).
5. **Het kind beperkt zich zelf tot de Hoge Raad en het Parket.** In deze run vroeg het niet naar de instanties, en de
   jurist gaf daar geen beperking. Het tweede antwoord uit de set ("Alle instanties; verder geen beperking.") viel nu
   op de vraag naar het aspect van de meldingsplicht. Het kind noemt de beperking in *Gedaan*, en het eindantwoord zegt
   "bij de Hoge Raad en het Parket". Het is dus zichtbaar, maar de jurist koos het niet.

## Brongetrouw

De samenvattingen in het eindantwoord zijn vergeleken met de volledige tekst via de open data van de Rechtspraak. Alle
genoemde uitspraken zijn van 2022–2024 en zijn door het kind op naam gelezen. Alleen PHR:2025:435 valt buiten de
periode; die staat apart onder *Twijfel en aannames*.

| Uitspraak | Lex zegt | Volgens de tekst | Oordeel |
|---|---|---|---|
| HR:2023:1371 | meldingsplicht binnen twee weken; vermoeden bij niet melden; disculpatie alleen als het niet-melden niet te wijten is; prejudiciële vragen over evenredigheid en goede trouw | r.o. 3.3 en 3.5; de vragen noemen "uiterst moeilijk" en goede trouw | **klopt**. "Hoge drempel" staat er niet letterlijk, maar is een redelijke duiding |
| HR:2023:563 | tijdig gemeld; schikking met de curator; het hof vernietigt op art. 36.1 Leidraad | schikking en Leidraad kloppen; een melding staat er niet in | **deels onjuist** (punt 1) |
| HR:2023:176 en :183 | het hof verminderde wegens schending van het verdedigingsbeginsel; het andere-afloopcriterium; de Hoge Raad vernietigt | zo: het incidentele beroep is gegrond, en de Hoge Raad vernietigt en verwijst | **klopt** |
| HR:2023:181 en :184 | twee tijdvakken tijdig gemeld; bewijslast voor de overige bij de ontvanger; selectieve betalingen; de Hoge Raad verwijst | melding en verwijzing kloppen; de bewijslast is omgedraaid | **deels onjuist** (punt 2) |
| PHR:2024:936 | verjaring; uitstel van betaling voor de aansprakelijkheidsschuld; de A-G concludeert ontkennend | 1.7: "ontkennend"; de grondslag van de aansprakelijkstelling vervalt | **klopt** |

## Per beurt

| Beurt | Wat | Account | Centrale agent | Kind |
|---|---|---|---|---|
| 0 | opdracht → kaart 1 (periode) | 261.064 | 0 modelrondes | deel 1: 7 aanroepen, 13 tools, 261k ruw / 90,7k gewogen warm, `vraag` (2 vragen), begint op 22k |
| 1 | antwoord 1 → kaart 2 (aspect) | 0 | 0 | — |
| 2 | antwoord 2 → hervatten, eindantwoord | 374.787 | 2 modelrondes, 0 tools, 57k ruw / 31,8k gewogen warm | deel 2: 4 aanroepen, 8 tools, 318k ruw / 138,3k gewogen warm, `klaar` met rapport, begint op 69k |

Deel 2 is per aanroep duurder dan deel 1 (69k–94k tegen 22k–61k), omdat het de eerdere resultaten meedraagt. Daardoor
haalt het in 4 aanroepen het plafond, en blijven zes conclusies uit 2022 en PHR:2024:710 ongelezen. Dat staat eerlijk
onder *Niet gelezen*.

## Open punten

- Punt 1 van #1505 (`afgesloten` na het hervatten) is niet gemeten, omdat het kind zelf afrondde.
- Het tokenplafond blijft een trigger, geen grens: deel 2 eindigt op 318k.

## Bestanden

- `b119-delegatie-runs.jsonl`: D01 (één regel, `centrale_agent_vat.py`), met de status en de stukken van beide
  rapporten.
- `b119-kinderen.jsonl`: de twee delen van de kindrun (aanroepen, modellen, ruw, gewogen, beginnende context,
  sjabloon, tools), zonder tekst.
