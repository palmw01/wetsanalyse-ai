"use client";

import { NodeAnnotatiePaneel } from "@/components/annotaties/NodeAnnotatiePaneel";
import { bronDoel, samenhangBeschikbaar } from "@/lib/samenhang";
import { ThreadRij, type ThreadActies } from "@/components/werkplek/ThreadRij";
import { reeksNavigatie } from "@/lib/reeks";
import { afronding } from "@/lib/beurtStroom";
import { useBeurt, type BeurtScherm } from "@/lib/useBeurt";
import { type NodeDoel } from "@/lib/annotatieNode";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { VraagLexContext } from "@/components/werkplek/VraagLexKnop";
import type { GraafOpties } from "@/components/graaf/useGraafStand";

import { WerkgebiedArtefactPaneel } from "@/components/werkplek/WerkgebiedArtefactPaneel";
import { ContextPaneel, ContextPaneelContext, contextSleutel, overzichtContext, type ContextDoel } from "@/components/werkplek/ContextPaneel";
import { WerkgebiedUitOverzicht } from "@/components/werkplek/WerkgebiedUitOverzicht";
import { annotatieDoelVan, artefactSleutel, bronselectieVanKaart, artefactKop, werkgebiedArtefactVan, type Artefact, type WerkgebiedArtefact } from "@/lib/artefact";
import { StatusLabel } from "@/components/ui/Lijst";
import { Suggestie, SuggestieRij } from "@/components/ui/Suggestie";
import { Melding } from "@/components/ui/Melding";
import { Zijpaneel } from "@/components/ui/Zijpaneel";
import { PaneelTabsContext } from "@/components/ui/PaneelKop";
import { TabRij } from "@/components/ui/Tabs";
import { leesOpslag, schrijfOpslag } from "@/lib/opslag";
import { bewaarVorm, leesBewaard, openTab, opslagSleutel, sluitTab, tabLabel, type PaneelInhoud, type TabStand } from "@/lib/paneelTabs";
import {
  foutTekst,
  startRun,
  haalGesprek,
  maakGesprek,
  voegBerichtToe,
  haalWerkgebied,
  wijzigGesprek,
  wijzigWerkgebied,
} from "@/lib/api";
import { resetdatum } from "@/lib/tokenbudget";
import type {
  AgentDoelInvoer,
  AgentHergebruik,
  BeurtMeting,
  Overzicht,
  BeslissingType,
  Bevestiging,
  Gesprek,
  Verbruiksstand,
} from "@/lib/types";
import { ANNULEER_TEKST, afgehandeld } from "@/lib/werkgebiedAnnoteren";
import {
  antwoordOp, antwoordTekst, groepeerVragen, klaarActie, openVraag,
} from "@/lib/vraagkaart";
import { VraagDock } from "@/components/werkplek/VraagDock";
import { BronselectieKaart } from "@/components/werkplek/BronselectieKaart";
import { ConnectorsMenu } from "@/components/werkplek/ConnectorsMenu";
import { actieveConnectors, beurtBronnen, moetVerversen, toonMenu, wissel as wisselConnector, zelfAanTeZetten, type BronUit, type ConnectorStand } from "@/lib/connectorsMenu";
import { useConnectorLijst } from "@/lib/useConnectorLijst";
import {
  doelInvoerVan, isVerwijderd,
} from "@/lib/annotatie";
import { BREED, useBreedScherm } from "@/lib/useBreedScherm";
import { useOnbewaardBewaker } from "@/lib/useOnbewaardBewaker";
import { bewaarConcept, leesConcept } from "@/lib/conceptVraag";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type { ThreadItem } from "@/lib/threadItem";
import { LEX_KORT, WerkplekHeader } from "./WerkplekHeader";
import { itemsUitGesprek } from "@/lib/geschiedenis";
import { bevestigt, startOpties, userVelden, type BeurtVerzoek } from "@/lib/beurtVerzoek";
import { DEMO_DOEL, DEMO_SLUG, type DemoScene } from "@/lib/rondleidingDemo";
import {
  SOORT_LABEL, VERVOLG_TEKST, chipTekst, overVan, suggestiesVan, werkgebiedSuggesties, type Onderwerp, type Vervolg,
} from "@/lib/vraagLex";

// De thread-items staan in `lib/threadItem.ts`, zodat de rondleiding er een voorbeeldbeurt
// mee kan opbouwen zonder dit component te importeren.
type Item = ThreadItem;

/** De graafopties zonder een doorgegeven kennisgraaf: die geldt alleen voor het paneel direct na een
 *  wissel, niet als er intussen annotaties veranderden. */
function zonderKennisgraaf(g: GraafOpties): GraafOpties {
  if (!g.kennisgraaf) return g;
  const { kennisgraaf: _weg, ...rest } = g;
  return rest;
}

