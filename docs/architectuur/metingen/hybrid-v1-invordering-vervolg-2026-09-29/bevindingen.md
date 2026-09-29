# Wat de vergelijking wel en niet aantoont

De verbeterde keten maakt gemiste datum- en berekeningsfuncties bereikbaar en voorkomt in
deze proef klassekeuzes buiten de toegestane verzameling. De aantallen op zichzelf bewijzen
geen juridische kwaliteitswinst. De volledige [modelvergelijking](model-vergelijking.md) en
het [beoordelingsdossier](model-dossier.md) bewaren ook verdwenen en anders geklasseerde
voorstellen. Hieronder staan de bevindingen uit de drie herhalingen van de hoofdgevallen.

## Het voorbeeld met twee annotaties

Bij IW 9 lid 1 geeft A achtereenvolgens **3, 3 en 2** voorstellen. De centrale
invorderbaarheidsuitspraak wordt alleen in de tweede baseline-run opgenomen. De eerdere
export met twee voorstellen is dus als uitkomst opnieuw gereproduceerd; een vast aantal
van twee volgt niet uit de bron of uit een vaste selectie van de keten.

B en C geven ieder in alle drie runs dezelfde **drie** voorstellen:

| Bronoffset | Fragment | Modelklasse |
|---|---|---|
| [0,87) | Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet. | Rechtsfeit |
| [0,20) | Een belastingaanslag | Rechtsobject |
| [37,86) | zes weken na de dagtekening van het aanslagbiljet | Tijdsaanduiding |

Dit is een concreet verschil in inhoud en herhaalbaarheid. Het blijft te beoordelen of de
centrale uitspraak hier als Rechtsfeit of Rechtsbetrekking moet worden geduid, en welke
zelfstandige functie het aanslagbiljet heeft. Dat laatste objectfragment verschijnt in de
eerste baseline-run en verdwijnt in B/C. De kortere duurkern krijgt nu T als toegestane
hypothese en wordt niet naast dezelfde langere T-functie uitgevoerd.

In deze zes verbeterde runs accepteert de classifier de centrale uitspraak direct. De
nieuwe gerichte herbeoordeling van een afwijzing wordt daardoor hier niet live aangesproken.
KEEP, CHANGE, HUMAN_REVIEW, ontbrekende context en technische fouten zijn met nepmodellen
en de historische afwijzingskeuze getest. Uit deze live proef kan geen frequentie of
meerwaarde van die specifieke reviewroute worden geschat.

## De andere hoofdgevallen

| Casus | A: voorstellen per run | B: voorstellen per run | C: voorstellen per run | Terugkerend verschil |
|---|---|---|---|---|
| IW 9 lid 5 | 27 / 27 / 32 | 28 / 28 / 28 | 26 / 28 / 28 | B/C kiezen de eerste volzin als Afleidingsregel; A kiest Rechtsbetrekking. De te brede nominalisatie stopt nu vóór de volgende termijnregel. |
| Leidraad §9.1 | 9 / 10 / 10 | 15 / 13 / 15 | 15 / 15 / 16 | Beide datumtoewijzingen worden in alle B/C-runs als Afleidingsregel voorgesteld. Beide vermeldingen van 31 december en de maandultimo zijn bereikbaar als T. |
| Leidraad §9.5 | 41 / 41 / 40 | 56 / 55 / 56 | 48 / 48 / 49 | Twaalf kalenderdatums zonder jaartal, volledige datumomschrijvingen en de kalenderberekening worden bereikbaar. B heeft 55 vaste voorstellen op 56 verschillende; C 41 op 56; A 25 op 58. |

Bij lid 5 wordt de afzonderlijke terugval naar lid 1 als AR-kandidaat aangeboden. Het model
accepteert deze in één C-run, en wijst haar in alle B-runs af. Kandidaatdekking is hier dus
nog geen volledige inhoudelijke uitvoer. In C ronde 2 en 3 ontbreken bruikbare reacties
voor vier nominalisatiekandidaten, ook na de review. Hun acht gele voorstellen zijn
menselijke beoordelingsgevallen, geen door het model gekozen rechtsfeiten. De tabel telt
ze mee als voorstellen en het dossier onderscheidt geaccepteerde van menselijke gevallen.

