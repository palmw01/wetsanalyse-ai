# Stap 2 – B: een rechtsgevolg als hoofdzin (gevolgdetector)

Code: commit `1be399b`. Voor: `01-C/`. Criterium: `../criteria/02-B.yaml`.

**Criterium: geslaagd.** De waarneming B7 (ankerdekking-minimum v1) gaat van 77,8% naar 75,3% en is
geen poort. De v1-detectie is identiek, dus dit is variatie.

- **Deterministisch.**
  - E08 ("De eerste termijn vervalt …", 435–567) is een kandidaat met [RB, RF].
  - E17 krijgt Rechtsbetrekking erbij.
  - In de diagnostiek (LI-D3) komen vier vervalclauses bij.
  - Een inversievoorwaarde ("Is de dagtekening …, vervalt …") hoort niet meer bij de clause.
- **Model, IW05 × 5.**
  - E08 wordt nu gemarkeerd, in 5/5 runs, maar als **Rechtsfeit**: het concept zegt Rechtsbetrekking.
  - E17 wordt 5/5 Afleidingsregel.
  - De ankerdekking van Rechtsbetrekking stijgt van 0% naar 33%, via E01.
  - Welke klasse E08 en E17 horen te krijgen, is precies reviewvraag 1 van het concept.
