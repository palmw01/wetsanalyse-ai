# JAS-klassen – volledige referentie

De dertien klassen van het Juridisch Analyseschema, zoals vastgelegd in de officiële
Rijksspecificatie. Dit zijn de **enige** toegestane klassen; verzin er geen bij.

**Bron.** `docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md` (BZK, W3C-licentie – zie
`wetsanalyse-rijk/BRON.md`) en de JAS-tabel `docs/wetsanalyse/wa-table.png`. Per klasse staan de
drie bronvelden *omschrijving / vraag / uitdrukkingswijze* hier **volledig**, met regelverwijzing,
plus de korte definitie uit de tabel. Regelverwijzingen zoals `H2:44` betekenen: `H2-JAS.md`,
regel 44.

**Waarom deze referentie er is.** De compacte tabel in `SKILL.md` volstaat voor het gewone geval.
Sla dit bestand op zodra je twijfelt tussen twee klassen, een grensgeval tegenkomt, of de
uitdrukkingswijze van een klasse precies wilt weten.

## Dertien klassen, zestien rijen

De JAS-tabel nummert **zestien** rijen; onze labelset telt er dertien. Drie paren zijn
samengevoegd omdat de bron ze "vanwege de nauwe samenhang" (`H2:80`, `H2:89`, `H2:125`) gezamenlijk
behandelt:

| tabelrijen | onze klasse |
|---|---|
| 7 Variabele + 8 Variabelewaarde | Variabele en variabelewaarde |
| 9 Parameter + 10 Parameterwaarde | Parameter en parameterwaarde |
| 14 Delegatiebevoegdheid + 15 Delegatie-invulling | Delegatiebevoegdheid en delegatie-invulling |

Het onderscheid binnen een paar blijft inhoudelijk gelden — een parameter is de *beschrijving*,
een parameterwaarde de *concrete waarde* — maar beide krijgen hetzelfde label. Zeg in de
`toelichting` welke helft je bedoelt.

## Ordening: welke klasse is specifieker?

De taxonomie uit het begrippenkader (`H3-Kader.md:19-33`) ordent de klassen. Bij samenloop is dit
de tiebreaker: **hoe dieper in de boom, hoe specifieker**.

```
rechtssubject · rechtsobject · rechtsbetrekking · delegatiebevoegdheid ·
delegatie-invulling · rechtsfeit
voorwaarde
└── afleidingsregel
    ├── operator
    ├── variabele
    │   ├── variabelewaarde
    │   ├── tijdsaanduiding
    │   └── plaatsaanduiding
    └── parameter
        └── parameterwaarde
```

Let op dat tijds- en plaatsaanduiding hier onder **variabele** hangen. Dat verklaart de
prioriteitsregel hieronder: ze zijn een verbijzondering, en de verbijzondering wint.

---

## 1. Rechtssubject

**Omschrijving** (`H2:26`) — Een rechtssubject is de drager van rechten en plichten. Het is een
partij in een rechtsbetrekking.

**Vraag** (`H2:27`) — Wie heeft het recht? Wie heeft de plicht? Van wie is een rechtsobject? Bij
wie hoort een waarde?

**Uitdrukkingswijze** (`H2:28`) — Te herkennen aan een zelfstandig naamwoord waarmee een persoon
of andere entiteit wordt beschreven, of aan een persoonlijk voornaamwoord zoals ‘hij’, ‘zij’ en
soms ook ‘het’. Maar ook een onbepaald of betrekkelijk voornaamwoord kan wijzen op een
rechtssubject, bijvoorbeeld ‘iemand’, ‘een ieder’ of ‘degene’.

**Uit de JAS-tabel** (rij 1) — "Drager van rechten en plichten. Natuurlijke persoon of
rechtspersoon. Partij in een rechtsbetrekking **of bij een rechtsfeit**."

> De tabel is hier ruimer dan de prozatekst: een rechtssubject kan ook partij zijn bij een
> *rechtsfeit*, niet alleen bij een rechtsbetrekking.

