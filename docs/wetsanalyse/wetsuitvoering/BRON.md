# Herkomst

Deze map bevat de markdown-bronbestanden van de specificatie van het **Juridisch Referentiemodel (JRM 2)**, de
methode wetsuitvoering, gepubliceerd door het Ministerie van BZK.

- Bron: https://minbzk.github.io/wetsuitvoering/ – repo https://github.com/minbzk/wetsuitvoering
- Branch: main · commit 4a9b58440c6a07113bce0095d29b60dd11a56bc3 (2025-03-21)
- Opgehaald: 2026-11-12

De inhoud: de hoofdclassificaties van het JRM (H1), juridische scenario's als kernonderdeel (H2), het rechtsgevolg
als eigen classificatie (H3), het juridisch relevant feit (H4) en de waarde ter vervanging van parameter- en
variabelewaarde (H5). Verwant aan de werkversie *Doorontwikkelingen en voortschrijdend inzicht in Wetsanalyse*
(M06 in het bronregister van de skill wetsanalyse).

## Licentie

Het bronmateriaal staat onder de **W3C Software and Document License**; de volledige tekst staat naast dit bestand
in [`LICENSE`](LICENSE). Die licentie staat kopiëren, wijzigen en verspreiden toe, op voorwaarde dat de volledige
notice zichtbaar meegaat op elke kopie – vandaar dat `LICENSE` hier staat. Deze map valt daarmee buiten de licentie
van de rest van dit project.

## Wijzigingen ten opzichte van de bron

De inhoudelijke documenten (`abstract.md` en `H1`–`H5`) zijn **ongewijzigd** overgenomen. Afwijkingen, hier
vastgelegd omdat de licentie vermelding van wijzigingen verlangt:

1. Dit `BRON.md` is toegevoegd; het bestaat niet in de bronrepo.
2. De `README.md` van de bronrepo is niet overgenomen: die bevat de ReSpec-template-instructie van Logius over het
   publicatiegereedschap, niet over de methode (zoals bij `wetsanalyse-rijk/`).
3. De map `js/` (ReSpec-configuratie) en `media/` zijn niet overgenomen; de documenten verwijzen er niet naar voor
   hun inhoud.

De skill `.claude/skills/wetsuitvoering/` werkt deze specificatie uit voor gebruik met Claude en Lex. Waar die skill
letterlijk citeert, staat dat erbij; de rest is een eigen uitwerking.
