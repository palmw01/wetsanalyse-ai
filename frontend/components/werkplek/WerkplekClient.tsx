"use client";

import Link from "next/link";
import { NodeAnnotatiePaneel } from "@/components/annotaties/NodeAnnotatiePaneel";
import { samenhangBeschikbaar } from "@/lib/samenhang";
import { ThreadRij, type ThreadActies } from "@/components/werkplek/ThreadRij";
import { reeksNavigatie, reeksUitBerichten, verwerkReeksEvent, type Reeks } from "@/lib/reeks";
import { mergeToolExecution, toolSpoorUit, type NodeDoel, type ToolExecution, type NodeElement, type NodeWeergave } from "@/lib/annotatieNode";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { ArtefactPaneel } from "@/components/werkplek/ArtefactPaneel";
import { Melding } from "@/components/ui/Melding";
import {
  foutTekst,
  haalActieveRun,
  startRun,
  stopRun,
  volgRun,
  haalGesprek,
  maakGesprek,
  voegBerichtToe,
} from "@/lib/api";
import { resetdatum } from "@/lib/tokenbudget";
import type {
  Anker,
  AnnotatieElement,
  AgentDoel,
  AgentDoelInvoer,
  AgentHergebruik,
  AgentKandidaat,
  AgentKeuze,
  AnnotatieDocument,
  BeslissingInvoer,
  BeslissingType,
  Bron,
  GraafArtikel,
  Verbruiksstand,
  VoorstelElement,
} from "@/lib/types";
import {
  BESLIST_LIFECYCLES, doelInvoerVan,
  eigenMarkeringenVoorContext, isVerwijderd, kandidatenAlsTekst, mergeVoorstellen, vraagContextLabel,
  vraagContextVan, vraagSuggesties,
} from "@/lib/annotatie";
import {
  definitieveStroomfout, herstelWachttijd, leesLopendeRuns, naEenGebrokenStream, onthoudRun,
  schrijfLopendeRuns, standVanVorigeRun, vergeetRun, wachtMetWekker,
} from "@/lib/lopendeRun";
import { useBreedScherm } from "@/lib/useBreedScherm";
import { jasStyle } from "@/lib/jas";
import type { ThreadItem } from "@/lib/threadItem";
import { WerkplekHeader } from "./WerkplekHeader";
import { parseHergebruik } from "@/lib/agentEvents";
import {
  pasDemoBeslissingToe, voegDemoElementToe, wisDemoElement, zetDemoStatus, type DemoScene,
} from "@/lib/rondleidingDemo";

// De thread-items staan in `lib/threadItem.ts`, zodat de rondleiding er een voorbeeldbeurt
// mee kan opbouwen zonder dit component te importeren.
type Item = ThreadItem;

/** Wat er zojuist is vastgelegd, in één zin voor de schermlezer. */
function beslissingMelding(req: BeslissingInvoer): string {
  if (req.type === "approve") return "Akkoord bevonden.";
  if (req.type === "reject") return "Verworpen.";
  if (req.type === "comment") return "Opmerking opgeslagen.";
  const w = req.wijziging ?? {};
  if (w.klasse) return `Klasse gewijzigd naar ${w.klasse}.`;
  if (w.tekst) return `Fragment aangepast naar ${w.tekst}.`;
  if (w.toelichting !== undefined) return w.toelichting ? "Toelichting opgeslagen." : "Toelichting gewist.";
  return "Wijziging opgeslagen.";
}

/** Hoeveel elementen wachten nog op een oordeel? Zelfde regel als de reviewlijst. */
function teBeoordelen(doc: AnnotatieDocument): number {
  return doc.elementen.filter((el) => !BESLIST_LIFECYCLES.includes(el.lifecycle)).length;
}

function uid(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

/** Is dit een door onszelf afgebroken stream, of een echte fout? */
function isAfgebroken(e: unknown): boolean {
  return (e as Error)?.name === "AbortError";
}

// Opnieuw aanhaken bij een weggevallen verbinding gebeurt zolang dit venster leeft, met een
// oplopende wachttijd (`herstelWachttijd`) en een banner die zegt wat er aan de hand is. De regel
// zelf staat in `lib/lopendeRun.ts`; hier staat alleen wat het scherm ermee doet.
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
  /** Roept terug zodra een beurt is afgerond, zodat de stand meteen ververst. */
  onBeurtKlaar?: () => void;
  /** Start de rondleiding vanuit de lege staat – precies het moment waarop iemand hem nodig heeft. */
  onRondleiding?: () => void;
}

