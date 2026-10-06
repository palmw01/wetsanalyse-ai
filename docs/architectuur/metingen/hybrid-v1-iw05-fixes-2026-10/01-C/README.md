# Stap 1 – C: precieze spans voor de functiedetector

Code: commit `e341d5b` (codegelijk aan de PR-commit na de rebase). Voor: `00-nul/`. Criterium: `../criteria/01-C.yaml`.

**Criterium: geslaagd** (`criteria.txt`).

- **Deterministisch.** "zoveel … als …" (E05, 296–433) en "vindt het eerste lid toepassing" (E17)
  zijn kandidaten op hun eigen span. De normkandidaat over volzin 1 (E01) draagt geen Afleidingsregel
  meer. De v1-audit is identiek.
- **Model, IW05 × 5** (`vergelijk-iw05.md`):
  - volzin 1 was 5/5 Afleidingsregel en is nu Rechtsbetrekking (2/5) of niet voorgesteld;
  - "zoveel … als …" is 5/5 Afleidingsregel;
  - F1 29% → 35%.
- **Model, v1 16 × 3** (`vergelijk-v1.md`): alle maten binnen de spreiding. De code is op v1
  ongewijzigd, dus elk verschil hier is run-variatie. Deze stap dient zo als ijkpunt voor de
  variatie.
