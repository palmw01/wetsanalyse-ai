# Briefing: analist van Lex Bench

Soort: *werkinstructie* · Plan: [`../architectuur/plan-lex-bench.md`](../architectuur/plan-lex-bench.md) §4.2–§4.3, §22
besluit 4 · Profiel: [`.claude/agents/bench-analist.md`](../../.claude/agents/bench-analist.md)

Deze briefing gaat in zijn geheel mee in de opdracht van de analist (`eval/lex_bench_team.py opdracht`). Het eerste
deel is voor de analist, het tweede voor de coördinator die de run draait.

## Voor de analist

### Je opdracht

Je krijgt het dossier van één casus: de naam, de aanleiding, het doel, de analysevraag, het praktijkvoorbeeld, de
context, wat erbuiten valt, de gebeurtenis, de regelingen waarin gezocht wordt, en de deelvragen. Bepaal per deelvraag
welke bepalingen een jurist nodig heeft om haar te beantwoorden. Dat is je bronselectie. Er staat geen verwachting in
het dossier: die maak jij.

### Wat telt als bepaling

- Een **lid** als het artikel leden heeft, anders het **artikel**. Een onderdeel alleen als juist dat onderdeel de
  deelvraag draagt. Geef de bron als jci-achtige iri van de graaf, in de vorm `urn:bwb:<bwb-id>:artikel:<nummer>:lid:<nummer>`. Haal
  de iri uit de graaf (`graaf_lezen`) als je hem niet zeker weet.
- Neem op wat de deelvraag **draagt** (*kern*) en wat de kern **nodig heeft** om toegepast te worden, zoals een
  definitie of de bepaling waarnaar ze verwijst (*afhankelijkheid*). Wat nuttig is maar niet nodig, is *aanverwant*.
- Vermeld bij elke bepaling de **zoekvraag** (a tot en met d) waarlangs je haar vond.
- Zoek in de regelingen van het dossier. Brengt een verwijzing je in een andere regeling, volg haar dan volgens het
  volg-beleid. Wat de deelvraag nodig heeft maar niet in de graaf staat, zet je bij `buiten_graaf`.

### Bewijs

Elke opgenomen bepaling draagt het citaat waarop je keuze rust, letterlijk uit `bron_lezen` (of `graaf_lezen` als
`bron_lezen` de bepaling niet kan ophalen, zoals bij een beleidsregel met een `id:`-iri). Noteer welke van de twee je
gebruikte, en de toestand of de url die `bron_lezen` meegaf. Een parafrase is geen bewijs.

### Uitsluiten en twijfel

- Bekeek je een bepaling en laat je haar bewust weg, zet haar dan bij `uitgesloten` van die deelvraag, met een reden.
  Dat geldt vooral voor wat het dossier onder *wat valt erbuiten* noemt.
- Weet je het niet zeker, zet de bepaling dan bij `twijfel`, met de reden. Dat is geen fout: de jurist beslist.
- Eén bepaling staat per deelvraag maar op één plek: opgenomen, uitgesloten of twijfel.

### Blind blijven

Je ziet Lex niet, en je leest geen bestanden uit de repo. Je logboek is van jou alleen: gebruik de run uit de opdracht
en lees geen ander logboek. Je weet niet wie de andere analist is en wat die koos, en daar zoek je ook niet naar.

### Het formulier

Je laatste bericht is één JSON-object volgens het formulier in de opdracht, zonder tekst eromheen. Elke deelvraag van
het dossier komt er precies één keer in voor, met haar nummer (vanaf 0, in de volgorde van het dossier).

## Voor de coördinator

De coördinator is de sessie die de run draait. Die kent de verwachting van een ontwikkelcasus misschien wel; daarom
krijgt de analist alles via de opdracht en niets via een gesprek.

1. **Opdracht maken.** `cd tools/graph-qa && uv run python -m eval.lex_bench_team opdracht --casus LB-xx --analist A
   --run <run>-a` (of `--dossier <pad>` voor een casus buiten de repo, zoals een blinde). De opdracht bevat deze
   briefing, de twee uitwerkingen uit de skill, het dossier zonder verwachting en het formulier. Een run heet
   bijvoorbeeld `lb-03-2026-11-20`; de analisten krijgen `-a` en `-b` erachter.
2. **Analisten starten.** Per casus twee analisten (A en B) los van elkaar, elk met het profiel `bench-analist` en
   alleen hun eigen opdracht. Bij een *makkelijke* casus één analist met een tegenlezer (besluit 4, §22): het profiel
   `bench-reviewer` in de modus tegenlezen, zie [`briefing-reviewer.md`](briefing-reviewer.md).
3. **Controleren.** Sla het antwoord op als `formulier-a.json` (en `-b`) in de meetmap en toets het:
   `uv run python -m eval.lex_bench_team controleer <formulier> --casus LB-xx`. Een fout gaat terug naar dezelfde
   analist, met de melding, niet naar een nieuwe.
4. **Samenvoegen en bevriezen.** `uv run python -m eval.lex_bench_team samenvoegen formulier-a.json formulier-b.json
   --casus LB-xx --run <run> --uit <nieuwe map>`. Wat beide opnemen, komt in `verwacht` (bij een verschil in rol de
   zwaarste, met het verschil in `onenig`). Wat één van beide opneemt, staat alleen in `onenig`, met het standpunt van
   allebei. Wat beide uitsluiten, komt in `uitgesloten`. Dat is de teamverwachting, `status: concept`. De map krijgt
   haar met de formulieren en `bevroren.json` (de sha256 van elk bestand), en een bestaande map blijft staan. Een
   blinde casus bevriest buiten de repo; in de repo komen alleen de hashes. Zet de hash van de teamverwachting in het
   runrecord.
5. **Pas daarna** draait of leest iemand de Lex-arm. De reviewer beoordeelt daarna de verschillen
   ([`briefing-reviewer.md`](briefing-reviewer.md)).

Er draait in LB2 geen model: de eerste run is de pilot LB3, met een eigen akkoord en de plafonds van §7.
