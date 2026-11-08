# Regie binnen een werkgebied (ADR-012), eerste meting op acceptatie

Soort: *meting* · 8 november 2026 · Code: bundel 17 (#1099, met #1087, #1088 en #1100), master `c53dd3f5` · Akkoord van de
gebruiker voor de tokens.

## Opzet

Een vers werkgebied *Meting regie ADR-012* (`bc252e2c-c415-4f20-8db9-c5f2484f8d13`) op de Invorderingswet 1990, met twee
deelvragen:

1. Binnen welke termijn moet een aanslag worden betaald?
2. Wanneer is een aanslag ineens invorderbaar?

Eén regiegesprek (`08fafe6218544fc3`), bediend via de acceptatie-MCP zoals de werkplek dat doet. Het verloop:

1. de getypte opdracht "Zoek per deelvraag de bronnen en annoteer de kern";
2. de bevestiging van de bronnenronde;
3. het opnemen van bronnen als jurist;
4. het voorstel en de bevestiging van de annoteerronde;
5. een poging tot *Stop alles*.

`REGIE_PARALLEL` = 2. De tijden komen van de wandklok van de meetsessie (start van de bevestigde run tot de bundel). Het
verbruik komt uit de `meting`-events van de kind-runs, niet uit het accounttotaal: daar telden andere sessies op hetzelfde
account tegelijk mee.

## Uitkomst

| Ronde | Taken | Tegelijk | Wandklok | Verbruik | Schatting (bovenkant) |
|---|---|---|---|---|---|
| Bronnen | 2 deelgesprekken | ja | 52,4 s | 0 tokens | 0 |
| Annoteren | 2 deelgesprekken, 1 bepaling elk | ja | 80,2 s | 37.026 tokens | 30.996 (46.494) |

Per kind van de annoteerronde, uit de `meting`-events:

| Kind | Bepaling | Duur | Invoer / uitvoer | Modelrondes | Markeringen | Aandeel |
|---|---|---|---|---|---|---|
| Deelvraag 1 | Iw art. 28b lid 1 | 18,8 s | 5.972 / 610 | 4 | 13 | 19.373 |
| Deelvraag 2 | Iw art. 10 lid 1 | 73,2 s | 25.120 / 5.324 | 12 | 63 | 19.373 |

**Wat werkte**

- **Eerst het plan, nooit zelf beginnen.** De getypte opdracht met bronnen én annoteren leverde de bronnenronde op, met een
  bevestiging (`plan_id`, "kost geen tokens"). Annoteren kwam pas in een tweede regie, na het opnemen.
- **Deelgesprekken onder het regiegesprek.** Per ronde twee deelgesprekken met `ouder_id` en `regie_id`, beide gestart
  vóór het eerste klaar was. Ze lopen dus echt naast elkaar.
- **De bundel uit de stand.** "8 / 8 voorgestelde bronnen in het paneel" na de bronnenronde, "1 bepaling met
  markeringen te beoordelen" per kind na het annoteren. Het artefact `regie` stond op het bericht.
- **Geen overlap en geen dubbele laag.** Het aantal voorstellen per bepaling in de werkvoorraad (13 en 63) is gelijk aan wat
  elk kind maakte. Na afloop is `te_annoteren` leeg.
- **Deterministisch plan.** Dezelfde stand gaf hetzelfde `plan_id`, ook in een volgende regie.
- **Het slot werkte stil mee.** Drie regies na elkaar in hetzelfde werkgebied, zonder 409. Een regie gaf het slot vrij bij
  het afronden.

**Wat opviel**

1. **Al geannoteerde bepalingen noemt het plan niet.** Art. 9 lid 1, lid 5 en lid 6 Iw waren op acceptatie al
   geannoteerd (te beoordelen; de lagen zijn gedeeld). Het plan telde alleen het nieuwe werk. Het zei "1 bepaling" zonder
   uit te leggen waarom de drie andere opgenomen bronnen ontbraken. Verbeterpunt: in `buiten` noemen hoeveel bepalingen er
   al een annotatie hebben en op beoordeling wachten.
2. **De schatting per bepaling kent de lengte niet.** De mediaan (15.498 tokens) paste goed op een kort lid (6.582), maar
   art. 10 lid 1 kostte 30.444 en ging zo over het aandeel van zijn kind (19.373). Dat is de bekende grens: een lopende
   bepaling maakt af, en met één bepaling per kind valt er niets tussen te stoppen. Samen bleef het onder de bovenkant
   (37.026 tegen 46.494). Verbeterpunt: de schatting wegen naar de lengte van de bepaling, als een meting dat waard blijkt.
3. **Het voordeel van tegelijk volgt de langste.** 80,2 s wandklok tegen 92,0 s voor de twee kinderen na elkaar: ongeveer
   13 % sneller, omdat het lange lid de tijd bepaalt. Met meer bepalingen per kind en meer deelvragen wordt de winst groter.
   Dat is hier niet gemeten.
4. **De bronnenronde zoekt opnieuw na het opnemen.** De tweede bronnenregie vond 16 en 11 voorstellen (eerst 8 en 8): de
   zoekstand was verouderd door de nieuwe selectie. Dat is het bedoelde gedrag, en het blijft gratis.

**Niet gemeten**

- **Stop alles.** De gratis bronnenronde was al klaar (~1 s) voordat het stopverzoek via de MCP aankwam. Een stop op een
  annoteerronde kost tokens, en met één bepaling per kind maakt elk kind toch af. Het doorstoppen naar de kinderen is
  gedekt in `tests/test_regie_ingang.py` en `tests/test_regisseur.py`.
- **Eén trace in Application Insights.** `logs_zoek` van de acceptatie-MCP vraagt Grafana-toegang die deze sessie niet had.
  Te controleren met `azure-infra` → `telemetrie`, of in Grafana op de `regie_id` `652d4f50b9d34c5c`.

## Gegevens

- **Werkgebied:** `bc252e2c-c415-4f20-8db9-c5f2484f8d13`.
- **Regiegesprek:** `08fafe6218544fc3`.
- **Bronnenronde:**
  - regie `e4933a58c7b94eb5`, run `1cc966e022754543b7bae9dc42ceaa29`;
  - kinderen `a90d2940…` en `c4c99746…`.
- **Annoteerronde:**
  - regie `652d4f50b9d34c5c`, run `91947c37d2b445208ca305668b8e5020`;
  - kinderen `3048c56bfd354af4ab9be4eb3b84156f` (28b lid 1) en `cd852115ec254ac6a38a1ca101594c60` (10 lid 1).
- **De poging tot stoppen:** regie `ab49b8c7e70c4b01`, run `3b6e978318434bc7932abe8c7037641b`.
