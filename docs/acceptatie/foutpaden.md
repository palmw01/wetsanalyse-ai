# Foutpaden K1–K10 als scenario's

Lex Bench §20.5 stap 5, keten 5. De foutpaden komen uit het testplan keten-e2e
([§2.1](../architectuur/testplan/keten-e2e.md)); dit bestand maakt er draaiboeken van. Elk scenario is een reis plus een
verstoring. Je toetst wat de jurist ziet en wat er níet mag gebeuren, nooit een exacte tekst. De scenario's gelden voor
elke casus.

risico: R01, R03, R04, R05, R07, R08, R09, R12, R14, R18, R19

## Waar elk scenario draait

| | foutpad | waar | stand |
|---|---|---|---|
| K1 | de graaf is leeg midden in een reis | graph-qa-suite | `tests/test_foutpaden_keten.py` |
| K2 | een deploy van graph-qa halverwege een beurt | graph-qa-suite, en de gedeelde store | `test_foutpaden_keten.py` (afbraak); `test_runstore_postgres.py` (wezen, afsluiten) |
| K3 | een model-400 of een 429 | graph-qa-suite | `test_foutpaden_keten.py`; de herhaling in `test_http_beleid.py` |
| K4 | een gedeeld account | straat, met akkoord | scenario hieronder; vangrail en `opruimen` in de acceptatie-MCP |
| K5 | het tokenbudget raakt op | graph-qa-suite | `test_foutpaden_keten.py` (de start); `test_reeks.py` (halverwege een reeks) |
| K6 | een connector valt uit of is traag | graph-qa-suite (deels), straat | scenario hieronder |
| K7 | herladen en een tweede tabblad | straat, met akkoord | scenario hieronder |
| K8 | inloggen tot en met de eerste beurt | browsertest tegen een echte api | nog te bouwen; scenario hieronder |
| K9 | een rollback onder last | straat, met akkoord | scenario hieronder |
| K10 | een analist tegenover een beheerder | straat, met een analistaccount dat de gebruiker kiest | scenario hieronder |

Een scenario op de straat draait als onderdeel van de vaste reis (testplan keten-e2e §5 punt 4). Dat gebeurt alleen met
akkoord, op het account van de gebruiker met het runvoorvoegsel `acc-test-…` (alleen eigen objecten, alleen die
opruimen, nooit in bulk: [`testaccount.md`](testaccount.md)), en nooit op
productie. Wie het draait, noteert per stap de uitkomst in het logboek van de run (`logboek_aanvullen`).

## De scenario's in de suite

**K1 – De graaf is leeg.** Een annotatie terwijl GraphDB leeg is opgekomen.
- *Verwacht:* de jurist leest dat de kennisgraaf niet beschikbaar is en vanzelf terugkomt. Er komt geen voorstel en geen
  doel, de beurt eindigt met één `done` (mislukt), en dezelfde melding staat in het gesprek.
- *Mag niet:* "Er ging iets mis", de kale tekst van GraphDB, of een element zonder bron.
- *Gevonden bij het bouwen:* het annoteren leest de bron in code, buiten `dispatch` om, en kreeg de algemene melding.
  Opgelost in `agent.agent._foutmelding`, voor elke route die de graaf zelf leest.
- *Nog op de straat:* de stand van een eerdere deelvraag blijft staan, en na de graafwacht gaat het verder.

**K2 – Een beurt die halverwege afbreekt.**
- *Verwacht:* wat al getoond is, blijft staan. Er komt een fout zonder interne tekst en precies één `done` (mislukt). De
  afbraak wordt in het gesprek vastgelegd, zodat herladen hem toont, en een nieuwe beurt op hetzelfde gesprek kan meteen.
- Bij een deploy verdwijnt de replica. De gedeelde store rondt de lopende runs af en legt ze vast (`sluit`), en een run
  zonder hartslag eindigt voor de kijker met een fout en een `done` (de wezen in `test_runstore_postgres.py`).
- *Nog op de straat:* geen half artefact (een half annotatievoorstel, een half werkgebied), en bij een kindgesprek een
  rapport *mislukt* aan de ouder.

**K3 – Een 429 of een 400 van het model.**
- *Verwacht:* een eigen melding ("overbelast", "weigerde"), geen tekst van de provider, één `done` (mislukt), en
  dezelfde melding in het gesprek.