export function WerkplekClient({
  initialGesprekId, onGesprekAangemaakt, onGewijzigd, demo, onDemoBeslissing,
  onDemoArtefact, demoOpenSignaal = 0, demoSluitSignaal = 0, onRondleiding,
  verbruik = null, onBeurtKlaar,
}: Props) {
  // Budget op? Dan gaat de invoer dicht. Alleen bij een actieve begrenzing – staat die uit, dan is
  // `geblokkeerd` per definitie false en verandert er niets.
  const geblokkeerd = Boolean(verbruik?.actief && verbruik.geblokkeerd);
  const [gesprekId, setGesprekId] = useState<string | null>(initialGesprekId);
  const [items, setItems] = useState<Item[]>(demo?.items ?? []);
  const [docs, setDocs] = useState<Record<string, AnnotatieDocument>>(demo?.docs ?? {});
  const [infos] = useState<Record<string, GraafArtikel>>(demo?.infos ?? {});
  // Slugs waarvan de api 404 gaf: het document bestaat niet meer. Dat is een tóéstand, geen fout —
  // opnieuw proberen kan per definitie niet lukken. Apart van `docs` omdat "nog niet geladen" en
  // "bestaat niet meer" twee verschillende dingen zijn.
  const [verwijderd, setVerwijderd] = useState<Record<string, true>>({});
  const [invoer, setInvoer] = useState("");
  // Niet-blokkerende melding als het opslaan van een beurt faalt (de chat loopt door).
  const [bewaarFout, setBewaarFout] = useState<string | null>(null);
  // De vraag is geweigerd omdat het tokenbudget op is. Apart van `bewaarFout`: die zegt dat het
  // gesprek niet bewaard wordt, en dat is hier onwaar – er is alleen niets verstuurd.
  const [budgetGeweigerd, setBudgetGeweigerd] = useState(false);
  const [bezig, setBezig] = useState(false);
  const [actiefId, setActiefId] = useState<string | undefined>();
  const [nodeDoel, setNodeDoel] = useState<NodeDoel>();
  /** De reeks (run-id) waaruit de open annotatie is geopend; het paneel bladert dan door de leden. */
  const [nodeReeks, setNodeReeks] = useState<string>();
  // Opent het node-paneel op de 3D-graaf (knop onder een antwoord) of op de tekst (annotatie).
  const [nodeTab, setNodeTab] = useState<"tekst" | "graaf">("tekst");
  const [samenhangAan, setSamenhangAan] = useState(false);
  useEffect(() => { void samenhangBeschikbaar().then(setSamenhangAan); }, []);
  const [nodeVraag, setNodeVraag] = useState<{ element: NodeElement; view: NodeWeergave }>();
  const [artefactSlug, setArtefactSlug] = useState<string | undefined>();
  // Zichtbaarheid van de "naar beneden"-pil: aan zodra de gebruiker weg van de bodem scrolt.
  const [toonNaarBeneden, setToonNaarBeneden] = useState(false);
  // Wat er zojuist is opgeslagen, voor schermlezers. Zonder dit gebeurt elke annotatie-wijziging
  // volledig stil: de kaart verandert visueel, maar er wordt niets aangekondigd.
  const [melding, setMelding] = useState("");
  // Waar de volgende vraag over gaat, gezet vanuit een reviewkaart. Zolang dit staat gaat de beurt
  // als adviesvraag (met contextblok) in plaats van als gewone vraag.
  const [vraagOver, setVraagOver] = useState<{ slug: string; el: AnnotatieElement } | null>(null);
  // De run die nu loopt. Die leeft bij de agent, niet in dit venster: dit id is waarmee we
  // aanhaken en waarmee de stopknop hem beëindigt.
  const [runId, setRunId] = useState<string | null>(null);
  // Stoppen is gevraagd maar nog niet gebeurd. De agent-nodes zijn synchroon, dus een lopende
  // LLM-call maakt zichzelf af – dat kan tientallen seconden duren en de knop hoort dat te tonen
  // in plaats van te doen alsof het al klaar is.
  const [stopt, setStopt] = useState(false);
  // Zojuist geprobeerd te openen, maar de annotatie bestaat niet meer. Geen storing: geen rode balk
  // en geen retry.
  const [artefactWeg, setArtefactWeg] = useState<string | null>(null);
  // De vorige beurt van dit gesprek is nooit afgekomen: het run-register van de agent is leeg (een
  // herstart of deploy). Beter dit zeggen dan een gesprek dat halverwege ophoudt zonder uitleg.
  const [runVerdwenen, setRunVerdwenen] = useState(false);
  // De verbinding met de lopende beurt is weg en we haken opnieuw aan. Een tóéstand en geen tekst in
  // de antwoordbubbel: alleen zo kan de melding vanzelf verdwijnen zodra de stroom weer loopt, in
  // plaats van te blijven staan tot je herlaadt.
  const [verbindingWeg, setVerbindingWeg] = useState(false);
  const lijstRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  // Synchrone guard tegen dubbel-verzenden (twee Enters in dezelfde tick): de `bezig`-state komt te laat
  // – vóór de eerste `await` (maakGesprek) is die nog false, wat twee gesprekken zou aanmaken.
  const bezigRef = useRef(false);
  // Waarmee een lopende beurt is af te breken. Een annotatie duurt tot ~90 seconden; zonder dit is
  // een verkeerd gestelde vraag anderhalve minuut wachten.
  const afbrekenRef = useRef<AbortController | null>(null);
  // "Stick-to-bottom": alleen automatisch meescrollen als de gebruiker al onderaan staat, zodat
  // omhoogscrollen tijdens het streamen niet telkens wordt teruggetrokken.
  const stickRef = useRef(true);
  // Leeft dit venster nog? De unmount-cleanup aborteert `afbrekenRef`, maar een aanhaakactie die ná
  // die cleanup zijn controller zet, wordt door niets meer opgeruimd – en laat dan een SSE-stroom
  // open staan voor een scherm dat niemand ziet.
  const levendRef = useRef(true);
  // Past het artefact naast de chat? Dan wordt het een eigen kolom in plaats van een overlay, en
  // blijft Lex bereikbaar tijdens het reviewen.
  const breed = useBreedScherm();

  // Verdwijnt dit venster (van gesprek wisselen remount het component), dan koppelen we alleen de
  // KIJKER los. De run zelf draait bij de agent door en wordt opgepakt zodra je terugkomt.
  //
  // Geen `abort()` op de beurt zelf: dan breekt van gesprek wisselen, naar het annotatie-overzicht
  // lopen of herladen het antwoord af waar je op wacht. Stoppen is een expliciete handeling
  // (`stop()`), geen bijwerking van navigeren.
  useEffect(() => {
    levendRef.current = true;
    return () => {
      levendRef.current = false;
      afbrekenRef.current?.abort();
    };
  }, []);

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
    const geldt = () => levendRef.current && poging === hydratiePoging.current;
    haalGesprek(id)
      .then((g) => {
        if (!geldt()) return;
        // De berichten van één reeks (zelfde `reeks.run_id`) worden weer één reeksblok.
        const reeksen = new Map<string, typeof g.berichten>();
        for (const b of g.berichten) if (b.reeks) reeksen.set(b.reeks.run_id, [...(reeksen.get(b.reeks.run_id) ?? []), b]);
        const geschiedenis = g.berichten.flatMap((b): Item[] => {
          if (b.reeks) {
            const groep = reeksen.get(b.reeks.run_id) ?? [];
            const reeks = groep[0] === b ? reeksUitBerichten(groep) : null;
            return reeks ? [{ id: uid(), type: "reeks", reeks }] : [];
          }
          return [b.rol === "user"
            ? { id: uid(), type: "user" as const, tekst: b.tekst }
            : b.annotatie_slug || b.annotatie_doel
              ? { id: uid(), type: "annotatie" as const, slug: b.annotatie_slug || b.annotatie_doel!.bron_iri,
                  titel: b.annotatie_doel?.label || b.annotatie_titel || undefined, annotatie_doel: b.annotatie_doel,
                  tool_executions: toolSpoorUit(b.tool_executions), denk: b.denk,
                  // De samenvatting van Lex (hoogstens vier zinnen), zoals graph-qa hem bewaarde.
                  tekst: b.tekst?.trim() || undefined,
                  // Na herladen moet nog te zien zijn dat er niets opnieuw is bekeken.
                  hergebruik: b.hergebruik ? parseHergebruik(b.hergebruik) : undefined }
              : { id: uid(), type: "antwoord" as const, tekst: b.tekst, denk: b.denk, bronnen: b.bronnen, tool_executions: toolSpoorUit(b.tool_executions) }];
        });
        // VÓÓR wat er al staat, niet in plaats daarvan. Verstuurde de jurist een vraag terwijl dit nog
        // laadde (een koude start duurt seconden), dan staan zijn vraag en het lopende antwoord al in
        // de thread – vervangen liet het antwoord onzichtbaar binnenstromen tot een herlaadbeurt.
        setItems((xs) => [...geschiedenis, ...xs]);
        // Een bericht met alleen een slug en geen bronnode verwijst naar een annotatie die niet meer
        // bestaat: de kaart wordt een tombstone.
        const weg = g.berichten.filter((b) => b.annotatie_slug && !b.annotatie_doel);
        if (weg.length) setVerwijderd((m) => ({ ...m, ...Object.fromEntries(weg.map((b) => [b.annotatie_slug!, true as const])) }));
        // Liep hier nog een beurt terwijl je ergens anders keek? Pak hem weer op. De run-ids uit de
        // geschiedenis gaan mee: daarmee is "afgerond terwijl je weg was" te onderscheiden van
        // "weg door een herstart".
        // Een reeks bewaart per onderdeel een bericht met run_id `<run>.<n>`; het run-id van de
        // reeks zelf staat in `reeks.run_id`. Zonder dat telde een afgeronde reeks als verdwenen.
        void hervatBeurt(id, g.berichten.flatMap((b) => [b.run_id, b.reeks?.run_id ?? ""]).filter(Boolean));
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
    // unmount loopt via `levendRef`.
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

  // Auto-groeiende textarea (groeit met de inhoud tot een max; daarna intern scrollen).
  useLayoutEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "0px";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [invoer]);

  function updateItem(id: string, patch: Partial<Item>) {
    setItems((xs) => xs.map((x) => (x.id === id ? ({ ...x, ...patch } as Item) : x)));
  }

  useEffect(() => {
    if (!demo || demoOpenSignaal === 0) return;
    const slug = Object.keys(demo.docs)[0];
    if (slug) void openArtefact(slug);
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
    setArtefactSlug(undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoSluitSignaal]);

  // De rondleiding wacht met haar reviewstappen tot het paneel er echt is.
  useEffect(() => {
    onDemoArtefact?.(Boolean(artefactSlug));
    // Alleen bij een echte wisseling van het paneel melden. `onDemoArtefact` is een inline callback
    // van de rondleiding en dus elke render een andere referentie; in de dependencies zou dit
    // effect bij iedere render opnieuw vuren.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [artefactSlug]);

  // Het laatst gevraagde artefact. Opent de jurist A (traag) en dan B, dan mag A bij het binnenkomen
  // B niet meer verdringen.
  const gevraagdArtefact = useRef<string | null>(null);

  async function openArtefact(slug: string, doel?: NodeDoel) {
    gevraagdArtefact.current = slug;
    if (doel?.bron_iri) { setArtefactSlug(undefined); setNodeTab("tekst"); setNodeDoel(doel); return; }
    setNodeDoel(undefined);
    // Zonder bronnode is er alleen het document van de rondleiding, dat al in het geheugen staat.
    // Elk ander slug-only bericht verwijst naar een annotatie die niet meer bestaat.
    if (docs[slug] && infos[slug]) {
      setArtefactWeg(null);
      setArtefactSlug(slug);
      return;
    }
    setVerwijderd((m) => ({ ...m, [slug]: true }));
    setArtefactWeg(slug);
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

  /** @param doel de bepaling, als die al vaststaat (zie `startRun`).
   *  @param hergebruik "opnieuw" = de jurist vraagt expliciet om een nieuwe ronde op een al
   *    geannoteerd artikel; zonder doel betekent dat niets (de agent weet dan nog niet welk). */
  async function verstuur(vast?: string, doel?: AgentDoelInvoer, hergebruik?: "opnieuw", doelen?: AgentDoelInvoer[]) {
    // In de rondleiding is dit venster een voorbeeld: er gaat niets naar de agent. De invoerbalk is
    // ook uitgeschakeld, dit is het vangnet voor Enter en de voorbeeldknoppen.
    if (demo) return;
    // Budget op: geen enkele weg naar een nieuwe beurt. De knoppen zijn ook uitgeschakeld, maar dat
    // is de zichtbare helft — dit is de sluitende. De eerste versie schermde alleen de verzendknop
    // af, en toen bleven de voorbeeldvragen, de kandidatenlijst en het beginscherm gewoon open.
    if (geblokkeerd) return;
    const prompt = (vast ?? invoer).trim();
    if (!prompt || bezigRef.current) return;
    bezigRef.current = true;
    setInvoer("");

    // Een vraag bij een markering gaat als ADVIES: dezelfde thread, maar met contextblok en langs de
    // antwoordroute – die kan topologisch geen annotatie wijzigen.
    const context = vraagOver;
    const nodeContext = nodeVraag;
    setNodeVraag(undefined);
    setVraagOver(null);
    const contextLabel = nodeContext ? `${nodeContext.view.doel.label}: ${nodeContext.element.tekst}` : context ? vraagContextLabel(context.el, docs[context.slug]) : "";
    // Vangnet: het paneel gaat al dicht zodra je "Vraag Lex" aanklikt, maar je kunt het intussen
    // opnieuw hebben geopend. Dan wint het antwoord – dat wil je zien binnenkomen.
    if (context && !breed) setArtefactSlug(undefined);

    // Toon de user-bubbel + antwoord-placeholder OPTIMISTISCH, vóór het (bij een nieuw gesprek) awaiten
    // van maakGesprek – anders "verdwijnt" het bericht tijdens die round-trip.
    const antId = uid();
    // Het id van de user-bubbel vasthouden: moet de beurt worden teruggedraaid (er liep er al een),
    // dan halen we precies déze weg. Filteren op de tekst zou een eerdere, identieke vraag treffen.
    const vraagId = uid();
    setItems((xs) => [
      ...xs,
      { id: vraagId, type: "user", tekst: prompt, over: contextLabel || undefined },
      { id: antId, type: "antwoord", tekst: "" },
    ]);
    setBezig(true);
    stickRef.current = true; // een nieuwe beurt springt altijd naar de bodem
    // Meldingen over de vórige beurt horen niet bij deze. `runVerdwenen` had geen enkele weg terug
    // behalve een herlaadbeurt, en bleef dus staan terwijl je alweer een vraag stelde.
    setRunVerdwenen(false);
    setVerbindingWeg(false);
    setBudgetGeweigerd(false);

    // Zorg voor een gesprek-id (maak er bij de eerste beurt één aan; titel = de vraag, afgekapt).
    let gid = gesprekId;
    if (!gid) {
      try {
        const g = await maakGesprek(prompt.slice(0, 80));
        gid = g.id;
        setGesprekId(gid);
        onGesprekAangemaakt(gid);
      } catch (e) {
        updateItem(antId, { tekst: `**Er ging iets mis.** ${foutTekst(e)}` });
        setBezig(false);
        bezigRef.current = false;
        return;
      }
    }

    // De chip is UI-state en reist niet mee naar de api; zonder deze regel leest een herladen gesprek
    // als een losse vraag zonder onderwerp.
    //
    // Bewust GEAWAIT: de vraag moet vastliggen vóórdat de run begint. De volgorde in de thread is de
    // autoincrement-id, dus een snelle beurt zou anders vóór zijn eigen vraag kunnen landen – en bij
    // het aanhaken na een herlaadbeurt is deze regel de user-bubbel waar het antwoord onder hoort.
    await persisteer(gid, "user", { tekst: contextLabel ? `Bij ${contextLabel}: ${prompt}` : prompt });

    // Markeringen die de jurist al maakte gaan mee als context (`bestaande_elementen`). De agent kan
    // niet zelf in het document kijken – dat leeft in de api. Alleen de bepaling die nú open staat:
    // de agent leest ze tegen de tekst die hij zelf ophaalt, dus markeringen uit een ander artikel
    // kan hij daar per definitie niet in terugvinden.
    const reedsEigen = eigenMarkeringenVoorContext(artefactSlug ? docs[artefactSlug] : undefined);
    const basis = nodeContext ? { modus: "advies" as const, context: {
      bron_iri: nodeContext.element.eigenaar_iri, snapshot_id: nodeContext.view.snapshot_id,
      bwbId: nodeContext.view.doel.bwb_id, artikel: nodeContext.view.doel.artikel, lid: nodeContext.view.doel.lid,
      element_id: nodeContext.element.id, klasse: nodeContext.element.klasse, fragment: nodeContext.element.tekst,
      corpus: nodeContext.view.segmenten.map((s) => s.tekst).join("\n\n"),
    } } : context
      ? {
          modus: "advies" as const,
          context: vraagContextVan(context.slug, docs[context.slug], infos[context.slug], context.el),
        }
      : reedsEigen.length
        ? { context: { bestaande_elementen: reedsEigen } }
        : undefined;
    // Een adviesvraag draagt nooit een doel: die route annoteert niet.
    const extra = doelen?.length && !context && !nodeContext
      // Meerdere onderdelen van één artikel: één run, elk onderdeel een eigen laag.
      ? { ...basis, doelen }
      : doel && !context && !nodeContext ? { ...basis, doel, ...(hergebruik ? { hergebruik } : {}) } : basis;

    let gestart;
    try {
      gestart = await startRun(prompt, gid, extra);
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
        await volgBeurt({ runId: lopend, gid, antId: hervatId, vanaf: 0 });
        return;
      }
      // Het tokenbudget is op. Net als bij een lopende beurt hierboven: deze vraag is NIET
      // aangenomen, dus geen mislukte antwoordbubbel laten staan maar de vraag teruggeven. En de
      // verbruiksstand meteen ophalen – dit pad komt nooit bij `volgBeurt`, dus zonder deze
      // aanroep blijven de strook en de dichte invoerbalk tot een minuut achterlopen. Precies
      // daardoor kón deze vraag überhaupt nog verstuurd worden.
      if ((e as { budgetOp?: true }).budgetOp) {
        // Alleen de lege ANTWOORDbubbel weg; de vraag blijft staan. Die is namelijk al opgeslagen –
        // `persisteer(…, "user", …)` draait vóór `startRun` – dus hem uit beeld halen zou hem bij
        // een herlaadbeurt gewoon laten terugkomen. Wat je ziet klopt zo met wat er bewaard is.
        setItems((xs) => xs.filter((x) => x.id !== antId));
        setBudgetGeweigerd(true);
        onBeurtKlaar?.();
        setBezig(false);
        bezigRef.current = false;
        return;
      }
      // De vraag is al bewaard; de foutmelding gaat er als antwoord bij. Anders stond er na een
      // herlaadbeurt een vraag zonder enig antwoord, en leek het alsof hij nog liep.
      const fout = `**Er ging iets mis.** ${foutTekst(e)}`;
      updateItem(antId, { tekst: fout });
      void persisteer(gid, "assistant", { tekst: fout });
      setBezig(false);
      bezigRef.current = false;
      return;
    }

    // Onthoud dát er een beurt liep. Komt de agent tussentijds opnieuw op, dan is dit het enige
    // spoor waarmee de werkplek kan zeggen wat er gebeurd is.
    schrijfLopendeRuns(onthoudRun(leesLopendeRuns(), gid, gestart.run_id));
    await volgBeurt({ runId: gestart.run_id, gid, antId });
  }

  /** Haak aan bij een run en verwerk hem tot het eind: verzamelen wat binnenkomt, en vastleggen wat
   *  eruit komt.
   *
   *  Eén functie voor twee ingangen – een verse beurt (`verstuur`) en het weer oppakken van een
   *  beurt die doorliep terwijl je ergens anders keek (`hervatBeurt`). Dat moet dezelfde code zijn,
   *  anders lopen de twee paden uit elkaar op precies het moment dat het ertoe doet.
   */
  async function volgBeurt({
    runId: id, gid, antId, vanaf = 0, herstel = 0,
  }: { runId: string; gid: string; antId: string; vanaf?: number; herstel?: number }) {
    // Het venster is tussen het besluit en dit moment verdwenen: niet alsnog aanhaken. De run zelf
    // loopt gewoon door bij de agent.
    if (!levendRef.current) return;
    const beheerser = new AbortController();
    afbrekenRef.current = beheerser;
    setRunId(id);
    bezigRef.current = true;
    setBezig(true);

    const doelRef: { d: AgentDoel | null } = { d: null };
    // Ontdubbeld verzamelen: komt hetzelfde element twee keer binnen, dan wint de laatste versie.
    let els: VoorstelElement[] = [];
    let kandidaten: AgentKandidaat[] = [];
    let keuze: AgentKeuze | undefined;
    // Een reeks (meerdere onderdelen in één run): de stroom wordt per onderdeel ingedeeld.
    let reeks: Reeks | null = null;
    let hergebruik: AgentHergebruik | undefined;
    let tekst = "";
    let denk = "";
    let bronnen: Bron[] = [];
    // Heeft de agent de beurt zelf vastgelegd? Dan schrijft de werkplek niets meer weg – anders
    // staat alles er twee keer. Blijft dit leeg, dan legt de client het bericht zelf vast; zo werkt
    // een graph-qa zonder api-koppeling gewoon door.
    let opgeslagen: { annotatie_slug: string; run_id: string; annotatie_doel?: NodeDoel } | null = null;
    let toolExecutions: ToolExecution[] = [];
    // De verbinding viel weg terwijl de run doorliep. Buiten de `try` gezet omdat het opnieuw
    // aanhaken ná de `finally` moet gebeuren: die reset `bezig`/`afbrekenRef`, en een nieuwe lus
    // die daarvóór begint raakt zijn eigen beheerser kwijt.
    let verbroken = false;
    // Kwam er iets over déze verbinding binnen? Zo ja, dan telt een volgende breuk als een verse
    // onderbreking en begint de wachttijd weer onderaan – anders zou een lange beurt met twee losse
    // dips in de hoogste backoff blijven hangen.
    let ontving = false;
    // De stroom zelf is afgelopen; wat daarna misgaat (het document of de wettekst ophalen) is geen
    // verbroken verbinding. Zonder dit onderscheid speelde een mislukte graaf-call na een geslaagde
    // beurt de hele run eindeloos opnieuw af onder "De verbinding met Lex is weggevallen".
    let stroomKlaar = false;
    // Tokens en denkregels komen tientallen keren per seconde binnen. Elke keer de thread bijwerken
    // renderde het hele gesprek per token; nu hooguit één keer per frame. Voor elke andere
    // bijwerking van dit item wordt de wachtende stand eerst weggeschreven (`schrijfStroom`), zodat
    // er nooit een oudere tekst overheen komt.
    let frame = 0;
    const schrijfStroom = () => {
      if (!frame) return;
      cancelAnimationFrame(frame);
      frame = 0;
      updateItem(antId, { tekst, denk });
    };
    const planStroom = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        updateItem(antId, { tekst, denk });
      });
    };
    try {
      await volgRun(
        id,
        {
          onLeeft: () => {
            ontving = true;
            setVerbindingWeg(false);
            // Er ís weer contact met een lopende beurt; een eerdere "de agent is herstart"-melding
            // slaat nu nergens meer op.
            setRunVerdwenen(false);
          },
          onStatus: (m) => {
            denk += (denk ? "\n" : "") + "· " + m;
            planStroom();
          },
          onReason: (t) => {
            denk += t;
            planStroom();
          },
          onToken: (t) => {
            tekst += t;
            planStroom();
          },
          onSources: (b) => {
            bronnen = b;
            updateItem(antId, { bronnen: b });
          },
          onGrounding: (g) => updateItem(antId, { grounding: g }),
          onToolExecution: (event) => {
            toolExecutions = mergeToolExecution(toolExecutions, event);
            updateItem(antId, { tool_executions: toolExecutions });
          },
          onDoel: (d) => (doelRef.d = d),
          onElement: (e) => (els = mergeVoorstellen(els, e)),
          onKandidaten: (k, kz) => { kandidaten = k; keuze = kz; },
          onReeksEvent: (ev) => {
            schrijfStroom();
            const volgende = verwerkReeksEvent(reeks, ev);
            if (!volgende || volgende === reeks) return;
            reeks = volgende;
            const r = volgende;
            setItems((xs) => xs.map((x) => (x.id === antId ? { id: antId, type: "reeks", reeks: r, tekst } : x)));
          },
          onHergebruik: (h) => (hergebruik = h),
          // De eventlog van de run is gecapt: er is narratie weggevallen. Benoem dat, in plaats van
          // een tekst te tonen die compleet lijkt maar het niet is.
          // Er viel narratie weg doordat de eventlog gecapt is. Zet de markering in het spoor waar
          // hij hoort: stond er al antwoordtekst, dan is die mogelijk onvolledig; anders raakte het
          // alleen het denkproces en zou een "…" in het antwoord een gat suggereren dat er niet is.
          onGat: () => {
            schrijfStroom();
            if (tekst) {
              tekst += "\n\n…\n\n";
              updateItem(antId, { tekst });
            } else {
              denk += (denk ? "\n" : "") + "· (een deel van het spoor is niet bewaard)";
              updateItem(antId, { denk });
            }
          },
          onOpgeslagen: (uitkomst) => (opgeslagen = uitkomst),
          onWaarschuwing: (bericht) => setMelding(bericht),
        },
        vanaf,
        beheerser.signal,
      );
      schrijfStroom();
      stroomKlaar = true;
      // De stroom liep tot het einde: deze beurt is afgerond en het spoor mag weg. Bij loskoppelen
      // komen we hier niet (dat gooit een AbortError), en dan blijft het spoor terecht staan.
      vergeetLopendeRun(gid);

      // Kandidaten EERST: dit is een keuzelijst in de thread, geen uitkomst die is vastgelegd.
      // Stond deze tak onder de `opgeslagen`-check, dan sneed die hem af zodra graph-qa zelf ging
      // wegschrijven – en verdween de keuzelijst stilzwijgend uit beeld.
      // Een reeks legt zichzelf per onderdeel vast (graph-qa); het blok staat al in beeld.
      if (reeks) {
        onGewijzigd();
        return;
      }
      if (kandidaten.length) {
        setItems((xs) =>
          xs.map((x) => (x.id === antId ? { id: antId, type: "kandidaten", tekst, kandidaten, ...(keuze ? { keuze } : {}) } : x)),
        );
        // Alleen de tekst overleeft een herlaadbeurt: de kandidaten zitten niet in het
        // berichtcontract van de api. Beter een leesbare opsomming dan "ik vond 5 bepalingen".
        // Heeft de agent de beurt al vastgelegd, dan schrijft de client niets meer – anders stond
        // de opsomming er twee keer.
        if (!opgeslagen) {
          void persisteer(gid, "assistant", { tekst: kandidatenAlsTekst(tekst, kandidaten), denk, run_id: id, tool_executions: toolExecutions });
        }
        onGewijzigd();
        return;
      }

      // De agent heeft het vastgelegd. Nu alleen nog tonen wat er staat – de api is de bron.
      if (opgeslagen) {
        await toonVastgelegdeBeurt(opgeslagen, {
          antId, tekst, denk, hergebruik, doel: doelInvoerVan(doelRef.d), tool_executions: toolExecutions,
        });
        onGewijzigd();
        return;
      }

      const doel = doelRef.d;
      if (doel && doel.bwbId && els.length) {
        // De agent had dit moeten vastleggen (`agent/beurt.py`) en deed dat niet: geen
        // `opgeslagen`-event terwijl er wél markeringen waren. Dat is een storing en die tonen we
        // als storing.
        //
        // De werkplek schrijft het hier niet zelf weg. Dat zou een tweede, volledige implementatie
        // van dezelfde handeling zijn – mét eigen artikelophaling en eigen titelopbouw – en welke
        // van de twee liep, hing dan af van de aan/afwezigheid van één SSE-event. Bij een
        // gedeeltelijk falen levert dat een tweede document op. Eén schrijver, en die is de agent.
        const melding =
          "**Deze beurt is niet vastgelegd.** De markeringen zijn wel voorgesteld, maar niet " +
          "opgeslagen. Stel de vraag opnieuw; blijft het gebeuren, meld het dan.";
        updateItem(antId, { tekst: melding, denk });
        void persisteer(gid, "assistant", { tekst: melding, denk, run_id: id, tool_executions: toolExecutions });
      } else {
        if (!tekst.trim()) updateItem(antId, { tekst: "(geen antwoord)" });
        // `run_id` maakt dit bericht idempotent: kijken er twee tabbladen mee, dan landt de
        // uitkomst van deze run toch maar één keer.
        void persisteer(gid, "assistant", { tekst: tekst.trim() || "(geen antwoord)", denk, bronnen, run_id: id, tool_executions: toolExecutions });
      }
      onGewijzigd();
    } catch (e) {
      // Een half frame met oudere tekst mag de foutmelding of het herstel niet overschrijven.
      cancelAnimationFrame(frame);
      frame = 0;
      if (stroomKlaar) {
        // De beurt zelf is rond; alleen de naverwerking faalde. Niet opnieuw aanhaken – dat speelt
        // dezelfde afloop nog eens af – maar zeggen wat er mis is, bij het antwoord.
        setVerbindingWeg(false);
        setMelding(foutTekst(e));
        return;
      }
      // Losgekoppeld is géén fout en géén einde: de run draait door bij de agent en wordt opgepakt
      // zodra dit venster terugkomt. Niets bewaren dus – het definitieve antwoord komt later.
      // Een wegvallende verbinding is óók geen einde: de beurt is van de server. Zie
      // `naEenGebrokenStream` voor de regel en waarom hij bestaat.
      const besluit = naEenGebrokenStream(
        isAfgebroken(e), levendRef.current, definitieveStroomfout(e),
      );
      if (besluit === "negeren") {
        // Zelf losgekoppeld (stopknop, van gesprek wisselen): er valt niets meer te herstellen, dus
        // ook geen melding daarover laten staan.
        setVerbindingWeg(false);
        return;
      }
      verbroken = besluit === "opnieuw";
      // Bij een herkansing blijft de bubbel staan zoals hij is: het heraanhaken speelt de eventlog
      // opnieuw af, dus de tekst wordt zo meteen alsnog opgebouwd. Wat er aan de hand is staat in de
      // banner – die verdwijnt vanzelf zodra er weer iets binnenkomt.
      setVerbindingWeg(verbroken);
      if (!verbroken) updateItem(antId, { tekst: `**Er ging iets mis.** ${foutTekst(e)}` });
    } finally {
      afbrekenRef.current = null;
      setRunId(null);
      setStopt(false);
      setBezig(false);
      bezigRef.current = false;
      // De beurt is klaar (geslaagd of niet): het verbruik is hoe dan ook opgelopen, dus de meter
      // hoort nu bij te zijn en niet pas bij het volgende minuut-interval.
      onBeurtKlaar?.();
    }

    if (verbroken && levendRef.current) {
      // Even wachten: valt de verbinding weg doordat de dienst opnieuw opstart, dan is meteen
      // opnieuw proberen gegarandeerd weer mis. De wachttijd loopt op, maar wordt gewekt zodra het
      // netwerk terug is of het tabblad weer in beeld komt. `vanaf: 0` speelt de hele eventlog
      // terug, dus wat er tijdens de onderbreking gebeurde komt alsnog in beeld – inclusief het
      // `opgeslagen`-event.
      const doorgaan = await wachtMetWekker(
        herstelWachttijd(herstel), () => levendRef.current,
      );
      if (!doorgaan) return;
      await volgBeurt({ runId: id, gid, antId, vanaf: 0, herstel: ontving ? 0 : herstel + 1 });
    }
  }

  /** De beurt is afgerond (of afgebroken); het spoor mag weg. */
  function vergeetLopendeRun(gid: string) {
    schrijfLopendeRuns(vergeetRun(leesLopendeRuns(), gid));
  }

  /** De agent heeft de beurt al weggeschreven; haal op wat er staat en toon het.
   *
   *  Bewust ophalen in plaats van de inhoud in het SSE-contract te proppen: dan blijft de api de ene
   *  bron van waarheid en groeit het eventcontract niet mee met het datamodel.
   */
  async function toonVastgelegdeBeurt(
    uitkomst: { annotatie_slug: string; annotatie_doel?: NodeDoel },
    { antId, tekst, denk, hergebruik, doel, tool_executions }: {
      antId: string; tekst?: string; denk: string;
      hergebruik?: AgentHergebruik; doel?: AgentDoelInvoer; tool_executions?: ToolExecution[];
    },
  ) {
    const node = uitkomst.annotatie_doel ?? (doel?.bron_iri ? {
      bron_iri: doel.bron_iri, label: doel.label, snapshot_id: doel.snapshot_id,
    } : undefined);
    if (!node) return; // een gewoon antwoord staat al in beeld
    setItems((xs) => xs.map((x) => x.id === antId ? { id: antId, type: "annotatie", slug: uitkomst.annotatie_slug || node.bron_iri,
      annotatie_doel: node, titel: node.label, tekst: tekst?.trim() || undefined, denk, hergebruik, doel,
      tool_executions } : x));
    setArtefactSlug(undefined); setNodeDoel(node);
  }

  /** Loopt er nog een beurt in dit gesprek? Haak er dan weer op aan.
   *
   *  Dit is de terugweg van de omkering: de run overleefde het wegklikken, dus bij binnenkomst
   *  hoort hij weer in beeld te komen – inclusief wat je gemist hebt (`vanaf: 0` speelt de eventlog
   *  af). Alleen bij een lópende run: een beurt die klaar is staat al in de gehydrateerde
   *  geschiedenis, en die twee keer tonen is erger dan hem missen.
   */
  async function hervatBeurt(gid: string, berichtRunIds: string[]) {
    if (bezigRef.current) return;
    const lopend = await haalActieveRun(gid);
    // Opnieuw toetsen ná de round-trip: typte de jurist ondertussen een vraag, dan draait die run al
    // en zouden hier twee lussen naast elkaar komen – met twee placeholders en een `afbrekenRef`
    // die de eerste kwijtraakt.
    if (bezigRef.current) return;
    // Niet kunnen vaststellen is geen "er liep niets": stil laten, anders meld je een afgebroken
    // beurt die in werkelijkheid gewoon doorloopt.
    if (lopend === "onbekend") return;
    if (lopend && lopend.status === "loopt") {
      const antId = uid();
      // Een lopende reeks heeft de onderdelen die al klaar waren al als berichten bewaard; het
      // aanhaken speelt de hele stroom opnieuw af. Het gehydrateerde blok gaat dus weg, anders
      // staat de reeks er twee keer.
      setItems((xs) => [
        ...xs.filter((x) => !(x.type === "reeks" && x.reeks.runId === lopend.run_id)),
        { id: antId, type: "antwoord", tekst: "" },
      ]);
      await volgBeurt({ runId: lopend.run_id, gid, antId, vanaf: 0 });
      return;
    }

    // Geen lopende run. Stond er wél een open? Dan is het register leeg – een herstart of deploy —
    // tenzij de beurt gewoon is afgerond en zijn bericht heeft achtergelaten.
    const stand = standVanVorigeRun(leesLopendeRuns()[gid], berichtRunIds);
    if (stand === "verdwenen") setRunVerdwenen(true);
    if (stand !== "geen") vergeetLopendeRun(gid);
  }

  /** Stop de lopende beurt. Een verzoek aan de agent, geen dichtvallende verbinding.
   *
   *  De agent-nodes zijn synchroon: een lopende LLM-call maakt zichzelf af en de run eindigt op de
   *  eerstvolgende grens. Dat kan tientallen seconden duren, dus de knop blijft in de "stopt"-stand
   *  staan tot het echt zover is – doen alsof het meteen klaar is zou liegen. Wat er tot dan toe
   *  binnenkwam, wordt gewoon vastgelegd zoals bij een normale afloop.
   */
  async function stop() {
    if (!runId || stopt) return;
    setStopt(true);
    try {
      await stopRun(runId);
    } catch {
      // Mislukt het stopverzoek, dan loopt de beurt gewoon door. Zet de knop terug in plaats van
      // hem eeuwig op "Stoppen…" te laten staan.
      setStopt(false);
    }
  }

  // De handelingen hieronder werken op het document van de rondleiding: alleen dat opent in
  // `ArtefactPaneel`. Een echte annotatie opent in `NodeAnnotatiePaneel`, dat zelf naar de api schrijft.

  async function eigenMarkering(
    slug: string,
    invoer: { klasse: string; tekst: string; lid: string; toelichting: string; anker: Anker },
  ) {
    const doc = docs[slug];
    if (!doc) return;
    const { doc: bijDemo, id } = voegDemoElementToe(doc, invoer);
    setDocs((m) => ({ ...m, [slug]: bijDemo }));
    setMelding(`Gemarkeerd als ${invoer.klasse}.`);
    // Zet de verse markering meteen in beeld. De tekst toont alleen de geselecteerde, dus zonder dit
    // lijkt zelf markeren niets te doen: je selectie verdwijnt en er komt geen kleur voor terug.
    setActiefId(id);
  }

  /** Was de gewiste markering actief, dan valt de focus terug op de hele tekst – anders wijst
   *  `actiefId` naar een element dat niet meer bestaat. */
  async function wisEigenMarkering(slug: string, elementId: string) {
    setDocs((m) => (m[slug] ? { ...m, [slug]: wisDemoElement(m[slug], elementId) } : m));
    setActiefId((huidig) => (huidig === elementId ? undefined : huidig));
    setMelding("Markering gewist.");
  }

  async function status(slug: string, nieuweStatus: "geaccordeerd" | "in_review") {
    setDocs((m) => (m[slug] ? { ...m, [slug]: zetDemoStatus(m[slug], nieuweStatus) } : m));
    setMelding(nieuweStatus === "geaccordeerd" ? "Annotatie afgerond." : "Annotatie heropend.");
  }

  async function beslissing(slug: string, elementId: string, req: BeslissingInvoer) {
    setDocs((m) => (m[slug] ? { ...m, [slug]: pasDemoBeslissingToe(m[slug], elementId, req) } : m));
    setMelding(beslissingMelding(req));
    onDemoBeslissing?.(req.type);
  }

  // De handelingen van de thread-rijen, als één object dat nooit verandert. `ThreadRij` is een
  // `memo`: een verse callback per render zou elke rij toch weer laten renderen. De ref wijst naar
  // de handlers van de laatste render (die lezen actuele state), het object zelf blijft gelijk.
  const actiesRef = useRef<ThreadActies | null>(null);
  useLayoutEffect(() => {
    actiesRef.current = {
      verstuur: (...args) => void verstuur(...args),
      openArtefact: (slug, doel) => void openArtefact(slug, doel),
      openSamenhang: (doel) => {
        setArtefactSlug(undefined);
        setNodeTab("graaf");
        setNodeDoel(doel);
      },
      openReeksLid: (reeksRun, doel) => {
        setNodeReeks(reeksRun);
        void openArtefact(doel.bron_iri, doel);
      },
      stop: () => void stop(),
    };
  });
  const [acties] = useState<ThreadActies>(() => ({
    verstuur: (...args) => actiesRef.current?.verstuur(...args),
    openArtefact: (slug, doel) => actiesRef.current?.openArtefact(slug, doel),
    openSamenhang: (doel) => actiesRef.current?.openSamenhang(doel),
    openReeksLid: (reeksRun, doel) => actiesRef.current?.openReeksLid(reeksRun, doel),
    stop: () => actiesRef.current?.stop(),
  }));

  function opToets(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // `isComposing`: met een IME (of een Android-toetsenbord dat een woordsuggestie met Enter
    // bevestigt) hoort Enter de compositie af te ronden, niet de beurt te versturen.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void verstuur();
    }
  }

  // De laatste annotatie in dit gesprek: die hoort altijd één klik weg te zijn. Verwijderde
  // documenten slaan we over – anders verdwijnt de balk terwijl er verderop in het gesprek nog een
  // annotatie staat die wél bestaat.
  // Eén "laatste", over beide soorten heen: de node-annotatie ging eerst altijd voor, ook als er
  // daarna nog een artikeldocument in het gesprek stond.
  const laatsteItem = [...items]
    .reverse()
    .find((x): x is Extract<Item, { type: "annotatie" }> => x.type === "annotatie" && !verwijderd[x.slug]);
  const laatsteNodeAnnotatie = laatsteItem?.annotatie_doel ? laatsteItem : undefined;
  const laatsteAnnotatie = laatsteItem && !laatsteItem.annotatie_doel ? laatsteItem.slug : undefined;

  // Hoort de open annotatie bij een reeks in dit gesprek, dan bladert het paneel door de leden.
  const nodeReeksNav = (() => {
    if (!nodeDoel || !nodeReeks) return undefined;
    const item = items.find((x): x is Extract<Item, { type: "reeks" }> => x.type === "reeks" && x.reeks.runId === nodeReeks);
    const nav = item && reeksNavigatie(item.reeks, nodeDoel.bron_iri);
    return nav ? { ...nav, onGa: (d: NodeDoel) => setNodeDoel(d) } : undefined;
  })();
  const artefact = nodeDoel ? <NodeAnnotatiePaneel key={`${nodeDoel.bron_iri}:${nodeDoel.snapshot_id ?? ""}:${nodeTab}`} doel={nodeDoel}
    variant={breed ? "kolom" : "side"} onSluit={() => { setNodeDoel(undefined); setNodeReeks(undefined); }} beginTab={nodeTab}
    reeks={nodeReeksNav}
    onVraag={(element, view) => {
      setVraagOver(null); setNodeVraag({ element, view });
      setInvoer(`Waarom is dit een ${element.klasse}?`);
      if (!breed) setNodeDoel(undefined);
      taRef.current?.focus();
    }}
    onVraagOverBron={(knoop) => {
      // Een gewone vraag: de bepaling staat met haar vindplaats in de tekst, zodat Lex haar in de
      // graaf terugvindt. Geen nieuw agentcontract.
      const plek = knoop.bwb_id && knoop.artikel
        ? ` (${knoop.bwb_id}, artikel ${knoop.artikel}${knoop.lid ? `, lid ${knoop.lid}` : ""})` : "";
      setVraagOver(null); setNodeVraag(undefined);
      setInvoer(`Hoe hangt ${knoop.label}${plek} samen met de bepalingen waarnaar het verwijst of die ernaar verwijzen?`);
      if (!breed) setNodeDoel(undefined);
      requestAnimationFrame(() => taRef.current?.focus());
    }} /> : artefactSlug && docs[artefactSlug] && infos[artefactSlug] && (
    <ArtefactPaneel
      variant={breed ? "kolom" : "side"}
      doc={docs[artefactSlug]}
      info={infos[artefactSlug]}
      actiefId={actiefId}
      // Nog eens op dezelfde markering klikken laat hem weer los. Selecteren zet de tekst in
      // focus (alleen die markering), dus zonder toggle zou je er niet meer uit komen.
      onKies={(id) => setActiefId((huidig) => (id && id === huidig ? undefined : id))}
      onBeslissing={(elementId, req) => beslissing(artefactSlug, elementId, req)}
      onEigenMarkering={(invoer) => eigenMarkering(artefactSlug, invoer)}
      onWisEigenMarkering={(elementId) => wisEigenMarkering(artefactSlug, elementId)}
      onStatus={(nieuweStatus) => status(artefactSlug, nieuweStatus)}
      // In de rondleiding bestaat *Vraag Lex* niet, om dezelfde reden als op `/annotaties/node`:
      // er is geen bruikbaar chatveld om iets in klaar te zetten – het invoerveld staat daar stil.
      // De knop deed er wél iets: hij sloot op een smal scherm het artefact, waarna de rondleiding
      // haar anker kwijt was en het paneel er zes seconden later vanzelf weer in ploft.
      onVraag={demo ? undefined : (el) => {
        setVraagOver({ slug: artefactSlug, el });
        // Op een smal scherm ligt het artefact óver de chat, dus stap hier al opzij – niet pas bij
        // het versturen. Anders lijkt "Vraag Lex" niets te doen: de chip met de markering en het
        // invoerveld staan achter het paneel, en je typt in een veld dat je niet ziet.
        if (!breed) setArtefactSlug(undefined);
        // Focus in dezelfde gebeurtenis als de klik: iOS opent het toetsenbord alleen binnen een
        // gebruikersgebaar.
        taRef.current?.focus();
      }}
      onSluit={() => setArtefactSlug(undefined)}
    />
  );

  return (
    <div className="flex min-h-0 min-w-0 flex-1">
    <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
      {/* Beknopte statusmelding voor schermlezers (niet de hele thread live maken → geen token-spam). */}
      <p className="sr-only" aria-live="polite">
        {stopt ? "Bezig met stoppen; de agent rondt zijn huidige stap af." : bezig ? "Bezig met antwoorden…" : melding}
      </p>
      {/* Begroeting en silhouet: volledig in de lege werkplek, een smalle strook zodra er een gesprek
          loopt. Buiten de scroller, zodat alleen de thread scrolt. */}
      <WerkplekHeader compact={items.length > 0} />
      {/* De annotatie blijft bereikbaar. De chip in de thread scrolt weg zodra het gesprek doorloopt;
          dan is er geen weg terug naar het werk waar je middenin zat. */}
      {!nodeDoel && !artefactSlug && laatsteNodeAnnotatie && (
        <button
          type="button"
          onClick={() => void openArtefact(laatsteNodeAnnotatie.slug, laatsteNodeAnnotatie.annotatie_doel)}
          className="focus-ring flex w-full shrink-0 items-center gap-2 border-b border-line bg-surface px-4 py-2 text-left text-xs text-muted transition hover:bg-surface-2"
        >
          <span className="truncate font-medium text-ink">{laatsteNodeAnnotatie.titel || "Laatste annotatie"}</span>
          <span className="ml-auto shrink-0 font-medium text-lint">Openen</span>
        </button>
      )}
      {!nodeDoel && !artefactSlug && laatsteAnnotatie && docs[laatsteAnnotatie] && (
        <button
          type="button"
          onClick={() => void openArtefact(laatsteAnnotatie)}
          className="focus-ring flex w-full shrink-0 items-center gap-2 border-b border-line bg-surface px-4 py-2 text-left text-xs text-muted transition hover:bg-surface-2 disabled:opacity-60"
        >
          <span className="truncate">
            <span className="font-medium text-ink">
              {docs[laatsteAnnotatie].werkgebied || docs[laatsteAnnotatie].bwbId} – art.{" "}
              {docs[laatsteAnnotatie].artikel}
            </span>{" "}
            · {docs[laatsteAnnotatie].elementen.length} elementen
            {teBeoordelen(docs[laatsteAnnotatie]) > 0 && ` · ${teBeoordelen(docs[laatsteAnnotatie])} te beoordelen`}
          </span>
          <span className="ml-auto shrink-0 font-medium text-lint">
            Openen
          </span>
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
              onClick={() => setRunVerdwenen(false)}
              className="focus-ring rounded font-medium underline underline-offset-2"
            >
              Sluiten
            </button>
          </Melding>
        </div>
      )}

      {/* Verwijderd is een toestand, geen storing: een neutrale mededeling zónder "Opnieuw proberen",
          want die knop kan hier per definitie niet slagen. */}
      {artefactWeg && (
        <div className="shrink-0 px-4 pt-2">
          <Melding type="uitleg" compact>
            Deze annotatie is verwijderd. Het gesprek blijft staan.{" "}
            <Link href="/annotaties" className="focus-ring rounded font-medium underline underline-offset-2">
              Alle annotaties
            </Link>
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
                Ik zoek bepalingen op, citeer letterlijk en stel JAS-markeringen voor. Wat ik voorstel,
                beoordeel jij.
              </p>
              <p className="mx-auto mt-3 max-w-md text-sm text-faint md:mt-0">
                Stel een vraag over de wet- en regelgeving, of vraag een annotatie volgens het JAS.
              </p>
              {onRondleiding && (
                <div className="mt-5">
                  <button
                    type="button"
                    onClick={onRondleiding}
                    className="focus-ring rounded-full border border-lint/30 bg-lint/5 px-4 py-2 text-sm font-medium text-lint transition-colors hover:bg-lint/10"
                  >
                    Laat me de werkplek zien
                  </button>
                </div>
              )}
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {VOORBEELDEN.map((v) => (
                  <button
                    key={v}
                    type="button"
                    disabled={geblokkeerd}
                    title={geblokkeerd ? "Je tokenbudget is op" : undefined}
                    onClick={() => void verstuur(v)}
                    className="rounded-bubbel border border-line bg-paper px-4 py-2.5 text-left text-sm text-lint shadow-zacht transition-all hover:-translate-y-0.5 hover:border-lint/40 hover:shadow-kaart disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0 disabled:hover:border-line disabled:hover:shadow-zacht focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint"
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
          )}

          {items.map((item, i) => (
            // `thread-rij` laat de browser layout en paint overslaan voor beurten buiten beeld
            // (`content-visibility`, zie globals.css); de DOM blijft staan, dus zoeken, schermlezers
            // en het meescrollen blijven kloppen.
            <div key={item.id} className="thread-rij">
              <ThreadRij
                item={item}
                // Alleen de laatste beurt kan aan het streamen zijn.
                streamt={bezig && i === items.length - 1}
                bezig={bezig}
                geblokkeerd={geblokkeerd}
                demo={!!demo}
                samenhangAan={samenhangAan}
                loopt={item.type === "reeks" && !!runId && runId === item.reeks.runId}
                doc={item.type === "annotatie" ? docs[item.slug] : undefined}
                verwijderd={item.type === "annotatie" && !!verwijderd[item.slug]}
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
          className="absolute bottom-24 left-1/2 z-10 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-line bg-paper text-lint shadow-kaart transition-colors hover:border-lint/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M12 5v14M19 12l-7 7-7-7" />
          </svg>
        </button>
      )}

      {/* Invoerbalk – gepind onderaan, gecentreerd, auto-groeiend */}
      <div className="shrink-0 bg-paper">
        <div className="mx-auto max-w-3xl px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2">
          {/* Waar de volgende vraag over gaat. Zichtbaar zolang hij geldt, want anders stel je
              ongemerkt een adviesvraag over een element dat je allang niet meer voor je hebt. */}
          {/* De vragen die bij een markering hoe dan ook gesteld worden, als één klik. Een leeg veld
              met "Wat wil je weten over deze markering?" is een open vraag op het moment dat je juist
              snel wilt beoordelen. Ze verdwijnen zodra er een beurt loopt: een tweede vraag zou de
              eerste toch afgewezen krijgen (er loopt al een run op dit gesprek). */}
          {/* Dezelfde chip als bij `vraagOver` hieronder: klasse, fragment en een kruisje. */}
          {nodeVraag && (
            <div className="mb-1.5 flex items-center gap-1.5">
              <span className="inline-flex min-w-0 items-center gap-1.5 rounded-full border border-lint/30 bg-lint/5 px-2.5 py-1 text-xs text-lint">
                <span className={`shrink-0 rounded px-1 text-[0.7rem] ${jasStyle(nodeVraag.element.klasse)}`}>
                  {nodeVraag.element.klasse}
                </span>
                <span className="truncate">“{nodeVraag.element.tekst}”</span>
                <button
                  type="button"
                  onClick={() => setNodeVraag(undefined)}
                  aria-label="Vraag niet aan deze markering koppelen"
                  className="focus-ring inline-flex min-h-[24px] min-w-[24px] shrink-0 items-center justify-center rounded-full p-0.5 hover:bg-lint/10 coarse:min-h-[44px] coarse:min-w-[44px]"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden>
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </span>
            </div>
          )}
          {vraagOver && !bezig && (
            <div className="mb-1.5 flex flex-wrap gap-1.5">
              {vraagSuggesties(vraagOver.el).map((vraag) => (
                <button
                  key={vraag}
                  type="button"
                  disabled={geblokkeerd}
                  title={geblokkeerd ? "Je tokenbudget is op" : undefined}
                  onClick={() => void verstuur(vraag)}
                  className="focus-ring inline-flex min-h-[24px] items-center rounded-full border border-line bg-paper px-2.5 py-1 text-xs text-muted transition hover:border-lint hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-line disabled:hover:text-muted coarse:min-h-[44px]"
                >
                  {vraag}
                </button>
              ))}
            </div>
          )}
          {vraagOver && (
            <div className="mb-1.5 flex items-center gap-1.5">
              <span className="inline-flex min-w-0 items-center gap-1.5 rounded-full border border-lint/30 bg-lint/5 px-2.5 py-1 text-xs text-lint">
                <span className={`shrink-0 rounded px-1 text-[0.7rem] ${jasStyle(vraagOver.el.klasse)}`}>
                  {vraagOver.el.klasse}
                </span>
                <span className="truncate">“{vraagOver.el.tekst}”</span>
                <button
                  type="button"
                  onClick={() => setVraagOver(null)}
                  aria-label="Vraag niet aan dit element koppelen"
                  className="focus-ring shrink-0 rounded-full p-0.5 hover:bg-lint/10"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden>
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </span>
            </div>
          )}
          <div data-tour="invoer" className="flex items-end gap-2 rounded-bubbel border border-line bg-white px-2 py-1.5 shadow-zacht transition-shadow focus-within:border-lint focus-within:shadow-kaart">
            <textarea
              ref={taRef}
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
                    : vraagOver
                      ? "Wat wil je weten over deze markering?"
                      : "Stel een vraag of geef een opdracht aan Lex…"
              }
              className="max-h-[200px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-ink placeholder:text-faint focus:outline-none"
            />
            {/* Tijdens het antwoorden is dit de stopknop: hetzelfde plekje, andere betekenis – je hoeft
                niet te zoeken waar je moet klikken om te onderbreken. */}
            <button
              type="button"
              onClick={() => (bezig ? void stop() : void verstuur())}
              disabled={Boolean(demo) || geblokkeerd || (!bezig && !invoer.trim()) || stopt}
              aria-label={bezig ? (stopt ? "Bezig met stoppen" : "Stoppen") : "Versturen"}
              title={stopt ? "De agent rondt zijn huidige stap nog af" : undefined}
              className="focus-ring mb-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-paper transition-colors hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-40"
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
        </div>
      </div>

      {/* Op een smal scherm schuift het artefact als overlay over de chat heen. */}
      {!breed && artefact}
    </div>

    {/* Op een breed scherm staat het ernaast: chat en review tegelijk in beeld. */}
    {breed && artefact && (
      <div className="hidden w-[min(34rem,42vw)] shrink-0 xl:block">{artefact}</div>
    )}
    </div>
  );
}

const VOORBEELDEN = [
  "Wat betekent het begrip 'belastingschuldige'?",
  "annoteer artikel 9 lid 1 van de Invorderingswet 1990",
  "Welke artikelen gaan over invordering?",
];