Bij §9.5 blijft een inhoudelijke vraag of overlappende korte tijdsfragmenten en omschrijvingen
dezelfde of verschillende functies dragen. Alleen expliciet geregistreerde kernalternatieven
van dezelfde geaccepteerde T-functie worden automatisch ontdubbeld. Algemene overlap is
onvoldoende grond om een voorstel te verwijderen. De grotere stabiliteit van B berust
mede op de nieuwe vaste datumregels en bewijst geen algemene juridische betrouwbaarheid
van de classifier.

## Contracten, context en technische grenzen

De exacte klassegroepen beperken het batchschema tot de keuzeruimte van iedere kandidaat
in die batch. De baseline kon binnen zijn gezamenlijke enum nog een klasse kiezen die voor
een afzonderlijke kandidaat niet toegestaan was. De per-kandidaatvalidator ving dit al af;
de nieuwe indeling voorkomt dat specifieke gat vooraf. Afgebroken antwoorden en ontbrekende
tooluitvoer blijven mogelijk. Zij krijgen een afzonderlijke technische registratie en,
wanneer review niet slaagt, menselijke beoordeling.

Meer context levert in deze proef **geen algemene verbetering** op. Bij lid 1 verandert C
niets ten opzichte van B; bij lid 5 en §9.5 is de uitvoer minder stabiel. Context vergroot
ook de input per aanvraag. De exacte groepen kosten op hun beurt meer aanvragen dan één
universele batch. Tokens, herpogingen, reviewcalls, technische fouten en kostenraming staan
per variant in de machineleesbare [vergelijking](model-vergelijking.json). De proefmodus is
bovendien geen wijziging van de standaardinstelling `universeel`.

| Technische maat, 24 pogingen per variant | A | B | C |
|---|---:|---:|---:|
| Adapteraanroepen, inclusief review/herpogingen | 27 | 159 | 156 |
| Ongeldige klassekeuzes per kandidaat | 24 | 0 | 0 |
| Kandidaten zonder bruikbare classifieruitvoer | 0 | 2 | 8 |
| Eindvoorstellen voor menselijke beoordeling | 5 | 2 | 8 |
| Ontdubbelde expliciete tijdkernalternatieven | 0 | 18 | 17 |
| Kostenraming in USD | 0,6987 | 2,0224 | 3,0166 |

Alle 72 primaire pogingen zijn afgerond. De totale raming is **USD 5,7377** voor 342
adapteraanroepen. De nieuwe batchindeling vraagt ongeveer zesmaal zoveel aanroepen als A.
Bij B blijven twee controles door ontbrekende tooluitvoer en mislukte review geel; bij C
betreft dit acht nominalisatievoorstellen in lid 5. Deze technische last hoort mee te wegen
bij een latere keuze voor standaardinstellingen. De raming volgt de in de runbestanden
opgenomen [Microsoft Foundry-lijstprijzen van Anthropic](https://www-cdn.anthropic.com/files/4zrzovbb/website/3684c2faafb97418665782cea0001f439f74b1d2.pdf),
niet een factuur; er zijn geen cachetokens gerapporteerd.

De elf oorspronkelijke controlepogingen met een onafgesloten onderzoekssnapshot zijn
uitsluitend technisch hersteld: dezelfde reacties, dezelfde detectie, nul extra aanvragen.
De oorspronkelijke bestanden blijven bewaard. Dit herstel wordt niet als annotatieverbetering
geteld. De graaf zelf en de productieresolver zijn ongewijzigd; de tegenstrijdige Awb-wortel
blijft een apart bronprobleem.

## Inhoudelijke beoordeling

De eerstvolgende beoordeling hoort per bronfunctie te bepalen welke voorstellen juist,
overbodig, verkeerd begrensd of nog ontbrekend zijn. In het bijzonder:

- Rechtsfeit versus Rechtsbetrekking bij invorderbaarheid, met behoud van de werkelijk genoemde objecten.
- De combinatie van berekening, toepassingsvoorwaarden en terugval naar lid 1; één klasse op één brede span representeert niet alle onderlinge relaties.
- Voorbeeldwaarden in §9.5 tegenover de algemene regel die zij illustreren.
- Overlappende T/RO/V-voorstellen en generieke naamwoordgroepen, ook in de controleartikelen.
- Het verloren ontwikkelanker WZT01/E11 na de bewuste grens bij de puntkomma; de oude referentie blijft onaangepast zichtbaar.

Deze ronde levert de technische implementatie, reproduceerbare resultaten en het volledige
beoordelingsmateriaal. De 60 conceptpunten blijven ongeadjudiceerd. Uitrol, nieuwe relationele
opslag en een claim van juridische precision/recall vallen buiten deze oplevering.
