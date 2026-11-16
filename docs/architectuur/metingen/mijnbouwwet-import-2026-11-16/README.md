# Analyse van de import van de Mijnbouwwet (16 nov 2026)

Soort: *meting* · Code: branch `claude/mijnbouwwet-import` (op master `7859d2eb`) · Hoort bij:
[onderzoek-bronselectie-termijnen-2026-11.md](../../onderzoek-bronselectie-termijnen-2026-11.md), besluit gebruiker

De Mijnbouwwet (BWBR0014168) komt in de graaf: het winstaandeel van het werkgebied Termijnen staat daar. Eerst is de
import lokaal gedraaid met de echte importer, met dezelfde download, XSD-controle, parser en WTI-verrijking als de job op
Azure (`BWB_IMPORT_WTI=true`). De zeven regelingen van de graaf liepen mee, zodat verwijzingen tussen de wetten op dezelfde
manier oplossen als in één run. Er is niets naar GraphDB geschreven. De gebouwde graphs zijn vergeleken met de bron-XML, met
de officiële bron (`bron_lezen`) en met een import zonder de Mijnbouwwet.

**Toestand**: 2026-06-04, de nieuwste van 90 toestanden bij de officiële bron.

## Wat eerst misging, en het herstel

De importer weigerde de wet: *Sub-paragraaf 4.1a.1.1* en *Paragraaf 4.1a* kregen dezelfde IRI
(`urn:bwb:BWBR0014168:hoofdstuk:4:paragraaf:4.1a`). De jci van een sub-paragraaf draagt het segment `sub-paragraaf=`,
maar `_JCI_STRUCTUUR` in `bronmodel/bwb/references.py` kende alleen hoofdstuk, titeldeel, afdeling en paragraaf. De sleutel
viel zo terug op die van de ouder. Op Azure was de import van deze wet daardoor mislukt (exitcode 1); de andere wetten
waren wel geschreven.

Het herstel leest een sub-paragraaf als geneste paragraaf, zoals de parser al deed (`_STRUCTUUR_TAGS`):
`…:paragraaf:4.1a:paragraaf:4.1a.1.1`. Dat gebeurt op de drie plekken die de jci-vectoren gelijk houden: de importer
(`references.py`), `bronmodel.vindplaats` en de frontend (`lib/samenhang.ts`), met drie nieuwe vectoren en een test in
`tools/bwb-import/tests/test_references.py`. Geen andere regeling van de graaf heeft sub-paragrafen (0 in alle zeven
toestanden), dus geen bestaande IRI verandert.

## Volledigheid en juistheid

- **Tekstdekking 100,17%**: graaf 260.078 tekens tegen bron 259.635. De drempel van de importpoort is 99,5%. De graaf telt
  iets meer omdat titels en labels erbij komen; hetzelfde geldt voor de andere regelingen (100,00–100,15%).
- **XSD geldig, WTI gelukt, niets overgeslagen** (`wet.overgeslagen` leeg).
- **Structuur gelijk aan de bron**: 17 hoofdstukken, 7 afdelingen, 40 paragrafen (inclusief 4 sub-paragrafen), 322
  artikelen (waarvan 29 vervallen, als "Vervallen" met status `vervallen`), 643 leden en 1 bijlage. Onderdelen: 609 in de graaf
  tegen 607 `<li>` in de bron. Het verschil zijn twee slotteksten (art. 63 lid 3, art. 68a lid 2): een alinea na een lijst
  wordt een eigen node, zoals bij de andere regelingen.
- **Tekst per artikel**: van alle 322 artikelen staat elk woord van de bron ook in de graaf (artikel met alles eronder,
  zonder nummers en koppen). Geen enkel artikel met een tekort. Geen lege tekst.
- **Geen wezen en geen dubbele ouders**: elke node van de wet hangt aan precies één ouder.
- **Steekproef tegen de officiële bron**: art. 72 letterlijk gelijk.

## Verwijzingen

- 703 verwijzingen in de bron (510 intern, 193 naar andere regelingen), 770 in de graaf (de importer herkent ook verwijzingen
  in de tekst). Naar de Mijnbouwwet zelf 586, naar de AWR 14, naar de Invorderingswet 1990 17 en naar de Awb 25. De
  rest gaat naar wetten buiten de graaf (onder meer BWBR0037885 en de Wet Vpb 1969).
- **Twee verwijzingen blijven bewust onopgelost.** Art. 142 lid 2 verwijst naar "hoofdstuk V, afdelingen 2 [en] 4" van de
  AWR, maar de jci noemt alleen de afdeling. De AWR heeft meer afdelingen 2 en 4 (hoofdstuk V, VIII, IX), dus de
  structuurindex lost ze niet op: liever geen doel dan het verkeerde. De ankertekst noemt het hoofdstuk wel. Dit is een
  bekende grens van de importer en geldt voor elke regeling; geen blokkade.
- **Inkomend**: de Awb verwijst 25 keer naar de Mijnbouwwet. Die doelen bestaan na de import als node.
- **De zeven bestaande regelingen veranderen niet**: hun graphs zijn triple voor triple gelijk aan een import zonder de
  Mijnbouwwet (0 erbij, 0 eraf).

## Definities en WTI

- 60 begrippen uit de begripsbepalingen (onder meer *winningsvergunning*, *mijnbouwwerk*, *opslagvergunning*, *de inspecteur*,
  *de ontvanger*). Het winstaandeel zelf wordt niet gedefinieerd maar geregeld in art. 65–72.
- WTI: citeertitel, soort *wet*, geldig vanaf, toestand-URL, de eerstverantwoordelijke organisatie (TOOI
  `mnre1045`, het ministerie van Economische Zaken en Klimaat volgens de TOOI-tabel van de importer). De WTI van de Mijnbouwwet heeft **geen afkorting**, dus "Mbw" vindt Lex niet als afkorting. Dat is wat de bron
  levert.

## Wat dit betekent voor het werkgebied Termijnen

- Art. 65: van wie het winstaandeel wordt geheven. Art. 70 lid 1: het winstaandeel wordt geheven bij wege van aanslag.
  Art. 71: de inspecteur heft en de ontvanger int. Art. 72: de heffing en invordering gaan met overeenkomstige toepassing
  van de AWR en de Invorderingswet 1990.
- Art. 72 is de brug tussen het winstaandeel en de voorlopige aanslag (AWR art. 13), de termijnen (Iw art. 9) en de
  verrekening (Iw art. 24). De graaf legt die brug vast als verwijzing naar de regeling als geheel.
- De Mijnbouwwet staat nog niet in het zoekbereik van het werkgebied. Dat kiest de gebruiker.

## Nog te doen na het mergen

De importlijst staat in de bicep (`bwbIds`), dus de Mijnbouwwet komt pas in de graaf van acceptatie na een `azure-infra`
deploy met daarna de import-job. Daarna een controle tegen de graaf zelf: aantallen, de IRI's van de sub-paragrafen, de
FTS-index op "winstaandeel" en de similarity-index (die de importer herbouwt als er een regeling bij komt).