function uid(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

// Opnieuw aanhaken bij een weggevallen verbinding gebeurt zolang dit venster leeft, met een
// oplopende wachttijd (`herstelWachttijd`) en een banner die zegt wat er aan de hand is. De lus staat in
// `lib/beurtLus.ts`, de regels in `lib/lopendeRun.ts`; hier staat alleen wat het scherm ermee doet.
//
// Eén poging na 1,5 seconde is niet genoeg: duurt de onderbreking langer – een herstart van
// graph-qa is dat al – dan komt de beurt als mislukt in beeld terwijl hij gewoon doorloopt, en
// brengt alleen een herlaadbeurt hem terug.

interface Props {
  /** Het te openen gesprek, of `null` voor een vers (nog niet gepersisteerd) gesprek. */
  initialGesprekId: string | null;
  /** Roept terug zodra bij de eerste beurt een gesprek is aangemaakt (voor sidebar-highlight + lijst). */
  onGesprekAangemaakt: (id: string) => void;
  /** Roept terug na elke persistente wijziging zodat de sidebar-lijst kan verversen. */
  onGewijzigd: () => void;
  /** De voorbeeldscène van de rondleiding. Is die gezet, dan draait dit venster als demo: de thread
   *  komt uit de scène, de invoer staat stil en elke mutatie blijft in dit geheugen – er gaat geen
   *  enkel verzoek naar de api. De rondleiding krijgt hiervoor een eigen mount (zie `WorkbenchShell`),
   *  zodat het echte gesprek onaangeroerd blijft en na afloop gewoon weer uit de api komt. */
  demo?: DemoScene;
  /** Meldt de rondleiding dat er in de demo iets beslist is, en wát – de bevestiging in de bubbel
   *  hoort te passen bij de handeling. Daarnaast: of het artefact openstaat. */
  onDemoBeslissing?: (type: BeslissingType) => void;
  onDemoArtefact?: (open: boolean) => void;
  /** Verhoog dit om het voorbeeldartefact te openen. De rondleiding laat de gebruiker eerst zelf op
   *  de kaart klikken en springt pas bij als dat uitblijft. */
  demoOpenSignaal?: number;
  /** Verhoog dit om het voorbeeldartefact te sluiten. De rondleiding doet dat als je terugloopt naar
   *  een stap die het paneel niet nodig heeft: die stappen wijzen naar de thread, en met het paneel
   *  ervoor is daar niets van te zien. */
  demoSluitSignaal?: number;
  /** De eigen verbruiksstand: bij een vol budget gaat de invoer dicht. `null` = onbekend, en dan
   *  blijft alles gewoon werken – een meter die niet laadt mag het werk niet stilleggen. */
  verbruik?: Verbruiksstand | null;
  /** Het werkgebied van dit gesprek (spoor G1; bij een nieuw gesprek dat van `?werkgebied=`): de
   *  chatkop van de shell noemt het, elke beurt draagt het mee (`werkgebied_id`), en een nieuw gesprek
   *  wordt eraan gekoppeld. */
  werkgebiedId?: string | null;
  onVerlaatWerkgebied?: () => void;
  /** Het gesprek is geladen: de shell leest er het werkgebied en het archief uit. */
  onGesprekGeladen?: (gesprek: Gesprek) => void;
  /** Verhoogd door de chatkop (*Bronnen*): open de bronnen van het werkgebied naast het gesprek (spoor G4). */
  bronnenSignaal?: number;
  /** Een werkgebied gemaakt vanuit een overzicht: de werkplek gaat in die context verder. */
  onKiesWerkgebied?: (id: string) => void;
  /** Roept terug zodra een beurt is afgerond, zodat de stand meteen ververst. */
  onBeurtKlaar?: () => void;
  /** Start de rondleiding vanuit de lege staat – precies het moment waarop iemand hem nodig heeft. */
  onRondleiding?: () => void;
  /** *Vraag Lex* van buiten de werkplek (`?vraag=<soort>:<id>`, F3b): de chip staat al klaar. */
  beginOnderwerp?: Onderwerp | null;
  /** Een vraag die klaar staat in het invoerveld (`?start=werkgebied`); versturen doet de analist. */
  beginInvoer?: string | null;
}

export function WerkplekClient({
  initialGesprekId, onGesprekAangemaakt, onGewijzigd, demo, onDemoBeslissing,
  onDemoArtefact, demoOpenSignaal = 0, demoSluitSignaal = 0, onRondleiding,
  verbruik = null, onBeurtKlaar, werkgebiedId = null, onVerlaatWerkgebied, onKiesWerkgebied, onGesprekGeladen, bronnenSignaal = 0,
  beginOnderwerp = null,
  beginInvoer = null,
}: Props) {
  // Budget op? Dan gaat de invoer dicht. Alleen bij een actieve begrenzing – staat die uit, dan is
  // `geblokkeerd` per definitie false en verandert er niets.
  const geblokkeerd = Boolean(verbruik?.actief && verbruik.geblokkeerd);
  const [gesprekId, setGesprekId] = useState<string | null>(initialGesprekId);
  // ADR-013, *Bronnen en tools*: wat de beheerder aanzette, de stand van dit gesprek en de standaard van het werkgebied.
  // De ref volgt de stand, zodat `verstuur` de stand van nu leest; `connectorsTeBewaren` = gekozen vóór er een gesprek was.
  // De lijst is van het venster (`lib/connectorLijst.ts`): een nieuwe mount (ander gesprek) toont meteen de laatst bekende.
  const connectorLijst = useConnectorLijst(!demo);
  const [gesprekConnectors, setGesprekConnectors] = useState<string[] | null>(null);
  // De standaard van het werkgebied hoort bij dát werkgebied: na een wissel telt de oude niet meer.
  const [wgConnectors, setWgConnectors] = useState<{ id: string; connectors: string[] | null } | null>(null);
  const connectorStand: ConnectorStand = {
    beschikbaar: connectorLijst.beschikbaar,
    laden: connectorLijst.laden ?? undefined,
    controleert: connectorLijst.controleert,
    gesprek: gesprekConnectors,
    werkgebied: werkgebiedId && wgConnectors?.id === werkgebiedId ? wgConnectors.connectors : null,
  };
  const connectorRef = useRef(connectorStand);
  connectorRef.current = connectorStand;
  const connectorsTeBewaren = useRef(false);
  const [items, setItems] = useState<Item[]>(demo?.items ?? []);
  // De open vraag die je met ✕ wegklikte (het item-id); "Een vraag stellen ›" opent hem weer.
  const [weggeklikt, setWeggeklikt] = useState<string | null>(null);
  const [invoer, setInvoer] = useState(beginInvoer ?? "");
  // Het concept van de vraag per gesprek (UI-08, `lib/conceptVraag.ts`). Eerst lezen, pas daarna schrijven: anders wist
  // de lege begininvoer het concept voordat het terug is. Lezen in een effect, want `sessionStorage` bestaat niet
  // tijdens de server-render. Een klaargezette vraag (`beginInvoer`) gaat voor; na versturen is de invoer leeg en het
  // concept dus weg.
  const conceptGelezen = useRef(false);
  useEffect(() => {
    if (demo) return;
    if (!conceptGelezen.current) {
      conceptGelezen.current = true;
      const concept = beginInvoer ? "" : leesConcept(gesprekId);
      // Eenmalig herstel uit de opslag van de browser, geen afgeleide state.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (concept) { setInvoer(concept); return; }
    }
    bewaarConcept(gesprekId, invoer);
  }, [demo, gesprekId, invoer, beginInvoer]);
  // Niet-blokkerende melding als het opslaan van een beurt faalt (de chat loopt door).
  const [bewaarFout, setBewaarFout] = useState<string | null>(null);
  // De vraag is geweigerd omdat het tokenbudget op is. Apart van `bewaarFout`: die zegt dat het
  // gesprek niet bewaard wordt, en dat is hier onwaar – er is alleen niets verstuurd.
  const [budgetGeweigerd, setBudgetGeweigerd] = useState(false);
  const [nodeDoel, setNodeDoel] = useState<NodeDoel>();
  const [tabStand, setTabStand] = useState<TabStand>({ tabs: [] });
  // Waar de volgende opening vandaan komt ("een antwoord"): alleen voor de tooltip van de tab.
  const [volgendeVanuit, setVolgendeVanuit] = useState<string>();
  // Op een telefoon is het paneel een sheet; Escape (of *Vraag Lex*) verbergt hem, de tabs blijven.
  const [sheetVerborgen, setSheetVerborgen] = useState(false);
  // Op een breed scherm klapt Escape het zijpaneel in.
  const [inklapSignaal, setInklapSignaal] = useState(0);
  // Telt elke opening: het zijpaneel klapt dan uit.
  const [openTeller, setOpenTeller] = useState(0);
  const [tabsHersteld, setTabsHersteld] = useState(false);
  const [tabsGeladen, setTabsGeladen] = useState(false);
  /** Het open artefact van een werkgebied (begripsvoorstellen of gevonden bepalingen). Er staat
   *  hoogstens één artefact open: wie een annotatie opent, sluit dit, en andersom. */
  const [wgArtefact, zetWgArtefactOnbewaakt] = useState<WerkgebiedArtefact>();
  // Telt elke beurt die een werkgebied opleverde of aanpaste: het paneel laadt dan opnieuw, ook als het al
  // op dat werkgebied openstond (het dossier aanvullen geeft hetzelfde artefact terug).
  const [wgLading, setWgLading] = useState(0);
  // Wat er in dat paneel onbewaard openstaat (een begrip in bewerking). De bewaker hoort hier en niet in het paneel:
  // de wissels komen van de werkplek (FB-05).
  const [wgOnbewaard, setWgOnbewaard] = useState(false);
  const wgBewaker = useOnbewaardBewaker(wgOnbewaard);
  // Een context naast het gesprek die geen artefact van een beurt is (spoor G4): een bepaling, een
  // element, de bronnen van het werkgebied. Ook hier hoogstens één paneel tegelijk: opent er een
  // annotatie of artefact, dan gaat de context dicht; opent de context, dan gaan die dicht.
  const [ctx, setCtx] = useState<ContextDoel>();
  const [vorigPaneel, setVorigPaneel] = useState<{ n?: NodeDoel; w?: WerkgebiedArtefact }>({});
  if (vorigPaneel.n !== nodeDoel || vorigPaneel.w !== wgArtefact) {
    setVorigPaneel({ n: nodeDoel, w: wgArtefact });
    if (nodeDoel || wgArtefact) setCtx(undefined);
  }
  const [vorigBronnenSignaal, setVorigBronnenSignaal] = useState(bronnenSignaal);
  if (vorigBronnenSignaal !== bronnenSignaal) {
    setVorigBronnenSignaal(bronnenSignaal);
    if (werkgebiedId) {
      const bibliotheek: ContextDoel = { soort: "bibliotheek", werkgebied_id: werkgebiedId, titel: "" };
      setVolgendeVanuit("Bronnen in de chatkop");
      wisselPaneel(undefined, { ook: () => { setNodeDoel(undefined); setCtx(bibliotheek); } });
    }
  }

  /** De enige weg naar het paneel van een werkgebied naast het gesprek (FB-05). Alles wat dat paneel vervangt, sluit of
   *  opnieuw laadt – een ander artefact, een annotatie of context die ervoor in de plaats komt, een beurt die hetzelfde
   *  artefact opnieuw oplevert (`opnieuw`, de `key` met `wgLading`) – loopt hierdoor: staat er onbewaard werk open, dan
   *  vraagt het paneel eerst, zoals bij sluiten. `ook` draait binnen dezelfde vraag mee. De kale setter staat nergens
   *  anders (`app/paneelWissel.test.ts`). */
  function wisselPaneel(naar: WerkgebiedArtefact | undefined,
    { opnieuw = false, ook, handeling = "wisselen" }: { opnieuw?: boolean; ook?: () => void; handeling?: "wisselen" | "sluiten" } = {}) {
    wgBewaker.bewaak(() => {
      zetWgArtefactOnbewaakt(naar);
      if (opnieuw) setWgLading((n) => n + 1);
      ook?.();
    }, handeling);
  }
  /** Een tab in de slots laden (of alles leeg met `undefined`). Altijd via `wisselPaneel`, dus met de bewaker: staat er
   *  onbewaard werk in het artefact, dan vraagt het eerst. `ook` draait binnen dezelfde vraag mee. */
  function laad(i: PaneelInhoud | undefined, ook?: () => void) {
    if (!i) {
      wisselPaneel(undefined, { handeling: "sluiten", ook: () => {
        setCtx(undefined); setNodeDoel(undefined); setNodeReeks(undefined); setNodeExtra([]); setNodeGraaf({}); ook?.();
      } });
    } else if (i.soort === "context") {
      wisselPaneel(undefined, { ook: () => { setNodeDoel(undefined); setCtx(i.ctx); ook?.(); } });
    } else if (i.soort === "annotatie") {
      wisselPaneel(undefined, { ook: () => {
        setCtx(undefined); setNodeTab(i.tab); setNodeExtra(i.extra); setNodeGraaf(i.graaf); setNodeReeks(i.reeks); setNodeDoel(i.doel); ook?.();
      } });
    } else {
      wisselPaneel(i.artefact, { ook: () => { setCtx(undefined); setNodeDoel(undefined); ook?.(); } });
    }
  }
  /** Een tab sluiten (✕ op de tab, of ✕ in de kop van wat er open is). Was hij actief, dan komt de buur. */
  function sluitPaneelTab(sleutel: string | undefined) {
    if (!sleutel) return laad(undefined);
    const na = sluitTab(tabStand, sleutel);
    if (tabStand.actief !== sleutel) return setTabStand({ tabs: na.tabs, actief: na.actief });
    laad(na.buur?.inhoud, () => setTabStand({ tabs: na.tabs, actief: na.actief }));
  }
  /** Escape: verbergen, niet sluiten. Breed klapt het zijpaneel in (de inhoud blijft gemount); op een telefoon gaat de sheet
   *  weg, en dan loopt het door de bewaker – de inhoud wordt ontkoppeld. */
  function verbergPaneel() {
    if (breed) setInklapSignaal((n) => n + 1);
    else wgBewaker.bewaak(() => setSheetVerborgen(true), "sluiten");
  }

  /** Het overzicht waaruit de jurist een werkgebied maakt (de dialoog staat open). */
  const [wgUitOverzicht, setWgUitOverzicht] = useState<Overzicht>();
  /** Wat er bij het maken misging (een bepaling die de api niet kon opnemen): zichtbaar, niet stil. */
  const [wgMelding, setWgMelding] = useState<string | null>(null);
  /** De reeks (run-id) waaruit de open annotatie is geopend; het paneel bladert dan door de leden. */
  const [nodeReeks, setNodeReeks] = useState<string>();
  // Opent het node-paneel op de graaf (knop onder een antwoord) of op de tekst (annotatie).
  const [nodeTab, setNodeTab] = useState<"tekst" | "graaf">("tekst");
  // Wat de graaf verder meeopent: de bepalingen die een antwoord noemt (`antwoordDoelen`) of de delen
  // van een overzicht (`overzichtDoelen`). Leeg zodra het paneel op een andere manier opent.
  const [nodeExtra, setNodeExtra] = useState<NodeDoel[]>([]);
  // Met welk bereik de graaf opent en wat de nadruk krijgt (een overzicht: de hele kennisgraaf).
  const [nodeGraaf, setNodeGraaf] = useState<GraafOpties>({});

  // ── De tabs van het paneel (het bronvenster, PR 3b) ──────────────────────────────────────────────────────────────
  // De slots hierboven zijn de actieve tab; dit is de lijst ernaast (`lib/paneelTabs.ts`). Wisselen laadt een tab in de
  // slots, altijd via `wisselPaneel` (de bewaker); per gesprek bewaard in deze browser.
  const huidig = useMemo<PaneelInhoud | undefined>(() => ctx ? { soort: "context", ctx }
    : nodeDoel ? { soort: "annotatie", doel: nodeDoel, tab: nodeTab, extra: nodeExtra, graaf: nodeGraaf, reeks: nodeReeks }
      : wgArtefact ? { soort: "artefact", artefact: wgArtefact } : undefined,
  [ctx, nodeDoel, nodeTab, nodeExtra, nodeGraaf, nodeReeks, wgArtefact]);
  const [vorigHuidig, setVorigHuidig] = useState<PaneelInhoud | undefined>();
  if (vorigHuidig !== huidig) {
    setVorigHuidig(huidig);
    if (huidig) {
      setTabStand((st) => openTab(st, huidig, volgendeVanuit));
      setVolgendeVanuit(undefined);
      setSheetVerborgen(false);
      setOpenTeller((n) => n + 1);
    } else if (vorigHuidig) {
      // Dicht zonder dat een tab gesloten werd (een paneel dat zichzelf sloot): de actieve tab vervalt.
      setTabStand((st) => (st.actief ? { tabs: st.tabs.filter((t) => t.sleutel !== st.actief), actief: undefined } : st));
    }
  }

  // De tabs van dit gesprek terughalen, één keer na het mounten (de server kent geen opslag). Een nieuw gesprek begint
  // leeg: zonder id is er niets te halen, en er wordt pas bewaard zodra het gesprek een id heeft. Op een breed scherm komt
  // de actieve tab meteen terug, met de bewaarde ingeklapte stand; op een telefoon staat hij klaar achter *Paneel · Openen*.
  useEffect(() => {
    // Opslag lezen kan pas na het mounten; de setState is hier het doel van het effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (demo || !gesprekId) { setTabsGeladen(true); return; }
    const bewaard = leesOpslag(opslagSleutel(gesprekId), leesBewaard);
    setTabsGeladen(true);
    if (!bewaard) return;
    setTabStand(bewaard);
    const actief = bewaard.tabs.find((t) => t.sleutel === bewaard.actief);
    let isBreed = false;
    try { isBreed = window.matchMedia(BREED).matches; } catch { /* geen matchMedia */ }
    if (actief && isBreed) { setTabsHersteld(true); laad(actief.inhoud); }
    // Alleen bij het mounten (de werkplek remount per gesprek); `laad` is elke render een nieuwe functie.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (demo || !tabsGeladen || !gesprekId) return;
    schrijfOpslag(opslagSleutel(gesprekId), tabStand.tabs.length ? bewaarVorm(tabStand) : undefined);
  }, [tabStand, gesprekId, demo, tabsGeladen]);

  const [samenhangAan, setSamenhangAan] = useState(false);
  useEffect(() => { void samenhangBeschikbaar().then(setSamenhangAan); }, []);
  // Waar de volgende vraag over gaat (*Vraag Lex*, F3b): een markering, of een object uit een werkgebied.
  // Een chip boven het invoerveld zolang het geldt; na het versturen weg.
  const [onderwerp, setOnderwerp] = useState<Onderwerp | undefined>(beginOnderwerp ?? undefined);
  // Zichtbaarheid van de "naar beneden"-pil: aan zodra de gebruiker weg van de bodem scrolt.
  const [toonNaarBeneden, setToonNaarBeneden] = useState(false);
  // Wat er zojuist is opgeslagen, voor schermlezers. Zonder dit gebeurt elke annotatie-wijziging
  // volledig stil: de kaart verandert visueel, maar er wordt niets aangekondigd.
  const [melding, setMelding] = useState("");
  // Een vraag ging over een bron naast de wet die uit stond (ADR-013, graph-qa `bron_uit`): de jurist kan hem hier
  // aanzetten. Weg bij de volgende vraag.
  const [bronUit, setBronUit] = useState<BronUit[]>([]);
  // Een vervolgstap die Lex zelf aankondigde (`opgeslagen.vervolg`): verstuurd zodra de beurt klaar is en de werkplek
  // in dat werkgebied staat, als een klik op de suggestie met die actie.
  const [vervolg, setVervolg] = useState<(Vervolg & { id: string }) | null>(null);
  const vervolgGedaan = useRef("");
  const lijstRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  // "Stick-to-bottom": alleen automatisch meescrollen als de gebruiker al onderaan staat, zodat
  // omhoogscrollen tijdens het streamen niet telkens wordt teruggetrokken.
  const stickRef = useRef(true);
  // Past het artefact naast de chat? Dan wordt het een eigen kolom in plaats van een overlay, en
  // blijft Lex bereikbaar tijdens het reviewen.
  const breed = useBreedScherm();

  // De beurt van dit venster: starten, meekijken, opnieuw verbinden, stoppen en weer aanhaken (`lib/useBeurt.ts`).
  // Unmount koppelt alleen de kijker los; de run draait door bij de agent en komt terug bij binnenkomst. Wat er op
  // het scherm gebeurt, staat hieronder in `beurtScherm`.
  const beurt = useBeurt(beurtScherm());
  const { bezig, runId, stopt, verbindingWeg, runVerdwenen, beurtEinde } = beurt;

  // Hydrateer één keer bij mount: bestaande gespreksberichten → thread. Lees de id uit een MOUNT-vaste
  // ref, niet uit de reactieve prop: bij de eerste beurt zet de shell `activeId` (→ prop null→id) zónder
  // remount; zou de effect daarop herstarten, dan overschrijft `haalGesprek` de lopende stream. Een échte
  // gespreks-wissel remount dit component (via `key={mountKey}`), dus de ref draagt dan de juiste id.
  const hydratieId = useRef(initialGesprekId).current;
  // De geschiedenis kon niet worden geladen. Stil falen liet een leeg beginscherm zien alsof het
  // gesprek leeg was – en een volgende vraag belandde dan in een gesprek waarvan je de rest niet zag.
  const [hydratieFout, setHydratieFout] = useState<{ melding: string; weg: boolean } | null>(null);
  // Welke laadpoging telt. Een oudere poging (StrictMode draait het effect twee keer, of een
  // "opnieuw proberen" terwijl de vorige nog liep) mag de thread niet nog eens aanvullen.
  const hydratiePoging = useRef(0);

  function hydrateer(id: string) {
    setHydratieFout(null);
    const poging = ++hydratiePoging.current;
    const geldt = () => beurt.levend() && poging === hydratiePoging.current;
    haalGesprek(id)
      .then((g) => {
        if (!geldt()) return;
        onGesprekGeladen?.(g);
        setGesprekConnectors(g.connectors ?? null);
        const { items: geschiedenis, runIds } = itemsUitGesprek(g.berichten, uid);
        // VÓÓR wat er al staat, niet in plaats daarvan. Verstuurde de jurist een vraag terwijl dit nog
        // laadde (een koude start duurt seconden), dan staan zijn vraag en het lopende antwoord al in
        // de thread – vervangen liet het antwoord onzichtbaar binnenstromen tot een herlaadbeurt.
        setItems((xs) => [...geschiedenis, ...xs]);
        // Liep hier nog een beurt terwijl je ergens anders keek? Pak hem weer op. De run-ids uit de
        // geschiedenis gaan mee: daarmee is "afgerond terwijl je weg was" te onderscheiden van
        // "weg door een herstart".
        void beurt.hervat(id, runIds);
      })
      .catch((e) => {
        if (!geldt()) return;
        if (isVerwijderd(e)) {
          // Het gesprek bestaat niet (meer) – verwijderd in een ander tabblad, of een oude link. Een
          // volgende vraag begint dan een nieuw gesprek in plaats van op een 404 te stuiten.
          setGesprekId(null);
          setHydratieFout({ melding: "Dit gesprek bestaat niet meer. Een nieuwe vraag begint een nieuw gesprek.", weg: true });
          onGewijzigd();
        } else {
          setHydratieFout({ melding: foutTekst(e, "Het gesprek kon niet worden geladen."), weg: false });
        }
      });
  }

  useEffect(() => {
    if (hydratieId) hydrateer(hydratieId);
    const pogingen = hydratiePoging;
    return () => {
      pogingen.current += 1;
    };
    // `hydrateer` bewust niet als dependency: deze hydratatie hoort één keer per mount te draaien (zie
    // de toelichting hierboven), en de functie wordt elke render opnieuw gemaakt. Het afbreken bij
    // unmount loopt via `beurt.levend()`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydratieId]);

  useEffect(() => {
    const el = lijstRef.current;
    if (el && stickRef.current) el.scrollTo({ top: el.scrollHeight });
  }, [items, bezig]);

  function onThreadScroll() {
    const el = lijstRef.current;
    if (!el) return;
    const bijBodem = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    stickRef.current = bijBodem;
    setToonNaarBeneden(!bijBodem && items.length > 0); // React bail-out bij gelijke waarde
  }

  function naarBeneden() {
    const el = lijstRef.current;
    if (!el) return;
    stickRef.current = true;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setToonNaarBeneden(false);
  }

  function updateItem(id: string, patch: Partial<Item>) {
    setItems((xs) => xs.map((x) => (x.id === id ? ({ ...x, ...patch } as Item) : x)));
  }

  useEffect(() => {
    if (!demo || demoOpenSignaal === 0) return;
    void openArtefact(DEMO_SLUG, DEMO_DOEL);
    // Alleen op de teller reageren: `demo` en `openArtefact` horen hier niet in de dependencies,
    // want dan opent het paneel opnieuw zodra een van beide een nieuwe referentie krijgt — terwijl
    // de rondleiding juist één keer om dit signaal vraagt.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoOpenSignaal]);

  useEffect(() => {
    if (!demo || demoSluitSignaal === 0) return;
    // Een teller die als signaal dient: de rondleiding leeft in een ander component en kan dit
    // paneel niet rechtstreeks sluiten. Spiegelt het openen hierboven; de setState is hier het doel
    // van het effect, geen afgeleide state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setNodeDoel(undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoSluitSignaal]);

  // De rondleiding wacht met haar reviewstappen tot het paneel er echt is.
  useEffect(() => {
    onDemoArtefact?.(Boolean(nodeDoel));
    // Alleen bij een echte wisseling van het paneel melden. `onDemoArtefact` is een inline callback
    // van de rondleiding en dus elke render een andere referentie; in de dependencies zou dit
    // effect bij iedere render opnieuw vuren.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeDoel]);

  // Het laatst gevraagde artefact. Opent de jurist A (traag) en dan B, dan mag A bij het binnenkomen
  // B niet meer verdringen.
  const gevraagdArtefact = useRef<string | null>(null);

  async function openArtefact(slug: string, doel?: NodeDoel) {
    gevraagdArtefact.current = slug;
    wisselPaneel(undefined, { ook: () => {
      if (doel?.bron_iri) { setNodeTab("tekst"); setNodeExtra([]); setNodeGraaf({ keten: true }); setNodeDoel(doel); return; }
      setNodeDoel(undefined);
    } });
  }

  /** Persisteer één beurt. Mislukken mag de chat niet blokkeren – maar ook niet stil gebeuren:
   *  de beurt staat dan wél in beeld en is na herladen weg. Eén onopvallende melding boven de thread
   *  is genoeg; per beurt een foutregel zou het gesprek onleesbaar maken. */
  async function persisteer(gid: string, rol: "user" | "assistant", velden: Record<string, unknown>) {
    try {
      await voegBerichtToe(gid, { rol, ...velden });
      setBewaarFout(null);
    } catch (e) {
      setBewaarFout(foutTekst(e));
    }
  }

  /** Start een beurt. Zonder `verzoek.prompt` geldt wat er in het invoerveld staat (`lib/beurtVerzoek.ts`). */
  // Wat de beheerder aanzette en wat de omgeving aanbiedt: de laatst bekende stand van dit venster, ververst bij elke
  // mount, met een korte reeks herpogingen als de stand niet vast te stellen was (`lib/connectorLijst.ts`). Daarna
  // opnieuw bij het openen van het menu, vóór en na een beurt, en bij terugkomst in het venster.
  const verversAlsOnbekend = () => { if (moetVerversen(connectorRef.current)) connectorLijst.ververs(); };

  // De standaard van het werkgebied, alleen als er een menu is.
  const heeftConnectors = connectorLijst.beschikbaar.length > 0;
  useEffect(() => {
    if (!werkgebiedId || !heeftConnectors) return;
    let levend = true;
    haalWerkgebied(werkgebiedId)
      .then((wg) => levend && setWgConnectors({ id: werkgebiedId, connectors: wg.standaard_connectors ?? null }))
      .catch(() => {});
    return () => { levend = false; };
  }, [werkgebiedId, heeftConnectors]);

  function zetGesprekConnectors(connectors: string[] | null) {
    setGesprekConnectors(connectors);
    if (gesprekId) void wijzigGesprek(gesprekId, { connectors }).catch(() => {});
    else connectorsTeBewaren.current = connectors != null;
  }

  function kiesConnector(naam: string) {
    zetGesprekConnectors(wisselConnector(connectorRef.current, naam));
  }

  /** De stand van nu wordt de standaard van het werkgebied, en dit gesprek volgt die weer. */
  async function maakConnectorStandaard() {
    if (!werkgebiedId) return;
    const actief = actieveConnectors(connectorRef.current);
    try {
      const wg = await haalWerkgebied(werkgebiedId);
      await wijzigWerkgebied(werkgebiedId, { verwachte_revisie: wg.revisie, standaard_connectors: actief });
      setWgConnectors({ id: werkgebiedId, connectors: actief });
      zetGesprekConnectors(null);
    } catch {
      // Een 412 of storing: de stand van het gesprek blijft zoals hij was.
    }
  }

  async function verstuur(verzoek: BeurtVerzoek = {}) {
    // In de rondleiding is dit venster een voorbeeld: er gaat niets naar de agent. De invoerbalk is
    // ook uitgeschakeld, dit is het vangnet voor Enter en de voorbeeldknoppen.
    if (demo) return;
    // Budget op: geen enkele weg naar een nieuwe beurt. De knoppen zijn ook uitgeschakeld, maar dat
    // is de zichtbare helft — dit is de sluitende. De eerste versie schermde alleen de verzendknop
    // af, en toen bleven de voorbeeldvragen, de kandidatenlijst en het beginscherm gewoon open.
    if (geblokkeerd) return;
    const prompt = (verzoek.prompt ?? invoer).trim();
    // Synchrone guard tegen dubbel-verzenden (twee Enters in dezelfde tick): de `bezig`-state komt te laat.
    if (!prompt || !beurt.claim()) return;
    setInvoer("");
    setBronUit([]);
    // Was de bronstand niet vast te stellen, dan nu opnieuw, op de achtergrond: de beurt wacht er niet op en draagt de
    // opgeslagen keuze (graph-qa toetst de straat zelf).
    verversAlsOnbekend();

    // Een vraag bij een markering gaat als ADVIES: dezelfde thread, maar met contextblok en langs de
    // antwoordroute – die kan topologisch geen annotatie wijzigen. Een ander object gaat als
    // `onderwerp` mee (`lib/vraagLex.ts`).
    const vraagOver = onderwerp;
    setOnderwerp(undefined);
    const contextLabel = vraagOver ? overVan(vraagOver) : "";

    // Toon de user-bubbel + antwoord-placeholder OPTIMISTISCH, vóór het (bij een nieuw gesprek) awaiten
    // van maakGesprek – anders "verdwijnt" het bericht tijdens die round-trip.
    const antId = uid();
    // Het id van de user-bubbel vasthouden: moet de beurt worden teruggedraaid (er liep er al een),
    // dan halen we precies déze weg. Filteren op de tekst zou een eerdere, identieke vraag treffen.
    const vraagId = uid();
    // De knop bij een voorstel van Lex: dit bericht beantwoordt het, en daarna staat er geen knop meer.
    setItems((xs) => [
      ...xs,
      { id: vraagId, type: "user", tekst: prompt, over: contextLabel || undefined,
        ...(verzoek.intake ? { antwoordOp: antwoordOp(verzoek.intake) } : {}),
        ...(bevestigt(verzoek) ? { bevestigingKeuze: "gestart" as const } : {}) },
      { id: antId, type: "antwoord", tekst: "" },
    ]);
    stickRef.current = true; // een nieuwe beurt springt altijd naar de bodem
    // Meldingen over de vórige beurt horen niet bij deze (`beurt.claim` wist de zijne).
    setBudgetGeweigerd(false);

    // Zorg voor een gesprek-id (maak er bij de eerste beurt één aan; titel = de vraag, afgekapt).
    let gid = gesprekId;
    if (!gid) {
      try {
        const g = await maakGesprek(prompt.slice(0, 80), werkgebiedId ?? "");
        gid = g.id;
        setGesprekId(gid);
        onGesprekAangemaakt(gid);
        if (connectorsTeBewaren.current && connectorRef.current.gesprek != null) {
          // Gekozen in een nieuw gesprek: nu er een gesprek is, bewaren (stil falend; de beurt draagt de stand toch).
          connectorsTeBewaren.current = false;
          void wijzigGesprek(gid, { connectors: connectorRef.current.gesprek }).catch(() => {});
        }
      } catch (e) {
        updateItem(antId, { tekst: `**Er ging iets mis.** ${foutTekst(e)}` });
        beurt.vrij();
        return;
      }
    }

    // De chip is UI-state en reist niet mee naar de api: de contextregel staat in de tekst (`userVelden`).
    //
    // Bewust GEAWAIT: de vraag moet vastliggen vóórdat de run begint. De volgorde in de thread is de
    // autoincrement-id, dus een snelle beurt zou anders vóór zijn eigen vraag kunnen landen – en bij
    // het aanhaken na een herlaadbeurt is deze regel de user-bubbel waar het antwoord onder hoort.
    await persisteer(gid, "user", userVelden(verzoek, prompt, contextLabel));

    let gestart;
    try {
      // Welke route de beurt neemt (annoteren, vraagkaartje, actie, advies of onderwerp): `startOpties`.
      const stand = connectorRef.current;
      gestart = await startRun(prompt, gid, {
        ...startOpties(verzoek, { werkgebiedId, onderwerp: vraagOver }),
        // Alleen met een menu: zonder connector bij de beheerder beslist graph-qa zelf (alleen wetgeving).
        ...beurtBronnen(stand),
      });
    } catch (e) {
      // Er liep al een beurt (bijvoorbeeld in een ander tabblad). Deze vraag is dus NIET aangenomen:
      // zet hem terug in het invoerveld en haal de optimistische bubbels weg, zodat er niets
      // stilzwijgend verdwijnt. Aanhaken bij de lopende beurt gebeurt hieronder.
      const lopend = (e as { loopendeRun?: string }).loopendeRun;
      if (lopend) {
        // De vraagbubbel blijft staan, gemarkeerd als niet verstuurd: hij is al bewaard
        // (`persisteer` draait vóór `startRun`), dus weghalen zou hem bij een herlaadbeurt gewoon
        // laten terugkomen – en opnieuw versturen zette hem er dan dubbel in.
        setItems((xs) => xs
          .filter((x) => x.id !== antId)
          .map((x) => (x.id === vraagId && x.type === "user" ? { ...x, nietVerstuurd: true } : x)));
        setInvoer(prompt);
        setBewaarFout(null);
        const hervatId = uid();
        setItems((xs) => [...xs, { id: hervatId, type: "antwoord", tekst: "" }]);
        await beurt.volg(lopend, gid, hervatId);
        return;
      }
      // Het tokenbudget is op. Net als bij een lopende beurt hierboven: deze vraag is NIET
      // aangenomen, dus geen mislukte antwoordbubbel laten staan maar de vraag teruggeven. En de
      // verbruiksstand meteen ophalen – dit pad komt nooit bij `beurt.volg`, dus zonder deze
      // aanroep blijven de strook en de dichte invoerbalk tot een minuut achterlopen. Precies
      // daardoor kón deze vraag überhaupt nog verstuurd worden.
      if ((e as { budgetOp?: true }).budgetOp) {
        // Alleen de lege ANTWOORDbubbel weg; de vraag blijft staan. Die is namelijk al opgeslagen –
        // `persisteer(…, "user", …)` draait vóór `startRun` – dus hem uit beeld halen zou hem bij
        // een herlaadbeurt gewoon laten terugkomen. Wat je ziet klopt zo met wat er bewaard is.
        setItems((xs) => xs.filter((x) => x.id !== antId));
        setBudgetGeweigerd(true);
        onBeurtKlaar?.();
        beurt.vrij();
        return;
      }
      // De vraag is al bewaard; de foutmelding gaat er als antwoord bij. Anders stond er na een
      // herlaadbeurt een vraag zonder enig antwoord, en leek het alsof hij nog liep.
      const fout = `**Er ging iets mis.** ${foutTekst(e)}`;
      updateItem(antId, { tekst: fout });
      void persisteer(gid, "assistant", { tekst: fout });
      beurt.vrij();
      return;
    }

    // Onthoud dát er een beurt liep. Komt de agent tussentijds opnieuw op, dan is dit het enige
    // spoor waarmee de werkplek kan zeggen wat er gebeurd is.
    beurt.onthoud(gid, gestart.run_id);
    await beurt.volg(gestart.run_id, gid, antId);
  }

  /** Wat het scherm met een beurt doet (`useBeurt`): de bubbel bijwerken, een paneel openen, tonen wat de agent
   *  vastlegde. Elke render vers; de hook leest de laatste via een ref. */
  function beurtScherm(): BeurtScherm {
    return {
      schrijfStroom: (antId, stand) => updateItem(antId, { tekst: stand.tekst, denk: stand.denk }),
      handlers: (antId, p, stroom) => ({
        onStatus: (m) => { p.pas({ type: "status", bericht: m }); stroom.plan(); },
        onReason: (t) => { p.pas({ type: "reason", tekst: t }); stroom.plan(); },
        onToken: (t) => { p.pas({ type: "token", tekst: t }); stroom.plan(); },
        onSources: (b) => updateItem(antId, { bronnen: b }),
        onGrounding: (g) => updateItem(antId, { grounding: g }),
        onAntwoord: (a) => updateItem(antId, { antwoord: a }),
        onOverzicht: (o) => {
          updateItem(antId, { overzicht: o });
          // Op een breed scherm staat het meteen naast het antwoord, zoals de bronselectie. Op een smal
          // scherm niet: daar ligt het paneel over het antwoord, en het kaartje is één tik.
          if (breed && o.regelingen.length) wisselPaneel(undefined, { ook: () => { setNodeDoel(undefined); setCtx(overzichtContext(o)); } });
        },
        onVraagkaart: (k) => updateItem(antId, { vraagkaart: k }),
        onDoel: (d) => p.pas({ type: "doel", doel: d }),
        onKandidaten: (k, kz) => p.pas({ type: "kandidaten", kandidaten: k, keuze: kz }),
        onReeksEvent: (ev) => {
          stroom.nu();
          const voor = p.stand().reeks;
          p.pas({ type: "reeks", event: ev });
          const { reeks: r, tekst } = p.stand();
          if (r === voor || !r) return;
          setItems((xs) => xs.map((x) => (x.id === antId ? { id: antId, type: "reeks", reeks: r, tekst } : x)));
        },
        onHergebruik: (h) => p.pas({ type: "hergebruik", hergebruik: h }),
        onRun: (r) => p.pas({ type: "meting", meting: r.instellingen?.meting }),
        // De eventlog van de run is gecapt: er is narratie weggevallen. Benoem dat, in plaats van
        // een tekst te tonen die compleet lijkt maar het niet is (`GAT_IN_TEKST`/`GAT_IN_DENK`).
        onGat: () => {
          stroom.nu();
          p.pas({ type: "gat" });
          updateItem(antId, p.stand().tekst ? { tekst: p.stand().tekst } : { denk: p.stand().denk });
        },
        onOpgeslagen: (uitkomst) => p.pas({ type: "opgeslagen", uitkomst }),
        onWaarschuwing: (bericht) => setMelding(bericht),
        onBronUit: (bronnen) => setBronUit(bronnen),
        onBronstand: (regels) => connectorLijst.legBronstandOver(regels),
        onRegieTaak: () => onGewijzigd(),
      }),
      opKlaar: async (antId, stand) => {
        const { tekst, denk, kandidaten, keuze, opgeslagen } = stand;
        switch (afronding(stand)) {
          case "reeks": break;
          case "kandidaten":
            setItems((xs) =>
              xs.map((x) => (x.id === antId ? { id: antId, type: "kandidaten", tekst, kandidaten, ...(keuze ? { keuze } : {}) } : x)),
            );
            break;
          case "opgeslagen":
            await toonVastgelegdeBeurt(opgeslagen!, {
              antId, tekst, denk, hergebruik: stand.hergebruik, doel: doelInvoerVan(stand.doel),
              meting: stand.meting,
            });
            // Lex gaat zelf verder (na *Werkgebied aanmaken*: de bronselectie). Alleen live, nooit na herladen: dan
            // start er niets vanzelf.
            if (opgeslagen!.vervolg) setVervolg({ ...opgeslagen!.vervolg, id: uid() });
            break;
          case "leeg":
            // Geen `opgeslagen` en geen fout: het gesprek werd verwijderd terwijl de beurt liep.
            updateItem(antId, { tekst: "(geen antwoord)" });
            break;
          case "tekst": break;
        }
        onGewijzigd();
      },
      opMislukt: (antId, stand, fout) => {
        // Dezelfde melding als op het bericht dat graph-qa bewaarde: live en na herladen staat er hetzelfde.
        updateItem(antId, { tekst: stand.tekst, denk: stand.denk, uitkomst: { status: "mislukt", melding: foutTekst(fout) } });
      },
      // De beurt zelf is rond; alleen de naverwerking faalde (het document of de wettekst ophalen): zeg wat er mis is.
      opNaverwerkingFout: (fout) => setMelding(foutTekst(fout)),
      voorHervatten: (runId) => {
        const antId = uid();
        // Een lopende reeks heeft de onderdelen die al klaar waren al als berichten bewaard; het aanhaken speelt de
        // hele stroom opnieuw af. Het gehydrateerde blok gaat dus weg, anders staat de reeks er twee keer.
        setItems((xs) => [
          ...xs.filter((x) => !(x.type === "reeks" && x.reeks.runId === runId)),
          { id: antId, type: "antwoord", tekst: "" },
        ]);
        return antId;
      },
      onBeurtKlaar: () => { verversAlsOnbekend(); onBeurtKlaar?.(); },
    };
  }

  useEffect(() => {
    if (!vervolg || vervolgGedaan.current === vervolg.id || bezig || werkgebiedId !== vervolg.werkgebied_id) return;
    vervolgGedaan.current = vervolg.id;
    void verstuur({ prompt: VERVOLG_TEKST[vervolg.actie], actie: vervolg.actie });
    // `verstuur` is elke render nieuw; het effect hoort alleen bij de vervolgstap en de stand van de beurt.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vervolg, bezig, werkgebiedId]);

  /** De agent heeft de beurt al weggeschreven; haal op wat er staat en toon het.
   *
   *  Bewust ophalen in plaats van de inhoud in het SSE-contract te proppen: dan blijft de api de ene
   *  bron van waarheid en groeit het eventcontract niet mee met het datamodel.
   */
  async function toonVastgelegdeBeurt(
    uitkomst: { artefact?: Artefact; annotatie_doel?: NodeDoel; bevestiging?: Bevestiging },
    { antId, tekst, denk, hergebruik, doel, meting }: {
      antId: string; tekst?: string; denk: string;
      hergebruik?: AgentHergebruik; doel?: AgentDoelInvoer;
      meting?: BeurtMeting;
    },
  ) {
    // Een artefact van een werkgebied (begripsvoorstellen, gevonden bepalingen): de chip, en het paneel open.
    const begrippen = werkgebiedArtefactVan(uitkomst.artefact);
    if (begrippen?.soort === "bronselectie") {
      // Het antwoord en het kaartje staan al in beeld; het paneel ernaast toont de stand per deelvraag. Op een
      // smal scherm niet vanzelf: daar ligt het paneel over de vraag die je moet beantwoorden.
      if (breed) wisselPaneel(begrippen, { opnieuw: true, ook: () => setNodeDoel(undefined) });
      return;
    }
    if (uitkomst.artefact && begrippen) {
      const artefact = uitkomst.artefact;
      setItems((xs) => xs.map((x) => x.id === antId ? { id: antId, type: "artefact", artefact, tekst: tekst?.trim() || undefined, denk } : x));
      wisselPaneel(begrippen, { opnieuw: true, ook: () => setNodeDoel(undefined) });
      // Een werkgebied dat Lex met je samenstelde: het gesprek gaat erin verder (de shell koppelt het,
      // de suggesties bieden bepalingen zoeken en begrippen voorstellen), het paneel toont wat er staat.
      if (begrippen.soort === "werkgebied") onKiesWerkgebied?.(begrippen.werkgebied_id);
      return;
    }
    const node = annotatieDoelVan(uitkomst.artefact) ?? uitkomst.annotatie_doel ?? (doel?.bron_iri ? {
      bron_iri: doel.bron_iri, label: doel.label, snapshot_id: doel.snapshot_id,
    } : undefined);
    // Een voorstel om het werkgebied te annoteren: het antwoord staat al in beeld, de knop erbij.
    if (!node && uitkomst.bevestiging) updateItem(antId, { bevestiging: uitkomst.bevestiging });
    if (!node) return; // een gewoon antwoord staat al in beeld
    setItems((xs) => xs.map((x) => x.id === antId ? { id: antId, type: "annotatie", slug: node.bron_iri,
      annotatie_doel: node, titel: uitkomst.artefact?.titel || node.label, tekst: tekst?.trim() || undefined, denk, hergebruik,
      meting } : x));
    // Deze beurt veranderde de annotaties: een kennisgraaf die een vorig paneel doorgaf, klopt niet meer.
    wisselPaneel(undefined, { ook: () => { setNodeGraaf((g) => ({ ...zonderKennisgraaf(g), keten: true })); setNodeDoel(node); } });
  }

  /** *Annuleren* bij een voorstel van Lex: niets starten. Geen beurt bij de agent – alleen een bericht in
   *  het gesprek dat het voorstel beantwoordt, zodat de knoppen ook na herladen weg zijn. */
  async function annuleer() {
    if (demo || !beurt.magStarten() || !gesprekId) return;
    setItems((xs) => [...xs, { id: uid(), type: "user", tekst: ANNULEER_TEKST, bevestigingKeuze: "geannuleerd" }]);
    stickRef.current = true;
    await persisteer(gesprekId, "user", { tekst: ANNULEER_TEKST, bevestiging_antwoord: { keuze: "geannuleerd" } });
  }

  // De handelingen van de thread-rijen, als één object dat nooit verandert. `ThreadRij` is een
  // `memo`: een verse callback per render zou elke rij toch weer laten renderen. De ref wijst naar
  // de handlers van de laatste render (die lezen actuele state), het object zelf blijft gelijk.
  const actiesRef = useRef<ThreadActies | null>(null);
  useLayoutEffect(() => {
    actiesRef.current = {
      verstuur: (verzoek) => void verstuur(verzoek),
      openArtefact: (slug, doel) => void openArtefact(slug, doel),
      openArtefactVan: (artefact) => {
        const ref = werkgebiedArtefactVan(artefact);
        if (!ref) return;
        wisselPaneel(ref, { ook: () => setNodeDoel(undefined) });
      },
      // Zonder eigen opties opent een antwoord op de ketting; een overzicht geeft zijn bereik zelf mee.
      openSamenhang: (doel, extra = [], graaf = { keten: true }) => { setVolgendeVanuit("een antwoord"); wisselPaneel(undefined, { ook: () => {
        setNodeTab("graaf");
        setNodeExtra(extra);
        setNodeGraaf(graaf);
        setNodeDoel(doel);
      } }); },
      openReeksLid: (reeksRun, doel) => {
        setNodeReeks(reeksRun);
        void openArtefact(doel.bron_iri, doel);
      },
      stop: () => void beurt.stop(),
      annuleer: () => void annuleer(),
      openOverzicht: (ov) => openContext(overzichtContext(ov)),
      openVraag: () => setWeggeklikt(null),
    };
  });
  const [acties] = useState<ThreadActies>(() => ({
    verstuur: (verzoek) => actiesRef.current?.verstuur(verzoek),
    openArtefact: (slug, doel) => actiesRef.current?.openArtefact(slug, doel),
    openArtefactVan: (artefact) => actiesRef.current?.openArtefactVan(artefact),
    openSamenhang: (doel, extra, graaf) => actiesRef.current?.openSamenhang(doel, extra, graaf),
    openReeksLid: (reeksRun, doel) => actiesRef.current?.openReeksLid(reeksRun, doel),
    stop: () => actiesRef.current?.stop(),
    annuleer: () => actiesRef.current?.annuleer(),
    openOverzicht: (ov) => actiesRef.current?.openOverzicht(ov),
    openVraag: () => actiesRef.current?.openVraag(),
  }));

  function opToets(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // `isComposing`: met een IME (of een Android-toetsenbord dat een woordsuggestie met Enter
    // bevestigt) hoort Enter de compositie af te ronden, niet de beurt te versturen.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void verstuur();
    }
  }

  // De laatste annotatie in dit gesprek: die hoort altijd één klik weg te zijn.
  // Ook over de soorten artefacten heen: stelde Lex na een annotatie begrippen voor, dan is dát het
  // laatste werk. Een artefact dat de werkplek (nog) niet kan openen, telt niet mee.
  const laatsteItem = [...items]
    .reverse()
    .find((x): x is Extract<Item, { type: "annotatie" | "artefact" }> =>
      x.type === "annotatie" || (x.type === "artefact" && !!werkgebiedArtefactVan(x.artefact)));
  // De bronselectie (spoor J) is een antwoord met een kaartje, geen artefact-item: komt ze na het laatste
  // artefact, dan is zij het laatste werk.
  const bsIndex = items.length - 1 - [...items].reverse().findIndex((x) => x.type === "antwoord" && x.vraagkaart?.modus === "bronselectie");
  const bsItem = items[bsIndex];
  const laatsteBronselectie = bsItem?.type === "antwoord" && bsIndex > (laatsteItem ? items.lastIndexOf(laatsteItem) : -1)
    ? bronselectieVanKaart(bsItem.vraagkaart) : undefined;
  // Een overzicht (het hoort bij een antwoord) is het laatste werk als er daarna geen artefact meer kwam.
  const ovIndex = items.length - 1 - [...items].reverse().findIndex((x) => x.type === "antwoord" && !!x.overzicht?.regelingen.length);
  const ovItem = items[ovIndex];
  const laatsteOverzicht = ovItem?.type === "antwoord" && ovIndex > Math.max(laatsteItem ? items.lastIndexOf(laatsteItem) : -1, laatsteBronselectie ? bsIndex : -1)
    ? ovItem.overzicht : undefined;
  const laatsteAnnotatieItem = !laatsteBronselectie && !laatsteOverzicht && laatsteItem?.type === "annotatie" ? laatsteItem : undefined;
  const laatsteNodeAnnotatie = laatsteAnnotatieItem?.annotatie_doel ? laatsteAnnotatieItem : undefined;
  const laatsteWgArtefact = laatsteBronselectie
    ?? (!laatsteOverzicht && laatsteItem?.type === "artefact" ? werkgebiedArtefactVan(laatsteItem.artefact) : undefined);
  const laatsteKop = laatsteWgArtefact && artefactKop(laatsteWgArtefact);
  // Het samenstellen van een werkgebied (activiteit 1): de vragen per reeks als één kaart, de open vraag
  // onderaan in plaats van het invoerveld.
  const { groepen: vraagGroepen, verborgen: verborgenItems } = useStabieleGroepen(items, bezig);
  // Welke voorstellen van Lex al beantwoord zijn (gestart of geannuleerd): daar staan geen knoppen meer.
  const keuzes = useMemo(() => afgehandeld(items), [items]);
  const open = openVraag(vraagGroepen);
  // Het open compacte kaartje van de bronselectie: *Klaar* mag dan ook vanuit het paneel.
  const paneelKaart = open?.open?.weergave === "paneel" ? open.open : undefined;
  const toonDock = !!open?.open && !bezig && !demo && weggeklikt !== open.openId;

  // Auto-groeiende textarea (groeit met de inhoud tot een max; daarna intern scrollen). Ook de breedte telt: een
  // plaatshouder die op een smal scherm afbrak, hield anders na het verbreden zijn hoogte, en dan staan tekst en knop
  // niet meer op één lijn. Alleen op een andere breedte: de hoogte zetten we zelf, en die mag geen lus starten.
  useLayoutEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    const pasAan = () => {
      ta.style.height = "0px";
      ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
    };
    pasAan();
    let breedte = ta.offsetWidth;
    const waarnemer = new ResizeObserver(() => {
      if (ta.offsetWidth === breedte) return;
      breedte = ta.offsetWidth;
      pasAan();
    });
    waarnemer.observe(ta);
    return () => waarnemer.disconnect();
  }, [invoer, toonDock]);

  const suggesties = onderwerp ? suggestiesVan(onderwerp)
    : werkgebiedId && !demo && !invoer.trim() ? werkgebiedSuggesties() : [];

  // Hoort de open annotatie bij een reeks in dit gesprek, dan bladert het paneel door de leden.
  const nodeReeksNav = (() => {
    if (!nodeDoel || !nodeReeks) return undefined;
    const item = items.find((x): x is Extract<Item, { type: "reeks" }> => x.type === "reeks" && x.reeks.runId === nodeReeks);
    const nav = item && reeksNavigatie(item.reeks, nodeDoel.bron_iri);
    return nav ? { ...nav, onGa: (d: NodeDoel) => { setNodeGraaf(zonderKennisgraaf); setNodeDoel(d); } } : undefined;
  })();
  const artefact = nodeDoel ? <NodeAnnotatiePaneel key={`${nodeDoel.bron_iri}:${nodeDoel.snapshot_id ?? ""}:${nodeDoel.versie ?? ""}:${nodeTab}:${nodeGraaf.bereik ?? ""}:${nodeGraaf.keten ? "keten" : ""}:${nodeExtra.map((d) => d.bron_iri).join("|")}`} doel={nodeDoel}
    extraDoelen={nodeExtra} graaf={nodeGraaf.keten ? { ...nodeGraaf, werkgebiedId } : nodeGraaf}
    // Een knoop uit een ander artikel (meegeopend, of uit de hele kennisgraaf): het paneel op dát
    // artikel; de rest van de kaart, het bereik en de nadruk blijven mee.
    onWisselDoel={(nieuw, graaf) => {
      setNodeExtra([nodeDoel, ...nodeExtra].filter((d) => d.bron_iri !== nieuw.bron_iri));
      setNodeGraaf({ ...nodeGraaf, ...graaf });
      setNodeTab("tekst");
      setNodeDoel(nieuw);
    }}
    variant={breed ? "kolom" : "side"} onSluit={() => sluitPaneelTab(tabStand.actief)} onVerberg={verbergPaneel} beginTab={nodeTab}
    reeks={nodeReeksNav}
    // De rondleiding draait op een voorbeeld in het geheugen, met het invoerveld stil: daar is geen
    // vraag te stellen, en de graaf heeft niets om te tonen.
    opslag={demo?.opslag}
    onBeslist={demo ? onDemoBeslissing : undefined}
    onVraag={demo ? undefined : (element, view) => {
      // Geen klaargezette vraag in het veld: de drie suggesties (per klasse) staan erboven als chips.
      setOnderwerp({ soort: "markering", element, view });
      setInvoer("");
      if (!breed) setSheetVerborgen(true);
      taRef.current?.focus();
    }}
    onVraagOverBron={demo ? undefined : (knoop) => {
      // Een gewone vraag: de bepaling staat met haar vindplaats in de tekst, zodat Lex haar in de
      // graaf terugvindt. Geen nieuw agentcontract.
      const plek = knoop.bwb_id && knoop.artikel
        ? ` (${knoop.bwb_id}, artikel ${knoop.artikel}${knoop.lid ? `, lid ${knoop.lid}` : ""})` : "";
      setOnderwerp(undefined);
      setInvoer(`Hoe hangt ${knoop.naam}${plek} samen met de bepalingen waarnaar het verwijst of die ernaar verwijzen?`);
      if (!breed) setSheetVerborgen(true);
      requestAnimationFrame(() => taRef.current?.focus());
    }} /> : (wgArtefact && (
    <WerkgebiedArtefactPaneel
      key={`${artefactSleutel(wgArtefact)}:${wgLading}`}
      doel={wgArtefact}
      onKlaar={paneelKaart && wgArtefact.soort === "bronselectie" && !bezig
        && wgArtefact.werkgebied_id === paneelKaart.intake_id.slice(3)
        ? (deelvraagId: string) => {
          if (deelvraagId !== paneelKaart.deelvraag_id) return;
          const a = klaarActie(paneelKaart);
          void verstuur({ prompt: antwoordTekst(paneelKaart, a), intake: a });
        } : undefined}
      klaarVoor={paneelKaart?.deelvraag_id}
      variant={breed ? "kolom" : "side"}
      bewaker={wgBewaker}
      onOnbewaard={setWgOnbewaard}
      onSluit={() => sluitPaneelTab(tabStand.actief)}
      onVerberg={verbergPaneel}
      onWissel={(d) => wisselPaneel(d)}
      onVerwijderd={(id) => { if (id === werkgebiedId) onVerlaatWerkgebied?.(); }}
    />
  ));

  /** Een context naast het gesprek (`ContextPaneelContext`): een bron uit een antwoord krijgt het werkgebied
   *  van het gesprek mee, zodat *Open volledige pagina* in dat werkgebied landt. */
  function openContext(d: ContextDoel) {
    const naar = d.soort === "bron" && !d.werkgebied_id && werkgebiedId ? { ...d, werkgebied_id: werkgebiedId } : d;
    setVolgendeVanuit("het gesprek");
    wisselPaneel(undefined, { ook: () => { setNodeDoel(undefined); setCtx(naar); } });
  }

  // Wat er in het paneel staat: iets anders openen klapt een ingeklapt zijpaneel uit.
  // De tabrij: in de balk van het zijpaneel, en op een telefoon boven de kop van de sheet (`PaneelTabsContext`).
  const tabRij = tabStand.tabs.length > 0 && (
    <TabRij label="Open in het paneel" active={tabStand.actief}
      tabs={tabStand.tabs.map((t) => { const l = tabLabel(t); return { key: t.sleutel, label: l.kort, title: l.vol, onSluit: () => sluitPaneelTab(t.sleutel) }; })}
      onChange={(k) => { const t = tabStand.tabs.find((x) => x.sleutel === k); if (t && k !== tabStand.actief) laad(t.inhoud); }} />
  );
  const paneel = ctx ? (
    <ContextPaneel key={contextSleutel(ctx)} doel={ctx} variant={breed ? "kolom" : "side"}
      onSluit={() => sluitPaneelTab(tabStand.actief)} onVerberg={verbergPaneel}
      onWissel={(d) => { setVolgendeVanuit("het paneel"); setCtx(d); }} onMaakWerkgebied={setWgUitOverzicht}
      onSamenhang={samenhangAan && !demo ? (iri) => acties.openSamenhang(bronDoel(iri) ?? { bron_iri: iri }) : undefined} />
  ) : artefact;

  /** *Vraag Lex* vanuit een object in een paneel (`VraagLexKnop`): de chip boven het invoerveld. Op een smal
   *  scherm ligt het paneel over de chat en sluit het – anders typ je in een veld dat je niet ziet. De
   *  focus in dezelfde gebeurtenis als de klik: iOS opent het toetsenbord alleen binnen een gebaar. */
  function kiesOnderwerp(o: Onderwerp) {
    setOnderwerp(o);
    setInvoer("");
    // Een open vraagkaart staat op de plek van het invoerveld: klap hem weg (niets beantwoord), anders zie je
    // de chip en de suggesties niet. *Een vraag stellen ›* haalt hem terug (spoor J: van deelvraag wisselen).
    if (open?.openId) setWeggeklikt(open.openId);
    if (!breed) wgBewaker.bewaak(() => setSheetVerborgen(true), "sluiten");
    taRef.current?.focus();
  }

  return (
    <VraagLexContext.Provider value={demo ? null : kiesOnderwerp}>
    <ContextPaneelContext.Provider value={demo ? null : openContext}>
    <div className="relative flex min-h-0 min-w-0 flex-1">
    <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
      {/* Beknopte statusmelding voor schermlezers (niet de hele thread live maken → geen token-spam). */}
      <p className="sr-only" aria-live="polite">
        {stopt ? "Bezig met stoppen; de agent rondt zijn huidige stap af." : bezig ? "Bezig met antwoorden…"
          : [beurtEinde, melding].filter(Boolean).join(" ")}
      </p>
      {/* Begroeting en silhouet: volledig in de lege werkplek, een smalle strook zodra er een gesprek
          loopt. Buiten de scroller, zodat alleen de thread scrolt. */}
      {/* In de rondleiding volledig: de eerste stap stelt Lex voor aan de hand van deze header. */}
      <WerkplekHeader compact={items.length > 0 && !demo} />
      {/* De annotatie blijft bereikbaar. De chip in de thread scrolt weg zodra het gesprek doorloopt;
          dan is er geen weg terug naar het werk waar je middenin zat. */}
      {wgUitOverzicht && (
        <WerkgebiedUitOverzicht overzicht={wgUitOverzicht} onSluit={() => setWgUitOverzicht(undefined)}
          onKlaar={(id, mislukt) => {
            setWgUitOverzicht(undefined);
            onKiesWerkgebied?.(id);
            setMelding("Werkgebied gemaakt.");
            setWgMelding(mislukt.length ? `Niet opgenomen (niet in de graaf of niet te verifiëren): ${mislukt.join(", ")}.` : null);
          }} />
      )}
      {wgMelding && (
        <div className="shrink-0 px-4 py-2">
          <Melding type="uitleg" compact>
            {wgMelding}{" "}
            <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => setWgMelding(null)}>
              Sluiten
            </button>
          </Melding>
        </div>
      )}
      {/* Op een telefoon: de sheet is verborgen (Escape, Vraag Lex) of er staan herstelde tabs klaar. Eén tik haalt hem terug. */}
      {!breed && !demo && tabStand.tabs.length > 0 && (sheetVerborgen || !huidig) && (
        <button type="button" data-paneel-terug
          onClick={() => {
            if (huidig) return setSheetVerborgen(false);
            const t = tabStand.tabs.find((x) => x.sleutel === tabStand.actief) ?? tabStand.tabs.at(-1);
            if (t) laad(t.inhoud);
          }}
          className="focus-ring flex w-full shrink-0 items-center gap-2 border-b border-line bg-surface px-4 py-2 text-left text-xs text-muted transition hover:bg-surface-2">
          <span className="truncate"><span className="font-medium text-ink">Paneel</span> · {tabStand.tabs.length === 1 ? "1 open" : `${tabStand.tabs.length} open`}</span>
          <span className="ml-auto shrink-0 font-medium text-lint">Openen</span>
        </button>
      )}
      {!nodeDoel && !wgArtefact && !ctx && laatsteWgArtefact && (
        <button
          type="button"
          onClick={() => wisselPaneel(laatsteWgArtefact)}
          className="focus-ring flex w-full shrink-0 items-center gap-2 border-b border-line bg-surface px-4 py-2 text-left text-xs text-muted transition hover:bg-surface-2"
        >
          <span className="truncate"><span className="font-medium text-ink">{laatsteKop?.titel}</span>{laatsteKop?.soort && <> · {laatsteKop.soort.toLowerCase()}</>}</span>
          <span className="ml-auto shrink-0 font-medium text-lint">Openen</span>
        </button>
      )}
      {!nodeDoel && !wgArtefact && !ctx && laatsteOverzicht && (
        <button
          type="button"
          onClick={() => openContext(overzichtContext(laatsteOverzicht))}
          data-testid="laatste-overzicht"
          className="focus-ring flex w-full shrink-0 items-center gap-2 border-b border-line bg-surface px-4 py-2 text-left text-xs text-muted transition hover:bg-surface-2"
        >
          <span className="truncate"><span className="font-medium text-ink">{laatsteOverzicht.gevraagd}</span> · overzicht</span>
          <span className="ml-auto shrink-0 font-medium text-lint">Openen</span>
        </button>
      )}
      {!nodeDoel && !wgArtefact && !ctx && laatsteNodeAnnotatie && (
        <button
          type="button"
          onClick={() => void openArtefact(laatsteNodeAnnotatie.slug, laatsteNodeAnnotatie.annotatie_doel)}
          className="focus-ring flex w-full shrink-0 items-center gap-2 border-b border-line bg-surface px-4 py-2 text-left text-xs text-muted transition hover:bg-surface-2"
        >
          <span className="truncate font-medium text-ink">{laatsteNodeAnnotatie.titel || "Laatste annotatie"}</span>
          <span className="ml-auto shrink-0 font-medium text-lint">Openen</span>
        </button>
      )}
      {hydratieFout && (
        <div className="shrink-0 px-4 pt-2">
          <Melding type={hydratieFout.weg ? "uitleg" : "fout"} compact>
            {hydratieFout.weg ? hydratieFout.melding : <>De eerdere berichten zijn niet geladen ({hydratieFout.melding}).</>}{" "}
            {!hydratieFout.weg && hydratieId && (
              <button
                type="button"
                onClick={() => hydrateer(hydratieId)}
                className="focus-ring rounded font-medium underline underline-offset-2"
              >
                Opnieuw proberen
              </button>
            )}
          </Melding>
        </div>
      )}

      {/* De verbinding met de lopende beurt is weg. Geen sluitknop: deze melding hóórt vanzelf te
          verdwijnen zodra de stroom weer loopt – dat is het hele punt. */}
      {verbindingWeg && (
        <div className="shrink-0 px-4 pt-2">
          <Melding type="waarschuwing" compact>
            De verbinding met Lex is weggevallen. Je vraag loopt gewoon door bij de agent; ik probeer
            opnieuw te verbinden…
          </Melding>
        </div>
      )}

      {/* De vraag is geweigerd omdat het budget op is. Kort houden: wanneer het weer kan staat al in
          de strook bovenaan het scherm én onder de invoerbalk – dezelfde datum drie keer noemen
          leest als een storing. Geen sluitknop: hij verdwijnt zodra je weer een vraag verstuurt. */}
      {/* Een gevraagde bron stond uit, en de jurist kan hem zelf aanzetten (ADR-013). Lex zei het al in het antwoord;
          dit is de knop erbij. */}
      {zelfAanTeZetten(bronUit, connectorStand).length > 0 && (
        <div className="shrink-0 px-4 pt-2" data-bron-uit>
          <Melding type="uitleg" compact>
            {zelfAanTeZetten(bronUit, connectorStand).map((b) => (
              <span key={b.naam} className="mr-3 inline-flex items-center gap-2">
                {b.label} staat uit.
                <button
                  type="button"
                  onClick={() => {
                    zetGesprekConnectors(wisselConnector(connectorStand, b.naam));
                    setBronUit((nu) => nu.filter((x) => x.naam !== b.naam));
                  }}
                  className="focus-ring rounded font-medium underline underline-offset-2"
                >
                  Zet {b.label} aan
                </button>
              </span>
            ))}
            Stel je vraag daarna opnieuw.
          </Melding>
        </div>
      )}

      {budgetGeweigerd && (
        <div className="shrink-0 px-4 pt-2">
          <Melding type="waarschuwing" compact>
            Je vraag is niet verstuurd: je tokenbudget is op.
          </Melding>
        </div>
      )}

      {/* Een herstart van de agent wist het run-register. Zeg dat, in plaats van een gesprek dat
          halverwege ophoudt zonder uitleg. */}
      {runVerdwenen && (
        <div className="shrink-0 px-4 pt-2">
          <Melding type="waarschuwing" compact>
            De vorige vraag is afgebroken doordat de agent opnieuw is opgestart. Stel hem gerust nog
            een keer.{" "}
            <button
              type="button"
              onClick={beurt.sluitRunVerdwenen}
              className="focus-ring rounded font-medium underline underline-offset-2"
            >
              Sluiten
            </button>
          </Melding>
        </div>
      )}

      {bewaarFout && (
        <div role="status" className="shrink-0 border-b border-fout/30 bg-fout/10 px-4 py-2 text-center text-[0.8125rem] text-fout">
          Dit gesprek wordt op dit moment niet bewaard ({bewaarFout}). Wat je hier ziet verdwijnt bij
          het herladen.
        </div>
      )}
      {/* Thread – enige scrollende gebied; berichten in een gecentreerde leeskolom */}
      <div data-tour="thread" ref={lijstRef} onScroll={onThreadScroll} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
          {/* De begroeting en wat Lex doet staan in de header (`WerkplekHeader`); die zin is de
              KORTE variant van het IDENTITEIT-blok in tools/graph-qa/agent/prompts.py – dezelfde
              kadering (hulpmiddel, de jurist beslist), minder woorden. Verander je de een, verander
              dan de ander mee. Op een smal scherm toont de header alleen de groet; daar staat de
              kadering hieronder. */}
          {items.length === 0 && (
            <div className="pt-[6dvh] text-center">
              <p className="mx-auto max-w-md text-sm text-muted md:hidden">
                {LEX_KORT}
              </p>
              {/* Wat je kunt vragen staat al in het invoerveld; hier geen tweede uitnodiging. */}
              {onRondleiding && (
                <div className="mt-5 md:mt-0">
                  <button
                    type="button"
                    onClick={onRondleiding}
                    className="focus-ring rounded-knop border border-lint/30 bg-lint/5 px-4 py-2 text-sm font-medium text-lint transition-colors hover:bg-lint/10"
                  >
                    Laat me de werkplek zien
                  </button>
                </div>
              )}
              <SuggestieRij className="mt-6">
                {VOORBEELDEN.map((v) => (
                  <Suggestie key={v} disabled={geblokkeerd} title={geblokkeerd ? "Je tokenbudget is op" : undefined}
                    onClick={() => void verstuur({ prompt: v })}>
                    {v}
                  </Suggestie>
                ))}
              </SuggestieRij>
            </div>
          )}

          {items.map((item, i) => verborgenItems.has(item.id) ? null : (
            // `thread-rij` laat de browser layout en paint overslaan voor beurten buiten beeld
            // (`content-visibility`, zie globals.css); de DOM blijft staan, dus zoeken, schermlezers
            // en het meescrollen blijven kloppen.
            <div key={item.id} className="thread-rij">
              <ThreadRij
                item={item}
                vragen={vraagGroepen.get(item.id)}
                keuze={keuzes.get(item.id)}
                // Alleen de laatste beurt kan aan het streamen zijn.
                streamt={bezig && i === items.length - 1}
                bezig={bezig}
                geblokkeerd={geblokkeerd}
                demo={!!demo}
                samenhangAan={samenhangAan}
                loopt={item.type === "reeks" && !!runId && runId === item.reeks.runId}
                acties={acties}
              />
            </div>
          ))}
        </div>
      </div>

      {/* "Naar beneden"-pil: verschijnt als je weg van de bodem scrolt (bv. tijdens streamen). */}
      {toonNaarBeneden && (
        <button
          type="button"
          onClick={naarBeneden}
          aria-label="Naar nieuwste bericht"
          className="absolute bottom-24 left-1/2 z-10 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-knop border border-line bg-paper text-lint shadow-kaart transition-colors hover:border-lint/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M12 5v14M19 12l-7 7-7-7" />
          </svg>
        </button>
      )}

      {/* Invoerbalk – gepind onderaan, gecentreerd, auto-groeiend */}
      <div className="shrink-0 bg-paper">
        <div className="mx-auto max-w-3xl px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2">
          {toonDock && open?.open && open.open.weergave === "paneel" ? (
            <BronselectieKaart key={open.openId} kaart={open.open} uitgeschakeld={geblokkeerd}
              onSluit={() => setWeggeklikt(open.openId ?? null)}
              onActie={(a) => void verstuur({ prompt: antwoordTekst(open.open!, a), intake: a })}
              onBeoordelen={() => { const doel = bronselectieVanKaart(open.open); if (doel) wisselPaneel(doel, { ook: () => setNodeDoel(undefined) }); }} />
          ) : toonDock && open?.open ? (
            <VraagDock key={open.openId} kaart={open.open} uitgeschakeld={geblokkeerd}
              onSluit={() => setWeggeklikt(open.openId ?? null)}
              onActie={(a) => void verstuur({ prompt: antwoordTekst(open.open!, a), intake: a })} />
          ) : (<>
          {/* Waar de volgende vraag over gaat. Zichtbaar zolang hij geldt, want anders stel je
              ongemerkt een adviesvraag over een element dat je allang niet meer voor je hebt. */}
          {/* De vragen die bij een markering hoe dan ook gesteld worden, als één klik. Een leeg veld
              met "Wat wil je weten over deze markering?" is een open vraag op het moment dat je juist
              snel wilt beoordelen. Ze verdwijnen zodra er een beurt loopt: een tweede vraag zou de
              eerste toch afgewezen krijgen (er loopt al een run op dit gesprek). */}
          {onderwerp && (
            <div className="mb-1.5 flex items-center gap-1.5" data-onderwerp={onderwerp.soort}>
              <StatusLabel toon="lint" rekbaar className="gap-1.5 py-1 font-normal">
                {onderwerp.soort === "markering" ? (
                  <span className={`shrink-0 rounded px-1 text-[0.7rem] ${jasStyle(onderwerp.element.klasse)}`}>
                    {klasseLabel(onderwerp.element.klasse)}
                  </span>
                ) : (
                  <span className="shrink-0 rounded bg-lint/10 px-1 text-[0.7rem] font-medium">{SOORT_LABEL[onderwerp.soort]}</span>
                )}
                <span className="truncate">{onderwerp.soort === "markering" ? `“${chipTekst(onderwerp)}”` : chipTekst(onderwerp)}</span>
                <button
                  type="button"
                  onClick={() => setOnderwerp(undefined)}
                  aria-label={onderwerp.soort === "markering" ? "Vraag niet aan deze markering koppelen"
                    : `Vraag niet aan deze ${SOORT_LABEL[onderwerp.soort].toLowerCase()} koppelen`}
                  className="focus-ring inline-flex min-h-[24px] min-w-[24px] shrink-0 items-center justify-center rounded-knop-xs p-0.5 hover:bg-lint/10 coarse:min-h-[44px] coarse:min-w-[44px]"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden>
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </StatusLabel>
            </div>
          )}
          {/* Wat Lex met het onderwerp kan; zonder onderwerp, in een werkgebied, wat hij met het werkgebied kan
              (F3d: dat waren de knoppen in de werkgebiedbalk). Die laatste wijken zodra je typt. */}
          {!bezig && suggesties.length > 0 && (
            // Eén rij die zijwaarts schuift: naast een paneel wordt de chat smal, en dan namen rijen suggesties de
            // leesruimte weg. De rand vervaagt, zodat je ziet dat er meer staat; de focus scrolt een knop in beeld.
            <div className="mb-1 flex gap-1.5 overflow-x-auto p-0.5 pb-1 pr-8 [mask-image:linear-gradient(to_right,black_calc(100%-2rem),transparent)]"
              data-testid="vraag-suggesties"
              data-suggesties-van={onderwerp?.soort ?? "werkgebied"}>
              {suggesties.map((s) => (
                <Suggestie
                  key={s.tekst}
                  klein
                  className="shrink-0 whitespace-nowrap"
                  disabled={geblokkeerd}
                  data-actie={s.actie}
                  data-invullen={s.invullen ? "" : undefined}
                  title={geblokkeerd ? "Je tokenbudget is op" : undefined}
                  onClick={() => {
                    // Een vraag die de analist afmaakt: in het veld, met de cursor aan het eind.
                    if (s.invullen) {
                      setInvoer(s.tekst);
                      taRef.current?.focus();
                      requestAnimationFrame(() => taRef.current?.setSelectionRange(s.tekst.length, s.tekst.length));
                      return;
                    }
                    void verstuur({ prompt: s.tekst, actie: s.actie });
                  }}
                >
                  {s.tekst}
                </Suggestie>
              ))}
            </div>
          )}
          {!demo && toonMenu(connectorStand) && (
            <div className="mb-1 flex min-w-0">
              <ConnectorsMenu stand={connectorStand} onWissel={kiesConnector} onOpen={verversAlsOnbekend}
                onOpnieuw={connectorLijst.ververs}
                onAlsStandaard={werkgebiedId ? () => void maakConnectorStandaard() : undefined}
                onTerugNaarStandaard={() => zetGesprekConnectors(null)} />
            </div>
          )}
          <div data-tour="invoer" className="flex items-end gap-2 rounded-bubbel border border-line bg-white px-2 py-1.5 shadow-zacht transition-shadow focus-within:border-lint focus-within:shadow-kaart">
            <textarea
              ref={taRef}
              // Een klaargezette vraag (`beginInvoer`) krijgt de focus, zodat één Enter volstaat.
              autoFocus={Boolean(beginInvoer)}
              value={invoer}
              onChange={(e) => setInvoer(e.target.value)}
              onKeyDown={opToets}
              rows={1}
              disabled={Boolean(demo) || geblokkeerd}
              placeholder={
                demo
                  ? "Tijdens de rondleiding staat het invoerveld stil"
                  : geblokkeerd
                    ? "Je tokenbudget is op"
                    : "Vraag of opdracht voor Lex…"
              }
              className="max-h-[200px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-ink placeholder:text-faint focus:outline-none"
            />
            {/* Tijdens het antwoorden is dit de stopknop: hetzelfde plekje, andere betekenis – je hoeft
                niet te zoeken waar je moet klikken om te onderbreken. */}
            <button
              type="button"
              onClick={() => (bezig ? void beurt.stop() : void verstuur())}
              disabled={Boolean(demo) || geblokkeerd || (!bezig && !invoer.trim()) || stopt}
              aria-label={bezig ? (stopt ? "Bezig met stoppen" : "Stoppen") : "Versturen"}
              title={stopt ? "De agent rondt zijn huidige stap nog af" : undefined}
              className="focus-ring inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-paper transition-colors hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-40"
            >
              {stopt ? (
                // Stoppen kan tientallen seconden duren (de agent rondt zijn stap af). Een knop die
                // er hetzelfde uitziet maar niet meer reageert, leest als kapot; deze draait zolang
                // het wachten duurt.
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="motion-safe:animate-spin" aria-hidden>
                  <path d="M12 3a9 9 0 1 0 9 9" strokeLinecap="round" />
                </svg>
              ) : bezig ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                  <rect x="5" y="5" width="14" height="14" rx="2" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              )}
            </button>
          </div>
          <p className="mt-2 text-center text-xs text-faint">
            {demo
              ? "Dit is een voorbeeld voor de rondleiding – er gaat niets naar de agent."
              : geblokkeerd && verbruik
                ? `Je tokenbudget is op. Je kunt weer verder op ${resetdatum(verbruik.reset_op)}.`
                : "De agent bevraagt de kennisgraaf – controleer altijd de bron."}
          </p>
          </>)}
        </div>
      </div>

      {/* Op een smal scherm schuift het artefact als overlay over de chat heen. */}
      {!breed && !sheetVerborgen && paneel && <PaneelTabsContext.Provider value={tabRij}>{paneel}</PaneelTabsContext.Provider>}
    </div>

    {/* Op een breed scherm staat het ernaast: chat en review tegelijk in beeld. */}
    {breed && paneel && <Zijpaneel label="Paneel" sleutel={String(openTeller)} hersteld={tabsHersteld} vast={Boolean(demo)} balk={tabRij}
      inklapSignaal={inklapSignaal}>{paneel}</Zijpaneel>}
    </div>
    </ContextPaneelContext.Provider>
    </VraagLexContext.Provider>
  );
}

/** De Vragen-kaarten van de thread. `ThreadRij` vergelijkt een groep op inhoud (zijn `memo`), dus een vers
 *  object per frame laat een kaart niet opnieuw renderen. */
function useStabieleGroepen(items: Item[], bezig: boolean) {
  return useMemo(() => groepeerVragen(
    items.map((x) => ({ id: x.id, type: x.type, tekst: "tekst" in x ? x.tekst : undefined,
      vraagkaart: x.type === "antwoord" ? x.vraagkaart : undefined,
      antwoordOp: x.type === "user" ? x.antwoordOp : undefined })),
    bezig,
  ), [items, bezig]);
}

const VOORBEELDEN = [
  "Wat betekent het begrip 'belastingschuldige'?",
  "annoteer artikel 9 lid 1 van de Invorderingswet 1990",
  "Welke artikelen gaan over invordering?",
];
