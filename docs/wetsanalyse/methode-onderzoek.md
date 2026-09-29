# Methode 2.1: JAS met JRM 2-verrijking

Soort: *specificatie* van de projectmethode (zie [`../README.md`](../README.md)) · Methodeversie
2.1 (onderzoek 11 sep 2026, implementatie 12 sep 2026) · Bijgewerkt: 29 september 2026

Status: dit is een geïmplementeerde conceptmethode. Een kwaliteitsverbetering is nog niet
empirisch bewezen; de juridische validatie is [`../PLAN.md`](../PLAN.md), spoor A.

Dit document legt uit **wat de methode inhoudt, waarop zij berust en hoe zij in de agents
terechtkomt**. De methode zelf staat in de skill [`.claude/skills/wetsanalyse/`](../../.claude/skills/wetsanalyse/SKILL.md):
- het [annotatieprotocol](../../.claude/skills/wetsanalyse/references/annotatieprotocol.md);
- de [klassereferentie](../../.claude/skills/wetsanalyse/references/jas-klassen-referentie.md);
- het [bronnen- en beslisregister](../../.claude/skills/wetsanalyse/references/bronnen.md) (M- en
  P-codes).

De proefresultaten van september staan in het [meetlogboek](../architectuur/metingen/README.md).

## Uitkomst

De belangrijkste zwakte van de oorspronkelijke invoer was dat juridische analyse werd teruggebracht
tot het vinden van losse tekstfragmenten met een label. De methode maakt de samenhang, bronnen en
onzekerheden expliciet. Een betekenisvolle analyse moet kunnen uitleggen:
- wie waarop aanspraak heeft;
- onder welke voorwaarden;
- door welk feit een toestand verandert;
- hoe dat uit de toepasselijke tekst volgt.

Grammaticale ontleding ondersteunt dit, maar vervangt de juridische interpretatie niet.

De uitvoer is tweeledig. Er is een volledig Markdown-dossier voor de skillworkflow, en er is de
platformannotatie met dertien JAS-labels. De aanvullende inhoud leeft in het dossier. Een groene
annotatiekaart bewijst niet dat er extern bronnenonderzoek of een volledige analyse heeft
plaatsgevonden.

## Onderzoeksbasis en bewaarbeleid

Het [bronnen- en beslisregister](../../.claude/skills/wetsanalyse/references/bronnen.md) legt de
gebruikte onderdelen vast. Het [bronmanifest](bronnen/manifest.json) bewaart herkomst, versies en
hashes van lokale exemplaren. De interne handleiding, de leidraad en het auteursrechtelijk
beschermde boek blijven lokaal en worden niet opnieuw gepubliceerd. Dit document bevat eigen
bevindingen en projectbesluiten.

De handleiding verbindt markeren en classificeren met het zichtbaar maken van samenhang. De
bespreking van elektronische berichten in het boek laat zien waarom een naamwoord als
*kennisgeving* niet automatisch een object is: de antecedent en de juridische context bepalen de
functie (M01–M04).

Bronnen worden beoordeeld op wat zij specifiek bijdragen:
- een praktijkvoorbeeld bewijst geen universele classificatieregel;
- een schrijfaanwijzing verklaart conventioneel taalgebruik, maar sluit afwijkende historische
  formuleringen niet uit;
- onderzoek naar een andere jurisdictie ondersteunt het ontwerp van annotatie en evaluatie, niet
  de inhoudelijke uitkomst van een Nederlandse wetsanalyse.

## JAS en de doorontwikkeling JRM 2

