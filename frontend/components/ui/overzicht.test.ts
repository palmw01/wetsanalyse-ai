import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Safari (iOS) rekent de minimale breedte van een omslaande flexrij als één regel. In een raster zonder
// expliciete kolom werd een kaart daardoor breder dan het scherm (de kaart liep rechts uit beeld). Een
// expliciete kolom (`grid-cols-1` = `minmax(0, 1fr)`) en `min-w-0` op de kaart houden hem binnen de
// breedte. Chromium heeft het probleem niet, dus de browsertests zien het niet: vandaar deze bron-toets.
const lees = (pad: string) => readFileSync(join(__dirname, "..", pad), "utf8");

const KAARTEN = ["annotaties/AnnotatieKaart.tsx", "werkgebieden/WerkgebiedKaart.tsx", "begrippen/BegripOverzichtKaart.tsx"];
const OVERZICHTEN = ["annotaties/AnnotatiesClient.tsx", "werkgebieden/WerkgebiedenClient.tsx", "begrippen/BegrippenOverzichtClient.tsx"];

describe("overzichten blijven binnen de schermbreedte", () => {
  it("het raster van een overzicht heeft een expliciete kolom", () => {
    const pagina = lees("ui/Pagina.tsx");
    const raster = pagina.slice(pagina.indexOf("export function OverzichtRaster"), pagina.indexOf("export function OverzichtSkelet"));
    expect(raster).toMatch(/className="grid grid-cols-1 /);
  });

  it.each(OVERZICHTEN)("%s zet zijn kaarten in OverzichtRaster, zonder eigen raster", (pad) => {
    const s = lees(pad);
    expect(s).toMatch(/<OverzichtRaster\b/);
    expect(s).not.toMatch(/className="grid /);
  });

  it("de overzichtskaart mag krimpen (min-w-0)", () => {
    const pagina = lees("ui/Pagina.tsx");
    const kaart = pagina.slice(pagina.indexOf("export function OverzichtKaart"), pagina.indexOf("export function OverzichtRaster"));
    expect(kaart).toMatch(/<article[^>]*className=\{`\$\{KLIK_KAART\} flex min-w-0 /s);
  });

  it.each(KAARTEN)("%s is een OverzichtKaart", (pad) => {
    expect(lees(pad)).toMatch(/<OverzichtKaart\b/);
  });
});
