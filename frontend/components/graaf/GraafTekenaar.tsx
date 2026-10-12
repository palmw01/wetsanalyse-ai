"use client";

/** De tekenaar: de enige plek die sigma.js kent. Een dunne adapter – hij tekent het model op de
 *  posities uit de layout, vraagt per knoop en lijn het beeld op bij de weergavestand (`weergave.ts`)
 *  en meldt klikken terug. Hij houdt zelf geen stand bij: wat zichtbaar is en wat nadruk heeft, staat
 *  in de context die hij krijgt. Een overstap naar een volgende sigma-versie raakt alleen dit bestand.
 *
 *  Lui geladen (`next/dynamic`, zie `Graaf.tsx`): WebGL en sigma komen pas binnen als de graaf opent. */
import { createNodeBorderProgram } from "@sigma/node-border";
import Graph from "graphology";
import Sigma from "sigma";
import { drawDiscNodeHover, drawDiscNodeLabel, EdgeArrowProgram, EdgeRectangleProgram } from "sigma/rendering";
import type { CameraState, NodeDisplayData } from "sigma/types";
import { useEffect, useMemo, useRef, type RefObject } from "react";
import type { Posities } from "@/lib/graaf/layout";
import { detailFactor, effectieveZoom, kiesLabels, labelPrioriteit, magLabel, type LabelKandidaat } from "@/lib/graaf/labels";
import type { GraafModel, KnoopData, KnoopSoort, RelatieData } from "@/lib/graaf/model";
import { GEDIMD_LABEL, LABELKLEUR } from "@/lib/graaf/stijl";
import { knoopBeeld, lijnBeeld, type WeergaveContext } from "@/lib/graaf/weergave";

export interface GraafBediening {
  /** Alles in beeld. */
  pasIn: () => void;
  /** Naar een knoop vliegen, en inzoomen als je ver weg was. */
  focus: (id: string) => void;
  /** < 1 zoomt in, > 1 zoomt uit. */
  zoom: (factor: number) => void;
  /** Een groep knopen in beeld (de focus van het antwoord); leeg of onbekend = alles in beeld. */
  toon: (ids: Iterable<string>) => void;
}

type TekenKnoop = KnoopData & { x: number; y: number };
/** Wat de `nodeReducer` voor de labelkeuze onthoudt, per knoop die een label mag hebben: zo hoeft de
 *  keuze per beeld niet alle knoopdata van sigma te kopiëren, en slaat ze gedimde knopen over. */
type LabelInfo = {
  soort: KnoopSoort; prioriteit: number; label: string; size: number;
  /** Positie in graafcoördinaten (`graphToViewport`). */
  x: number; y: number;
  /** Gekozen of aangewezen: altijd een label, ook als het botst. */
  altijd: boolean;
  /** Hoort een label te hebben (de keuze met haar buren, de doelen van de focus): los van de zoom. */
  vast: boolean;
};

const LABELGROOTTE = 12;
/** Een klik: losgelaten binnen zoveel pixels van waar je indrukte. Geen tijdgrens: wie lang drukt
 *  zonder te bewegen, klikt ook. */
const KLIK_AFSTAND = 5;
const LABELGEWICHT = "500";

/** Eén programma voor alle knopen: een cirkel met een rand van variabele dikte (0 = geen rand). Zo
 *  wisselt een knoop van gewoon naar omtrek (rand, dekking) zonder van programma te wisselen. */
const KnoopProgramma = createNodeBorderProgram<TekenKnoop, RelatieData>({
  borders: [
    { size: { attribute: "randDikte", defaultValue: 0 }, color: { attribute: "randKleur" } },
    { size: { fill: true }, color: { attribute: "color" } },
  ],
});

const beweging = () => (typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 400);

