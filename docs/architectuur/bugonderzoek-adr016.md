# Bugonderzoek centrale agent (ADR-016), vóór bundelen en de eindmeting A6

14 november 2026. Wat er onderzocht is:

- de open PR-stapel van T1/A1: #1514 (geweigerde aanroepen, `beurt_meting`, span), #1516 (annoteren via de centrale
  agent) en #1517 (de opdracht in het deelgesprek, `delegaties`);
- de werkplek-PR #1518 (`claude/werkplek-delegatie`): de voortgang van de delegatie, het api-veld `delegaties`, Grafana;
- de ADR-016-code op `master` (bundels 115–121): `subagent.py`, `nodes/subagent_vervolg.py`, `nodes/antwoord.py`,
  `gelezen.py`, de kinderen en de budgetpoort in `api/main.py`, de delegatieopslag in de api;
- het 2FA-noodherstel #1515.

Een bevinding staat hier alleen als ze in de code aan te wijzen is. B1 is lokaal gereproduceerd met een kleine test; de
andere volgen rechtstreeks uit de regels die genoemd worden. Wat niet aan te tonen was, staat onder *Twijfelgevallen*.
Er zijn geen fixes gebouwd.

Ernst: **meting** = blokkeert (een deel van) de eindmeting A6; **vóór `aan`** = moet opgelost zijn voordat
`CENTRALE_AGENT=aan` gaat; **later** = mag daarna.

## Bevestigde bugs

### B1 – Met twee of meer subagents verdwijnt het rapport van een kind als een ander kind een vraag heeft

**Ernst: meting** voor elk A6-scenario met meer subagents waarvan er één een vraag stelt; anders vóór `aan`.

`tools/graph-qa/agent/nodes/subagent_vervolg.py`, regels 72, 97 en 113–118 (master).

Het scenario:

1. De jurist bevestigt een plan met twee subagents (`sa_start`).
2. Kind A rondt af met een rapport (`klaar`), kind B met een vraag.
3. `_verwerk` geeft `{"paren": paren, "kaart": …}` terug (regel 72).
4. `subagent_vervolg_node` ziet de kaart en vervangt de hele uitkomst door `{"tekst": VOLGENDE, "kaart": …}`
   (regel 113–114). De `paren`, dus het rapport en de `source_trace` van A, vallen weg. De jurist leest alleen "Dank je.
   De subagent heeft nog een vraag." (dat zinnetje staat er ook na een bevestiging, waar het niet past).
5. Na het antwoord hervat de code alleen B (`sub.hervat`), en `_verwerk` geeft `{"paren": [(afloop, kind)]}` (regel 97).
   De bundel `rapporten` heeft één rapport: dat van B.

Het rapport van A staat nergens waar de code het terug kan halen. `Afloop.als_dict()` in `uitkomst.kinderen` draagt
geen rapport, en `Run.resultaat` leeft alleen in het proces van de eerste beurt. Het staat alleen nog in het deelgesprek
van A. De centrale agent vat A dus nooit samen, en `verify` toetst niet tegen wat A las.

Reproductie: zet in de test `Api` van `tests/test_subagent_vragen.py` twee taken en twee kinderen (A `klaar`, B `vraag` met
één antwoord), klik het laatste antwoord en kijk naar `upd["rapporten"]`. Daar staat alleen "1. RAPPORT …" (lokaal
gedraaid op master, 14 nov 2026). `tests/test_subagent_vragen.py::test_met_meer_kinderen_wacht_de_delegatie_zolang_er_een_een_vraag_heeft`
toetst alleen dat de delegatie wacht, niet wat de jurist van de andere kinderen krijgt.

Voorgestelde fix: bewaar per kind wat de bundel nodig heeft bij de delegatie. Dat is de rapporttekst uit
`rapport_tekst` of `rapport_inhoud`, plus de ids van wat het kind las. De `source_trace` zelf is te groot voor de
delegatie: de centrale agent kan die uit de checkpoint van het deelgesprek halen, of bij het hervatten de gelezen stukken
opnieuw in de trace zetten. Laat de hervatting dan alle kinderen met een rapport bundelen, niet alleen het hervatte kind.
Een kleiner alternatief: toon in stap 4 al de rapporten die klaar zijn (de centrale agent vat ze samen) en stel daarna de
vraag als kaart, of zeg in elk geval in de tekst uit code dat A klaar is en waar zijn rapport staat. Zet `VOLGENDE` na een
bevestiging om naar een zin die past.

