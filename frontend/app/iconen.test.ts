import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import sharp from "sharp";
import { describe, expect, it } from "vitest";

import { LEX_MERK_MARKERING, LEX_MERK_RADIUS, LEX_MERK_REGELS } from "@/components/ui/LexMerk";

import manifest from "./manifest";

// Het beeldmerk van Lex en de iconen die er uit `npm run iconen` van komen (bron: merk/lex-merk.svg).
// Wat hier vastligt: de formaten die browsers en besturingssystemen vragen, geen font of beeld in een SVG,
// één themakleur, en dat het oude Rijkswapen en het Belastingdienst-logo niet terugkomen.

const ROOT = join(__dirname, "..");
const pad = (p: string) => join(ROOT, p);
const tekst = (p: string) => readFileSync(pad(p), "utf8");

/** Breedte, hoogte en kleurtype uit de IHDR-chunk van een PNG. */
function ihdr(buf: Buffer) {
  expect(buf.subarray(1, 4).toString("latin1")).toBe("PNG");
  return { breedte: buf.readUInt32BE(16), hoogte: buf.readUInt32BE(20), kleurtype: buf.readUInt8(25) };
}
const MET_ALFA = new Set([4, 6]);

const rechthoeken = (svg: string) =>
  [...svg.matchAll(/<rect[^>]*? x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"/g)].map((m) => m.slice(1).map(Number));

describe("de iconen van Lex", () => {
  it("staan er in de formaten die browsers, iOS en Android vragen", () => {
    const maten: [string, number][] = [
      ["app/apple-icon.png", 180],
      ["public/icons/icon-192.png", 192],
      ["public/icons/icon-512.png", 512],
      ["public/icons/icon-maskable-512.png", 512],
    ];
    for (const [p, px] of maten) {
      const { breedte, hoogte } = ihdr(readFileSync(pad(p)));
      expect([breedte, hoogte], p).toEqual([px, px]);
    }
    // favicon.ico: 16, 32 en 48, elk als PNG
    const ico = readFileSync(pad("app/favicon.ico"));
    expect(ico.readUInt16LE(2)).toBe(1);
    const aantal = ico.readUInt16LE(4);
    const ingangen = Array.from({ length: aantal }, (_, i) => {
      const o = 6 + 16 * i;
      const data = ico.subarray(ico.readUInt32LE(o + 12), ico.readUInt32LE(o + 12) + ico.readUInt32LE(o + 8));
      return { px: ico.readUInt8(o), png: ihdr(data) };
    });
    expect(ingangen.map((i) => i.px)).toEqual([16, 32, 48]);
    for (const i of ingangen) expect(i.png.breedte).toBe(i.px);
  });

  it("het apple-icon en het maskable-icoon zijn opaak (anders zet iOS er een zwarte rand omheen)", () => {
    for (const p of ["app/apple-icon.png", "public/icons/icon-maskable-512.png"])
      expect(MET_ALFA.has(ihdr(readFileSync(pad(p))).kleurtype), p).toBe(false);
  });

  it("het maskable-icoon houdt het merk binnen de veilige zone (cirkel van 80 %) en vult het vlak tot de rand", async () => {
    const { data, info } = await sharp(pad("public/icons/icon-maskable-512.png")).raw().toBuffer({ resolveWithObject: true });
    const px = (x: number, y: number) => {
      const o = (y * info.width + x) * info.channels;
      return [data[o], data[o + 1], data[o + 2]];
    };
    const vlak = px(0, 0);
    expect(vlak).toEqual([0x15, 0x42, 0x73]);
    for (const [x, y] of [[511, 0], [0, 511], [511, 511], [256, 0], [0, 256]]) expect(px(x, y)).toEqual(vlak);
    const straal = 0.4 * info.width;
    let buiten = 0;
    for (let y = 0; y < info.height; y++)
      for (let x = 0; x < info.width; x++) {
        const [r, g, b] = px(x, y);
        const isVlak = Math.abs(r - vlak[0]) + Math.abs(g - vlak[1]) + Math.abs(b - vlak[2]) < 6;
        if (!isVlak && Math.hypot(x + 0.5 - 256, y + 0.5 - 256) > straal) buiten++;
      }
    expect(buiten).toBe(0);
  });

  it("de SVG's dragen geen font, geen beeld en geen externe verwijzing; de favicon heeft een donkere stand", () => {
    for (const p of ["app/icon.svg", "merk/lex-merk.svg", "merk/lex-merk-mono.svg"]) {
      const svg = tekst(p);
      expect(svg, p).not.toMatch(/<text|<image|font-family|@font-face|href=|url\(/);
    }
    expect(tekst("app/icon.svg")).toMatch(/@media \(prefers-color-scheme:\s*dark\)/);
  });

  it("het component tekent dezelfde rechthoeken als de bron", () => {
    const svg = tekst("merk/lex-merk.svg");
    expect(rechthoeken(svg)).toEqual([...LEX_MERK_REGELS.map((r) => [...r]), [...LEX_MERK_MARKERING]]);
    expect(svg).toMatch(new RegExp(`rx="${LEX_MERK_RADIUS}"`));
    // de gegenereerde favicon is bij de bron (draai `npm run iconen` na een wijziging)
    expect(rechthoeken(tekst("app/icon.svg"))).toEqual(rechthoeken(svg));
    // even maten: op 16 px valt alles op hele pixels
    for (const r of rechthoeken(svg)) for (const v of r) expect(v % 2, `${r}`).toBe(0);
  });

  it("het manifest noemt 192, 512 en maskable, met dezelfde themakleur als de viewport en het token --lint", () => {
    const m = manifest();
    const iconen = m.icons ?? [];
    expect(iconen.map((i) => `${i.sizes}:${i.purpose}`)).toEqual(["192x192:any", "512x512:any", "512x512:maskable"]);
    for (const i of iconen) expect(existsSync(pad(`public${i.src}`)), i.src).toBe(true);
    expect(m.short_name).toBe("Lex");

    const lint = tekst("app/globals.css").match(/--lint:\s*(\d+) (\d+) (\d+);/)!.slice(1).map(Number);
    const hex = "#" + lint.map((c) => c.toString(16).padStart(2, "0")).join("");
    expect(m.theme_color?.toLowerCase()).toBe(hex);
    expect(tekst("app/layout.tsx")).toMatch(new RegExp(`themeColor: "${hex}"`, "i"));
  });

  it("de iconen komen uit de bestandsconventies, niet uit een eigen lijst in de layout", () => {
    const layout = tekst("app/layout.tsx");
    expect(layout).not.toMatch(/\bicons:/);
    expect(layout).not.toMatch(/manifest:/);
  });

  it("het Rijkswapen en het Belastingdienst-logo komen niet terug; de app stelt zich voor met LexLogo", () => {
    for (const oud of [
      "public/favicon.ico", "public/favicon.svg", "public/favicon-16.png", "public/favicon-32.png",
      "public/favicon-48.png", "public/favicon-192.png", "public/favicon-512.png",
      "public/apple-touch-icon.png", "public/manifest.webmanifest", "public/belastingdienst-logo.svg",
    ])
      expect(existsSync(pad(oud)), oud).toBe(false);
    // besluit gebruiker 7 nov 2026: het logo van Lex vervangt het Belastingdienst-logo op elke plek
    for (const p of ["components/werkplek/GesprekSidebar.tsx", "components/auth/AuthFrame.tsx"]) {
      expect(tekst(p), p).toMatch(/<LexLogo\b/);
      expect(tekst(p), p).not.toMatch(/belastingdienst-logo/);
    }
    expect(tekst("app/layout.tsx")).not.toMatch(/\| Belastingdienst/);
  });
});
