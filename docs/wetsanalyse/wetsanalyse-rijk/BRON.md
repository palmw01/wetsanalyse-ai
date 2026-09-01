# Herkomst

Deze map bevat de markdown-bronbestanden van de officiële Wetsanalyse-documentatie
van de Rijksoverheid (Ministerie van BZK).

- Bron: https://minbzk.github.io/wetsanalyse/ – repo https://github.com/minbzk/wetsanalyse
- Branch: main · commit 5ae93cc2a053c19a9f20eea295e667bd144e47fb (2024-11-29)
- Opgehaald: 2026-06-06

`H2-JAS.md` bevat het volledige Juridisch Analyseschema (de gezaghebbende klassenindeling).

## Licentie

Het bronmateriaal staat onder de **W3C Software and Document License**; de volledige tekst
staat naast dit bestand in [`LICENSE`](LICENSE). Die licentie staat kopiëren, wijzigen en
verspreiden toe, maar stelt als voorwaarde dat de volledige notice zichtbaar meegaat op elke
kopie – vandaar dat `LICENSE` hier staat en niet alleen in de bronrepo.

Deze map valt daarmee **buiten** de EUPL-1.2 waaronder de rest van dit project staat; zie de
`LICENSE` in de projectroot.

## Wijzigingen ten opzichte van de bron

De inhoudelijke documenten (`abstract.md`, `H1-Inleiding.md`, `H2-JAS.md`, `H3-Kader.md` en
`media/`) zijn **ongewijzigd** overgenomen. Twee afwijkingen, hier vastgelegd omdat de licentie
vermelding van wijzigingen verlangt:

1. Dit `BRON.md` is toegevoegd; het bestaat niet in de bronrepo.
2. De `README.md` van de bronrepo is **niet overgenomen** (1 sep 2026). Dat bestand bevat de
   ReSpec-template-instructie van Logius — hoe je met `config.js` en GitHub Actions een HTML- en
   PDF-versie publiceert. Het gaat over het publicatiegereedschap van de bronrepo en niet over
   Wetsanalyse, en op deze plek was het misleidend: wie de `README.md` van een map opent, verwacht
   een inleiding op die map. De inhoudelijke bestanden zijn er niet door geraakt.
