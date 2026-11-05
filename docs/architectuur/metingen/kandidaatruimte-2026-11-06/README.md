# Kandidaatruimte per klasse, 6 november 2026

Nulmeting vóór het spoor dat de kandidaatruimte verbetert. Geen modelcalls: dit meet alleen wat de detectoren aanreiken.

**Waarom.** Het model kiest alleen uit de klassen die een detector aanbood. Staat een klasse niet in de kandidaatruimte, dan is ze
niet te kiezen, hoe goed het model ook is. Een klasse zonder treffers viel tot nu toe nergens op. De maat toont daarom alle dertien
klassen, ook met 0 referenties of 0 hypothesen, met per klasse het aantal hypothesen en hun precisie.

- `v1-voor.*`: de ontwikkelsplit van referentieset v1.
- `concept-voor.*`: de conceptcasussen `UBT01`–`UBT14` (bepalingen over uitbetaling op een bankrekening in vier regelingen).

**Lezen met voorbehoud.** De conceptcasussen zijn een AI-concept dat nog geen jurist zag, en hun gold bevat alleen de elementen die
de kandidaatruimte toetsen. De precisie is daar dus een ondergrens, en de cijfers zijn niet te vergelijken met v1. Ze tonen of een
fout weg is; ze bewijzen geen recall.

Opnieuw meten, vanuit `tools/graph-qa`:

```bash
.venv/bin/python -m eval.kandidaat_eval --casussen concept:UBT01,UBT02 --md /tmp/na.md
```
