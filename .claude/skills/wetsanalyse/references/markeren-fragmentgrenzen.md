# Markeren: waar begint en eindigt een fragment?

Classificeren is de helft van activiteit 2; de andere helft is *markeren* — bepalen welk stuk tekst
je precies aanwijst. De officiële Rijksspecificatie
(`docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md`) beschrijft de klassen maar geeft geen
markeerprocedure. Wat hieronder staat is de operationele uitwerking daarvan.

**Herkomst.** De klasse-inhoud komt uit de Rijksbron (zie `jas-klassen-referentie.md`, met
regelverwijzingen). De markeerregels in dit bestand zijn afgeleid uit de readers van het
Expertisecentrum BRM en het boek van Ausems, Bulles & Lokin — materiaal van derden dat lokaal-only
in `docs/wetsanalyse/` staat en niet in deze publieke repo (zie `CLAUDE.md`). Ze zijn hier in eigen
woorden weergegeven, niet overgenomen. Waar de bronnen elkaar tegenspreken staat dat erbij.

## De leidende norm

**Markeer precies zoveel tekst als nodig is om de betekenis van het element volledig te dragen —
niet meer, niet minder.** De klasse die je wilt toekennen bepaalt daarbij de omvang: dezelfde zin
levert een kort fragment op als je een variabele markeert en een lang fragment als je de
afleidingsregel markeert waarin die variabele zit.

Dat betekent dat "hoeveel tekst?" geen losse vraag is. Bepaal eerst welke klasse je wilt
vastleggen, en laat die de grenzen kiezen.

## Fragmentgrenzen per klasse

| klasse | wat hoort erbij |
|---|---|
| **Variabele** | het kenmerk zelf, mét lidwoord. **Geen** werkwoord, **geen** voorwaarden. |
| **Parameter** | de beschrijving van de waarde. De grootheid (‘procent’) hoort bij de parameter, niet bij de parameterwaarde. |
| **Parameterwaarde** | alleen de concrete waarde (het bedrag, het percentage, de datum). |
| **Afleidingsregel** | de hele regel: werkwoorden, voorwaarden, verwijzingen en het afsluitende leesteken. |
| **Voorwaarde** | de hele zin of het hele zinsdeel waarin de conditie wordt omschreven. |
| **Rechtsbetrekking** | de volledige formulering die de relatie draagt — in de praktijk vaak het hele lid. |
| **Rechtssubject / Rechtsobject** | het zelfstandig naamwoord met zijn lidwoord en de bepalingen die het afbakenen. |

Twee regels die overal gelden:

- **Neem het lidwoord mee.** Dat maakt het achteraf mogelijk te controleren of elk deel van de
  tekst is bekeken.
- **Neem een verwijzing mee als die de betekenis draagt.** In "het overeenkomstig het eerste lid
  berekende bedrag" hoort de verwijzing bij het fragment: zonder haar is het bedrag niet bepaald.

## Overlappende markeringen zijn normaal

Markeringen mogen elkaar overlappen en dat is geen fout maar de verwachte uitkomst. Een voorwaarde
bevat vrijwel altijd variabelen; een rechtsbetrekking bevat de rechtssubjecten en het rechtsobject
waar zij over gaat. Dezelfde woorden dragen dan meerdere klassen, elk met een eigen markering.

Zo levert één lid van een bepaling over een verschuldigde bijdrage al snel op: het rechtssubject
(wie is de bijdrage verschuldigd), de rechtsbetrekking (de hele formulering van de plicht), het
rechtsobject (de bijdrage), een variabele (het bedrag waarover wordt gerekend) en een
tijdsaanduiding (het kalenderjaar). Vijf markeringen, deels op dezelfde woorden.

Werk dus fijnmazig. Eén markering per lid is vrijwel zeker te grof.

## Waar je begint

Anker je analyse aan een **centrale klasse** — een klasse die relaties met andere klassen heeft:
*rechtsbetrekking*, *rechtsfeit*, *afleidingsregel* of *voorwaarde*. Zoek die eerst, en hang de
rest eraan op: wie is rechthebbende, wie plichthebbende, wat is het voorwerp, onder welke
voorwaarden.

> De readers verschillen hier: de een omschrijft een centrale klasse als een klasse die *andere
> klassen omvat*, de ander als een klasse die *relaties heeft met* andere klassen, en de een rekent
> `voorwaarde` er wel toe en de ander niet. De relatie-omschrijving is voor annoteren de
> bruikbaarste; `voorwaarde` telt mee.

Bij een bepaling die iets berekent: begin bij de formulering die de **uiteindelijke waarde**
vaststelt, en zoek van daaruit terug naar de invoervariabelen.

Vaste ontleedvolgorde per bepaling:

1. rechtssubject(en) — ook de partij die er niet staat, zie hieronder
2. rechtsbetrekking — de formulering die het recht of de plicht draagt
3. rechtsobject — waar gaat dat recht of die plicht over
4. rechtsfeit — welke handeling of gebeurtenis verandert de toestand
5. voorwaarde(n) — en bij elke voorwaarde de variabelen waaraan getoetst wordt
6. operator, parameter/parameterwaarde, tijds- en plaatsaanduiding
7. delegatiebevoegdheid, brondefinitie

## De tegenpartij staat er meestal niet

Wetgeving noemt vrijwel altijd maar één kant van een rechtsbetrekking — meestal de partij die
handelt. De andere kant (vaak de Staat of het bestuursorgaan) is impliciet.

Dat levert een spanning op met brongetrouwheid, en die lossen we hier eenduidig op: **markeer
alleen wat er letterlijk staat.** Ontbreekt de tegenpartij in de tekst, dan maak je daar géén
markering voor — je benoemt het in de `toelichting` van de rechtsbetrekking. Hetzelfde geldt voor
een voorwaarde die wel meespeelt maar nergens in woorden staat. Een element zonder tekstanker is
een interpretatie, en die hoort in de toelichting, niet in een fragment.

## Verwijzende woorden

Een verwijzend woord krijgt de klasse van datgene waarnaar het verwijst. Zoek dus eerst het
antecedent, classificeer dát, en pas daarna het verwijzende fragment.

- Een persoonlijk voornaamwoord dat verwijst naar iemand die handelt of een recht of plicht draagt,
  is zelf een **rechtssubject** ("hij" → de geadresseerde).
- Een aanwijzend voornaamwoord dat naar een zaak of aanspraak verwijst, is een **rechtsobject**
  ("een dergelijke kennisgeving").

**Toets bij twijfel over een persoonsaanduiding:** verricht die persoon in dít fragment een
handeling, of draagt hij hier een recht of plicht? Zo ja → rechtssubject. Zo nee → het is
waarschijnlijk een nadere typering van een rechtsobject. In "een bericht dat tot een of meer
geadresseerden is gericht" bakenen de geadresseerden het *bericht* af; in "voor zover de
geadresseerde kenbaar heeft gemaakt…" handelt de geadresseerde zelf en is hij rechtssubject.

## Dezelfde woorden, andere betekenis

Een term die in meerdere bepalingen voorkomt betekent daar niet noodzakelijk hetzelfde —
"verzekerde" is in drie zorgwetten drie verschillende afbakeningen.

Werkwijze wanneer je vermoedt dat een formulering elders anders wordt gebruikt: zoek eerst alle
vindplaatsen binnen het werkgebied, stel per vindplaats vast wat er bedoeld wordt, en classificeer
pas daarna. **Markeer het tekstdeel mee waaruit de afwijkende betekenis blijkt** — de
leeftijdsgrens, de uitzondering, de afbakenende bijzin. Zonder dat deel vallen twee verschillende
begrippen samen in één markering.

## Opsommingen en onderdelen

Bij een artikel met een aanhef en onderdelen a, b, c:

- de **aanhef** draagt de klasse van het geheel — een samengestelde voorwaarde, een afleidingsregel,
  of de operator die de onderdelen verbindt;
- **elk onderdeel** krijgt een eigen markering, in de rol die de aanhef eraan geeft.

Een limitatieve opsomming van mogelijke waarden levert één variabele op met meerdere
**variabelewaarden**, niet een reeks losse variabelen.

Let bij samengestelde voorwaarden op het verbindende woord: ‘en’ is cumulatief, ‘of’ alternatief.
‘ten minste’ duidt op cumulatie, maar signaleert ook dat de opsomming mogelijk niet limitatief is —
noteer dat als aandachtspunt.

Staat er ‘en’ tussen twee volwaardige regels, dan zitten er waarschijnlijk **twee**
afleidingsregels in één lid.

## Wat je niet markeert

Volledigheid is een controlemiddel, geen doel. Niet elk woord hoeft een markering te dragen.

- **Verbindende zinsdelen** die alleen een relatie leggen tussen elementen die je al hebt
  gemarkeerd, krijgen geen eigen markering.
- **Losse woorden zonder relatie tot een centrale klasse** markeer je niet. Elk zelfstandig
  naamwoord aanwijzen levert ruis op, geen structuur.
- **Vaste, triviale waarden** zoals "nihil" zijn geen parameter om apart vast te leggen.
- **Impliciet toepassingsbereik** is geen plaatsaanduiding: de meeste wetgeving geldt zonder het te
  zeggen voor heel Nederland.
- Wat overblijft is doorgaans taalkundige hulptekst. Blijft er véél tekst ongemarkeerd, dan is dat
  een signaal dat je iets gemist hebt — geen bewijs dat de bepaling leeg is.

## Twee onderdelen kunnen hetzelfde betekenen

Onderdelen van een opsomming kunnen juridisch op hetzelfde neerkomen terwijl ze anders zijn
geformuleerd. Voeg ze niet stilzwijgend samen: markeer beide en benoem de samenval in de
`toelichting`.
