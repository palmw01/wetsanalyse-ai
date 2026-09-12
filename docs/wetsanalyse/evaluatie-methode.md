# Evaluatie JAS-methode 2.1

Datum: 2026-09-12. Status: technische implementatie gecontroleerd; juridische vaststelling
van de referentieset en volledige kwalificatie van de methode staan nog open.

## Technische verificatie

De gerichte regressies omvatten annotatie, kandidaatclassificatie, critic, prioriteitsregels,
klasse- en contractdrift, bronankers, promptpropagatie, voorbeeldintegriteit en evaluatiescorers.
Uitkomst: **190 tests geslaagd**. Skillvalidatie, beide generatiecontroles en `git diff --check`
slagen eveneens. De asyncio-critic-tests bleven in de sandbox hangen en zijn buiten de
sandbox met dezelfde fakes succesvol uitgevoerd; dit was geen modelkwaliteitsmeting.

Vanuit `tools/graph-qa`:

```bash
.venv/bin/python -m pytest tests/test_jas_protocol.py tests/test_methode_drift.py tests/test_annotatie.py tests/test_prioriteitsregels.py tests/test_golden_annotatie.py tests/test_critic_lus.py tests/test_kandidaten.py tests/test_contract_drift.py tests/test_prompt_caching.py tests/test_anker_lid.py tests/test_jas_klassen.py tests/test_eval_scorers_v2.py -q
```

Vanuit de projectroot:

```bash
python3 tools/graph-qa/scripts/genereer_jas_klassen.py --check
python3 tools/graph-qa/scripts/render_jas_referentieset.py --check
```

De nieuwe tests bewijzen onder meer dat gewijzigde protocolsecties de relevante prompts
bereiken, dat een verfijnde kandidaatgrens tegen de brontekst wordt gecontroleerd, dat
verzonnen tekst wordt geweigerd en dat conceptmarkeringen naar een exact voorkomen verwijzen.
Zij bewijzen niet dat een model de juridische instructies altijd juist uitvoert.

## Directe modelproef: 24 aanvragen

[Meetresultaten](modelvergelijking.json) en [beide promptteksten](modelvergelijking-prompts.json)
zijn bewaard. Model: `claude-sonnet-4-6`, via de bestaande providerconfiguratie. Vier
ontwikkelgevallen, drie herhalingen per variant, identiek bronpakket en tokenlimiet8192.
Temperatuur is niet expliciet ingesteld; beide varianten gebruiken dezelfde providerdefault.
Het baselinecommit en de hashes van prompts en analyseteksten staan in de meetgegevens.
De volgorde oud/nieuw wisselt per herhaling.

Dit is een vergelijking van de directe annotator met oude promptbouw versus protocol2.0,
met dezelfde klassedefinities. Geen retrieval, critic, herziening of volledig dossier.
Dossierbron-ID's worden als regelingidentificatie meegestuurd; er wordt geen aanvullende
rechtscontext opgehaald. Die beperking geldt identiek voor beide varianten.

| Controle | Oude prompt | Protocol2.0 | Betekenis |
|---|---:|---:|---|
| Letterlijke uitvoerfragmenten | 97/97 | 104/104 | Tekst komt voor in aangeboden corpus; geen juridische kwaliteitsscore. |
| IW01: volledige dragende invorderingszin | 0/3 | 0/3 | Beide bleven bij het losse gezegde. |
| AWB04: volledige staffelinhoud als afleidingsregel | 1/3 | 3/3 | Nieuwe instructie hield de berekening beter bijeen in deze proef. |
| IW01: extra parameterlabel op zes weken | 0/3 | 2/3 | Ongewenste duiding van dezelfde temporele functie; regressiesignaal. |

Bij de staffelcontrole is het al dan niet opnemen van de eindpunt afzonderlijk beschouwd:
volledige inhoud is niet hetzelfde als een exact identieke fragmentgrens. De proef maakt
ook duidelijk waarom méér markeringen geen bewijs van betere analyse is. Voor de Wzt- en
RVV-uitkomsten wordt zonder deskundige referentie geen juistheidsscore toegekend.

## Bijstelling en gerichte hertoets: zes aanvragen

De uitkomsten hebben geleid tot protocol2.1: de volledige normformulering bij een
rechtsbetrekking wordt explicieter voorgeschreven, en een gelijkblijvende tijdsduur
rechtvaardigt niet automatisch een extra parameterlabel. Dit is een projectregel die
terug te vinden is in het bronnen- en beslisregister.

[De hertoets](modelvergelijking-v21.json) gebruikt dezelfde invorderingszin, hetzelfde model,
drie herhalingen en dezelfde oude baselineprompt. De complete prompts zijn in dit bestand
opgenomen. Het betreft ontwikkelmateriaal, geen onafhankelijke generalisatietoets.

| Controle IW01 | Oude prompt | Protocol2.1 |
|---|---:|---:|
| Volledige invorderingszin als rechtsbetrekking | 0/3 | 3/3 |
| Extra parameterlabel op zes weken | 0/3 | 1/3 |
| Letterlijke fragmenten | 12/12 | 12/12 |

De grensregel wordt in deze hertoets beter gevolgd. De dubbele temporele duiding is nog
niet betrouwbaar opgelost. Die uitkomst blijft zichtbaar; er is geen claim van foutloze
annotatie of 10/10-juridische kwaliteit. De volledige critic-keten kan afwijkend reageren
en is hier alleen technisch met fakes getoetst.

Herhalen vanuit `tools/graph-qa`, naar een **nieuw** uitvoerbestand:

```bash
.venv/bin/python -m eval.compare_annotatie_prompts --baseline-ref <commit-uit-rapport> --cases IW01 AWB04 WZT01 RVV03 --herhalingen 3 --output /tmp/jas-nieuwe-meting.json
```

Dit commando doet betaalde aanvragen aan de geconfigureerde provider. Het weigert
held-outcasussen en overschrijft geen bestaande meting. Een infrastructuurfout wordt als
niet volledig gemeten opgeslagen, niet als inhoudelijke modelscore.

## Open inhoudelijke acceptatiepunten

- De 24 conceptgevallen moeten samen met de gebruiker/deskundige worden beoordeeld en
  aangevuld tot volledige referenties, met onderbouwde alternatieven waar nodig.
- De nog optredende dubbele tijd/parameterduiding vraagt aandacht in de menselijke review
  en een beoordeling van de volledige annotatieketen.
- De afzonderlijke BW- en Omgevingswetfamilies zijn niet gebruikt voor modelafstemming.
  Een toets daarop volgt pas na vastlegging van de deskundige referenties.
- Historische voorbeeldteksten zijn geen actuele toepasselijkheidsanalyse. Overgangsrecht
  is als controle opgenomen, maar nog niet met een volwaardig eigen referentiegeval getest.
- Het volledige dossierproces met externe bronzoekacties is nog niet end-to-end met een
  deskundige geëvalueerd. De huidige app heeft geen volledige dossieropslag gekregen.
De aanvankelijke JRM-downloadblokkade is opgelost: op 12 september is de oorspronkelijke
publicatie via PNA bewaard en gecontroleerd, inclusief tekstextractie en hashes.

De oplevering omvat dus een onderbouwde methode en werkende technische koppeling, met
meetbare eerste gedragsverbetering én zichtbare resterende beperkingen. Vaststelling
van juridische kwaliteit blijft afhankelijk van de geplande gezamenlijke beoordeling.
