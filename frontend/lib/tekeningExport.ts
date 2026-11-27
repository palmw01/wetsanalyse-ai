/** Een tekening exporteren als SVG of PNG (*Groot bekijken*, `TekeningVenster`). Het 2c-diagram komt als SVG uit de api
 *  (`GET /v1/annotatie/diagram?vorm=svg`): dezelfde tekening als in het rapport, met echte kleuren in plaats van de
 *  CSS-variabelen van de werkplek. Een PNG maakt de browser zelf, uit die SVG of uit de lagen van de graaf. */
import { downloadBlob } from "@/lib/api";
import { zonderRand } from "./rand";

/** Hoeveel scherper dan het scherm een PNG wordt: goed genoeg om in een document of dia te plakken. */
export const PNG_SCHAAL = 2;

/** Een bestandsnaam zonder vreemde tekens: "diagram-rechtsbetrekking-473c19a14797.svg". */
export function tekeningNaam(delen: string[], formaat: "svg" | "png"): string {
  const stam = zonderRand(delen.join("-").toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-"), "-").slice(0, 80) || "tekening";
  return `${stam}.${formaat}`;
}

/** De SVG van een 2c-diagram rond een centrale markering, zoals de api hem tekent. */
export async function diagramSvg(elementId: string): Promise<string> {
  const r = await fetch(`/api/annotatie/v2/diagram?element_id=${encodeURIComponent(elementId)}&vorm=svg`, { cache: "no-store" });
  if (!r.ok) throw new Error("Het diagram kon niet als SVG worden opgehaald.");
  return r.text();
}

/** Een SVG als PNG op `schaal`, op een witte achtergrond. Als `data:`-URL en niet als `blob:`: het beveiligingsbeleid
 *  van de werkplek staat alleen `data:` toe als bron van een afbeelding (`lib/csp.ts`, `img-src 'self' data:`). */
export async function svgNaarPng(svg: string, schaal = PNG_SCHAAL): Promise<Blob> {
  const bytes = new TextEncoder().encode(svg);
  let binair = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binair += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  const beeld = new Image();
  await new Promise<void>((klaar, mis) => {
    beeld.onload = () => klaar();
    beeld.onerror = () => mis(new Error("De SVG kon niet worden getekend."));
    beeld.src = `data:image/svg+xml;base64,${btoa(binair)}`;
  });
  const doek = document.createElement("canvas");
  doek.width = Math.max(1, Math.round((beeld.naturalWidth || 800) * schaal));
  doek.height = Math.max(1, Math.round((beeld.naturalHeight || 600) * schaal));
  const ctx = doek.getContext("2d");
  if (!ctx) throw new Error("De afbeelding kon niet worden gemaakt.");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, doek.width, doek.height);
  ctx.drawImage(beeld, 0, 0, doek.width, doek.height);
  return alsPng(doek);
}

/** Een canvas als PNG. */
export function alsPng(doek: HTMLCanvasElement): Promise<Blob> {
  return new Promise((klaar, mis) => doek.toBlob((b) => (b ? klaar(b) : mis(new Error("De afbeelding kon niet worden gemaakt."))), "image/png"));
}

/** Download wat er gemaakt is. */
export async function bewaar(maak: () => Promise<Blob | string>, naam: string, type = "image/svg+xml"): Promise<void> {
  const uit = await maak();
  downloadBlob(typeof uit === "string" ? new Blob([uit], { type: `${type};charset=utf-8` }) : uit, naam);
}
