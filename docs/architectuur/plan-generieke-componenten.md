# Plan: generieke componenten in de frontend

Inventarisatie van 15 nov 2026, op `origin/master` (2d527e8b) plus de LexRij-commit (dfbe4a0f, PR #1566). Alleen
gelezen, nog niets gebouwd. Aanleiding: het denkproces stond bij een antwoord bovenaan en bij een annotatie onderaan, met
een ander label, omdat elke soort Lex-beurt zijn kop zelf opbouwde (opgelost met `LexRij`, vormtest `app/lexRij.test.ts`).
Dit plan zoekt de andere plekken waar één patroon met de hand en in eigen Tailwind-klassen terugkomt.

Het kernprincipe staat in `frontend/CLAUDE.md` §*Generieke componenten*: één component per patroon, de oude varianten
verdwijnen en een vormtest in `app/*.test.ts` bewaakt dat ze niet terugkomen. Wat al bewaakt wordt (knoppen en labels,
het menu ⋯, de paneelkop, KeuzeRij, KaartActies, BlokKop, herkomst, wettekst, ingangen, Vraag Lex, het denkproces, de
artefacttitels) staat hier niet opnieuw in.

Regelnummers van `components/werkplek/ThreadRij.tsx` zijn die van master. Na #1566 schuiven ze ongeveer 26 regels omhoog.
De functienamen blijven hetzelfde.

## Overzicht, op wat de gebruiker het meest ziet

| # | patroon | plekken | voorstel | omvang |
|---|---|---|---|---|
| 1 | kaartje naar een paneel in het gesprek | 6 | `BronChip` wordt `PaneelChip` | S |
| 2 | laden, fout en *Opnieuw proberen* | 12 | `LaadStand` in `ui/` | M |
| 3 | melding met een handeling, en de stroken boven het gesprek | 8 | `Melding` uitbreiden (`actie`, `strook`) | S |
| 4 | lege toestand | ~45 | `Leeg` + `LeegWaarde` | M |
| 5 | overzichtskaart en zijn skelet | 3 + 3 | `OverzichtKaart`, `OverzichtSkelet` | M |
| 6 | uitklap (`<details>`) | ~25 | `Uitklap` met drie vormen | M |
| 7 | kop en sluitknop van een dialoog | 7 | `Dialog` met `titel` | S |
| 8 | datum en tijd | ~17 | `lib/datum.ts` uitbreiden | S |
| 9 | "Lex denkt"-stippen | 3 | `Denkt` | XS |
| 10 | kopiëren naar het klembord | 4 | `useKopieer` + `KopieerKnop` | S |
| 11 | tekstmaten en kleuren buiten de tokens | ~130 | tokens `text-2xs`/`text-3xs`, geen `bg-white` | M (mechanisch) |
| 12 | telwoorden (1 bron / 2 bronnen) | ~45 | `aantal()` in `lib/` | M (mechanisch) |

Omvang: XS < 50 regels, S < 200, M < 600, telkens inclusief vormtest.

---

## 1. Het kaartje naar een paneel in het gesprek

**Patroon.** Een rechthoek met een icoontegel, titel en ondertitel en een chevron. Een klik opent iets naast het gesprek.
Het is het meest geziene element na het antwoord zelf.

**Plekken.**
- `components/antwoord/BepalingChip.tsx:14` – `BronChip`, het enige gedeelde exemplaar.
- `components/werkplek/ThreadRij.tsx:305` – `OverzichtKaartje`, letterlijk dezelfde klassen (`:309`).
- `components/werkplek/ThreadRij.tsx:326` – `ArtefactChip` (`:343`), plus een eigen vorm voor "nog niet te openen" met een
  gestippelde rand (`:330`).
- `components/werkplek/ThreadRij.tsx:365` – `AnnotatieChip` (`:380`).
- `components/werkplek/ThreadRij.tsx:409` – `KandidatenKeuze` (`:428`), dezelfde kaart zonder icoon en mét een
  uitgeschakelde stand.
- Het chevron-pad `m9 18 6-6-6-6` staat vijf keer inline (`BepalingChip.tsx`, 4× `ThreadRij.tsx`), terwijl
  `ui/Icoon.tsx` al `PijlRechts` heeft.

**Wat afwijkt en wat de gebruiker merkt.**
- Het werkwoord in de ondertitel verschilt per soort: "bekijken", "beoordelen" en "review openen".
- `BronChip` kapt de ondertitel af (`truncate`), `ArtefactChip` en `OverzichtKaartje` niet: een lange ondertitel wrapt
  daar naar twee regels.
- Alleen `KandidatenKeuze` kent een uitgeschakelde stand. Een artefactchip tijdens een lopende beurt niet.
- `OverzichtKaartje` maakt het meervoud met `regeling{n === 1 ? "" : "en"}` in plaats van een hele zin.
- Elke kopie heeft een eigen focusstijl (`focus-visible:outline…` in plaats van `focus-ring`). Dat is nu nog gelijk,
  maar dat is toeval.

**Voorstel.** `BronChip` gaat naar `components/ui/PaneelChip.tsx`, met de props `titel`, `sub`, `icoon?` (zonder icoon
geen tegel), `onClick`, `uitgeschakeld?` en `nietTeOpenen?` (de gestippelde vorm, geen knop). De handeling komt uit één
tabel per soort (`lib/artefactTitels` of `ARTEFACT_SOORT_LABEL`). Daarmee wordt het één werkwoord per soort, en dat kiest
de gebruiker of de ontwerper één keer. De chevron wordt `PijlRechts`.

**Vormtest.** `app/paneelChip.test.ts`: de klassenreeks `h-9 w-9 shrink-0 items-center justify-center rounded-lg` en het
pad `m9 18 6-6-6-6` komen alleen voor in `components/ui/PaneelChip.tsx`. Elke `<button>` in `components/werkplek/` en
`components/antwoord/` met `rounded-kaart border border-line bg-surface` faalt.

**Omvang.** S: één nieuw bestand, vier functies in `ThreadRij.tsx` worden aanroepen, een test. Draai de browserregressie
mee (`data-testid="overzicht-kaartje"`, `data-tour="chip"` en `data-artefact-soort` blijven als doorgegeven `data-`
attributen).

## 2. Laden, een fout en *Opnieuw proberen*

**Patroon.** Een object laden: zolang het laadt een skelet of een regel, en bij een fout een melding met
*Opnieuw proberen*. Soms is er ook de stand "verwijderd".

**Plekken.**
- `components/annotaties/NodeAnnotatiePaneel.tsx:443` – een lokale `LaadStand`, titel "Niet geladen", knop alleen
  `underline`.
- `components/werkgebieden/BegripInhoud.tsx:142` – `BegripLaadStand`, titel "Het begrip kon niet worden geladen.",
  knop `focus-ring rounded font-medium text-lint underline`, skelet `SkeletonCard regels={4}`.
- `components/werkplek/WerkgebiedArtefactPaneel.tsx:294`, `components/werkgebieden/DeelvraagPaneel.tsx:123` en
  `BronnenBijDeelvraag.tsx:143` – hetzelfde als het begrip, telkens met de hand overgetypt.
- `components/werkgebieden/ElementenTab.tsx:86` – geen titel, de knop is een `Button variant="secondary" size="sm"`
  onder de tekst.
- `components/werkplek/GesprekLijst.tsx:158` – geen `Melding`, een kale `<p>` in `text-xs text-muted` met een
  `Button size="xs"`.
- `components/graaf/Graaf.tsx:229` en `:267` – titel "Niet geladen", twee knopstijlen in één bestand.
- `components/werkplek/WerkplekClient.tsx:1189` – de geschiedenis van het gesprek, met `underline-offset-2`.
- Laadregels zonder skelet, telkens anders geformuleerd en gekleurd: "Laden…" (`text-sm text-muted`: `OverzichtTab.tsx:118`,
  `BegripTerm.tsx:79`; `text-xs text-muted`: `RevisieHistorie.tsx:46`, `GeneriekGebruiken.tsx:66`, `GesprekActies.tsx:109`),
  "Tekst laden…" (`WettekstBlok.tsx:118`), "Werkgebieden laden…" (`OpnemenInWerkgebied.tsx:79`), "Leden ophalen…"
  (`BronnenBijDeelvraag.tsx:397`) en in `text-faint` "Tekst ophalen…", "Details ophalen…" en "Graafgegevens ophalen…"
  (`GraafInspector.tsx:150`, `:225`, `KnoopFeiten.tsx:23`).

**Wat afwijkt en wat de gebruiker merkt.** In het ene paneel staat de fout onder "Niet geladen", in het andere onder
"Het werkgebied kon niet worden geladen.". De herstelknop is daarbij soms een onderstreept woord in de tekst, soms een
lintblauwe link en soms een echte knop eronder. In de graaf staan twee van die vormen in één scherm. Laden heet afwisselend
"laden" en "ophalen", in twee grijstinten. Een foutzin zonder `Melding` (`GesprekLijst`) heeft geen icoon en geen
`role="alert"`.

**Voorstel.** `components/ui/LaadStand.tsx` met
`LaadStand({ wat, fout, onOpnieuw, verwijderd?, skelet = "kaart" | "regels" | "regel", children })`. De titel komt uit
`wat` ("Het begrip kon niet worden geladen."), de herstelknop is `MeldingActie` (bevinding 3) en de laadregel is één zin
("{Wat} laden…") in één kleur. De lokale `LaadStand`, `BegripLaadStand` en de vijf overgetypte varianten verdwijnen.

**Vormtest.** `app/laadStand.test.ts`: de tekst `Opnieuw proberen` komt alleen voor in `components/ui/LaadStand.tsx`,
`components/ui/Melding.tsx`, `app/error.tsx` en `app/global-error.tsx`. Een menuregel (`ConnectorsMenu.tsx:104`,
`MenuKnop`) staat op een korte uitzonderingslijst. `ophalen…` als laadtekst komt nergens meer voor.

**Omvang.** M: ongeveer twaalf plekken, mechanisch, één nieuw component.

## 3. Een melding met een handeling, en de stroken boven het gesprek

**Patroon.** Een melding met een knop erin (*Sluiten*, *Opnieuw proberen*, een link), en een melding over de volle
breedte boven het gesprek.

**Plekken.**
- `components/werkplek/WorkbenchShell.tsx:375` (budget op), `:384` (budget bijna op) en `:398` (fout), plus
  `WerkplekClient.tsx:1269` (gesprek niet bewaard): vier keer met de hand gebouwd, als
  `border-b border-fout/30 bg-fout/10 … text-center text-[0.8125rem]`, zonder icoon.
- `WerkplekClient.tsx:1206`–`:1262`: drie meldingen boven hetzelfde gesprek zijn wél `Melding compact`, met een icoon en
  links uitgelijnd.
- De knop in de melding staat er zes keer met de hand in, met vier klassensets (zie ook bevinding 2):
  `WorkbenchShell.tsx:389`/`:401`, `WerkplekClient.tsx:1232`/`:1259`, `BronnenBijDeelvraag.tsx:123`.

**Wat afwijkt en wat de gebruiker merkt.** Boven het gesprek staan twee soorten melding door elkaar: een gecentreerde
gekleurde strook zonder icoon, en een `Melding` met icoon. Welke vorm verschijnt, hangt af van het bestand en niet van wat
er speelt. De foutstrook heeft `role="status"`, waar een `Melding type="fout"` `role="alert"` heeft, dus een schermlezer
leest de ene fout direct voor en de andere niet.

**Voorstel.** Breid `Melding` uit:
- `actie?: { tekst; onClick } | ReactNode`, getekend als `MeldingActie` (één linkstijl);
- `onSluit?` voor *Sluiten*;
- `strook?: boolean`: de volle breedte met `border-b`, met icoon. De vier stroken worden `Melding strook`.

**Vormtest.** In `app/knoppen.test.ts` (of een nieuwe `app/melding.test.ts`): `bg-fout/10`, `bg-waarschuwing/10`,
`bg-succes/10` en `bg-info/10` komen alleen in `components/ui/Melding.tsx` voor. Daarbuiten staat in een `<Melding>` geen
`<button`.

**Omvang.** S. Laat de strook vóór de bouw door de gebruiker zien: met icoon is hij iets hoger dan nu.

## 4. De lege toestand

**Patroon.** "Nog geen X" of "Geen X die hierop past" in een lijst, een tab, een overzicht of een veld.

**Plekken.**
- Een kader met een gestippelde rand in de overzichten: `AnnotatiesClient.tsx:146`, `BegrippenOverzichtClient.tsx:138`,
  `WerkgebiedenClient.tsx:118`/`:122`, `AanpassingLijst.tsx:118`, `ElementenTab.tsx:207`, `ReviewQueue.tsx:690` (daar
  `py-4 text-xs`).
- Een kale regel: `AnnotatiesClient.tsx:142` (de eerste lege stand van hetzelfde overzicht, zónder kader),
  `ElementenTab.tsx:105`, `SamenhangTab.tsx:33`, `ContextPaneel.tsx:294`, `BerichtenPanel.tsx:162` en de beheerpanelen
  (`ApiTokensPanel.tsx:173`, `BerichtenBeheerPanel.tsx:106`, `FeedbackLijstClient.tsx:81`, `UsersPanel.tsx:213`), in
  `text-sm` of `text-xs`.
- Een lege waarde in een veld: "Nog geen definitie." is `italic text-faint` op de overzichtskaart
  (`BegripOverzichtKaart.tsx:40`) en `text-muted` op de begripskaart (`BegripInhoud.tsx:356`). Verder `BegripInhoud.tsx:360`
  en `:364`, `DetailPaginas.tsx:127`/`:133`/`:220`, `OverzichtTab.tsx:46` (`font-normal text-muted`),
  `WerkgebiedSamenvatting.tsx:56`/`:90`/`:101` en `ElementPagina.tsx:138`.
- `Groep`, `ObjectRijen` en `Lijst` hebben al een `leeg`-slot. Dat wordt maar deels gebruikt.

**Wat afwijkt en wat de gebruiker merkt.** In `/annotaties` staat "Nog geen annotaties" als losse regel, en meteen daarna
"Geen annotatie die hierop past" in een kader. In `/werkgebieden` staan beide in een kader. Hetzelfde ontbrekende veld
("Nog geen definitie.") is cursief en lichtgrijs op de kaart, en gewoon grijs op de begripspagina.

**Voorstel.**
- `components/ui/Leeg.tsx`: `Leeg({ kader?, klein?, children })` voor een lege lijst. In een overzicht en een tab is dat
  het kader, in een paneelrij en een menu de regel.
- `LeegWaarde` voor een ontbrekend veld (één stijl: `text-muted`, niet cursief).
- `Groep`, `ObjectRijen` en `Lijst` tekenen hun `leeg` met `Leeg`.

**Vormtest.** `app/leeg.test.ts`: `border-dashed` komt alleen in `components/ui/` voor (de "nog niet te openen"-chip valt
onder `PaneelChip`), en een `<p>` of `<span>` met `text-muted` of `text-faint` waarvan de tekst begint met
"Nog geen" of "Geen " faalt buiten `Leeg.tsx`.

**Omvang.** M: veel plekken, maar elke wijziging is één regel.

## 5. De overzichtskaart en zijn skelet

**Patroon.** De drie overzichten (`/annotaties`, `/begrippen`, `/werkgebieden`) hebben een raster van kaarten met een
titel-link, een status, een metaregel en `KaartActies`, plus een skelet zolang het laadt.

**Plekken.**
- `components/annotaties/AnnotatieKaart.tsx:38`, `components/begrippen/BegripOverzichtKaart.tsx:22` en
  `components/werkgebieden/WerkgebiedKaart.tsx:22`: drie keer letterlijk
  `rounded-kaart border border-line bg-paper p-4 shadow-zacht transition hover:-translate-y-0.5 …`, wat de waarde van
  `KLIK_KAART` (`ui/Pagina.tsx:268`) is. `KLIK_KAART` wordt buiten `Pagina.tsx` alleen in `ProjectTabs.tsx` gebruikt,
  terwijl `frontend/CLAUDE.md` zegt dat de drie overzichtskaarten hem gebruiken.
- De koppen: `h3 … font-display text-sm font-semibold text-lint`, de ene met `truncate`, de andere niet
  (`BegripOverzichtKaart.tsx:24` wrapt, `WerkgebiedKaart.tsx:24` kapt af). `gap-2` bij begrippen, `gap-3` bij de andere twee.
- De skeletten: `AnnotatiesClient.tsx:131` (drie onder elkaar, met een voortgangsbalk),
  `BegrippenOverzichtClient.tsx:128` en `WerkgebiedenClient.tsx:108` (twee in een raster).
- Het raster `grid grid-cols-1 gap-3 sm:grid-cols-2` staat vijf keer.
- De telling ("12 begrippen (de eerste 50)") staat alleen in `/begrippen` (`BegrippenOverzichtClient.tsx:145`).

**Wat afwijkt en wat de gebruiker merkt.** Een lange begripsnaam wrapt, een lange werkgebiednaam kapt af. Het skelet van
de annotaties is een kolom, dat van de andere twee een raster: de pagina springt bij het laden. Alleen in één overzicht
zie je hoeveel er zijn.

**Voorstel.** In `components/ui/Pagina.tsx` (bij `KaartActies`):
- `OverzichtKaart({ titel, href, status, meta, children, acties })`, die `KLIK_KAART` gebruikt;
- `OverzichtRaster` (het raster, met de telling erboven);
- `OverzichtSkelet({ aantal })`, in de vorm van de kaart.

De drie kaarten houden alleen hun inhoud.

**Vormtest.** In `app/uitlijning.test.ts`, bij "een overzichtskaart eindigt in KaartActies": `hover:-translate-y-0.5`
komt alleen in `components/ui/` voor, en een bestand met `<KaartActies>` gebruikt `OverzichtKaart`.

**Omvang.** M.

## 6. De uitklap (`<details>`)

**Patroon.** Een ingeklapt blok: *Historie*, *Dekking*, *Waarom stelt Lex dit voor?*, *Al besloten (3)*.

**Plekken** (ongeveer 25, in drie families):
- **Kader** (`rounded-kaart border border-line bg-surface/60 px-3 py-2 text-sm`): `DekkingOverzicht.tsx:20`,
  `RevisieHistorie.tsx:39`, `BegripInhoud.tsx:556` en `ArtefactInhoud.tsx:521`. Die laatste heeft geen `focus-ring`, geen
  `list-none` en geen chevron, en toont dus het driehoekje van de browser.
- **Regel** (`text-xs text-muted`): `BegripTerm.tsx:208`/`:258`, `BegripRelaties.tsx:108`, `BegripPassages.tsx:141`,
  `DefinitieOnderbouwing.tsx:17`, `KaartVoorstel.tsx:94`, `BegripInhoud.tsx:523` (`text-[11px]`, zonder `rounded`),
  `BronPagina.tsx:103`, `Contextweergave.tsx:301`, en met een eigen chevron `GraafInspector.tsx:174` en `KnoopFeiten.tsx:59`.
- **Sectie** (`text-sm font-semibold text-lint`): `BegripTerm.tsx:300` en `BegripVoorstellen.tsx:156`/`:171`/`:183`.

**Wat afwijkt en wat de gebruiker merkt.** De ene uitklap heeft een chevron die draait, de andere het driehoekje van het
besturingssysteem. Dat gaat in tegen de regel *Symbolen zijn iconen, geen tekens*: het driehoekje ziet er op elk platform
anders uit. De telling staat soms tussen haakjes in de tekst en soms helemaal niet.

**Voorstel.** `components/ui/Uitklap.tsx`:
`Uitklap({ samenvatting, telling?, vorm: "kader" | "regel" | "sectie", open?, onToggle?, children })`, altijd
`list-none` met `ChevronOmlaag` en `focus-ring`. `WaaromUitklap` wordt een gebruiker ervan.

**Vormtest.** `app/uitklap.test.ts`: `<details` komt alleen voor in `components/ui/Uitklap.tsx`.

**Omvang.** M. Draai daarna `scripts/test-*.mjs` voor de schermen met `data-testid="revisies"` en `"dekking"`.

## 7. De kop en de sluitknop van een dialoog

**Patroon.** Een `Dialog` met een titel bovenaan.

**Plekken.** `FeedbackDialoog.tsx:71`, `DisclaimerDialog.tsx:26`, `InstellingenDialog.tsx`, `BegripOpvolging.tsx`,
`BegripPassages.tsx:222`, `GeneriekGebruiken.tsx:60` en `WerkgebiedUitOverzicht.tsx`. Elk zet zelf een
`<h2 className="font-display text-base font-semibold text-lint">`. `Dialog` (`ui/Dialog.tsx:88`) heeft geen `titel` en
geen sluitknop: sluiten gaat via de achtergrond, Escape, of wat de inhoud zelf aanbiedt.

**Wat afwijkt en wat de gebruiker merkt.** `GeneriekGebruiken` heeft geen zichtbare manier om te sluiten. Op een telefoon
moet je naast het venster tikken. De andere dialogen hebben *Annuleren* in een `ButtonRow`, een `BewerkVoet` of een losse
`Button ghost`. De zijpanelen hebben wel een vaste kop (`PaneelKop`) met ✕, en de dialogen dus niet.

**Voorstel.** `Dialog` krijgt `titel?` en `sub?`. Daarmee tekent hij `DialoogKop`: de titel links, `SluitKnop` rechts,
hetzelfde ✕ als `PaneelKop`. `label` valt standaard terug op `titel`. De paneeldialogen (`ContextPaneel`,
`WerkgebiedArtefactPaneel`, `NodeAnnotatiePaneel`) houden `PaneelKop` en vallen hierbuiten.

**Vormtest.** `app/dialoog.test.ts`: een bestand met `<Dialog ` en `variant="compact"` of `"center"` heeft geen eigen
`<h2`.

**Omvang.** S.

## 8. Datum en tijd

**Patroon.** Een moment tonen.

**Plekken.** `lib/datum.ts` heeft `datumTijd` en `datumTekst`, maar die worden in zes bestanden gebruikt. Daarnaast
formatteren ongeveer 17 plekken zelf, in zes vormen:
- "12 nov." – `OverzichtTab.tsx:113`, `GesprekLijst.tsx:26`;
- "12 nov. 2026" – `WerkgebiedKaart.tsx:13`, `ProjectKop.tsx:81`, `lib/verwijderen.ts:48`, `lib/waarom.ts:55`;
- "12 nov. 2026 14:03" – `BegripInhoud.tsx:41`, `HistorieTab.tsx:12`, `RevisieHistorie.tsx:57`, `ElementPagina.tsx:176`,
  `NodeAnnotatiePaneel.tsx:396`, zonder `timeZone`, terwijl `datumTijd` `Europe/Amsterdam` vastzet;
- "12 nov. 14:03" – `BegripVoorstellen.tsx:20`, `lib/artefactVersie.ts:27`;
- "12-11-2026 14:03:05" (de standaard van de browser) – `ApiTokensPanel.tsx:96`;
- "12 november 2026" – `RegistratiesPanel.tsx:28`, `BerichtenPanel.tsx:25`, `BerichtenArchiefClient.tsx:15`,
  `lib/tokenbudget.ts:30`.

**Wat afwijkt en wat de gebruiker merkt.** Hetzelfde moment staat op de begripskaart, in de historie en in de revisies
telkens net anders. Op een laptop buiten de Nederlandse tijdzone verschuiven de tijden zonder `timeZone`. De API-tokens
tonen seconden en een streepjesdatum.

**Voorstel.** Breid `lib/datum.ts` uit met `datumKort` ("12 nov 2026"), `datumTijd` (bestaat al), `tijdOfDatum`
(vandaag de tijd, anders "12 nov", voor de gesprekkenlijst) en `datumLang` ("12 november 2026"), allemaal met
`Europe/Amsterdam`. Of een overzicht het jaar toont, kiest de gebruiker één keer (nu wisselt het).

**Vormtest.** `app/datum.test.ts`: `toLocaleDateString(`, `toLocaleTimeString(` en `new Date(…).toLocaleString(` komen
alleen in `lib/datum.ts` voor. `toLocaleString` op een getal (tokens, tekens) blijft toegestaan.

**Omvang.** S.

## 9. "Lex denkt": de stippen

**Plekken.** `ThreadRij.tsx:446` (`Punten`: drie stippen in `bg-muted`, die tegelijk pulseren), `VragenKaart.tsx:32`
(drie stippen in `bg-accent-soft`, met een vertraging per stip) en `ThreadRij.tsx:606` (`DenkProces`: één stip in
`bg-accent-soft`).

**Wat de gebruiker merkt.** Tijdens het samenstellen van een werkgebied denkt Lex met blauwe, golvende stippen, en bij een
gewone vraag met grijze stippen die tegelijk knipperen.

**Voorstel.** `components/ui/Denkt.tsx` met één vorm (de golvende van de vraagkaart, `motion-safe:`), die `LexRij`
(`denkt`) en `VragenKaart` gebruiken.

**Vormtest.** In `app/eenDenkproces.test.ts`: `animate-pulse rounded-full` komt alleen in `Denkt.tsx`, `Skeleton.tsx` en
`GesprekStatus.tsx` voor.

**Omvang.** XS.

## 10. Kopiëren naar het klembord

**Plekken.** `ThreadRij.tsx:545` (`KopieerKnop`, foutzin "Kopiëren lukte niet"), `admin/KopieerVeld.tsx:15` ("Kopiëren
lukt niet in deze browser. Selecteer de waarde en kopieer die zelf."), `admin/ApiTokensPanel.tsx:30` en
`werkplek/ExportKnop.tsx:58`.

**Wat de gebruiker merkt.** Bij een mislukte kopie geeft elke plek een andere zin. De bevestiging ("Gekopieerd") verschilt
ook in vorm en duur.

**Voorstel.** `lib/kopieer.ts` met `useKopieer()` (de stand gekopieerd of mislukt, de reset na een paar seconden, één
foutzin) en `components/ui/KopieerKnop.tsx`. `KopieerVeld` en `ExportRegels` gebruiken de hook.

**Vormtest.** `navigator.clipboard` komt alleen voor in `lib/kopieer.ts`.

**Omvang.** S.

## 11. Tekstmaten en kleuren buiten de tokens

**Plekken.**
- 121 losse tekstmaten in `components/` en `app/`: `text-[11px]` (37×), `text-[0.7rem]` (16×), `text-[10px]` (15×),
  `text-[0.65rem]` (8×), `text-[15px]` (8×), `text-[0.8125rem]` (6×), `text-[0.75rem]`, `text-[13px]` en een paar
  andere. Ze zijn deels gelijk aan elkaar maar anders geschreven (11px is 0,6875rem en dicht bij 0,7rem; 10px is dicht
  bij 0,65rem).
- `bg-white` 7× (`BronselectieKaart.tsx:43`, `VraagDock.tsx:83`/`:88`, `VragenKaart.tsx:14` …) naast het token
  `bg-paper`.
- `rounded-[20px]` en `rounded-[24px]` 5× voor de vraagkaarten, naast `rounded-kaart` en `rounded-bubbel`.

**Wat de gebruiker merkt.** De kleine tekst (tellers, metaregels, tooltips) is van plek tot plek een halve pixel anders.
Een donkere stand (`data-theme="dark"`, ligt klaar) laat `bg-white` wit staan.

**Voorstel.** Tokens in `tailwind.config.ts`: `text-2xs` (11px) en `text-3xs` (10px), eventueel `text-md` (15px), en
`rounded-vraag` voor de vraagkaarten. Daarna een mechanische vervanging.

**Vormtest.** In `app/knoppen.test.ts` (of `app/tokens.test.ts`): geen `text-[<getal>` en geen `bg-white` buiten
`app/global-error.tsx`.

**Omvang.** M, mechanisch, maar in veel bestanden tegelijk. Doe het als een eigen PR zonder andere wijzigingen, zodat de
review alleen klassen ziet.

## 12. Telwoorden

**Plekken.** Ongeveer 45 keer `n === 1 ? "1 x" : \`${n} xen\`` inline, onder andere `ElementenTab.tsx:141`/`:142`/`:271`/`:400`,
`BegripInhoud.tsx:656`, `DetailPaginas.tsx:227`, `WerkgebiedKaart.tsx:31`, `BegrippenOverzichtClient.tsx:146`,
`Graaf.tsx:251`/`:255`, `lib/kaartVoorstel.ts:70`/`:99`/`:128` en `lib/herbeoordeling.ts:44`/`:45`/`:54`. Losse helpers
doen hetzelfde: `lib/gesprekkenOpruimen.ts:6`, `lib/werkgebiedAnnoteren.ts:77`/`:81` en `bronnenZin`.

**Wat de gebruiker merkt.** Weinig. De zinnen kloppen, op `OverzichtKaartje` na (bevinding 1). Het risico zit in de
volgende plek die het met de hand doet.

**Voorstel.** `aantal(n, "bron", "bronnen")` in `lib/tekst.ts`. De losse helpers worden aanroepen ervan.

**Vormtest.** Het patroon `=== 1 ? "1 ` komt alleen in `lib/tekst.ts` voor.

**Omvang.** M, mechanisch. Laagste prioriteit: doe het hooguit samen met bevinding 11.

---

## Kleine vondsten (bij een PR hierboven meenemen)

- `ThreadRij.tsx` `BevestigingBlok` bouwt zijn knoprij met `flex flex-col gap-2 sm:flex-row` in plaats van `ButtonRow`.
  Neem dat mee bij bevinding 1.
- `GesprekActies.tsx:108`, `MethodesPanel.tsx:112`, `Relaties.tsx:67`/`:261` en `VersieKiezer.tsx:114` tonen een fout als
  kale `<p className="… text-fout">`. Een veldfout hoort bij `Field` (`error`), een laadfout bij `LaadStand`. Neem dat mee
  bij bevinding 2.

## Bewust níet generiek maken

- **De meldingen op het graafcanvas** (`CanvasMelding` in `graaf/Graaf.tsx:31`). Die zweven met een eigen transparantie
  over een canvas. Ze blijven een eigen vorm, maar de herstelknop erin wordt `MeldingActie`.
- **De knoptekst tijdens het wachten** ("Bezig met inloggen…", "Bezig met verifiëren…" in `auth/`). Dat is één regel per
  formulier. Een `bezig`-prop op `Button` levert weinig op, en de tekst verschilt terecht.
- **De grote vraagkaarten** (`VraagDock`, `BronselectieKaart`, `VragenKaart`). Ze lijken op een `Kaart`, maar ze zijn de
  vraagkaartfamilie van activiteit 1 met een eigen ritme (sticky kop, ruimere radius). Ze krijgen tokens (bevinding 11),
  maar worden niet samengevoegd met `Kaart`.
- **De beheerpanelen** onder `components/admin/`. Die gebruiken `SettingGroup` en `SettingRow` al. Hun lege toestanden
  vallen onder bevinding 4, maar de panelen zelf zijn per soort verschillend genoeg.
- **`app/global-error.tsx`**. Die vervangt de hele documentboom en kan de app-CSS niet veronderstellen (staat al in
  `frontend/CLAUDE.md`). Hij valt buiten elke vormtest hierboven.
- **De menuregel *Opnieuw proberen*** in `ConnectorsMenu.tsx:104`. Dat is een `MenuKnop` in een menu ⋯, dus een andere
  vorm met een eigen regel. Hij staat op de uitzonderingslijst van bevinding 2.
- **De `<details>` in `WaaromUitklap` voor het technische spoor** (`group/tech`) gaat wel naar `Uitklap`, maar het
  toolspoor zelf (`eenSpoor.test.ts`) blijft wat het is.

## Volgorde

Bevinding 3 komt eerst (`Melding` met `actie`), want 2 bouwt erop. Daarna 1, 2, 7 en 9: klein, en de gebruiker ziet het
meteen. Dan 4, 5, 6, 8 en 10. Als laatste 11 en 12, als twee mechanische PR's zonder ander werk erin. Per PR één patroon
en één vormtest, gebundeld zoals gebruikelijk.