### B2 – Een subagent heet in `beurt_meting` "supervisor" zolang `CENTRALE_AGENT=meten`

**Ernst: meting** (de cijfers per vorm in de logregel en in Grafana); met `aan` klopt het vanzelf.

- `tools/graph-qa/agent/subagent.py`, regel 434: het `ChatRequest` van een kind heeft geen `agentvorm`.
- `tools/graph-qa/api/main.py`, regel ~384 op #1514: `gemeten(..., agentvorm=vorm_van(settings.centrale_agent, request.agentvorm), subagent=bool(request.profiel))`.

`vorm_van("meten", None)` geeft `"supervisor"`. Op acceptatie (stand `meten`) krijgt dus elk kind van de centrale agent
`agentvorm: supervisor, subagent: true`. Het paneel van #1518 groepeert op `route, agentvorm, subagent` en zet de kinderen
daarmee in de rij van de supervisor. Precies die scheiding wilde #1514 maken (analyse, gat 8). Het gedrag van het kind
verandert niet: `_kies` kiest het profiel op `opdracht` vóór er naar de vorm gekeken wordt. Het meetscript leest de
`meting`-events en geen `agentvorm`, dus de vat-uitkomst raakt dit niet.

Waarom de test het niet ziet: `tests/test_a6_aansluiting.py::test_beurt_meting_noemt_het_model_dat_draaide_en_de_vorm`
geeft `agentvorm="centraal"` zelf aan `_meting`. De weg langs `_stroom_voor` toetst hij niet.

Voorgestelde fix: in `_stroom_voor` heeft een run met `request.profiel` de vorm `centraal` (een kind start alleen vanuit de
centrale agent). Of: zet `agentvorm="centraal"` in het `ChatRequest` van `_draai_kind`. Test het langs `_stroom_voor` met
`centrale_agent="meten"`.

### B3 – De werkplek toont een kind dat niet startte (`niet_gestart`) als "mislukt"

**Ernst: vóór `aan`.**

