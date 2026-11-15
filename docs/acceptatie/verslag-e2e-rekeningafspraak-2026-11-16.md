# Verslag: end-to-end wetsanalyse Rekeningafspraken, 16 nov 2026

Soort: *verslag van een acceptatietest, verandert niet achteraf* · Scenario: [wetsanalyse-e2e.md](wetsanalyse-e2e.md) ·
Briefing: [briefing-team.md](briefing-team.md)

Het team bestond uit de agent-jurist en de agent-gegevensspecialist. Ze voerden een wetsanalyse uit op acceptatie, met
Lex zoals het op 15 nov 2026 werd uitgerold: de centrale agent met subagents, en geen supervisor meer. Ze gebruikten
alleen de methode wetsanalyse (JAS), niet het JRM. Dit verslag vat hun rapporten samen. Het hoofdstuk over het
denkproces heeft de coördinator zelf geschreven.

Het dossier, het logboek en de ruwe uitvoer staan lokaal in `docs/acceptatie/lokaal/rekeningafspraak-2026-11-16/`
(gitignored). Het dossier noemt interne teams en systemen; die staan hier niet.

## In het kort

- **Gedaan:**
  - stap 1, het werkgebied;
  - stap 2, de bronselectie, voor één van de vijf deelvragen;
  - stap 3, de annotatie van 12 bepalingen onder die deelvraag;
  - stap 4, vier begrippen volgens NL-SBB, waarvan twee geaccordeerd;
  - stap 5, het beoordelen, als steekproef van 24 en 14 elementen;
  - stap 6, het valideren aan de drie praktijkvoorbeelden;
  - twee vrije vragen die de subagents moesten inzetten.
- **Lex-verbruik:** 1.246.770 tokens. Het plafond was 2,0M.
- **Het grootste probleem is de vorm van de antwoorden, niet het budget.** Vier keer liep een agent vast op zijn
  eigen contextruimte; er waren drie juristen nodig. De oorzaak is dat de api voor één besluit of één bepaling
  tienduizenden tokens teruggeeft (B-1).
- **De annotaties zijn op de beoordeelde elementen goed.**
  - Van de 24 beoordeelde elementen waren er 22 juist, 1 is aangepast en 1 is zelf gemarkeerd.
  - Elk citaat stond letterlijk op zijn anker, getoetst tegen de officiële XML.
  - Het ontbrekende zit in twee klassen: Rechtsfeit, bij een naamwoord als 'uitbetaling', en Voorwaarde, bij een
    beperkende bijzin.
- **Het zoeken naar bronnen mist de kern** (B-2). De bepalingen die de deelvraag beantwoorden, Iw 7a, Awir 25 en
  Awb 4:89, vond Lex niet zelf. Hij vond wel de regeling die ernaar verwijst. Voor het eerste praktijkvoorbeeld
  ontbrak de bepaling die de uitkomst geeft (Uitv.reg. Awir art. 6), hoewel die binnen het zoekbereik lag.
- **De subagents werken**, maar de centrale agent vult hun rapport aan met eigen duiding die niet in de bron staat. Hij
  mag zelf niet nalezen (B-3).
- **Het denkproces** is bij de vaste routes kort en klopt meestal. Bij de subagents ontbreken resultaatregels, en de
  annotatieregel noemt het artikel niet (hoofdstuk *Het denkproces*).
- **'Werk het begrip volledig uit' werkt een begrip niet volledig uit** (B-6). Dat merkte ook de gebruiker op.

## Opzet en beperkingen

- **Account:** palmw01, rol beheerder, gedeeld met de gebruiker. Daardoor zijn de rechten van een analist niet
  getoetst, en staat al het verbruik op dit account.
- **Vooraf opgeschoond, na akkoord van de gebruiker:**
  - ongeveer 480 test- en meetgesprekken zijn verwijderd;
  - werkgebieden, annotaties en begrippen bleven staan.
  - Er zijn twee manieren nodig, omdat de bulkroute alleen gesprekken buiten een werkgebied wist (zie O-1).
- **Niet uitgevoerd:**
  - De vergelijking van bron en graaf, en de logs (stap 8). `graaf_lezen` en `logs_zoek` waren in deze sessie niet
    geconfigureerd. De graaftoegang staat nu machine-lokaal ingesteld en werkt na een herstart van de MCP. Het
    wachtwoord voor Grafana zet de gebruiker. De trace- en run-id's staan in het logboek, zodat het achteraf kan.
  - De weergave in de browser.
