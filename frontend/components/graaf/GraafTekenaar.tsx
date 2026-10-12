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
import { EdgeArrowProgram, EdgeRectangleProgram } from "sigma/rendering";
import type { CameraState, NodeDisplayData } from "sigma/types";
import { useEffect, useMemo, useRef, type RefObject } from "react";
import type { Posities } from "@/lib/graaf/layout";
import type { GraafModel, KnoopData, RelatieData } from "@/lib/graaf/model";
import { LABELKLEUR } from "@/lib/graaf/stijl";
import { knoopBeeld, lijnBeeld, type WeergaveContext } from "@/lib/graaf/weergave";

export interface GraafBediening {
  /** Alles in beeld. */
  pasIn: () => void;
  /** Naar een knoop vliegen, en inzoomen als je ver weg was. */
  focus: (id: string) => void;
  /** < 1 zoomt in, > 1 zoomt uit. */
  zoom: (factor: number) => void;
}

type TekenKnoop = KnoopData & { x: number; y: number };

/** Eén programma voor alle knopen: een cirkel met een rand van variabele dikte (0 = geen rand). Zo
 *  wisselt een knoop van gewoon naar omtrek (rand, dekking) zonder van programma te wisselen. */
const KnoopProgramma = createNodeBorderProgram<TekenKnoop, RelatieData>({
  borders: [
    { size: { attribute: "randDikte", defaultValue: 0 }, color: { attribute: "randKleur" } },
    { size: { fill: true }, color: { attribute: "color" } },
  ],
});

const beweging = () => (typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 400);

export function GraafTekenaar({ model, posities, context, zichtbaar, cameraRef, bedieningRef, onKies, onFout }: {
  model: GraafModel;
  posities: Posities;
  context: WeergaveContext;
  /** Staat de graaf in beeld? Een verborgen tab heeft geen afmeting; bij terugkomst opnieuw meten. */
  zichtbaar: boolean;
  /** De camerastand buiten deze component: vergroten remount hem, en dan blijft het beeld staan. */
  cameraRef: RefObject<CameraState | null>;
  bedieningRef: RefObject<GraafBediening | null>;
  /** Een knoop gekozen, of `null`: klik op de achtergrond. */
  onKies: (id: string | null) => void;
  /** Geen WebGL, of de context ging verloren: de UI valt terug op zoeken, lagen en de inspector. */
  onFout: () => void;
}) {
  const houder = useRef<HTMLDivElement>(null);
  const sigma = useRef<Sigma<TekenKnoop, RelatieData> | null>(null);
  const ctx = useRef(context);
  const handlers = useRef({ onKies, onFout });
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
    let s: Sigma<TekenKnoop, RelatieData>;
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
        labelFont: getComputedStyle(el).fontFamily || "sans-serif",
        labelSize: 12,
        labelWeight: "500",
        labelColor: { color: LABELKLEUR },
        labelDensity: 0.7,
        labelGridCellSize: 80,
        // Laag: ook leden krijgen een naam zodra er ruimte is; de labelgrid houdt het leesbaar.
        labelRenderedSizeThreshold: 3,
        // Bij de hele kennisgraaf: lijnen even weg tijdens het slepen, zodat pannen vloeiend blijft.
        hideEdgesOnMove: teken.size > 5000,
        minCameraRatio: 0.01,
        maxCameraRatio: 3,
        stagePadding: 24,
        nodeReducer: (id, a) => {
          const b = knoopBeeld(id, a, ctx.current);
          // `randDikte`/`randKleur` lezen de randen van `KnoopProgramma`; sigma geeft ze ongewijzigd door.
          const beeld: Partial<NodeDisplayData> & { randDikte: number; randKleur: string } = {
            x: a.x, y: a.y, size: b.grootte, color: b.kleur, label: b.label, hidden: b.verborgen,
            forceLabel: b.altijdLabel, zIndex: b.niveau,
            randDikte: b.omtrek ? 0.32 : 0, randKleur: b.omtrek ?? b.kleur,
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
    if (cameraRef.current) s.getCamera().setState(cameraRef.current);

    s.on("clickNode", ({ node }) => handlers.current.onKies(node));
    s.on("clickStage", () => handlers.current.onKies(null));
    s.on("enterNode", () => { el.style.cursor = "pointer"; });
    s.on("leaveNode", () => { el.style.cursor = ""; });
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
    bedieningRef.current = {
      pasIn: () => beweeg({ x: 0.5, y: 0.5, ratio: 1, angle: 0 }, beweging()),
      zoom: (factor) => {
        const cam = s.getCamera();
        const huidig = { ...cam.getState(), ...doelCamera };
        beweeg({ ratio: cam.getBoundedRatio(huidig.ratio * factor) }, beweging() / 2);
      },
      focus: (id) => {
        const d = s.getNodeDisplayData(id);
        if (!d) return;
        const huidig = { ...s.getCamera().getState(), ...doelCamera };
        beweeg({ x: d.x, y: d.y, ratio: Math.min(huidig.ratio, 0.4) }, beweging());
      },
    };
    // Een nieuwe maat (vergroten, de inspector die in- of uitklapt): opnieuw meten én tekenen.
    const meet = new ResizeObserver(() => s.resize(true).refresh());
    meet.observe(el);
    return () => {
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
      s.setSetting("hideEdgesOnMove", teken.size > 5000);
      s.setGraph(teken);
    }
  }, [teken]);

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
