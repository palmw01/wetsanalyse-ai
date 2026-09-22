---
name: wetsanalyse
metadata:
  methode_versie: "2.1"
description: >-
  Analyseer Nederlandse wet- en regelgeving volgens JAS, met JRM 2-verrijking.
  Gebruik voor juridisch ontleden, markeren en classificeren van bepalingen en
  voor een brononderbouwd conceptanalysedossier bij activiteit 2 van Wetsanalyse.
  Omvat grammatica, verwijzingen, juridische samenhang en scenario-toetsing.
---

# Wetsanalyse — JAS met JRM 2-verrijking

Lever een controleerbaar concept voor een menselijke analist. Methodeversie: 2.1,
2026-09-12. De dertien platformlabels blijven behouden; JRM 2 is aanvullende
semantiek in het dossier, geen vervanging van het annotatiecontract.

## Kies de uitvoervorm

- **Volledige analyse (standaard):** Markdown-dossier volgens
  [het sjabloon](assets/analysedossier.md). Lees het
  [analyseprotocol](references/analyseprotocol.md) en de
  [kwaliteitsrubriek](references/kwaliteit.md). Volg noodzakelijke officiële bronnen
  met de beschikbare zoek-/brontools. Ontbrekende toegang is een open punt, geen bewijs.
- **Alleen markeringen / platformannotatie:** werk uitsluitend binnen de aangeboden
  brontekst en het bestaande JSON-contract. Lees het
  [runtimeprotocol](references/annotatieprotocol.md). Geen extern onderzoek suggereren
  dat niet is uitgevoerd. Gebruik toelichtingen en alternatieven voor lokale twijfel;
  deze beperkte uitvoervorm levert geen volledig dossier of volledigheidsverklaring.

## Traceerbare grondslag

[Bronnen en beslisregister](references/bronnen.md) verbindt iedere methodestap met
bron + sectie en onderscheidt eigen projectkeuzes. De lokale originelen en hun hashes
staan in het gekoppelde manifest. Lees de relevante bronverantwoording bij twijfel of
wanneer je de methode zelf aanpast.

## Essentiële werkwijze

1. Leg opdracht, werkgebied, bronversie en peildatum vast. Ontbreken bepalende gegevens,
   vraag ze gericht op; werk ondertussen aan de delen die daarvan niet afhangen.
2. Ontleed structuur en grammatica vóór classificatie. Een grammaticaal onderwerp is
   niet automatisch de juridische actor. Lees [analyseprotocol](references/analyseprotocol.md).
3. Bepaal normeenheden, hun hoofdfunctie en samenhang; markeer betekenisdragende
   fragmenten volgens [fragmentgrenzen](references/markeren-fragmentgrenzen.md).
4. Onderzoek noodzakelijke context volgens [verwijzingen volgen](references/verwijzingen-volgen.md).
   Scheid wetstekst, interpretatie, beleid en hypothetische scenariofeiten.
5. Classificeer met de onderstaande labels en [klassenreferentie](references/jas-klassen-referentie.md).
   Onderbouw alternatieven; vul impliciete partijen nooit als letterlijk citaat in.
6. Verbind elementen en scenario's volgens [JRM-verrijking](references/jrm-verrijking.md).
7. Controleer dekking en onderbouwing. Lever open punten met concrete reviewvragen op.
   Alleen een mens kan de status 'vastgesteld' verlenen.

Elk citaat is letterlijk, aaneengesloten en herleidbaar tot bron + artikel + lid/onderdeel
+ voorkomen. Herformuleringen staan afzonderlijk. Meerdere markeringen mogen overlappen
als zij verschillende juridische functies dragen. Een taxonomie is geen algemene
voorrangsregel: uitsluitend tijd/plaats boven variabele/parameter bij dezelfde functie.

## Platformlabels

Signaalwoorden zijn zoekhulp, geen beslisregels. De klasse volgt uit de juridische
functie in context. De oorspronkelijke zestien tabelrijen zijn in dit platform tot
dertien labels samengevoegd; het onderscheid binnen de drie paren blijft inhoudelijk bestaan.