De doorontwikkeling heet **JRM 2** (Juridisch Referentiemodel) en is expliciet een werkversie. Zij
voegt onder meer rechtsgevolgen en juridisch relevante feiten toe en geeft scenario's een centrale
rol. Relaties en toestanden krijgen daarmee een explicietere plaats; het is geen hernoeming van
labels. Het projectprofiel behoudt JAS en legt deze informatie vast in het dossier. Het dossier is
geen volledige implementatie van de formele modellen die JRM beoogt.
[M06: Bulles en Van der Hoven, 2024](https://regels.overheid.nl/publicaties/doorontwikkelingen-en-voortschrijdend-inzicht-in-wetsanalyse/download)

De WetsTaal-werkversie bevat bruikbare patronen, maar ook onvoltooide hoofdstukken. Zij wordt
daarom niet integraal als instructie aan een agent gegeven. Verschillen in subtypen tussen bronnen
worden met bronvariant en onderbouwing geregistreerd. Een ontbrekend subtype wordt niet stil
verwijderd. [M05: WetsTaal](https://regels.overheid.nl/standaarden/wetstaal)

## Tekstanalyse

**Eerst de structuur, dan de betekenis.** Een zin, een normeenheid en een annotatie zijn
verschillende dingen. Een lid kan meerdere normen bevatten, en een norm kan een aanhef en meerdere
onderdelen nodig hebben. De analyse maakt daarom eerst een structuurkaart. Daarna zoekt zij per
norm de dragende uitspraak, actor, object en beperkingen. Fragmenten blijven exact; analytische
reconstructies worden apart vastgelegd.

Zo worden twee fouten voorkomen: alleen *bedraagt* markeren en daarmee de rekenregel verliezen, of
een heel lid één label geven. Overlap mag waar elementen verschillende functies dragen.
Concurrerende interpretaties horen bij de alternatieven. Een hiërarchische tekening levert geen
algemene voorrangsregel op.

**Grammaticale controles met juridische gevolgen.** De methode controleert passief en ellips,
modaliteit, negatie, kwantoren, bijzinnen, opsommingen, coreferentie, vergelijkingen en tijd. Elke
controle beantwoordt een concrete vraag:
- wie handelt;
- wat is de voorwaarde;
- waarop werkt *niet*;
- welk antecedent is bedoeld;
- deelt deze uitzondering de aanhef van alle onderdelen?

De Aanwijzingen geven aanknopingspunten voor *indien* tegenover *voor zover*, voor ficties
tegenover vermoedens en voor opsommingen. Ze worden toegepast als contextgevoelige controlevragen.
Het wetsdoel wordt aan de juiste versie en wijziging verbonden, en niet afgeleid uit een plausibel
verhaal van het model.
[M07: Aanwijzingen 3.10–3.12, 4.43 en 4.47](https://www.kcbr.nl/print-instrument/12640)

**Signaalwoorden zijn geen beslisboom.** Annotatieonderzoek beschrijft problemen met modale
werkwoorden, geneste lijsten en minder expliciete uitzonderingen. Herkenningswoorden zijn daarom een
zoekhulp, waarvan de functie in context wordt getoetst. De hybride keten past dit toe: detectoren
bieden hypothesen, en de classificatie en de mens beslissen
([annotatieketen](../architectuur/annotatieketen.md)).
[M08: Nazarenko, Lévy en Wyner, 2018](https://aclanthology.org/L18-1177/)

## Brononderzoek en juridische interpretatie

De dossierworkflow volgt de noodzakelijke officiële bronnen. Iedere verwijzing krijgt een functie
en een uitkomst ([verwijzingen volgen](../../.claude/skills/wetsanalyse/references/verwijzingen-volgen.md)).
Definities, delegatie, uitzonderingen en tijdswerking kunnen meerdere stappen vragen, dus een vaste
diepte is geen volledigheidscriterium. Het operationele startbudget is twintig nieuwe passages.
Raakt dat op, dan blijven de wachtrij en de beïnvloede conclusies zichtbaar.

De primaire wettekst blijft gescheiden van historische toelichting, rechtspraak, beleid en eigen
reconstructie. Grammaticale, systematische, historische en doelgerichte argumenten worden alleen
gebruikt waar ze een materiële interpretatievraag helpen beantwoorden, en geen enkele krijgt
automatisch voorrang. Ontbrekende informatie is geen negatieve conclusie: een niet-gevonden sanctie
bewijst niet dat er geen sanctie is, en een onbekende waarde is niet nul.

Het dossier bewaart bronversie, peildatum en raadpleegdatum apart. Exacte citaten met context en
positie sluiten aan bij het W3C-annotatiemodel. Een hash borgt de tekstidentiteit, niet de
juridische geldigheid.
[M10: Web Annotation Data Model](https://www.w3.org/TR/2017/REC-annotation-model-20170223/)

## Kwaliteit aantonen

Een agent mag zijn onzekerheid niet wegpoetsen om een groen rapport te halen. De gemeten
overeenstemming bij annotatie hangt af van taak, meetwijze en beoordelingsronde. Daarom zijn drie
dingen gescheiden: technische brongetrouwheid, inhoudelijke juistheid en menselijke beoordeling.
Een betwistbare duiding kan een aanvaardbaar alternatief zijn; een adjudicatie wordt met reden
vastgelegd.
[M09: Van Dijck, Aguilera en Chakravarthy](https://link.springer.com/article/10.1007/s10506-024-09423-9)

De [kwaliteitsrubriek](../../.claude/skills/wetsanalyse/references/kwaliteit.md) beoordeelt
bronintegriteit, grammatica, classificatie, samenhang, interpretatie, dekking, scenario's en
reviewbaarheid. Een kritieke fout blokkeert de betrokken analyse en mag niet in een gemiddelde
verdwijnen.

De [referentieset](referentieset/README.md) bevat 24 conceptgevallen, verdeeld over zes
wetsfamilies. BW6 en de Omgevingswet zijn held-out en komen nooit in prompts of voorbeelden. De set
is nog geen gold. Wie referentiegrenzen verandert, moet oude en nieuwe uitkomsten opnieuw
beoordelen.

Een hogere run-tot-run-overeenstemming is nooit op zichzelf bewijs van betere annotatie: een keten
kan heel stabiel dezelfde fout maken. Stabiliteitsmaten wijzen alleen aan *waar* de keten wisselt.

## Hoe de methode in de agents terechtkomt

**Twee wegen.**
- **Klassetekst.** De omschrijving, herkenningsvraag en uitdrukkingswijze per klasse komen uit
  `references/jas-klassen-referentie.md`. `tools/graph-qa/scripts/genereer_jas_klassen.py`
  genereert daaruit `agent/jas_klassen.py`, bewaakt door `tests/test_methode_drift.py`. De hybride
  annotatieketen gebruikt deze klassetekst, samen met de detectieprofielen en regels in
  `agent/jas_pipeline/`. Kennis over annotatie hoort daar in regels en tests, niet in prompts
  ([ADR-001](../architectuur/adr-001-hybride-jas-pijplijn.md)).
- **Methodepakket per rol.** De QA-agents laden een geselecteerd deel van de skill per rol:
  1. `SKILL.md` draagt de enige machineleesbare methodeversie (`metadata.methode_versie`).
  2. [`agentrollen.json`](../../.claude/skills/wetsanalyse/agentrollen.json) koppelt rollen aan
     stabiele sectie-ID's, referentiebestanden en M/P-codes.
     [`agentrollen.md`](../../.claude/skills/wetsanalyse/references/agentrollen.md) beschrijft de
     selectie.
  3. `scripts/genereer_methodepakket.py` compileert `agent/methodepakket.py`. De compiler weigert
     onbekende of ontbrekende rollen, ontbrekende of dubbele secties, ongeldige broncodes en paden
     buiten de skill. De SHA-256 van het pakket identificeert de exacte selectie, en de bestandshashes
     dekken ook `SKILL.md`, de rolmapping en het bronregister.
  4. `agent/methode.instructies` selecteert de rol en logt `methode_rol`, `methode_versie`,
     `methode_sha256` en `methode_secties`.

| Rol | Geïmporteerde inhoud |
|---|---|
| supervisor | Brongebruik, scope, keuze tussen annotatie, definitie en duiding |
| retrieval | Exact doel, volledige bedoelde bron, ontbrekende context |
| definitie | Brondefinitie, bereik, verwijzingen, definitie tegenover interpretatie |
| duiding | Grammatica, context, wetsdoel met brononderbouwing, JRM 2, alternatieven |
| algemeen | Brongebruik en onzekerheid |
| decompositie | Scope en afhankelijkheden behouden in deelvragen |
| synthese | Onderbouwing, onzekerheid en tegenspraak behouden |

De annotatierollen (kandidaten, annotator, Critic en herziening) zijn met ADR-001 PR 18 uit het
pakket verdwenen, samen met de generatieve annotatieketen.

**Onderhoud.** Bewerk de skill, nooit de gegenereerde Python. Draai daarna vanuit `tools/graph-qa`:

```bash
.venv/bin/python scripts/genereer_jas_klassen.py            # en --check
.venv/bin/python scripts/genereer_methodepakket.py          # en --check
python3 scripts/render_jas_referentieset.py --check          # leesbare dossiers uit v1/cases.json
.venv/bin/python -m pytest -q
```

CI controleert de generatie vóór de tests, dus een methodewijziging zonder regeneratie blokkeert de
build. Let op: een wijziging aan `SKILL.md`, `agentrollen.json` of `references/bronnen.md` verandert
de pakkethash. Die hash staat in run-manifesten en in de freeze, dus leg zo'n wijziging vast vóór
een meting.

## Open inhoudelijke punten

- De 24 conceptgevallen moeten door deskundigen worden beoordeeld en aangevuld tot volledige
  referenties, met onderbouwde alternatieven waar nodig (V7).
- De dubbele duiding van tijd en parameter op dezelfde temporele functie verdient aandacht in de
  review.
- Overgangsrecht staat als controle in de methode, maar heeft nog geen eigen referentiegeval.
- Het volledige dossierproces met externe bronzoekacties is nog niet end-to-end met een deskundige
  geëvalueerd. De app heeft geen dossieropslag.
