# Skillimport in de bestaande agents

De platformagents laden nu een geselecteerd deel van de wetsanalyse-skill per rol.
De inhoudelijke methode blijft versie 2.1. De SHA-256 van het pakket identificeert
de precieze bronselectie en inhoud binnen die versie. Dit maakt de import controleerbaar;
het is geen certificering van juridische juistheid.

## Bron → selectie → uitvoering

1. [SKILL.md](../../.claude/skills/wetsanalyse/SKILL.md) bevat de enige machineleesbare
   methodeversie in `metadata.methode_versie`.
2. [agentrollen.json](../../.claude/skills/wetsanalyse/agentrollen.json) koppelt rollen
   aan stabiele sectie-ID’s, referentiebestanden en M/P-codes.
3. [Agentrollen](../../.claude/skills/wetsanalyse/references/agentrollen.md) beschrijft
   de selectie voor het platform. Het
   [annotatieprotocol](../../.claude/skills/wetsanalyse/references/annotatieprotocol.md)
   blijft de inhoudelijke bron voor kandidaten, classificatie en review.
4. `scripts/genereer_jas_klassen.py` genereert de klassendefinities en
   [methodepakket.py](../../tools/graph-qa/agent/methodepakket.py).
   De compiler weigert onbekende of ontbrekende rollen, ontbrekende/dubbele secties,
   ongeldige broncodes en bronpaden buiten de skill.
5. [methode.instructies](../../tools/graph-qa/agent/methode.py) selecteert de rol
   en schrijft alleen technische metadata naar de bestaande logging:
   `methode_rol`, `methode_versie`, `methode_sha256`, `methode_secties`.
   De bestaande formatter voegt request-/tracecontext toe indien aanwezig.

De M-codes verwijzen naar methodebronnen; P-codes naar expliciete projectkeuzes in
[het beslisregister](../../.claude/skills/wetsanalyse/references/bronnen.md).
De oorspronkelijke bronnen en hun bestandscontroles staan in het
[bronmanifest](bronnen/manifest.json). Sectiehashes controleren de geselecteerde
tekst; bronbestandhashes omvatten ook skillmetadata, rolmapping, bronregister en
klassereferentie. Niet-geselecteerde dossierinstructies worden niet stilzwijgend
als runtime-opdracht ingevoerd.

## Verdeling

| Bestaande rol | Geïmporteerde inhoud |
| --- | --- |
| Supervisor | Brongebruik, scope, keuze annotatie/definitie/duiding |
| Retrieval | Exact doel, volledige bedoelde bron, ontbrekende context |
| Definitie | Brondefinitie, bereik, verwijzingen, definitie versus interpretatie |
| Duiding | Grammatica, context, wetsdoel met brononderbouwing, JRM 2, alternatieven |
| Algemeen | Brongebruik en onzekerheid |
| Kandidaten | Gedeelde normanalyse en voorlopige betekenisvolle spans |
| Annotator / classificatie | Gedeelde analyse, fragmentgrenzen, overlap, alternatieven |
| Critic / herziening | Dezelfde analyse plus blijvende inhoudelijke bezwaren |
| Decompositie | Scope en afhankelijkheden behouden in deelvragen |
| Synthese | Onderbouwing, onzekerheid en tegenspraak behouden |

Gewone antwoorden en deelvraagoplossingen gebruiken dezelfde specialistselectie.
Advies gebruikt duiding. Een expliciet doel gaat rechtstreeks naar de annotatieketen.
Correctie en herziening laden opnieuw de bijbehorende rolselectie. Stabiele
instructies staan in het systeemblok; bron-/gespreksgegevens blijven apart.
De technische JSON-contracten, toolsets en graaftopologie zijn behouden.
De definitierol zoekt nu de daadwerkelijk aangetroffen definitiebepaling; de oude
verplichting om altijd artikel 1 en 2 op te halen is vervallen.

## Onderhoud en controle

Vanuit `tools/graph-qa`:

```bash
.venv/bin/python scripts/genereer_jas_klassen.py
.venv/bin/python scripts/genereer_jas_klassen.py --check
.venv/bin/python -m pytest -q
```

Bewerk de skill, niet de gegenereerde Python. Beide CI-workflows controleren
generatie vóór de tests. De publish-workflow reageert ook op skillwijzigingen.
Een wijziging in de geïmporteerde methode zonder regeneratie blokkeert daardoor de build.

Gecontroleerd op 12 september 2026:

- 700 tests geslaagd; 16 optionele tests overgeslagen.
- Vastgelegde modelaanroepen bewijzen import op gewone, advies-, doel-, retrieval-,
  kandidaat-, classificatie-, critic-, herzienings-, decompositie-, synthese- en correctieroutes.
- Bestaande tests bewaken toolsets, scope, bronankers, menselijke keuzes en uitvoercontracten.
- Driftcontrole, bronhashcontroles en skillvalidatie geslaagd.
- Wheel gebouwd, lokaal zonder dependencies geïnstalleerd in een nieuwe virtualenv,
  en vanuit `/tmp` met Python `-I` succesvol geïmporteerd. De rolprompts werken zonder
  repository of skill/PDF-bestanden. De bestaande Dockerfile kopieert dezelfde `agent/`-package;
  deze controle is geen uitgevoerde containerdeploy.

## Modelproef

[compare_methodeketen.py](../../tools/graph-qa/eval/compare_methodeketen.py) vergelijkt
vier bestaande ontwikkelcasussen op dezelfde modelinstellingen en vaste openbare bronpassages.
De baseline is een bestandssnapshot van de werkende methode 2.1 direct vóór deze import,
niet de oudere Git-HEAD. De rapporten bewaren hashes van de agentbestanden en werkelijke
modelaanroepen en events. De held-out wetsfamilies zijn niet gebruikt.

De proef start met een expliciet doel en omvat bronophaling, annotator, critic,
eventuele patch/herziening en eindbeoordeling. Router en retrieval-LLM worden afzonderlijk
met vastgelegde testaanroepen gecontroleerd. De bronadapter gebruikt een synthetische,
gedeelde technische vindplaats; alleen de opgeslagen passage is de juridische analysebron.
Daarom meet deze proef geen betrouwbaarheid van bronselectie of juridische verwijzingen.
Eén meting per casus en variant is onvoldoende voor uitspraken over statistische verbetering
of een expertgoldscore. De resultaten staan hieronder.


### Uitkomst van de proef

Alle acht ketens voltooiden vier modelaanroepen: annotator, critic, herziening en
laatste critic. De uitvoer bleef letterlijk: 38/38 fragmenten vóór import, 39/39 erna.
Aantal fragmenten is geen maat voor volledigheid of juistheid.

| Casus | Elementen vóór → na | Letterlijk vóór → na | Geel vóór → na | Rood vóór → na |
| --- | --- | --- | --- | --- |
| IW01 | 5 → 5 | 5/5 → 5/5 | 1 → 4 | 0 → 0 |
| AWB04 | 9 → 8 | 9/9 → 8/8 | 6 → 4 | 0 → 0 |
| WZT01 | 15 → 16 | 15/15 → 16/16 | 8 → 7 | 0 → 0 |
| RVV03 | 9 → 10 | 9/9 → 10/10 | 4 → 6 | 1 → 0 |

Bij IW blijft de volledige normzin in beide varianten gemarkeerd. Bij Awb blijft
de volledige dwangsomstaffel behouden. Bij Wzt blijven in beide varianten korte
rechtsbetrekkings- en afleidingsfragmenten staan; de import lost dat niet aantoonbaar op.
Het RVV-resultaat na import classificeert bovendien “over te steken” als Rechtsobject;
dat is een concreet punt voor inhoudelijke herbeoordeling.
Ook de verschillen in geel/rood zijn modeloordelen, geen onafhankelijke kwaliteitsmeting.
De referentieset blijft concept en vraagt inhoudelijke adjudicatie door een expert.

Bewijsbestanden:

- [Voor import](agentimport-keten-voor.json): openbare bronpassages, requests, events en codehashes.
- [Na import](agentimport-keten-na.json): dezelfde opzet en modelinstellingen.
- [Vergelijking](agentimport-vergelijking.json): tellingen en pakketidentiteiten.
- [Gemeten methodepakket](agentimport-methodepakket-gemeten.json): exacte selectie bij start van de proef.

Na start van de proef zijn uitsluitend de tabelopmaak van P12, afsluitende witruimte en de uitleg van het
generatiepad gecorrigeerd. Dat verandert de hash van de bronbestanden en daarmee de
pakkethash. De geselecteerde secties en rollen zijn exact gelijk gebleven; alle 16
gemeten nieuwe systeemprompts zijn byte-voor-byte vergeleken met de definitieve
runtimeprompts en komen overeen. Beide pakketidentiteiten staan in het vergelijkingsbestand.