export function GraafTekenaar({ model, posities, context, zichtbaar, inpassen, cameraRef, bedieningRef, bedekking, onKies, onFout }: {
  model: GraafModel;
  posities: Posities;
  context: WeergaveContext;
  /** Staat de graaf in beeld? Een verborgen tab heeft geen afmeting; bij terugkomst opnieuw meten. */
  zichtbaar: boolean;
  /** Wat in beeld hoort als er een nieuwe kaart komt (`sleutel` verandert): de focus van het antwoord,
   *  of de keuze. Declaratief, zodat het ook werkt als sigma nog aan het laden was. Een bewaarde
   *  camerastand (vergroten) gaat voor. */
  inpassen?: { sleutel: string; ids: readonly string[] };
  /** De camerastand buiten deze component: vergroten remount hem, en dan blijft het beeld staan. */
  cameraRef: RefObject<CameraState | null>;
  bedieningRef: RefObject<GraafBediening | null>;
  /** De laag met de zwevende bediening: haar knoppen en velden (`.pointer-events-auto`) tellen bij de
   *  labelkeuze als bezet, anders verdwijnt een label onder het zoekveld. */
  bedekking?: RefObject<HTMLElement | null>;
  /** Een knoop gekozen, of `null`: klik op de achtergrond. */
  onKies: (id: string | null) => void;
  /** Geen WebGL, of de context ging verloren: de UI valt terug op zoeken, lagen en de inspector. */
  onFout: () => void;
}) {
  const houder = useRef<HTMLDivElement>(null);
  const sigma = useRef<Sigma<TekenKnoop, RelatieData> | null>(null);
  const ctx = useRef(context);
  const inpassenRef = useRef(inpassen);
  const ingepast = useRef<string | undefined>(undefined);
  const handlers = useRef({ onKies, onFout });
  // De labels van het laatste beeld (`kiesLabels`), en de zoom waarop de knoopgroottes berekend zijn.
  const labels = useRef<Set<string>>(new Set());
  const labelInfo = useRef<Map<string, LabelInfo>>(new Map());
  const zoom = useRef(1);
  useEffect(() => { handlers.current = { onKies, onFout }; });

  // Het model met zijn posities: sigma eist x en y op de knopen. Een eigen graaf, zodat het model data
  // blijft en de layout er los van staat.
  const teken = useMemo(() => {
    const g = new Graph<TekenKnoop, RelatieData>({ type: "directed", multi: true, allowSelfLoops: true });
    model.forEachNode((id, a) => {
      const [x, y] = posities.get(id) ?? [0, 0];
      g.addNode(id, { ...a, x, y });
    });
    model.forEachEdge((e, a, bron, doel) => g.addDirectedEdgeWithKey(e, bron, doel, a));
    return g;
  }, [model, posities]);

  // Sigma één keer per montage; daarna wisselt alleen de graaf.
  useEffect(() => {
    const el = houder.current;
    if (!el) return;
    const font = getComputedStyle(el).fontFamily || "sans-serif";
    let s: Sigma<TekenKnoop, RelatieData>;
    let teKiezen = true;
    // Wordt hieronder gezet, ná sigma; sigma's tekenfunctie verwijst ernaar.
    let kiesDitBeeld: () => void = () => {};
    try {
      s = new Sigma<TekenKnoop, RelatieData>(teken, el, {
        allowInvalidContainer: true,
        zIndex: true,
        renderEdgeLabels: false,
        enableEdgeEvents: false,
        defaultNodeType: "knoop",
        nodeProgramClasses: { knoop: KnoopProgramma },
        defaultEdgeType: "lijn",
        edgeProgramClasses: { lijn: EdgeRectangleProgram, pijl: EdgeArrowProgram },
        labelFont: font,
        labelSize: LABELGROOTTE,
        labelWeight: LABELGEWICHT,
        labelColor: { attribute: "labelKleur", color: LABELKLEUR },
        // Welke labels er komen, kiest `kiesLabels` per beeld (zie `beforeRender`): sigma's eigen raster
        // toetst de breedte van een label niet. Daarom staat zijn raster op nul en is elk label "forced";
        // de tekenfunctie laat alleen door wat gekozen is.
        labelDensity: 0,
        labelRenderedSizeThreshold: 0,
        defaultDrawNodeLabel: (context, data, settings) => {
          // Het eerste label van een beeld: dan pas kiezen. Vóór het tekenen (`beforeRender`) zijn de
          // knoopdata en de cameramatrix nog die van het vorige beeld.
          if (teKiezen) { teKiezen = false; kiesDitBeeld(); }
          if (labels.current.has(data.key)) drawDiscNodeLabel(context, data, settings);
        },
        // De hover noemt de volledige naam: op de kaart staat "Lid 1", en in de hele kennisgraaf zijn
        // er honderden.
        defaultDrawNodeHover: (context, data, settings) =>
          drawDiscNodeHover(context, { ...data, label: (data as { naam?: string }).naam ?? data.label }, settings),
        // Bij de hele kennisgraaf: lijnen even weg tijdens het slepen, zodat pannen vloeiend blijft.
        hideEdgesOnMove: teken.size > 5000,
        // Een vaste schermgrootte, zoals op een kaart: inzoomen trekt knopen uit elkaar in plaats van ze
        // op te blazen (sigma's standaard groeit mee met de wortel van de zoom – en dan wordt een
        // ingezoomde regeling een kluwen overlappende schijven).
        zoomToSizeRatioFunction: () => 1,
        minCameraRatio: 0.01,
        maxCameraRatio: 3,
        stagePadding: 24,
        nodeReducer: (id, a) => {
          const b = knoopBeeld(id, a, ctx.current);
          // Uitgezoomd zijn de details kleiner; wat nadruk heeft houdt zijn maat.
          const factor = b.niveau >= 2 ? 1 : detailFactor(a.soort, zoom.current);
          const size = b.grootte * factor;
          // Het label staat er altijd (de hover toont het); of het op de kaart komt, beslist de keuze bij
          // het tekenen. Ook een gedimde knoop dingt mee – in grijs en met de laagste prioriteit – zodat
          // je je bij inzoomen buiten de nadruk ook kunt oriënteren.
          if (!b.verborgen) {
            labelInfo.current.set(id, { soort: a.soort, prioriteit: labelPrioriteit(b.niveau, b.altijdLabel, a.soort), label: a.kort,
              size, x: a.x, y: a.y, altijd: b.gekozen || b.aangewezen, vast: b.altijdLabel });
          } else labelInfo.current.delete(id);
          // `randDikte`/`randKleur` lezen de randen van `KnoopProgramma`; sigma geeft ze ongewijzigd door.
          const beeld: Partial<NodeDisplayData> & { randDikte: number; randKleur: string; labelKleur: string; naam: string } = {
            x: a.x, y: a.y, size, color: b.kleur, label: a.kort, naam: a.naam, hidden: b.verborgen,
            forceLabel: true, zIndex: b.niveau, highlighted: b.aangewezen,
            randDikte: b.omtrek ? 0.32 : 0, randKleur: b.omtrek ?? b.kleur,
            labelKleur: b.gedimd ? GEDIMD_LABEL : LABELKLEUR,
          };
          return beeld;
        },
        edgeReducer: (e, a) => {
          const g = sigma.current?.getGraph() ?? teken;
          const b = lijnBeeld(a, g.source(e), g.target(e), ctx.current);
          return { color: b.kleur, size: b.dikte, hidden: b.verborgen, type: b.pijl ? "pijl" : "lijn", zIndex: b.niveau };
        },
      });
    } catch {
      handlers.current.onFout();
      return;
    }
    sigma.current = s;
    // Een bewaarde stand (vergroten) gaat voor; anders meteen – zonder animatie – op wat in beeld hoort.
    if (cameraRef.current) {
      s.getCamera().setState(cameraRef.current);
      ingepast.current = inpassenRef.current?.sleutel;
    }

    // De labels van dit beeld: alles wat een label mag hebben en op het scherm staat, in volgorde van
    // prioriteit, zonder botsingen (`lib/graaf/labels.ts`). Per beeld, dus ook tijdens zoomen en pannen.
    const meetDoek = document.createElement("canvas").getContext("2d");
    const breedtes = new Map<string, number>();
    const breedteVan = (tekst: string) => {
      let b = breedtes.get(tekst);
      if (b === undefined) {
        if (meetDoek) meetDoek.font = `${LABELGEWICHT} ${LABELGROOTTE}px ${font}`;
        b = meetDoek ? meetDoek.measureText(tekst).width : tekst.length * 7;
        breedtes.set(tekst, b);
      }
      return b;
    };
    kiesDitBeeld = () => {
      const z = effectieveZoom(s.getCamera().getState().ratio, s.getGraph().order);
      const { width, height } = s.getDimensions();
      const kandidaten: LabelKandidaat[] = [];
      for (const [id, d] of labelInfo.current) {
        if (!d.altijd && !d.vast && !magLabel(d.soort, z)) continue;
        const p = s.graphToViewport(d);
        if (p.x < -400 || p.x > width || p.y < -20 || p.y > height + 20) continue;
        kandidaten.push({
          id, links: p.x + d.size + 3, boven: p.y - LABELGROOTTE * 0.75, breedte: breedteVan(d.label), hoogte: LABELGROOTTE * 1.2,
          prioriteit: d.prioriteit, altijd: d.altijd,
        });
      }
      const doek = el.getBoundingClientRect();
      const bezet = [...(bedekking?.current?.querySelectorAll<HTMLElement>(".pointer-events-auto") ?? [])].map((b) => {
        const r = b.getBoundingClientRect();
        return { links: r.left - doek.left, boven: r.top - doek.top, breedte: r.width, hoogte: r.height };
      });
      labels.current = kiesLabels(kandidaten, { breedte: width, hoogte: height, vorige: labels.current, bezet });
    };
    s.on("beforeRender", () => { teKiezen = true; });
    // Zonder één label in beeld roept sigma de tekenfunctie niet aan; dan is er ook niets gekozen.
    s.on("afterRender", () => {
      if (teKiezen) labels.current = new Set();
      el.dataset.labels = String(labels.current.size);
      // Welke soorten een label hebben (voor de browsertest: uitgezoomd geen artikelen, ingezoomd wel).
      el.dataset.labelSoorten = [...new Set([...labels.current].map((id) => labelInfo.current.get(id)?.soort ?? ""))].sort().join(",");
    });
    // De knoopgroottes hangen aan de zoom (`detailFactor`): alleen opnieuw berekenen als een drempel
    // gepasseerd wordt, niet bij elk beeld.
    const opCamera = () => {
      const z = effectieveZoom(s.getCamera().getState().ratio, s.getGraph().order);
      const oud = zoom.current;
      zoom.current = z;
      if (detailFactor("onderdeel", z) !== detailFactor("onderdeel", oud)) s.refresh();
    };
    s.getCamera().on("updated", opCamera);
    zoom.current = effectieveZoom(s.getCamera().getState().ratio, s.getGraph().order);

    // Een klik zelf herkennen, op afstand. Sigma's `clickNode`/`clickStage` laten een klik
    // alleen door bij minder dan 3 muisbewegingen tussen indrukken en loslaten – een telling, geen
    // afstand – en een trackpad of snelle muis geeft die bij een gewone klik al: dan deed klikken
    // niets. Ingedrukt op het ene en losgelaten op iets anders is geen klik.
    let neer: { x: number; y: number; knoop: string | null } | null = null;
    const omlaag = (knoop: string | null, e: { x: number; y: number }) => { neer = { x: e.x, y: e.y, knoop }; };
    const omhoog = (knoop: string | null, e: { x: number; y: number }) => {
      const begin = neer;
      neer = null;
      if (!begin || begin.knoop !== knoop) return;
      if (Math.hypot(e.x - begin.x, e.y - begin.y) > KLIK_AFSTAND) return;
      handlers.current.onKies(knoop);
    };
    s.on("downNode", ({ node, event }) => omlaag(node, event));
    s.on("downStage", ({ event }) => omlaag(null, event));
    s.on("upNode", ({ node, event }) => omhoog(node, event));
    s.on("upStage", ({ event }) => omhoog(null, event));
    s.on("enterNode", ({ node }) => { el.style.cursor = "pointer"; el.dataset.hoverNaam = s.getGraph().getNodeAttribute(node, "naam"); });
    s.on("leaveNode", () => { el.style.cursor = ""; delete el.dataset.hoverNaam; });
    const opVerlies = (e: Event) => { e.preventDefault(); handlers.current.onFout(); };
    const doek = s.getCanvases();
    for (const c of Object.values(doek)) c.addEventListener("webglcontextlost", opVerlies);

    // Waar een lopende camerabeweging heen gaat. Een remount (vergroten) tijdens zo'n beweging moet het
    // doel bewaren, niet de tussenstand – anders staat het nieuwe beeld halverwege een vlucht stil.
    let doelCamera: Partial<CameraState> | null = null;
    const beweeg = (naar: Partial<CameraState>, duur: number) => {
      doelCamera = naar;
      void s.getCamera().animate(naar, { duration: duur }).then(() => { if (doelCamera === naar) doelCamera = null; });
    };
    const toon = (ids: Iterable<string>, duur = beweging()) => {
      const punten = [...ids].map((id) => s.getNodeDisplayData(id)).filter((d) => d && !d.hidden) as NodeDisplayData[];
      if (!punten.length) return beweeg({ x: 0.5, y: 0.5, ratio: 1, angle: 0 }, duur);
      const xs = punten.map((d) => d.x), ys = punten.map((d) => d.y);
      const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
      // Camerastand in genormaliseerde coördinaten: ratio 1 is de hele graaf. Wat marge rond de groep; een
      // kleine groep in de hele kennisgraaf vraagt diep inzoomen, maar één knoop niet tot op de pixel: hoe
      // kleiner de kaart, hoe minder diep, zodat de buurt (het artikel om een lid) in beeld blijft.
      const minRatio = Math.min(1, Math.max(0.03, Math.sqrt(40 / Math.max(s.getGraph().order, 1))));
      const ratio = Math.min(1, Math.max(minRatio, Math.max(x1 - x0, y1 - y0) * 1.4));
      beweeg({ x: (x0 + x1) / 2, y: (y0 + y1) / 2, ratio }, duur);
    };
    bedieningRef.current = {
      pasIn: () => beweeg({ x: 0.5, y: 0.5, ratio: 1, angle: 0 }, beweging()),
      toon,
      zoom: (factor) => {
        const cam = s.getCamera();
        const huidig = { ...cam.getState(), ...doelCamera };
        beweeg({ ratio: cam.getBoundedRatio(huidig.ratio * factor) }, beweging() / 2);
      },
      focus: (id) => {
        const d = s.getNodeDisplayData(id);
        if (!d) return;
        const huidig = { ...s.getCamera().getState(), ...doelCamera };
        // Diep genoeg om de knoop met zijn buurt te zien – in de hele kennisgraaf veel dieper dan in één
        // artikel, waar je niet hoeft in te zoomen.
        const diepte = Math.min(1, Math.max(0.03, Math.sqrt(400 / Math.max(s.getGraph().order, 1))));
        beweeg({ x: d.x, y: d.y, ratio: Math.min(huidig.ratio, diepte) }, beweging());
      },
    };
    if (!cameraRef.current && inpassenRef.current?.ids.length) {
      toon(inpassenRef.current.ids, 0);
      ingepast.current = inpassenRef.current.sleutel;
    }
    // Een nieuwe maat (vergroten, de inspector die in- of uitklapt): opnieuw meten én tekenen.
    const meet = new ResizeObserver(() => s.resize(true).refresh());
    meet.observe(el);
    return () => {
      s.getCamera().removeListener("updated", opCamera);
      meet.disconnect();
      for (const c of Object.values(doek)) c.removeEventListener("webglcontextlost", opVerlies);
      cameraRef.current = { ...s.getCamera().getState(), ...doelCamera };
      bedieningRef.current = null;
      sigma.current = null;
      s.kill();
    };
    // Sigma maakt je één keer; een nieuwe graaf gaat via `setGraph` hieronder.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const s = sigma.current;
    if (s && s.getGraph() !== teken) {
      // De reducer vult `labelInfo` opnieuw voor de nieuwe graaf; knopen die weg zijn mogen niet blijven.
      labelInfo.current = new Map();
      s.setSetting("hideEdgesOnMove", teken.size > 5000);
      zoom.current = effectieveZoom(s.getCamera().getState().ratio, teken.order);
      s.setGraph(teken);
    }
  }, [teken]);

  // Na de nieuwe graaf: een nieuwe kaart (andere sleutel) in beeld brengen.
  useEffect(() => {
    inpassenRef.current = inpassen;
    if (!inpassen || ingepast.current === inpassen.sleutel || !sigma.current) return;
    ingepast.current = inpassen.sleutel;
    bedieningRef.current?.toon(inpassen.ids);
  }, [inpassen, bedieningRef]);

  useEffect(() => {
    ctx.current = context;
    // Volledig: een keuze verandert grootte en tekenvolgorde, en die zitten in de index.
    sigma.current?.refresh();
  }, [context]);

  useEffect(() => {
    if (zichtbaar) sigma.current?.resize(true).refresh();
  }, [zichtbaar]);

  return <div ref={houder} className="absolute inset-0" data-testid="graaf-tekenaar"
    data-knopen={teken.order} data-lijnen={teken.size} />;
}