---

## 2. Rechtsobject

**Omschrijving** (`H2:35`) — Een rechtsobject is het voorwerp van een rechtsbetrekking en/of
rechtsfeit. Een rechtsobject kan zowel een fysieke (bijvoorbeeld een personenauto of een huis) als
een niet-fysieke verschijningsvorm (bijvoorbeeld medische zorg) hebben.

**Vraag** (`H2:36`) — Wat is het voorwerp van een recht of plicht? Waar is het rechtssubject
eigenaar of houder van? Waar heeft een waarde betrekking op? Waarover is iets verschuldigd?

**Uitdrukkingswijze** (`H2:37`) — Te herkennen aan een zelfstandig naamwoord waarmee het voorwerp
van een recht of plicht wordt omschreven, bijvoorbeeld een studie, een woning of een
dienstbetrekking. Ook een aanwijzend of betrekkelijk voornaamwoord kan wijzen op een rechtsobject,
bijvoorbeeld ‘dat’, ‘hetgeen’ en ‘welk(e)’.

**Uit de JAS-tabel** (rij 2) — "Voorwerp van een rechtsbetrekking of rechtsfeit met een fysieke of
een niet-fysieke verschijningsvorm."

---

## 3. Rechtsbetrekking

**Omschrijving** (`H2:44`) — Een rechtsbetrekking is een juridische relatie tussen twee
rechtssubjecten en beschrijft een specifieke juridische toestand tussen deze rechtssubjecten. Een
van deze rechtssubjecten heeft een plicht en de ander het bijbehorend recht. De algemene juridische
toestand van een rechtssubject is de verzameling van alle specifieke rechtsbetrekkingen waarin dit
rechtssubject als rechthebbende of plichthebbende partij optreedt.

**Vraag** (`H2:45`) — Hoe verhouden twee rechtssubjecten zich tot elkaar? Welke relatie(s) hebben
twee rechtssubjecten met elkaar?

**Uitdrukkingswijze** (`H2:46`) — Te herkennen aan een of meer werkwoorden, langs **twee**
herkenningsroutes:

- *hoofdwerkwoord met hulpwerkwoord* — bij een recht: ‘kan verzoeken’, ‘mag wijzigen’; bij een
  plicht: ‘stelt vast’, ‘mag niet inhalen’, ‘is verplicht informatie te verstrekken’, ‘moet
  informeren’, ‘dient te voldoen’.
- *samengesteld werkwoord* — bij een recht: ‘heeft recht op’, ‘heeft aanspraak op’; bij een plicht:
  ‘heeft de plicht om’, ‘draagt de last om’.

**Uit de JAS-tabel** (rij 3) — "Juridische relatie tussen twee rechtssubjecten waarvan het ene
rechtssubject rechthebbend en het andere rechtssubject plichthebbend is."

---

## 4. Rechtsfeit

**Omschrijving** (`H2:53`) — Een rechtsfeit is een handeling of gebeurtenis die, of tijdsverloop
dat een wijziging in de juridische toestand teweegbrengt. Aan een rechtsfeit zijn dus
rechtsgevolgen verbonden die een rechtsbetrekking creëren, wijzigen of beëindigen.

**Vraag** (`H2:54`) — Wat is de gebeurtenis of handeling die, of het tijdsverloop dat gevolgen
heeft voor de rechtsbetrekking?

**Uitdrukkingswijze** (`H2:55`) — Te herkennen aan een actieve werkwoordsvorm, al dan niet in
combinatie met een zelfstandig naamwoord, zoals ‘indienen van een bezwaarschrift’, ‘toekennen van
een subsidie’, ‘horen van belanghebbende’ of ‘kenbaar maken van elektronische bereikbaarheid’.

**Uit de JAS-tabel** (rij 4) — "Handeling of gebeurtenis die, of tijdsverloop dat een wijziging in
de juridische toestand teweegbrengt."

