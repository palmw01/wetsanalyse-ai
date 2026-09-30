"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import ForceGraph3D, { type ForceGraphMethods, type LinkObject } from "react-force-graph-3d";
import { Group, Mesh, MeshLambertMaterial, OctahedronGeometry, SphereGeometry, Vector3, type BufferGeometry, type PerspectiveCamera } from "three";
import SpriteText from "three-spritetext";
import type { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { SOORT_LABEL, isDubbelklik, type GraafData, type GraafKnoop, type GraafRelatie } from "@/lib/samenhang";

type LinkMeta = Omit<GraafRelatie, "source" | "target">;
type RenderLink = LinkObject<GraafKnoop, LinkMeta>;
type Punt = { x: number; y: number; z: number };
export type CameraStand = { positie: Punt; doel: Punt };
export interface GraafCameraBediening { pasIn: () => void; focus: (node: GraafKnoop) => void; zoom: (factor: number) => void }

/** Pas op de werkelijke viewport en het centrum van de knopen.
 * De bibliotheek past rond de wereldoorsprong; bij een smalle, nog initialiserende
 * viewport kan die berekening midden ín de graaf belanden. */
function pasCameraIn(fg: ForceGraphMethods<GraafKnoop, LinkMeta>, nodes: GraafKnoop[], width: number, height: number, ms: number) {
  if (!nodes.length || width < 1 || height < 1) return;
  const cam = fg.camera() as PerspectiveCamera;
  const controls = fg.controls() as OrbitControls;
  const midden = new Vector3(...(["x", "y", "z"] as const).map((as) => (Math.min(...nodes.map((n) => n[as])) + Math.max(...nodes.map((n) => n[as]))) / 2) as [number, number, number]);
  const richting = cam.position.clone().sub(controls.target).normalize();
  if (!richting.lengthSq()) richting.set(0.24, 0.16, 1).normalize();
  const rechts = new Vector3(0, 1, 0).cross(richting).normalize();
  if (!rechts.lengthSq()) rechts.set(1, 0, 0);
  const boven = richting.clone().cross(rechts).normalize();
  const tanY = Math.tan(cam.fov * Math.PI / 360);
  const tanX = tanY * (width / height);
  // Marge voor de labels: die hangen onder en naast de knoop, en een afgesneden label leest als fout.
  let afstand = 100;
  for (const node of nodes) {
    const p = new Vector3(node.x, node.y, node.z).sub(midden);
    afstand = Math.max(afstand, (Math.abs(p.dot(rechts)) + 80) / tanX + p.dot(richting), (Math.abs(p.dot(boven)) + 22) / tanY + p.dot(richting));
  }
  const positie = midden.clone().add(richting.multiplyScalar(afstand * 1.04));
  fg.cameraPosition(positie, midden, ms);
}

function webglBeschikbaar(): boolean {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2");
    if (!gl) return false;
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch { return false; }
}

// De geometrie per vorm en straal, gedeeld over alle knopen. Elke klik bouwt de knoopobjecten
// opnieuw (dimmen en labels hangen aan de selectie), en daarbij voor elke knoop een verse bol
// uitrekenen maakte kiezen in een groot artikel merkbaar traag. Delen is veilig: de renderer ruimt
// bij het vervangen de GPU-buffers op (`dispose`), en three.js laadt een gedisposede geometrie bij
// het volgende frame gewoon opnieuw.
const VORMEN = new Map<string, BufferGeometry>();
function vormVan(soort: "bol" | "klasse" | "halo", straal: number): BufferGeometry {
  const sleutel = `${soort}:${straal}`;
  let vorm = VORMEN.get(sleutel);
  if (!vorm) {
    vorm = soort === "klasse" ? new OctahedronGeometry(straal * 1.25)
      : soort === "halo" ? new SphereGeometry(straal + 2.5, 22, 16)
      : new SphereGeometry(straal, 20, 14);
    VORMEN.set(sleutel, vorm);
  }
  return vorm;
}

const idVan = (value: RenderLink["source"]): string => typeof value === "object" ? String(value.id) : String(value);

/** De tooltips van de bibliotheek zijn innerHTML; namen en ankerteksten komen uit de brongraaf. */
function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
const tip = (hoofd: string, sub = "") =>
  `<div class="samenhang-tip"><strong>${esc(hoofd)}</strong>${sub ? `<span>${esc(sub)}</span>` : ""}</div>`;

// Kleur, breedte en kromming per verbinding. Verwijzingen krommen het sterkst, zodat ze niet over de
// structuurlijnen heen liggen. Gedimd (buiten de selectie) blijft de kleur, maar met
// een lage alfa – zoals in de CGM-viewer, zodat het pad van de selectie eruit springt.
const LIJN: Record<GraafRelatie["soort"], { kleur: string; rgb: string; breedte: number; krom: number }> = {
  bevat: { kleur: "#8aa1b6", rgb: "138,161,182", breedte: 1.6, krom: 0.06 },
  verwijst_naar: { kleur: "#6b4e91", rgb: "107,78,145", breedte: 1.1, krom: 0.18 },
  markeert: { kleur: "#9fb3c5", rgb: "159,179,197", breedte: 0.7, krom: 0.1 },
  heeft_klasse: { kleur: "#b7c4d1", rgb: "183,196,209", breedte: 0.5, krom: 0.1 },
};
export function GraafCanvas({ data, selectie, onSelecteer, onDubbelklik, onInteractie, camera: cameraRef, bediening: bedieningRef, zichtbaar }: {
  data: GraafData; selectie: string; onSelecteer: (id: string) => void;
  /** Tweede klik op dezelfde knoop binnen 300 ms (de renderer kent alleen klik). */
  onDubbelklik?: (id: string) => void;
  /** De eerste keer dat de gebruiker zelf draait of zoomt. */
  onInteractie?: () => void;
  camera: MutableRefObject<CameraStand | null>;
  bediening: MutableRefObject<GraafCameraBediening | null>;
  zichtbaar: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const graph = useRef<ForceGraphMethods<GraafKnoop, LinkMeta> | undefined>(undefined);
  const [maat, setMaat] = useState({ width: 0, height: 0 });
  const [webgl] = useState(webglBeschikbaar);
  const [verloren, setVerloren] = useState(false);
  const [gereed, setGereed] = useState(false);
  const minderBeweging = useRef(false);
  const onInteractieRef = useRef(onInteractie);
  const vorigeKlik = useRef<{ id: string; tijd: number } | null>(null);
  useEffect(() => { onInteractieRef.current = onInteractie; }, [onInteractie]);
  const gestartRef = useRef(false);
  const frameRef = useRef(0);
  // De bibliotheek vervangt link-id's door objecten: geef nooit onze canonieke data door.
  const renderData = useMemo(() => ({ nodes: data.nodes.map((n) => ({ ...n })), links: data.links.map((l) => ({ ...l })) }), [data]);
  const buren = useMemo(() => {
    const ids = new Set([selectie]);
    for (const l of data.links) {
      if (l.source === selectie) ids.add(l.target);
      if (l.target === selectie) ids.add(l.source);
    }
    return ids;
  }, [data, selectie]);

  useEffect(() => {
    const el = container.current;
    if (!el) return;
    const query = matchMedia("(prefers-reduced-motion: reduce)");
    const beweging = () => { minderBeweging.current = query.matches; };
    beweging();
    query.addEventListener("change", beweging);
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      // Een verborgen tab behoudt zijn laatste maat en daarmee de camera.
      if (width > 0 && height > 0) setMaat({ width: Math.floor(width), height: Math.floor(height) });
    });
    observer.observe(el);
    return () => { observer.disconnect(); query.removeEventListener("change", beweging); };
  }, []);

  const klaar = useCallback(() => {
    const fg = graph.current;
    if (!fg || gestartRef.current) return;
    gestartRef.current = true;
    // De eerste engine-stop valt vóór de renderer zijn viewport en camera heeft gezet.
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = requestAnimationFrame(() => {
        if (cameraRef.current) fg.cameraPosition(cameraRef.current.positie, cameraRef.current.doel, 0);
        else {
          fg.cameraPosition({ x: 130, y: 70, z: 430 }, { x: 35, y: 0, z: 0 }, 0);
          pasCameraIn(fg, data.nodes, maat.width, maat.height, 0);
        }
        (fg.controls() as OrbitControls).update();
        frameRef.current = requestAnimationFrame(() => setGereed(true));
      });
    });
  }, [cameraRef, data.nodes, maat]);

  useEffect(() => () => cancelAnimationFrame(frameRef.current), []);

  useEffect(() => {
    const fg = graph.current;
    if (!fg || !gereed) return;
    const controls = fg.controls() as OrbitControls;
    controls.enableDamping = !minderBeweging.current;
    controls.autoRotate = false;
    function onthoud() {
      const positie = fg!.camera().position;
      const doel = controls.target;
      cameraRef.current = { positie: { x: positie.x, y: positie.y, z: positie.z }, doel: { x: doel.x, y: doel.y, z: doel.z } };
    }
    controls.addEventListener("end", onthoud);
    const eerste = () => onInteractieRef.current?.();
    controls.addEventListener("start", eerste);
    const canvas = fg.renderer().domElement;
    const verlies = (event: Event) => { event.preventDefault(); setVerloren(true); };
    canvas.addEventListener("webglcontextlost", verlies);
    return () => {
      onthoud();
      controls.removeEventListener("end", onthoud);
      controls.removeEventListener("start", eerste);
      canvas.removeEventListener("webglcontextlost", verlies);
    };
  }, [gereed, cameraRef]);

  useEffect(() => {
    const fg = graph.current;
    if (!fg || !gereed) return;
    bedieningRef.current = {
      pasIn: () => pasCameraIn(fg, data.nodes, maat.width, maat.height, minderBeweging.current ? 0 : 450),
      // Zoals `focusNode` in de CGM-viewer: vanaf het midden van de kaart door de knoop heen naar buiten.
      focus: (node) => {
        const midden = new Vector3(...(["x", "y", "z"] as const).map((as) => data.nodes.reduce((t, n) => t + n[as], 0) / Math.max(data.nodes.length, 1)) as [number, number, number]);
        const richting = new Vector3(node.x, node.y, node.z).sub(midden);
        if (richting.lengthSq() < 1) richting.set(0.24, 0.16, 1);
        const doel = new Vector3(node.x, node.y, node.z).add(richting.normalize().multiplyScalar(280));
        fg.cameraPosition(doel, node, minderBeweging.current ? 0 : 600);
      },
      // In- of uitzoomen langs de kijklijn naar het huidige draaipunt.
      zoom: (factor) => {
        const controls = fg.controls() as OrbitControls;
        const doel = controls.target.clone();
        const positie = fg.camera().position.clone().sub(doel).multiplyScalar(factor).add(doel);
        fg.cameraPosition(positie, doel, minderBeweging.current ? 0 : 250);
      },
    };
    return () => { bedieningRef.current = null; };
  }, [gereed, bedieningRef, data.nodes, maat]);

  useEffect(() => {
    const fg = graph.current;
    if (!fg || !gereed) return;
    const wissel = () => zichtbaar && !document.hidden ? fg.resumeAnimation() : fg.pauseAnimation();
    wissel();
    document.addEventListener("visibilitychange", wissel);
    return () => document.removeEventListener("visibilitychange", wissel);
  }, [zichtbaar, gereed]);

  // Dimmen alleen met een selectie; zonder selectie (klik op de achtergrond) is alles gelijkwaardig.
  const dim = (id: string) => !!selectie && !buren.has(id);
  const maakObject = useCallback((node: GraafKnoop) => {
    const group = new Group();
    const radius = node.straal;
    const geometry = vormVan(node.soort === "klasse" ? "klasse" : "bol", radius);
    // Een bepaling buiten het geopende artikel is een draadmodel: een verwijzing, nog geen geladen bron.
    const gedimd = !!selectie && !buren.has(node.id);
    const material = new MeshLambertMaterial({ color: node.kleur, transparent: true, wireframe: node.rand,
      opacity: gedimd ? 0.16 : node.rand ? 0.85 : 1 });
    group.add(new Mesh(geometry, material));
    if (node.id === selectie) {
      group.add(new Mesh(vormVan("halo", radius),
        new MeshLambertMaterial({ color: "#007bc7", wireframe: true, transparent: true, opacity: 0.4 })));
    }
    // Vaste labels alleen voor de selectie en haar buren; de rest heeft een tooltip bij hover.
    if (selectie && buren.has(node.id)) {
      const label = new SpriteText(node.kort, 10, "#253c53");
      label.fontFace = "Fira Sans, sans-serif";
      label.backgroundColor = "rgba(255,255,255,0.94)";
      label.padding = [1.5, 3];
      label.borderRadius = 3;
      // Labels blijven 12 schermpixels hoog bij draaien, zoomen en vergroten.
      label.material.sizeAttenuation = false;
      label.material.depthTest = false;
      label.renderOrder = 2;
      const fov = (graph.current?.camera() as PerspectiveCamera | undefined)?.fov ?? 50;
      label.scale.multiplyScalar((2 * Math.tan(fov * Math.PI / 360) * 12) / (Math.max(maat.height, 1) * 10));
      label.position.set(0, -(radius + 9), 0);
      group.add(label);
    }
    return group;
  }, [buren, selectie, maat.height]);
  const raaktSelectie = (edge: RenderLink) => idVan(edge.source) === selectie || idVan(edge.target) === selectie;
  const lijnKleur = (edge: RenderLink) => {
    const lijn = LIJN[edge.soort];
    if (raaktSelectie(edge)) return "#007bc7";
    return dim(idVan(edge.source)) || dim(idVan(edge.target)) ? `rgba(${lijn.rgb},0.08)` : lijn.kleur;
  };

  return <div ref={container} className="relative h-full min-h-0 w-full overflow-hidden" data-testid="graaf-canvas" data-graaf-status={gereed ? "gereed" : "laden"}>
    {!webgl || verloren ? <div role="status" className="flex h-full items-center justify-center p-8 text-center text-sm text-muted">
      <p>{verloren ? "De 3D-weergave is onderbroken." : "Deze browser kan de 3D-weergave niet openen."}<br />Je kunt alle bronnen en markeringen blijven bekijken via de lijst.<br />Herlaad de pagina om 3D opnieuw te proberen.</p>
    </div> : maat.width > 0 && <ForceGraph3D<GraafKnoop, LinkMeta>
      ref={graph} graphData={renderData} width={maat.width} height={maat.height}
      backgroundColor="#f7f9fc" showNavInfo={false} controlType="orbit"
      enableNodeDrag={false} cooldownTicks={0} onEngineStop={klaar}
      nodeThreeObject={maakObject}
      nodeLabel={(node) => tip(node.label, SOORT_LABEL[node.soort] + (node.rand && node.soort !== "extern" ? " · buiten dit artikel" : ""))}
      onNodeClick={(node) => {
        const nu = performance.now();
        if (onDubbelklik && isDubbelklik(vorigeKlik.current, node.id, nu)) { vorigeKlik.current = null; onDubbelklik(node.id); return; }
        vorigeKlik.current = { id: node.id, tijd: nu };
        onSelecteer(node.id);
      }}
      onBackgroundClick={() => onSelecteer("")}
      linkLabel={(edge) => tip(edge.label, edge.anker_tekst ? `“${edge.anker_tekst}”` : "")}
      linkColor={lijnKleur}
      linkWidth={(edge) => LIJN[edge.soort].breedte * (raaktSelectie(edge) ? 1.5 : 1)}
      linkCurvature={(edge) => LIJN[edge.soort].krom}
      linkOpacity={0.75} linkDirectionalArrowLength={4} linkDirectionalArrowRelPos={1}
      linkDirectionalArrowColor={lijnKleur}
      onLinkClick={(edge) => onSelecteer(idVan(edge.target))}
      rendererConfig={{ antialias: true, alpha: false }}
    />}
  </div>;
}