- **Werkgebied:** `0cde2261-f5f6-431d-aed2-f1e9cdf89ead` (*acc-test-rekeningafspraak-2026-11-16*). Het blijft staan als
  bewijs.

## Verloop per stap

**1. Werkgebied.**
- De velden uit het dossier zijn letterlijk overgenomen: aanleiding, context, doel, analysevraag en drie
  praktijkvoorbeelden.
- Lex stelde zeven deelvragen voor. Drie daarvan overlapten, en het aanwijzen van de rekening, het einde van een
  afspraak en de rangorde ontbraken. De jurist maakte er vijf van:
  - DV1 rekening en bevrijdende betaling;
  - DV2 betaling aan een derde;
  - DV3 beslag, onvatbaarheid en verrekening;
  - DV4 begin en einde;
  - DV5 rangorde.
- De gegevensspecialist beoordeelde ze op gegevens vóór de bronselectie begon. Dat staat in het logboek.
- Het samenstellen kostte bijna geen tokens: de meeste kaartjes vragen geen model.

**2. Bronselectie.**
- Alleen DV1 is afgewerkt.
- Lex vond Uitv.reg. Iw 1990 art. 40ca lid 1. De jurist noemde zelf Iw 1990 art. 7a, Awb art. 4:89 en Awir art. 25,
  en nam ze op.
- Bewust niet gekozen:
  - 40ca lid 3;
  - Leidraad 7a.1 tot en met 7a.3: beleid, bedoeld voor de validatie;
  - Leidraad 79.5, die bij DV3 hoort;
  - de Awir-artikelen over voorschotten.
- DV2 tot en met DV5 zijn niet gedaan. De besluitroute kostte per keer ongeveer 15k tokens context (B-1).

**3. Annoteren.**
- Lex noemde 12 bepalingen uit 4 bronnen, en de jurist bevestigde met 12. De annotatie liep in één run zonder fouten,
  run `5bb3e548a2e847aaa8ca6befcd9c4b2c`.
- Ze kostte ongeveer 133k tokens, ongeveer 9.300 per bepaling, en leverde 140 voorstellen op.
- Een artikel in de selectie telt mee met al zijn leden. Daardoor werden ook leden geannoteerd waar het de jurist niet
  om ging. Dat is zo ontworpen, maar het kost geld; zie V-4.

**4. Begrippen.**
- Lex stelde 14 groepen voor, deterministisch en zonder modeltokens. De gegevensspecialist maakte er vier begrippen van:

  | begrip | stand | definitie |
  |---|---|---|
  | belastingschuldige | geaccordeerd | brondefinitie Iw 1990 art. 2 lid 1 onder k |
  | bankrekening | geaccordeerd | eigen analysedefinitie op Awb 4:89 lid 1; 'op naam van' staat in de toelichting |
  | derde | concept, juridisch akkoord | eigen definitie; de toelichting met de kanttekeningen van de jurist volgt nog |
  | belanghebbende | concept, juridisch akkoord | brondefinitie Awb art. 1:2 lid 1 |

- De relatie tussen belastingschuldige en belanghebbende is als *verwant* vastgelegd.
- De NL-SBB-conformiteit: alle vier conform. De Turtle-export is goed opgebouwd.

**5. Beslissen.** Zie *JAS-conformiteit*.

**6. Valideren.** Zie *Praktijkvoorbeelden*.

**7. Beoordelen.** Zie *Bevindingen*.

## JAS-conformiteit van de annotaties

Op verzoek van de gebruiker beoordeelde de jurist elk element tegen de skill `wetsanalyse`:
- de klasse en de herkenningsvraag;
- de fragmentgrenzen;
- of het citaat letterlijk op het anker staat, getoetst met `bron_lezen`;
- wat er ontbreekt.

De gegevensspecialist deed los daarvan een steekproef in de klassen die gegevens dragen.

**De jurist, 24 elementen**, de dragers van de begrippen in Iw 7a lid 1 en 2, Awir 25 lid 1 en 2, en 40ca lid 1
onder d:

| klasse | goed | aangepast | afgewezen | zelf gemarkeerd |
|---|---|---|---|---|
| Rechtssubject | 15 | – | – | – |
| Rechtsobject | 5 | 1 → Rechtsfeit | – | – |
| Rechtsbetrekking | 1 | – | – | – |
| Operator | 1 | – | – | – |
| Voorwaarde | – | – | – | 1 |
| **totaal** | **22** | **1** | **0** | **1** |