**Onderscheid met rechtsbetrekking.** Beide zijn werkwoordelijk. Een rechtsbetrekking beschrijft
een *toestand* (‘mag’, ‘moet’, ‘heeft recht op’); een rechtsfeit beschrijft een *verandering* en
staat vaak in genominaliseerde vorm (‘indienen van…’).

---

## 5. Voorwaarde

**Omschrijving** (`H2:62`) — Een voorwaarde is een conditie die beschrijft aan welke omstandigheid
voldaan moet zijn voor het intreden van een rechtsgevolg. Een voorwaarde kan ook betrekking hebben
op een rechtssubject of op een waarde die bij een rechtsobject of bij een afleidingsregel hoort.
Een voorwaarde bevat vaste elementen, die in de logica operanden en operatoren worden genoemd.
Operanden kunnen rechtssubjecten of rechtsobjecten, eigenschappen van rechtssubjecten of
rechtsobjecten, berekeningen of waarden zijn. Een operator is de beschrijving van een vergelijking
die in de voorwaarde voorkomt, zoals ‘groter dan’, ‘kleiner dan’ en ‘gelijk aan’.

**Vraag** (`H2:63`) — Welke eisen worden gesteld aan een rechtssubject, een rechtsobject, een
rechtsbetrekking of een rechtsfeit? Onder welke omstandigheden geldt een waarde bij een
rechtsobject?

**Uitdrukkingswijze** (`H2:64`) — Te herkennen aan een voorwaardelijke bijzin, in de meeste
gevallen ingeleid door een voegwoord zoals ‘indien’, ‘als’, ‘tenzij’, ‘mits’ of een combinatie van
woorden, zoals ‘met dien verstande dat’ of ‘met uitzondering van’. Ook kan een voorwaarde afgeleid
worden uit een **bijwoord bij een werkwoord**, zoals ‘schriftelijk’ of ‘elektronisch’. Voorwaarden
kunnen enkelvoudig of samengesteld zijn: een samengestelde voorwaarde bestaat uit verschillende
eisen die alle vervuld moeten zijn (cumulatief) of waarvan er één vervuld moet zijn (alternatief).

**Uit de JAS-tabel** (rij 5) — "Conditie bij een rechtssubject, rechtsobject, rechtsbetrekking,
rechtsfeit **of afleidingsregel**. Bepaalt aan welke eisen voldaan moet worden."

> *Eigen toevoeging, niet uit de bron:* in de praktijk werkt **‘voor zover’** ook als
> voorwaardelijk signaalwoord. De bron noemt het niet — behandel het als hulpmiddel bij het
> herkennen, niet als bronformulering.

**Let op** — een voorwaarde hoeft geen voegwoord te hebben. Een bijwoord (‘schriftelijk’) of een
voorzetselbepaling draagt hem net zo goed.

---

## 6. Afleidingsregel

**Omschrijving** (`H2:71`) — Een afleidingsregel is een regel die nieuwe feiten of waarden creëert
met behulp van bestaande feiten of waarden. Te denken valt aan regels die bepalen of een recht
bestaat (een *beslisregel*), of die de hoogte en duur van een recht bepalen (een *rekenregel*). De
variabele die vastgesteld wordt door de afleidingsregels, noemen we **uitvoervariabele**. Bij een
rekenregel is dit de uitkomst van de rekensom; bij een beslisregel een conclusie als ja/nee of
waar/onwaar. De variabelen die gebruikt worden voor de vaststelling, noemen we
**invoervariabelen**. Als sprake is van vaste getallen of waarden in een afleidingsregel die over
een periode gelijk zijn voor alle rechtssubjecten en rechtsobjecten, noemen we deze **parameters**.

Afleidingsregels worden ook gebruikt om te bepalen of een rechtssubject of rechtsobject tot een
bepaalde doelgroep behoort; het gaat dan om het afleiden van **specialisaties** van
rechtssubjecten en rechtsobjecten op basis van bepaalde kenmerken.

**Vraag** (`H2:72`) — Hoe wordt een variabele berekend of afgeleid? Hoe wordt een specifiek
rechtssubject of rechtsobject bepaald?

