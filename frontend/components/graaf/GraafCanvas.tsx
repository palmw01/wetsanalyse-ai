"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import ForceGraph3D, { type ForceGraphMethods, type LinkObject } from "react-force-graph-3d";
import { Group, Mesh, MeshLambertMaterial, OctahedronGeometry, SphereGeometry, Vector3, type PerspectiveCamera } from "three";
import SpriteText from "three-spritetext";
import type { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { GraafData, GraafKnoop, GraafRelatie } from "@/lib/samenhang";

type LinkMeta = Omit<GraafRelatie, "source" | "target">;
type RenderLink = LinkObject<GraafKnoop, LinkMeta>;
type Punt = { x: number; y: number; z: number };
export type CameraStand = { positie: Punt; doel: Punt };
export interface GraafCameraBediening { pasIn: () => void; focus: (node: GraafKnoop) => void }

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
    afstand = Math.max(afstand, (Math.abs(p.dot(rechts)) + 95) / tanX + p.dot(richting), (Math.abs(p.dot(boven)) + 30) / tanY + p.dot(richting));
  }
  const positie = midden.clone().add(richting.multiplyScalar(afstand * 1.12));
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

const idVan = (value: RenderLink["source"]): string => typeof value === "object" ? String(value.id) : String(value);

export function GraafCanvas({ data, selectie, onSelecteer, camera: cameraRef, bediening: bedieningRef, zichtbaar }: {
  data: GraafData; selectie: string; onSelecteer: (id: string) => void;
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
    const canvas = fg.renderer().domElement;
    const verlies = (event: Event) => { event.preventDefault(); setVerloren(true); };
    canvas.addEventListener("webglcontextlost", verlies);
    return () => {
      onthoud();
      controls.removeEventListener("end", onthoud);
      canvas.removeEventListener("webglcontextlost", verlies);
    };
  }, [gereed, cameraRef]);

  useEffect(() => {
    const fg = graph.current;
    if (!fg || !gereed) return;
    bedieningRef.current = {
      pasIn: () => pasCameraIn(fg, data.nodes, maat.width, maat.height, minderBeweging.current ? 0 : 450),
      focus: (node) => fg.cameraPosition({ x: node.x + 45, y: node.y + 35, z: node.z + 230 }, node, minderBeweging.current ? 0 : 450),
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

  const maakObject = useCallback((node: GraafKnoop) => {
    const group = new Group();
    const gekozen = node.id === selectie;
    const radius = node.rand ? 4.5 : node.soort === "regeling" ? 9 : node.soort === "artikel" ? 8 : node.soort === "lid" ? 7 : 5.5;
    const geometry = node.soort === "klasse" ? new OctahedronGeometry(radius * 1.2) : new SphereGeometry(radius, 18, 12);
    // Een bepaling buiten het geopende artikel is gedempt en als draadmodel: hij is een verwijzing,
    // nog geen geladen bron.
    const material = new MeshLambertMaterial({ color: node.kleur, transparent: true, wireframe: node.rand,
      opacity: node.rand ? 0.7 : buren.has(node.id) ? 1 : 0.65 });
    group.add(new Mesh(geometry, material));
    if (gekozen) {
      const ring = new Mesh(new SphereGeometry(radius + 2.3, 20, 14), new MeshLambertMaterial({ color: "#007bc7", wireframe: true, transparent: true, opacity: 0.35 }));
      group.add(ring);
    }
    if (buren.has(node.id) || (node.soort !== "markering" && !node.rand)) {
      const label = new SpriteText(node.kort, 10, "#253c53");
      label.fontFace = "Fira Sans, sans-serif";
      label.backgroundColor = "rgba(255,255,255,0.92)";
      label.padding = [1, 2];
      label.borderRadius = 2;
      // Labels blijven 12 schermpixels hoog bij draaien, zoomen en vergroten.
      label.material.sizeAttenuation = false;
      const fov = (graph.current?.camera() as PerspectiveCamera | undefined)?.fov ?? 50;
      label.scale.multiplyScalar((2 * Math.tan(fov * Math.PI / 360) * 12) / (Math.max(maat.height, 1) * 10));
      label.position.set(0, -(radius + 10), 0);
      group.add(label);
    }
    return group;
  }, [buren, selectie, maat.height]);
  const raaktSelectie = (edge: RenderLink) => idVan(edge.source) === selectie || idVan(edge.target) === selectie;

  return <div ref={container} className="relative h-full min-h-0 w-full overflow-hidden" data-testid="graaf-canvas" data-graaf-status={gereed ? "gereed" : "laden"}>
    {!webgl || verloren ? <div role="status" className="flex h-full items-center justify-center p-8 text-center text-sm text-muted">
      <p>{verloren ? "De 3D-weergave is onderbroken." : "Deze browser kan de 3D-weergave niet openen."}<br />Je kunt alle bronnen en markeringen blijven bekijken via de lijst.<br />Herlaad de pagina om 3D opnieuw te proberen.</p>
    </div> : maat.width > 0 && <ForceGraph3D<GraafKnoop, LinkMeta>
      ref={graph} graphData={renderData} width={maat.width} height={maat.height}
      backgroundColor="#f7f9fc" showNavInfo={false} controlType="orbit"
      enableNodeDrag={false} cooldownTicks={0} onEngineStop={klaar}
      nodeThreeObject={maakObject} nodeLabel={() => ""}
      onNodeClick={(node) => onSelecteer(node.id)}
      linkLabel={() => ""}
      linkColor={(edge) => raaktSelectie(edge) ? "#007bc7" : edge.groep === "verwijzingen" ? "#6b4e91" : "#acbccb"}
      linkWidth={(edge) => raaktSelectie(edge) ? 1.3 : 0.45}
      linkOpacity={0.8} linkDirectionalArrowLength={3.5} linkDirectionalArrowRelPos={0.83}
      onLinkClick={(edge) => onSelecteer(idVan(edge.target))}
      rendererConfig={{ antialias: true, alpha: false }}
    />}
  </div>;
}