- `7250d8b52bd0`, 'uitbetaling', is aangepast van Rechtsobject naar Rechtsfeit. Het is de handeling betalen, met een
  rechtsgevolg (Awb 4:89 lid 3). De keten bood Rechtsfeit niet eens als keuze aan.
- Zelf gemarkeerd: de Voorwaarde 'die op naam staat van de belastingschuldige' (Iw 7a lid 1). De keten bood die
  spanoptie aan, maar markeerde haar niet.
- Elk citaat staat letterlijk op zijn anker, getoetst tegen de officiële XML van Iw 7a en 2, Awir 25 en Awb 4:89.
- Waarschijnlijk gemist, nog niet geverifieerd:
  - een Rechtsbetrekking in Iw 7a lid 1, tweede zin;
  - een Delegatiebevoegdheid in Iw 7a lid 4 en in Awir 25 lid 3;
  - een Voorwaarde 'op naam van de belanghebbende' in Awir 25 lid 1.

**De gegevensspecialist, 14 elementen** in de klassen die gegevens dragen: 12 juist. De twee afwijkingen zijn
'uitbetaling', dezelfde als hierboven, en 'zorg', waarvan het fragment te fijn is.

**Wat niet is beoordeeld:**
- ongeveer 50 open elementen in de lagen die wel geopend zijn;
- de lagen Iw 7a lid 3 en 4, Awb 4:89 lid 1 tot en met 4, en Awir 25 lid 3;
- 40ca lid 1 onder a tot en met c;
- de relaties tussen markeringen. Het denkproces meldt dat de keten er 22 voorstelde; de jurist heeft er geen gezien.
  Of ze in de weergave staan, is een open punt.

De reden is dat er geen lichte lijst van elementen per bepaling bestaat. De weergave van alleen Iw 7a lid 1 is 105k
tekens, en `annotatie_lezen` kost ongeveer 6k tokens per element (B-1).

**Oordeel:** wat beoordeeld is, is conform het JAS. De zwakke plekken zijn systematisch, niet toevallig:
- een naamwoord dat een handeling uitdrukt (Rechtsfeit) wordt een Rechtsobject;
- een beperkende bijzin wordt geen Voorwaarde.

Allebei horen ze in de detectoren, met een test en een annotatiemeting (ADR-001), en niet in een prompt.

## Praktijkvoorbeelden (stap 6)

De conclusies rusten op de feitenvalidatie van de specialist en het juridische oordeel van de jurist. De specialist kon
ze niet meer samen bevestigen, omdat zijn context op was.

| voorbeeld | volgt het uit de bronnen? | gat |
|---|---|---|
| **PV1** Kinderopvangtoeslag rechtstreeks naar de kinderopvang, met toestemming van de ouder | Nee, niet uit DV1. De grondslag is Uitv.reg. Awir art. 6 lid 1 onder a, letterlijk getoetst. De voorwaarde is een convenant met Dienst Toeslagen, niet de toestemming van de ouder. | De regeling viel binnen het zoekbereik, maar is niet geselecteerd. 'Toestemming' is beleid of de inhoud van het convenant, geen rechtsfeit uit de wet. |
| **PV2** Beslag door het CJIB op de zorgtoeslag | Nee, niet uit DV1. De route is Zvw art. 18f lid 6: uitbetaling aan het CAK, in afwijking van Awir 25 lid 1, letterlijk getoetst. Het CJIB int namens het CAK. Daarnaast Uitv.reg. Awir art. 6 lid 1 onder c en Awir 45. | De Zvw valt buiten het zoekbereik en DV3 is niet geannoteerd. Het dossier noemt de rechtsfiguur (beslag) mogelijk onjuist. |
| **PV3** Bewindvoerder bij schuldsanering, betaling naar een derdenrekening | Deels. Voor inkomstenbelasting geldt 40ca lid 1 onder a en b. Voor toeslagen geldt Uitv.reg. Awir art. 6 lid 2 onder e (de WSNP-bewindvoerder). | Inkomstenbelasting en toeslagen verschillen: 40ca noemt de WSNP-bewindvoerder niet. De beschermingsbewindvoerder staat in geen van beide regelingen. Beide punten zijn open. |

- Bij alle drie hebben **DV4** (werking in de tijd) en **DV5** (rangorde) geen bron. De rangorde is
  uitvoeringsbeleid; dat is een benoemd gat.