**Uitdrukkingswijze** (`H2:73`) — Te herkennen aan woorden die duiden op een berekening of
afleiding, zoals ‘is (…) verminderd met’, ‘bedraagt (…) vermeerderd met’, ‘wordt gesteld op’ of
‘is het gezamenlijke bedrag van’, maar ook eenvoudigweg ‘en’.

**Uit de JAS-tabel** (rij 6) — "Regel die op basis van bestaande feiten of waarden nieuwe feiten of
waarden creëert."

---

## 7. Variabele en variabelewaarde

**Omschrijving** (`H2:80`) — Een *variabele* is een kenmerk van een rechtssubject, rechtsobject,
rechtsbetrekking of rechtsfeit dat voor verschillende instanties daarvan (dus voor specifieke
personen, zaken, relaties, handelingen of gebeurtenissen in de werkelijkheid) een andere waarde kan
hebben. Een *variabelewaarde* geeft de waarde aan die een bepaalde variabele kan hebben. De wijze
waarop een variabelewaarde is omschreven in wetgeving kan een beperking in de mogelijke waarden
voor een variabele inhouden, of een voorwaarde aan een variabele stellen.

**Vraag** (`H2:81`) — Wat zijn de specifieke kenmerken van een rechtsobject, rechtssubject,
rechtsbetrekking of rechtsfeit? Welke eigenschappen worden genoemd? Welke waarde heeft een
rechtsobject? Hoe lang of hoe hoog is een rechtsobject? En voor de waarde: welk bedrag, welke duur
of welke hoogte hoort bij deze variabele?

**Uitdrukkingswijze** (`H2:82`) — vier varianten:

- **getal of datum** — een concreet bedrag, een concrete datum, een concrete tijdsduur of een
  andere numerieke waarde;
- **tekst** — bijvoorbeeld de variabele ‘naam van een werkgever’;
- **enumeratiewaarde** — een limitatieve opsomming van de mogelijke waarden, in getallen of tekst;
- **booleaanse waarde** — een bijzondere enumeratiewaarde met twee waarden, ‘ja’ (waar) of ‘nee’
  (onwaar); bijvoorbeeld de variabele ‘geregistreerd in het donorregister’.

**Uit de JAS-tabel** (rij 7 + 8) — "Beschrijving van een waarde die per rechtssubject,
rechtsobject, rechtsbetrekking of rechtsfeit kan verschillen." / "Concrete waarde die een bepaalde
variabele kan hebben."

---

## 8. Parameter en parameterwaarde

**Omschrijving** (`H2:89`) — Een *parameter* is een beschrijving van een waarde die gelijk is voor
alle rechtssubjecten, rechtsobjecten, rechtsbetrekkingen en rechtsfeiten. Vanwege de stabiele
waarde wordt een parameter ook wel constante genoemd. Parameters worden gebruikt in
afleidingsregels en voorwaarden. In de regel geldt een parameter voor een bepaalde periode,
bijvoorbeeld een kalenderjaar, **maar hij kan ook voor een onbepaalde duur gelden** (bijvoorbeeld
voor de hele geldigheidsduur van de wettelijke regel). De waarde die een parameter in de
desbetreffende periode heeft, is een *parameterwaarde*. De parameter is dus de omschrijving van de
waarde, en de parameterwaarde is de concrete waarde die daaraan is toegekend.

**Vraag** (`H2:90`) — Is sprake van een waarde die gedurende een periode een vaste hoogte heeft
voor alle rechtssubjecten en rechtsobjecten?

**Uitdrukkingswijze** (`H2:91`) — Een parameter is te herkennen aan een beschrijving van een
waarde, bijvoorbeeld van een tarief, een (drempel)bedrag (eventueel met een maximum of een
minimum) of een vrijstelling. Een parameterwaarde is te herkennen aan bijvoorbeeld een bedrag in
geld, een percentage of een datum.