| Klasse | Wat het is | Herken aan |
| --- | --- | --- |
| **Rechtssubject** | Drager van rechten en plichten. Natuurlijke persoon of rechtspersoon. Partij in een rechtsbetrekking of bij een rechtsfeit. | Zelfstandig naamwoord voor persoon/entiteit; ‘hij’, ‘zij’, ‘iemand’, ‘een ieder’, ‘degene’ |
| **Rechtsobject** | Voorwerp van een rechtsbetrekking of rechtsfeit, fysiek of niet-fysiek. | Zelfstandig naamwoord (een woning, medische zorg); ‘dat’, ‘hetgeen’, ‘welk(e)’ |
| **Rechtsbetrekking** | Juridische relatie tussen twee rechtssubjecten: de een rechthebbend, de ander plichthebbend. | Werkwoord(combinatie): ‘heeft recht op’, ‘kan verzoeken’ (recht); ‘stelt vast’, ‘is verplicht’, ‘dient te’ (plicht) |
| **Rechtsfeit** | Handeling, gebeurtenis of tijdsverloop dat een wijziging in de juridische toestand teweegbrengt. | Actieve werkwoordsvorm, vaak genominaliseerd: ‘indienen van een bezwaarschrift’ |
| **Voorwaarde** | Conditie bij een rechtssubject, rechtsobject, rechtsbetrekking, rechtsfeit of afleidingsregel. | ‘indien’, ‘als’, ‘mits’, ‘tenzij’, ‘met uitzondering van’; ook een bijwoord: ‘schriftelijk’ |
| **Afleidingsregel** | Regel die op basis van bestaande feiten of waarden nieuwe feiten of waarden creëert. | ‘verminderd met’, ‘bedraagt’, ‘wordt gesteld op’, ‘het gezamenlijke bedrag van’ |
| **Variabele en variabelewaarde** | Waarde die per rechtssubject, rechtsobject, rechtsbetrekking of rechtsfeit kan verschillen (+ die waarde). | Getal, datum, tekst, enumeratie (limitatieve opsomming), booleaans (ja/nee) |
| **Parameter en parameterwaarde** | Waarde die over een (bepaalde of onbepaalde) periode gelijk is voor allen (+ die waarde). | Tarief, percentage, (drempel)bedrag, vrijstelling |
| **Operator** | Bewerking, vergelijking of logische verbinding. | ‘de som van’, ‘vermeerderd met’; ‘groter dan’, ‘is gelijk aan’; ‘en’, ‘of’, ‘niet’, ‘ten minste’ |
| **Tijdsaanduiding** | Aanduiding van een tijdstip of tijdvak. | Concrete datum, ‘kalenderjaar’, ‘maand’, ‘week’ |
| **Plaatsaanduiding** | Aanduiding van een plaats of gebied. | ‘Nederland’, ‘de gemeente Amsterdam’, ‘een lidstaat van de EU’ |
| **Delegatiebevoegdheid en delegatie-invulling** | Bevoegdheid om in lagere regelgeving nadere regels te stellen (+ de regeling die dat invult). | ‘bij (of krachtens) amvb / ministeriële regeling worden regels gesteld’ (verplicht); ‘kunnen regels worden gesteld’ (facultatief) |
| **Brondefinitie** | In de wetgeving opgenomen definitie. | Definitieartikel met aanhef en onderdelen, vaak vooraan de regeling |


## Reikwijdte en onderzoek

Activiteit 2 omvat ook de samenhang van elementen (2c). Noodzakelijke begripsduiding,
interpretatie en scenario's ondersteunen dit; formele RegelSpraak-/gegevensmodellen,
uitvoerbare besluiten en een nieuwe app-interface vallen buiten deze versie.

Bronverantwoording, afwijkingen en onderzoeksbevindingen:
[onderzoeksdocument](../../../docs/wetsanalyse/methode-onderzoek.md).
Voor conceptvoorbeelden en de gezamenlijke beoordelingsprocedure:
[referentieset](../../../docs/wetsanalyse/referentieset/README.md).

## Import in platformagents

[Agentrollen](references/agentrollen.md) beschrijft de beperkte runtime-uitvoering.
`agentrollen.json` koppelt rollen aan stabiele sectie-ID’s en M/P-bronnen.
Genereer beide Pythonbestanden met `tools/graph-qa/scripts/genereer_jas_klassen.py`.
De machineleesbare methodeversie staat uitsluitend in bovenstaande metadata;
de pakkethash onderscheidt wijzigingen binnen dezelfde inhoudelijke methodeversie.
