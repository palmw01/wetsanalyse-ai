# Interactieve 3D-workbench

Start vanuit `frontend/`:

```bash
npm install
npm run mock:graaf
```

Open **http://127.0.0.1:3110/mock/graaf**. De server luistert alleen op localhost.
Een API, GraphDB, model of account is niet nodig. Deze route bestaat alleen in
ontwikkelmodus met `GRAAF_MOCK=1`; de gewone workbench blijft achter de login.

## Uitproberen

1. **Samenhang van artikel 9** opent chat en graaf naast elkaar. Draai de graaf
   door te slepen en zoom met het scrollwiel. Gebruik **Knopenlijst** om een
   knoop met het toetsenbord te kiezen, of klik direct op een knoop.
2. Kies **Artikel 9 · lid 2** en **Toon verbindingen**. De voorbeeldmarkeringen
   verschijnen. Selecteer een markering om haar JAS-klasse en toelichting te zien.
3. **Open brontekst** wisselt naar het bestaande annotatiepaneel. De gekozen
   markering blijft geselecteerd. Met **3D-graaf** keer je terug naar dezelfde context.
4. **Vraag Lex hierover** zet een vraag en context klaar. Versturen geeft een
   lokaal voorbeeldantwoord. Vrije vragen buiten het voorbeeld krijgen een uitleg.
5. **Vergroten**, **Alles in beeld** en **Hele voorbeeld tonen** laten de volledige
   voorbeeldgraaf zien. Verkleinen behoudt selectie, uitbreiding en camerastand.
6. Het tweede gesprek, **JAS-annotaties verkennen**, begint bij de tekst.
   Markeringen beoordelen en aanpassen werkt lokaal met de bestaande reviewkaart.
7. **Herstel voorbeelden** zet alle lokale wijzigingen terug.

Onder 1280 pixels wordt het paneel een overlay. Bij ontbrekende WebGL blijven
de knopenlijst, broninformatie en tekst beschikbaar. De graaf zelf is uitsluitend 3D.

## Gegevens en grenzen

De mock toont artikel 9, leden 1 en 2, uit de bestaande rondleidingfixture.
Dat is een beperkte voorbeeldscène, geen volledige of actuele juridische analyse.
De verbinding van lid 2 naar lid 1 volgt de expliciete verwijzing in de tekst.
Overige verbindingen zijn documentstructuur, markeringen en klasse-indelingen.
Afstand en positie in 3D hebben geen juridische betekenis.

De JAS-markeringen en chatantwoorden zijn voorbeelden. Mutaties blijven in het
geheugen; er wordt niets opgeslagen in de backend of naar een model gestuurd.
Instellingen, feedback en uitloggen tonen een lokale melding. JSON-export werkt
lokaal; PDF en CSV verwijzen naar de mogelijkheden van de echte workbench.

De interface hergebruikt `WerkplekClient`, `AppSidebar`, `ArtefactInhoud`,
`DocumentPaneel`, `ReviewQueue`, `Dialog` en de bestaande tokens en JAS-kleuren.
De 3D-renderer wordt dynamisch geladen zodra de graaf wordt geopend.

## Controleren

Met de lokale mock gestart:

```bash
npm run typecheck
npm run lint
npm test -- auth.config.test.ts lib/rondleiding.test.ts components/werkplek/DocumentPaneel.test.ts
node scripts/test-graaf-mock.mjs
```

De browsercontrole gebruikt Chromium op `/usr/bin/chromium`; met `CHROMIUM_PATH`
kun je een andere executable kiezen. Screenshots komen standaard in
`/tmp/wetsanalyse-graaf-mock` (`MOCK_SCREENSHOTS` overschrijft deze locatie).
`TEST_URL` overschrijft het lokale adres.

De controle doorloopt 3D-bediening, uitklappen, selectie tussen tekst en graaf,
vergroten, voorbeeldchat, filters, mobiel en ontbrekende WebGL. Zij weigert
backendmutaties, onverwachte API-aanroepen en browserfouten. De auth-tests
bewaken dat de mockvlag geen andere routes en geen productieomgeving openzet.