**Uit de JAS-tabel** (rij 9 + 10) — "Beschrijving van een waarde die over een **(bepaalde of
onbepaalde)** periode gelijk is voor alle rechtssubjecten, rechtsobjecten, rechtsbetrekkingen en
rechtsfeiten." / "Concrete waarde die een parameter over een periode kan hebben."

**Toets variabele of parameter** — varieert de waarde per rechtssubject of rechtsobject binnen de
periode? Ja → variabele. Nee, gelijk voor allen → parameter. Een constante zonder periodegebonden
waarde blijft een parameter; "onbepaalde duur" telt mee.

---

## 9. Operator

**Omschrijving** (`H2:98`) — Een operator is een woord, een combinatie van woorden **of een teken**
dat een rekenkundige bewerking, een samengestelde voorwaarde, een gelijkstelling of een
vergelijking van twee waarden of berekeningen uitdrukt. Een operator beschrijft hoe verschillende
elementen van een berekening, voorwaarde of samengestelde voorwaarde met elkaar verbonden worden om
tot een resultaat te leiden. Drie typen:

- **rekenkundige operatoren** — voeren een bewerking uit, zoals optellen, aftrekken,
  vermenigvuldigen;
- **vergelijkingsoperatoren** — vergelijken variabelen met elkaar of een variabele met een
  parameter;
- **logische operatoren** — bepalen bij samengestelde voorwaarden of aan (ten minste) één
  voorwaarde moet worden voldaan (OF, disjunctie, alternatief) of aan alle (EN, conjunctie,
  cumulatief); ook kan er sprake zijn van een voorwaarde waaraan niet voldaan mag zijn (NIET,
  negatie).

**Vraag** (`H2:99`) — Hoe worden variabelen of parameters verbonden in een berekening? In welke
verhouding staan voorwaarden tot elkaar? Welke vergelijking wordt in een voorwaarde gemaakt?

**Uitdrukkingswijze** (`H2:100`) —
rekenkundig: ‘het gezamenlijke bedrag van’, ‘de som van’, ‘vermeerderd met’, ‘verminderd met’,
‘percentage van’;
vergelijking: ‘groter dan’, ‘kleiner dan’, ‘meer bedraagt dan’, ‘is gelijk aan’;
logisch: ‘en’, ‘of’, ‘niet’, ‘ten minste’.

**Uit de JAS-tabel** (rij 11) — "Formulering die duidt op een rekenkundige bewerking, een
samengestelde voorwaarde, een gelijkstelling of een vergelijking."

**Samenloop met afleidingsregel — de bron lost dit niet op.** ‘het gezamenlijke bedrag van’,
‘vermeerderd met’, ‘verminderd met’ en ‘en’ staan letterlijk in *beide* uitdrukkingswijzen
(`H2:73` en `H2:100`). Er is geen bronregel die voorrang geeft. Werkafspraak: de **afleidingsregel**
is de regel als geheel (de hele bepaling die een waarde vaststelt), de **operator** is het woord of
de woordgroep die de verbinding maakt binnen die regel. Beide markeren mag; zie
`markeren-fragmentgrenzen.md` over overlappende markeringen. Noteer je keuze in de `toelichting`.

---

## 10. Tijdsaanduiding

**Omschrijving** (`H2:107`) — Een tijdsaanduiding is een omschrijving van een tijdstip of tijdvak.
Een tijdsaanduiding is nodig om de geldigheid van een rechtsbetrekking te duiden, om een
tijdsverloop met rechtsgevolg uit te drukken of als variabele bij een specifiek rechtssubject of
rechtsobject. Ook kan een tijdsaanduiding (met name een tijdstip) een parameterwaarde zijn — een
voorbeeld is een peildatum die wordt vergeleken met een andere datum (als variabele) in een
voorwaarde.