- Herhalen gebeurt alleen waar het beleid dat zegt (`test_http_beleid.py`).
- *Nog open:* dat het verbruik bij een herhaling niet dubbel telt, en bij een 429 midden in een annotatie van tien
  bepalingen dat wat klaar is blijft staan.

**K5 – Het budget is op.**
- *Verwacht:* bij de start een 429 met de reden `budget_op`, de melding en de resetdatum. Er loopt geen run en het model
  wordt niet aangeroepen.
- Halverwege een reeks stopt de reeks met de reden `budget_op` en de lijst van wat is overgeslagen (`test_reeks.py`).
- Een lopende beurt wordt nooit afgekapt: een halve annotatie is erger dan een kleine overschrijding.

## De scenario's op de straat

**K4 – Een gedeeld account.** Twee sessies op hetzelfde account en hetzelfde werkgebied, bijvoorbeeld de agent-jurist en
de agent-gegevensspecialist zonder eigen accounts.
1. Beide starten tegelijk een beurt op hetzelfde gesprek. *Verwacht:* de tweede krijgt 409 met het run_id van de eerste.
2. Beide beslissen over hetzelfde element met dezelfde `verwachte_revisies`. *Verwacht:* de tweede krijgt 412, niemand
   overschrijft stil.
3. Het verbruik per run: de delta van `/api/account/verbruik` om elke run heen, en de `run_id` in het meting-event.
   *Verwacht:* de twee runs zijn te scheiden.
4. Opruimen. *Verwacht:* `opruimen` vindt alleen wat het voorvoegsel van deze run draagt; de vangrail weigert een
   bulkroute en een gesprek zonder voorvoegsel.
- *Mag niet:* een meting die het verbruik van een andere run meetelt, of een wisactie die andermans gesprek raakt (beide
  in november 2026 gebeurd).

**K6 – Een connector die uitvalt of traag is.** Een vraag die een connector nodig heeft (Rechtspraak, Kamerstukken)
terwijl die niet antwoordt of tegen de time-out loopt.
- *Verwacht:* het antwoord zegt welke bron niet antwoordde, vult niets aan uit het geheugen, en de rest van het antwoord
  rust op wat wel binnenkwam.
- In de suite valt de uitval met een nep-connector te veroorzaken; de time-out van een echte bron (LiDO: 211 s gemeten op
  12 nov) alleen op de straat.

**K7 – Herladen en een tweede tabblad.**
1. Herlaad tijdens een lopende beurt. *Verwacht:* de kijker haakt aan met `vanaf` en ziet de beurt af, zonder gat of
   dubbele tekst.
2. Open hetzelfde werkgebied in twee tabbladen en rond in het ene een deelvraag af. *Verwacht:* het andere toont na een
   actie de nieuwe stand of een 412 met een nette melding, nooit een stille overschrijving.
3. Herlaad midden in de bronselectie. *Verwacht:* de stand per deelvraag komt van de api terug.

**K8 – Inloggen tot en met de eerste beurt.** Een browsertest tegen een echte api, niet tegen de gemockte BFF.
1. Zelfregistratie, goedkeuring door een beheerder, eerste login, 2FA instellen, een beurt.
2. Een beheerder zonder 2FA. *Verwacht:* het beheer blijft dicht.
3. Een rollback van de api met een bestaande sessie. *Verwacht:* de sessie werkt door, of de gebruiker krijgt een nette
   nieuwe login.
- *Te bouwen:* de browserregressie mockt `/api/**`; dit scenario vraagt een job met de api en Postgres naast de frontend.

**K9 – Een rollback onder last.** Een beurt loopt, en frontend en graph-qa gaan een revisie terug (`rollback.yml`).
- *Verwacht:* de rooktest is groen (`/api/health?keten=1`), de lopende beurt eindigt als bij K2, en het gesprek is leesbaar
  in de oude versie (N-1).
- Eén keer per release-cyclus, op acceptatie, met akkoord.

**K10 – Een analist tegenover een beheerder.** De vaste reis op een account met de rol `analist`. Het account van de
gebruiker is beheerder, dus dit vraagt een analistaccount dat alleen de gebruiker aanmaakt.
- *Verwacht:* geen beheerroute (403), wel alle stappen van de methode, en het verbruik binnen het budget van de rol.
- Leg in het logboek per stap vast welke route een 403 gaf. Een 403 op een methodestap is een bevinding.