`frontend/lib/delegatie.ts` (#1518), `STANDEN` (regel 54) en `standVan` (regel 91).

`Afloop.uitkomst` begint als `niet_gestart` (`subagent.py`, regel 142). In `voer_plan_uit` blijft het zo voor een kind dat
niet aan bod kwam omdat het plafond bereikt was (`aflopen[i].reden = "het plafond …"`, geen andere uitkomst). Die waarde
staat in het eind-event (`kinderen`) en in `uitkomst.kinderen` bij de api. `standVan` kent `niet_gestart` niet en maakt er
`mislukt` van: een rood label, waar `overgeslagen` ("niet aan bod") bedoeld is. Het Grafana-paneel van #1518 telt het
eveneens als `mislukt` (`countif(u !in (…))`).

Voorgestelde fix: zet in `standVan` `niet_gestart` om naar `overgeslagen`, en neem in `delegatie.test.ts` een kind met
`niet_gestart` op. Beter nog: één lijst van de uitkomsten met een vectorbestand dat beide kanten lezen, zoals bij het
denkproces, zodat een nieuwe uitkomst in graph-qa niet stil "mislukt" wordt.

### B4 – `delegaties` op het bericht valt stil weg als #1517 vóór #1518 landt, en de drifttest ziet het niet

**Ernst: meting** als de PR's in losse bundels gaan; geen probleem als ze samen landen.

- `tools/graph-qa/agent/beurt.py` (#1517), regel 421: het bericht krijgt `delegaties`.
- `api/app/gesprek_contracts.py` op master: `BerichtInvoer` kent `delegaties` niet. Pydantic laat het veld zonder fout
  vallen; pas #1518 voegt het toe.
- `tools/graph-qa/tests/test_contract_drift.py` (regel ~300–331) vergelijkt het bewaarde bericht met `BerichtInvoer`,
  maar met events zonder `regie`-event. Daardoor staat `delegaties` niet in het bericht dat de test bekijkt, en is de test
  op #1517 groen (lokaal gedraaid: 18 passed).

Voorgestelde fix: bundel #1517 en #1518 samen, en zet in de drifttest een `regie`-event met `fase: start` en een
`regie_id` bij de events, zodat elk veld dat de driver kan zetten getoetst wordt.

### B5 – #1517 schrijft de opdracht in het deelgesprek vóórdat het kind start

**Ernst: later.**

`tools/graph-qa/agent/subagent.py` (#1517), regel 476: `voeg_bericht_toe(...)` gebeurt vóór `kinderen.start(...)`.

Gaat het starten mis, door een budget dat op is (429 `budget_op`), een 409 op het gesprek of een storing, dan staat er een
opdracht in het deelgesprek zonder antwoord en zonder uitleg, terwijl het kind `budget_op` of `mislukt` heet. Bij het
hervatten wordt de hervattekst ("ANTWOORD OP JE VRAGEN (van de gebruiker) …", `berichten.HERVATTING`) een bericht met
`rol: user`. De jurist ziet dan een bericht uit code als iets wat hij zelf schreef.

Voorgestelde fix: schrijf het bericht pas nadat `kinderen.start` slaagde (de beurt loopt dan, en het antwoord volgt). Laat
het kenbaar zijn als bericht van de code, met een eigen veld of soort, en niet als gewone vraag van de jurist; de
werkplek toont het dan als "Opdracht van Lex".

## Twijfelgevallen (niet aangetoond)

- **De hartslag kan een vraag wegpoetsen.** `_hartslag` stuurt elke 30 s `{"status": "loopt"}`, en `wijzig` in
  `api/app/delegatie_store.py` staat `wacht → loopt` toe. De hartslag wordt vóór `_leg_vast` gestopt (`_met_hartslag`,
  `voer_plan_uit`). Een verzoek dat al onderweg was, kan de api toch ná `wacht` verwerken. Dan staat de delegatie weer op
  `loopt` zonder hartslag, wordt ze na `VERWEESD_NA` `mislukt`, en zegt de vraagkaart `AL_BEANTWOORD`. Niet
  gereproduceerd. Een hartslag zou zelf geen `wacht` mogen verlaten, bijvoorbeeld met een eigen veld zonder status.
- **`draai` wacht zonder grens.** `agents/uitvoering.draai` wacht in de nodethread tot `toekomst.done()`. Sluit de loop
  (een herstart terwijl een kind loopt), dan wordt de toekomst nooit klaar en blijft de thread hangen, en daarmee
  mogelijk het afsluiten van het proces. Niet gereproduceerd.
- **De periode van de jurist kan een vergaderjaar zijn.** `gelezen._PERIODE` neemt elk "2023-2024" uit de opdracht of de
  antwoorden. Een opdracht met een vergaderjaar van Kamerstukken maakt dan van elke duiding van een uitspraak buiten die
  jaren een bewering (`buiten_periode`), met een correctieronde als gevolg. Komt alleen voor bij een opdracht die beide
  bronnen noemt.
- **`model` in `beurt_meting` is nu het model van de laatste aanroep** (#1514). Bij een annotatiebeurt is dat de
  classifier of de reviewer, niet de ophaal-agent. Dat is een andere betekenis dan voorheen, voor elke route; let erop bij
  vergelijkingen met oudere metingen.
- **#1516 test alleen de weigering.** `test_een_getypt_annotatieverzoek_gaat_via_annoteer_naar_de_annotatieroute` toetst
  "meer dan één artikel". Het gewone pad (centrale agent → `annoteer` → ophaal-agent → `annoteer`-node → elementen) is
  lokaal nagelopen met een nep-LLM en werkt (events `doel`, `run`, `dekking`, `element`). Een test die dat vastlegt,
  ontbreekt.
- **#1515: het venster van de logquery.** `gestart` ligt twee minuten vóór de start van de job. Draai je de actie snel
  na elkaar, dan kan de uitkomst van de vorige uitvoering in het venster vallen voordat de nieuwe in Log Analytics staat.
  Klein risico, omdat `tail -1` de nieuwste neemt. Filter op de naam van de execution, of neem het tijdstip pas na
  `job start`.

## Nagelopen zonder bevinding

- #1514: de weigering (`weiger_event`) heeft dezelfde vorm als `execute_tool`. De api bewaart `tool_executions` als vrije
  dicts, en de werkplek leest `status: geweigerd` niet. `NA_SUBAGENT` en `NA_RAPPORT` dragen beide `reden: na_subagent`.
- #1518: het id-patroon van `delegaties` past bij de id's van `delegatie_store` (16 hextekens). `GET /v1/delegaties` filtert
  op gesprek én gebruiker.
- De budgetpoort: een kind boekt zijn eigen meter op zijn eigen `run_id`, en de ouder telt het niet nog eens mee. Een kind
  met een budget dat op is, wordt `budget_op` (`detail.reden`).
- *Stop* midden in een kind: `_stopwacht` stopt het kind, en de afloop wordt `gestopt`.
- Twee klikken op dezelfde vraagkaart: het gesprekslot van de ouder (409) laat er maar één tegelijk door.