De tijdsaanduiding is als aparte klasse opgenomen, hoewel deze ook beschouwd zou kunnen worden als
een verduidelijking van de klassen variabele of parameter. **Gelet op het belang van de
tijdsaanduiding voor het bepalen van de duur van een rechtsbetrekking of het tijdstip van een
tijdsverloop met rechtsgevolgen**, is tijdsaanduiding als aparte klasse opgenomen.

**Vraag** (`H2:108`) — Wanneer, op welk moment? Sinds wanneer of tot wanneer, vanaf welk moment of
tot welk moment?

**Uitdrukkingswijze** (`H2:109`) — Te herkennen aan een concrete datum (bijvoorbeeld 1 september
2009), of aan een omschrijving die een datum beschrijft (de eerste maandag van de maand). Tijdvakken
zijn vaak te herkennen aan woorden die een periode duiden, zoals jaar, maand, week en dag, of
specialisaties daarvan zoals kalenderjaar.

**Uit de JAS-tabel** (rij 12) — "Aanduiding van een tijdstip of tijdvak."

**Prioriteitsregel** (`H2:107`, letterlijk) — "Een formulering kan zowel tot de klasse
tijdsaanduiding als tot de klasse parameter of variabele behoren. Als dat zich voordoet, kiezen we
bij de analyse voor de meest specifieke klasse, dus de tijdsaanduiding."

---

## 11. Plaatsaanduiding

**Omschrijving** (`H2:116`) — Een plaatsaanduiding is een plaats of een gebied waar bepaalde
wetgeving betrekking op heeft. Zij bepaalt het toepassingsbereik van de regels voor
rechtssubjecten, rechtsobjecten, rechtsbetrekkingen of rechtsfeiten. **De meeste wetgeving geldt
voor heel Nederland en heeft daarom geen expliciete plaatsaanduiding.** Zodra het werkingsgebied
beperkter of ruimer moet zijn, wordt in wetgeving wel een expliciete plaatsaanduiding opgenomen.

**Vraag** (`H2:117`) — Waar (voor welk gebied of welke plaats) geldt de wettelijke regel (niet)?

**Uitdrukkingswijze** (`H2:118`) — Uitgedrukt met een algemene beschrijving van het gebied (een
lidstaat van de EU) of met de naam van een specifiek gebied (de gemeente Amsterdam, de provincie
Limburg, Nederland, Zwitserland).

**Uit de JAS-tabel** (rij 13) — "Aanduiding van een plaats of gebied."

**Prioriteitsregel** (`H2:116`, letterlijk) — "Een formulering in de wetgeving kan zowel tot de
klasse plaatsaanduiding als tot de klasse parameter of variabele behoren. Als dit zich voordoet,
kiezen we voor de meest specifieke klasse, namelijk de plaatsaanduiding."

**Let op** — markeer geen plaatsaanduiding waar er geen staat. Het landelijke bereik is impliciet
en is dus géén markering.

---

## 12. Delegatiebevoegdheid en delegatie-invulling

**Omschrijving** (`H2:125`) — Een *delegatiebevoegdheid* maakt het mogelijk of schrijft voor dat
(nadere) regels worden gesteld over een rechtsbetrekking, rechtsfeit of afleidingsregel. Met
*delegatie-invulling* duiden we de regeling of het regelingsonderdeel aan waarin de
delegatiebevoegdheid is gebruikt.

Een delegatiebevoegdheid wordt **altijd aan een specifiek rechtssubject toegekend**: de regering
(bij een amvb, vastgesteld door de Koning) of een minister (bij een ministeriële regeling). De
delegatie kan verplicht of facultatief zijn. Vaak is subdelegatie mogelijk: bepalingen in een amvb
kunnen verder worden uitgewerkt in een ministeriële regeling.

Vier dingen die de bron hier expliciet maakt en die je bij het annoteren nodig hebt:

1. **Delegaties bepalen het werkgebied.** "Het herkennen van delegatiebevoegdheden is vooral van
   belang voor het bepalen van het werkgebied van de Wetsanalyse. Als de delegatiebevoegdheid
   daadwerkelijk is gebruikt, moet de op grond daarvan vastgestelde gedelegeerde regelgeving in het
   werkgebied worden betrokken."
