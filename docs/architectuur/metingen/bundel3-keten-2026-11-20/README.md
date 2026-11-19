# Meting bundel 3: de keten met het model (20 nov 2026)

Soort: *meting*. Code: graph-qa `7c1c1b8c` (#1772) op acceptatie. `:latest` = `sha-7c1c1b8`, en de deploy-job wachtte tot
de revisie draaide. Eén run per bepaling, een gerichte set, het lichte regime.

## Opzet

- **Vraag:** herkent de keten met het model de vormen van bundel 3, en legt ze het skelet zoals bedoeld?
  - een datum uit een duur ("invorderbaar zes weken na …", L-2-1);
  - de telling "zoveel … als" (L-2-1);
  - het tijdstip als waarde (L-2-5);
  - de invoer met volgorde en zonder rechtsobject (L-2-2).
- **Set: blind en buiten Termijnen.** Termijnen is daarmee niet geraakt: de lagen zijn gedeeld per bronnode, en de
  lagen van IW art. 9 en AWR art. 13 zijn van Termijnen. Ik koos bepalingen met dezelfde vormen die nog geen laag
  hadden:
  - IW 1990 art. 52 lid 1 ("is invorderbaar zes weken na de dagtekening van de beschikking");
  - Awir art. 22 lid 2 ("in zoveel termijnen als er na de maand van dagtekening nog kalendermaanden van dat jaar
    overblijven");
  - IW 1990 art. 63b lid 5 (de datumvorm, met een bijzin en een nabepaling erachter).
  - "Wordt aangeduid als" en "zoveel … als er … zijn" staan in de graaf alleen in AWR 13 lid 2 en IW 9 lid 7. Die
    vormen zijn alleen deterministisch getoetst (`tests/annotatieketen/test_keten_vormen_termijnen.py`).
- **Werkwijze:**
  - een testwerkgebied `acc-test-2026-11-20-bundel3` met een gesprek;
  - per bepaling één beurt met `doel: {bron_iri}`;
  - lezen met `weergave` (`vorm=lijst` en `vorm=skelet`);
  - werkgebied en gesprek daarna opgeruimd met `opruimen`.
  - De drie nieuwe lagen blijven staan (voorgesteld, `in_review`): lagen zijn gedeeld en horen niet bij het
    werkgebied.
- **Tokens:** uit het meting-event per run, gecontroleerd tegen de delta van `/api/account/verbruik`
  (4.641.043 → 4.681.500 = 40.457, gelijk aan de som).

## Uitkomst

| Bepaling | Run | Tokens (in + uit) | Rondes | Wat de keten opleverde |
|---|---|---|---|---|
| IW 52 lid 1 | `a92bd344` | 10.629 + 757 | 8 | AR "invorderbaar zes weken na de dagtekening van de beschikking" (bewijs *Datum uit een rechtsgevolg*); "de dagtekening van de beschikking" als Tijdsaanduiding (bewijs *Tijdstip als waarde*), niet als Rechtsfeit; operator "na" in de AR met de dagtekening als operand 2 |
| Awir 22 lid 2 | `778cb6db` | 13.085 + 1.251 | 9 | AR "zoveel termijnen als er … overblijven"; uitvoer "zoveel termijnen"; invoer op volgorde 1–3 ("na de maand", "dagtekening", "dat jaar"), geen rechtsobject; skelet zonder gaten; een voorwaarde aan haar drager |
| IW 63b lid 5 | `d71a5140` | 13.493 + 1.242 | 10 | AR herkend, maar **te lang**: ze liep door tot "…, met overeenkomstige toepassing van de regels … opgelegd" |

Samen 40.457 tokens, zonder cache (`cache_lees` en `cache_schrijf` 0), met `claude-sonnet-4-6`.

## Bevindingen

1. **L-2-1, de datumregel, werkt met het model.**
   - In beide datumbepalingen kiest het model de Afleidingsregel uit de nieuwe kandidaat.
   - De rechtsbetrekking of het rechtsfeit van de hele zin blijft ernaast staan (M-2-1).
   - In beide gevallen koos het model voor de zin Rechtsfeit, niet Rechtsbetrekking. Dat is bestaand gedrag van de
     classifier, en bundel 3 verandert het niet.
2. **L-2-5 werkt.** "De dagtekening van de beschikking" komt als Tijdsaanduiding binnen, niet als Rechtsfeit. De
   jurist koos in Termijnen voor Variabele; de kandidaat biedt beide, en de methode laat de specifiekere klasse
   voorgaan.
3. **L-2-2, de invoer, werkt waar de regel een telling is.** In Awir 22 lid 2 staat de invoer op volgorde, zonder
   rechtsobject, en zonder gat in het skelet.
4. **Een fout in bundel 3, nu hersteld:** de span van de datumregel liep in art. 63b lid 5 door tot het eind van de
   zin.
   - **Oorzaak:** de parser hangt de nabepaling onder de tijdsbepaling, en het eind kwam uit die subboom.
   - **Herstel:** het eind is nu het minimum van tijdsbepaling, moment en eigen zinsdelen (gevolgdetector versie 4),
     met een test op deze zin. Dat is getest, maar niet opnieuw gemeten met het model.
5. **Een gat dat bundel 3 niet dicht:** een datumregel krijgt geen `invoer` en geen `uitvoer`.
   - Het bewijs `DATE_ASSIGNMENT` noemt geen spans voor uitkomst en invoer, zoals `CALCULATION_QUANTITY` dat wel doet.
   - Het skelet van IW 52 lid 1 heeft daardoor alleen een operator.
   - Het plan (L-2-1) zegt: het tijdstip is de invoer, de duur een parameter, de datum de uitvoer. Dat is een
     vervolgstap in `relaties.py`.
6. **Niet gemeten:**
   - "telkens een maand later" (de tijdrelatie);
   - `uitzondering_op` en `toepassing` (die wachten op M-1-1);
   - de vorm "wordt aangeduid als" met het model.

## Gegevens

- Run-id's: zie de tabel. De events staan in de runstore van acceptatie. De lagen staan op de drie bepalingen.
- Code: `7c1c1b8c`. Het herstel van bevinding 4 zit in de PR waarin dit bestand staat.