- **Gegevens:** per persoon is er hoogstens één bestemde rekening, gedeeld door de inkomstenbelasting en de toeslagen
  (Iw 7a lid 1). 'Belastingschuldige' (Iw) en 'belanghebbende' (Awir) zijn dezelfde persoon.
- Een gegevensmodel was er niet, dus de koppeling aan een model is een lijst van aannames met vragen. Die staat in het
  logboek bij stap 6.

## Centrale agent en subagents

Tot en met stap 5 gebruikte Lex geen enkele subagent. Alles liep via vaste routes:
- het werkgebied samenstellen;
- de bronselectie;
- de annotatieketen;
- de begrippen-agent.

Dat is zo ontworpen. De jurist stelde daarom twee vrije vragen, in gesprek `b91353cd72364f39`.

**V1: de wetsgeschiedenis van Iw 7a lid 4.**
- Run `5b0a07b25a6a4b4fb461485087d48d9a`, delegatie `5556253023bb4706`, profiel `wetsgeschiedenis_lezen`, deelgesprek
  `7b6290347b674f95`. Hij startte zonder bevestiging en stelde geen vraag naar boven. Kosten: ongeveer 299k tokens.
- **Het rapport van de subagent** is eerlijk:
  - de memorie van toelichting bij het Belastingplan 2015 gaat alleen over het schrappen van de omzetbelasting;
  - het lid zelf wordt niet toegelicht;
  - het dossier waarmee de bepaling oorspronkelijk werd ingevoerd, is niet gevonden.
  - Maar er hangt een passage aan over art. 43a, die er niets mee te maken heeft (alinea 559, door de code
    gekozen).
- **De centrale agent voegde eraan toe** dat lid 4 "de regel [is] dat betaling aan een aangewezen derde bevrijdend
  werkt". Dat staat niet in het rapport en niet in de wet: lid 4 is een delegatiebepaling.
  - De controle meldde acht onbevestigde duidingen, en er volgde een correctieronde. Toch bleef de zin staan.
  - Nalezen kon de centrale agent zelf niet: `get_lid` en `get_kamerstuk` werden geweigerd met de code `na_subagent`.

**V2: rechtspraak over betaling op een rekening van een derde** (Awir 25 en Awb 4:89).
- Er kwam eerst een plankaart met een bevestiging. Na de bevestiging volgde delegatie `a7d9818a28c743a5` met
  2× `rechtspraak_lezen`, in de deelgesprekken `38f012efc7274959` en `e7342227b96c4564`. Kosten: ongeveer 791k
  tokens.
- De subagents vonden juist de uitspraken die de drie praktijkvoorbeelden verklaren. Het citaat van Zvw 18f lid 6
  klopt letterlijk.
- **De centrale agent week op drie plekken af van de rapporten:**
  - de passage uit ECLI:NL:RVS:2019:3536 r.o. 5.3, die er voor PV1 toe doet, verving hij door r.o. 5.6, over het
    overgangsrecht;
  - bij ECLI:NL:CRVB:2021:669 noemt hij een "bewindvoerder", terwijl het om een kredietbank ging;
  - hij schrijft "CAK of CJIB", terwijl de wet "CAK" zegt.
- De plankaart noemde een stopgrens van ongeveer 2,39M tokens. Dat ligt boven het plafond van deze test, maar is wel
  expliciet gemaakt.

**Oordeel:**
- De subagent kiest per vraag het juiste profiel.
- De rapporten benoemen zelf wat niet gelezen is.
- De plankaart met bevestiging en budget werkt.
- Een vraag naar boven kwam in geen van beide gevallen. Dat klopt hier: geen kind liep vast op een keuze.
- **Het zwakke punt is de samenvatting door de centrale agent** (B-3). Zie ook *Centrale agent na A6*, punt 2 en 8, in
  `docs/PLAN.md`.

## Het denkproces

Op verzoek van de gebruiker is het veld `denk` van elk assistentbericht beoordeeld:
- 49 berichten, in zes gesprekken: de jurist, de specialist, het gesprek over de subagents en drie deelgesprekken;
- uitgelezen met `GET /api/gesprekken/<id>`.

De vragen waren: is de volgorde logisch, is het inhoudelijk correct, en sluit het aan bij wat Lex daarna deed en
antwoordde?