2. **De delegerende wet wijst nooit naar de invulling.** "De delegerende wet bevat logischerwijs
   geen concrete verwijzingen naar de delegatie-invulling. Die is immers op het moment van
   voorbereiden van die wet nog niet vastgesteld." Zoek een delegatie-invulling dus niet in de
   moederwet.
3. **wetten.nl-metadata is onvolledig.** De wetsinformatie bij een artikel "is echter niet altijd
   volledig. Afstemming met wetgevingsjuristen om het werkgebied compleet te maken is daarom van
   belang." Dat geldt ook voor de verwijzingen die de kennisgraaf uit die bron overneemt.
4. **Een delegatie-invulling is niet lexicaal te herkennen.** "In de delegatie-invulling wordt niet
   met standaard uitdrukkingswijzen gewerkt" (`H2:127`). Je vindt hem alleen via de relatie met de
   grondslag, niet via signaalwoorden.

**Vraag** (`H2:126`) — Geeft een wetsartikel de opdracht om (nadere) regels te stellen? Verwijst
een bepaling in een gedelegeerde regeling naar een artikel in de bovenliggende wet?

**Uitdrukkingswijze** (`H2:127`) — Verplichte delegatie: ‘bij (of krachtens) algemene maatregel van
bestuur / bij ministeriële regeling worden regels gesteld (…)’. Facultatieve bevoegdheid: ‘kunnen
regels worden gesteld’. Bij ‘**bij of krachtens**’ kan subdelegatie plaatsvinden.

**Uit de JAS-tabel** (rij 14 + 15) — "Bevoegdheid om in lagere regelgeving (nadere) regels te
stellen." / "Gedelegeerde regeling waarin (nadere) regels zijn gesteld."

---

## 13. Brondefinitie

**Omschrijving** (`H2:134`) — Een brondefinitie is een begripsomschrijving die expliciet is
opgenomen in de wetgeving en een eenduidige betekenis geeft aan een in de wetgeving (veel)
gebruikte term. Brondefinities staan in de regel in een of meer artikelen aan het begin van een wet
of gedelegeerde regeling. **Als in de wet een term is gedefinieerd, wordt deze definitie standaard
hergebruikt in de daarop gebaseerde gedelegeerde regelingen. De definities worden in de
gedelegeerde regeling niet opnieuw opgenomen.**

"Brondefinities moeten worden onderscheiden van de begrippen en begripsomschrijvingen die bij de
Wetsanalyse worden gemaakt voor geclassificeerde formuleringen in de wetgeving. Deze begrippen
hebben geen directe wettelijke bron, maar zijn nodig om formuleringen uniek te kunnen aanduiden."

**Vraag** (`H2:135`) — Is deze term uitdrukkelijk omschreven in de wetgeving?

**Uitdrukkingswijze** (`H2:136`) — Een artikel met brondefinities bestaat in de regel uit een
**aanhef en verschillende onderdelen**, bij voorkeur in alfabetische volgorde. Vaak staat dit
artikel aan het begin van de regeling, **maar er kunnen ook brondefinities zijn die voor een
specifiek onderdeel gelden** — een hoofdstuk, paragraaf of zelfs één artikel.

**Uit de JAS-tabel** (rij 16) — "In de wetgeving opgenomen definitie."

> *Eigen toevoeging, niet uit de bron:* de aanhef luidt in de praktijk vaak "In deze wet wordt
> verstaan onder…". `H2-JAS.md` noemt die formulering niet; gebruik hem als herkenningshulp, niet
> als bronformulering.

**Twee valkuilen**

- Annoteer je een amvb of ministeriële regeling, dan staan de definities daar **niet**: zoek ze in
  de moederwet.
- Een brondefinitie is een markering van tekst die in de wet staat. Een omschrijving die jij zelf
  formuleert om een markering te benoemen, is géén brondefinitie — die hoort bij activiteit 3 en
  valt buiten de huidige scope.