**Wat goed gaat:**
- Bij de vaste routes is het denkproces kort en feitelijk: een regel per kaart.
- Bij de annotatie staat per bepaling de hele keten met aantallen en duur: bron → taalanalyse → detectie → besluit
  → classificatie → review → resultaat → relaties → klaar. De aantallen kloppen met het antwoord, bijvoorbeeld "46
  voorgesteld" tegenover "46 JAS-elementen".
- De regel "Klaar · n bronnen" klopt in alle vijf beurten van de centrale agent en de subagents met het aantal bronnen
  op het bericht: 5, 10, 10, 18 en 5.
- De controleregel klopt met de grounding. In het deelgesprek over de wetsgeschiedenis staan "3 vermeldingen niet
  teruggevonden" en 3 keer `onbevestigd`.
- Een verkeerd BWB-id wordt eerlijk gemeld: "Rechtspraak · niet gezocht: het id kwam niet uit het gesprek" (bericht
  6787).

**Afwijkingen:**

| # | zwaarte | gesprek · bericht | regel | wat er mis is |
|---|---|---|---|---|
| D-1 | middel | `cd5be0db64c74de3` · 6761–6772 (12×) | "Lex · annoteert de aangewezen bepaling (art. )" | Het artikel ontbreekt tussen de haakjes. De volgende regel ("Bron · art. 7a lid 1") draagt het wel, maar noemt de regeling niet. |
| D-2 | middel | `7b6290347b674f95` · 6784 | "zoekt in Kamerstuk kst-34002-3 …; zoekt in Kamerstuk kst-34002-G …" en de ronden erna | Resultaatregels ontbreken bij gebeurde stappen. Ronde 4: alleen kst-34002-3 heeft een resultaat; dat G niets opleverde, staat er niet. Ronde 5 (3: 6 alinea's, G: 4) en ronde 7 (8: 2, 12: 0) hebben geen enkele resultaatregel. |
| D-3 | middel | `e7342227b96c4564` · 6791; `38f012efc7274959` · 6792 | "leest uitspraak …" ×5, gevolgd door 3 resultaatregels | Ook hier ontbreken resultaatregels: van de 22 leesacties in 6791 hebben er 17 een regel, in 6792 ontbreekt er 1. Wie meeleest, kan niet zien welke uitspraken gelezen zijn. |
| D-4 | middel | `e7342227b96c4564` · 6791 | elke regel "… deels gelezen, er is meer dan dit" tegenover het rapport "las ze volledig door" | Het rapport spreekt het denkproces tegen. Het denkproces heeft gelijk; het rapport claimt meer dan er gebeurd is. |
| D-5 | hoog | `b91353cd72364f39` · 6785 | "Ik heb het rapport van de subagent. Laat me eerst de tekst van artikel 7a lid 4 ophalen …" | De aangekondigde stap staat er niet, en ook niet dat hij geweigerd werd (`na_subagent`). Daarna volgen "Correctie · antwoord bijstellen" en "8 vermeldingen niet teruggevonden", maar het antwoord houdt de ongedekte bewering (B-3). Het denkproces laat zien dat er gecontroleerd is, maar niet dat de controle niets hielp. |
| D-6 | laag | `b91353cd72364f39` · 6785 | "Lex · geeft het lezen van de reeks aan een subagent" | Dit is een wetsgeschiedenis-vraag, geen reeks. Het profiel was `wetsgeschiedenis_lezen`, niet `bepalingen_duiden`. |
| D-7 | laag | `b91353cd72364f39` · 6793 | "verwerkt je antwoord voor de subagent" · "geeft je antwoord aan de subagent" | Dit was een bevestiging van het plan, geen antwoord op een vraag naar boven. De regel suggereert een vraag die er niet was. |
| D-8 | laag | `7b6290347b674f95` · 6784 | "zoekt de Kamerstukken van dossier 34002; zoekt …; zoekt …" | Drie zoekacties met een verschillende soort stuk (memorie van toelichting, nota naar aanleiding van het verslag, nota van wijziging) krijgen hetzelfde label. Ze lijken dubbel. |
| D-9 | laag | `60738491afee45bc` · 6777, 6779, 6783 | "Brondefinitie zoeken voor “X” (werkgebied …)" en daarna "Brondefinitie zoeken voor “X”" | Elke stap staat twee keer, met en zonder werkgebied. Hetzelfde geldt voor *Scherpere definitie*, *Uitleg in B1* en *Voorbeelden*. |
| D-10 | laag | `60738491afee45bc` · 6777 | einde: "Klaar · gedaan" | Waarom de uitleg en de voorbeelden zijn overgeslagen (er is geen overgenomen definitie), staat alleen in de tekst, niet in het denkproces. "Klaar · gedaan" noemt geen bron, hoewel de graaf is bevraagd. |
| D-11 | laag | `cd5be0db64c74de3` · 6703 | "stelt met je een werkgebied samen" · "begint met het samenstellen van een werkgebied" | Twee regels zeggen hetzelfde. |
| D-12 | laag | `cd5be0db64c74de3` · 6745 | "pakt de bronselectie op waar die was" | Er was nog niets: het was de eerste keer. |
| D-13 | laag | `cd5be0db64c74de3` · 6759, 6773 | (leeg) | Het aanbod om te annoteren en de slotsamenvatting hebben geen denkproces. Het aanbod noemt wel aantal en budget in de tekst. |
| D-14 | laag | `cd5be0db64c74de3` · 6753, 6755 | tekst "(geen antwoord)" | Een bericht met een kaart heeft als tekst letterlijk "(geen antwoord)". |
| D-15 | info | `b91353cd72364f39` · 6785, 6787, 6793 | "zoekt voor deze vraag in de wetgeving en …; … zijn niet nodig" | Er staat een bronnenregel in. Bij V2 komt die na "Lex · bekijkt de vraag", bij V1 is er geen regel "bekijkt de vraag". Bij een hervatte beurt (6793) wordt hij herhaald. De vaste routes beginnen niet met "bekijkt de vraag"; dat is zo ontworpen. |

**Oordeel:**
- **De volgorde** klopt overal.
- **Inhoudelijk** is het denkproces correct bij de vaste routes. Bij de subagents is het onvolledig: resultaten van
  gebeurde stappen ontbreken (D-2, D-3), waardoor wie meeleest niet kan zien wat er gelezen is.
- **De aansluiting** schiet tekort op twee plekken: een rapport dat meer claimt dan het denkproces laat zien (D-4),
  en een correctie die het antwoord niet zichtbaar herstelde (D-5).

## Bevindingen

**Fouten in Lex of de werkplek (eigen PR met een test):**

| # | zwaarte | bevinding | bewijs | voorstel |
|---|---|---|---|---|
| B-1 | hoog | De antwoorden zijn te groot voor een agent of een MCP-client. Elk besluit in de bronselectie geeft de hele selectie van alle deelvragen terug, ongeveer 15k tokens. Verder zijn te groot: `GET …/kandidaten` 57 kB (het filter op deelvraag filtert niet), `werkgebied_lezen` na één annotatie 184k tekens, de weergave van één lid 105k, de groepen 108k, en elke wijziging aan een begrip ongeveer 10k (met de koppelingen dubbel). Vier agents stopten hierdoor voor ze klaar waren. | traces `c7d42972922cb00f57ac2acc977898cc`, `0d4ea6a2662e1e8caf03735db6831d0c`, `aa8e9359…`, `3acde2a8…` | Laat een besluit alleen de geraakte deelvraag teruggeven. Laat het filter `?deelvraag_id=` echt filteren. Maak een compacte weergave (`?compact=1`: id, klasse, tekst, lifecycle per element), en een wijziging aan een begrip die alleen de stand teruggeeft, zoals `koppelstand`. |
| B-2 | hoog | Het zoeken naar bronnen mist de kern. Iw 7a lid 1, Awir 25 en Awb 4:89 vond Lex niet bij DV1, terwijl 40ca lid 1 wel gevonden werd en zelf naar 7a verwijst. De kandidaten per deelvraag verschillen nauwelijks: dezelfde bepalingen staan bij 4 of 5 deelvragen, met ruis uit de Leidraad. Uitv.reg. Awir art. 6, die PV1 beslist, ontbrak terwijl hij binnen het zoekbereik viel. | trace `7f4f2ecf58ad02a5add1de2bdd9d492a`; logboek stap 2 | Laat een verwezen artikel als kern meekomen. Zoek bij de gebeurtenis 'uitbetaling' ook de Awb-afdeling over betaling. Rangschik per deelvraag op de termen die alleen bij die deelvraag horen. Dit vraagt een meting (spoor zoekvragen). |
| B-3 | hoog | De centrale agent vult het rapport van een subagent aan met eigen duiding die niet in de bron staat, en kan niet nalezen (`na_subagent`). De correctieronde liet die duiding staan. | V1 run `5b0a07b25a6a4b4fb461485087d48d9a`; V2 run `0f23a525…` | Laat het nalezen na een subagent toe, of laat de centrale agent alleen weergeven wat in het rapport staat. Laat de correctie een onbevestigde duiding schrappen in plaats van herformuleren. |
| B-4 | middel | De annotatieketen biedt geen Rechtsfeit aan voor een naamwoord dat een handeling uitdrukt ('uitbetaling'). Een beperkende bijzin ('die op naam staat van …') wordt geen Voorwaarde, ook als de spanoptie er is. | element `7250d8b52bd0`; Voorwaarde `5eb76921…` | Een regel in de detectoren met een test, en een annotatiemeting (ADR-001, open keuze 11 in PLAN). |
| B-5 | middel | Een bulkbesluit 'edit' met `klasse` op het hoogste niveau geeft 200 en de stand `edited`, terwijl de klasse niet verandert. Pas met `wijziging` werkt het. | trace `219053b3…` tegenover `b3339936…` | Geef 422 bij een edit zonder wijziging. |
| B-6 | middel | *Werk het begrip volledig uit* maakt de uitleg in B1 en de voorbeelden alleen als er al een overgenomen definitie is, en nooit een toelichting of relaties (`agents/begrippen.py`, `uitwerken`). Een begrip zonder definitie blijft na één klik dus half leeg. Een tweede keer gaf 5 voorbeelden, waarvan 2 fout ('echtgenoot = wel'). | run `44a25a87…` (bankrekening), run `4f179325…` (derde) | Kies tussen twee manieren: alles in één beurt als voorstel, waarbij de uitleg op de voorgestelde definitie rust en vervalt als je die niet overneemt; of na het overnemen van de definitie vanzelf verder, met de toelichting erbij. Beide vragen een meting. |
| B-7 | middel | 'Een derde' wordt tot 'drie' teruggebracht, de woordvorm van het getal. 'Belanghebbende' wordt 'belanghebbend' en valt in twee groepen. Het synoniem belastingschuldige/belanghebbende krijgt geen signaal en geen voorstel voor een relatie. | logboek stap 4 | Uitzonderingen in de normalisatie van termen, met een test. Laat de begrippenketen synoniemen signaleren over regelingen heen. |
| B-8 | middel | Bij het afronden koos de jurist "Als beoordeeld vastleggen". Lex meldde "voorlopig afgerond", zonder reden. | run `48f966b3ff8a4b0793eda71bd501f83f` | Noem de reden van de poort op het kaartje. |
| B-9 | middel | De kaart met regelingen meldt dat ze delen weglaat die buiten het werkgebied vallen, en noemt daarbij juist de kern (Awir §3 Uitbetaling, Uitv.reg. Iw hoofdstuk IVA). | runs `db78cbed…`, `e3962090…` | Toon de reden uit de code, of herzie het filter. |
| B-10 | middel | De meting-events tonen 0 tokens terwijl het model werkte, bij de begrippen. | logboek stap 4 | Neem het verbruik van de stap op in het meting-event. |
| B-11 | middel | De subagent voor wetsgeschiedenis vindt het dossier waarmee de bepaling werd ingevoerd niet. Een passage die er niets mee te maken heeft (art. 43a) gaat als citaat mee. | deelgesprek `7b6290347b674f95` | De keuze "de code koos er alinea … bij" alleen binnen de kop van het gevraagde artikel. |
| B-12 | laag | Een zelf genoemde bepaling komt op artikelniveau binnen, terwijl Lex dezelfde op lidniveau voorstelt: ze staat dubbel in de lijst. *Wijzig deelvragen* draait een modelronde waarvan de voorstellen niet getoond worden. Het doel krijgt een slotpunt dat niet in het dossier staat. De drie praktijkvoorbeelden komen in één tekstvak. `lex_start` met een ongeldige actie (422) bewaart de vraag toch. De poort accordeert zonder uitleg en voorbeelden. De conformiteit ziet `wa:verwantMet` niet als relatie. De kadertekst zegt "geen wettelijke definities" terwijl er letterlijke brondefinities in staan. | logboek stap 1–5 | Per punt klein. |
| B-13 | laag | Het denkproces: D-1 tot en met D-15 hierboven. D-5 is hoog en hoort bij B-3. | zie de tabel | D-1, D-2 en D-3 eerst: die maken het denkproces onvolledig. |

**Opschonen van acceptatie:**
- **O-1, laag.** De bulkroute `DELETE /api/gesprekken/groep/recent` raakt geen gesprekken in een werkgebied. Een ouder
  wissen maakt de deelgesprekken los in plaats van ze mee te nemen, en de telling toont alleen *recent*. Opruimen na
  een meting met meetwerkgebieden kostte daardoor 84 losse verwijderingen. Dat is zo ontworpen ("een gesprek is een
  verslag"), maar opruimen in bulk per werkgebied of per ouder ontbreekt.

**De opzet van de test:**
- **V-1.** Een agent kan de stappen 2 tot en met 5 niet in één context afmaken (B-1). Totdat B-1 is opgelost, krijgt
  de briefing een kopje *Zuinig met context*: één bepaling tegelijk, geen `werkgebied_lezen`, beslissen via de kaart.
  De regels staan nu in [briefing-team.md](briefing-team.md).
- **V-2.** Bij een wachtbeurt dwingt de omgeving een "eindrapport" af. De gegevensspecialist leverde daardoor vijf
  tussenrapporten. Dat is ruis in de coördinatie, geen fout in Lex.
- **V-3.** De specialist gaf zijn akkoord op DV1 pas nadat de jurist de deelvraag had afgerond, terwijl de werkwijze
  dat akkoord vooraf vraagt. Dat is een kleine procesfout.
- **V-4.** Een artikel in de selectie annoteert al zijn leden. Wie alleen lid 1 en 4 nodig heeft, moet de leden
  selecteren. Zet dat in de briefing, of maak het zichtbaar op het aanbod om te annoteren.

**Vragen aan de gebruiker:**
- Hoort de Zvw (art. 18f) bij het zoekbereik van dit werkgebied? Zonder die wet heeft PV2 geen grondslag.
- Klopt PV2 zoals het in het dossier staat? Het noemt beslag door het CJIB, maar de wet regelt een uitbetaling aan het
  CAK.
- B-6: kies voor *Werk het begrip volledig uit* in één beurt, of voor vanzelf verder na het overnemen.

## Wat Lex goed deed

- Het werkgebied samenstellen, de bronselectiekaarten, de begrippenvoorstellen en de brondefinities gingen zonder
  model en kosten dus niets. De annotatie van 12 bepalingen liep in één run zonder fouten.
- De ankers zijn exact en door de api gevalideerd. De klassen van de dragers kloppen. Elk citaat is letterlijk.
- Zelf genoemde bepalingen vindt Lex meteen in de graaf. Het aanbod om te annoteren noemt het aantal per bron en het
  budget.
- Lex zegt eerlijk "geen voorstel" bij 'bankrekening'. De brondefinitie Awb 1:2 vond hij zelf. De poort houdt
  accorderen tegen tot de dragende passages beoordeeld zijn.
- De subagents kiezen het juiste profiel en benoemen wat niet gelezen is. De plankaart vraagt een bevestiging en noemt
  een budget. De rechtspraak-subagent vond de uitspraken die de praktijkvoorbeelden verklaren.

## Verbruik

| moment | Lex-tokens (account) |
|---|---|
| start (na reset) | 0 |
| na stap 1 en het begin van stap 2 | 20.809 |
| na de annotatie van 12 bepalingen | 153.592 |
| na de begrippen | 582.611 |
| eind (na V1 en V2) | 1.246.770 |

Grofweg ging het verbruik zo:
- het werkgebied en de bronselectie ongeveer 21k;
- de annotatie ongeveer 133k;
- de begrippen ongeveer 430k (verdiepen, uitwerken, meedenken);
- V1 ongeveer 299k;
- V2 ongeveer 791k.

Wat de twee subagent-vragen kostten, is ruw. Hun som valt hoger uit dan de laatste stap, omdat de begrippenstap en V1
overlapten. Het eigen verbruik van de Claude-agents staat hier los van.

## Niet getest

- De weergave in de browser.
- Analist-rechten: het account was een gedeeld beheerdersaccount.
- De logs (stap 8) en de vergelijking van bron en graaf.
- DV2 tot en met DV5 in de bronselectie.
- Ongeveer 50 open elementen.
- De relaties tussen markeringen.
- De werkplek-commando's in de UI: de agents werken via de MCP met dezelfde `actie`.
- Instellingen › Aanpassingen.
