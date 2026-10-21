import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Safari (iOS) rekent de minimale breedte van een omslaande flexrij als één regel. In een raster zonder
// expliciete kolom werd een kaart daardoor breder dan het scherm (de kaart liep rechts uit beeld). Een
// expliciete kolom (`grid-cols-1` = `minmax(0, 1fr)`) en `min-w-0` op de kaart houden hem binnen de
// breedte. Chromium heeft het probleem niet, dus de browsertests zien het niet: vandaar deze bron-toets.
const lees = (pad: string) => readFileSync(join(__dirname, "..", pad), "utf8");

describe("overzichten blijven binnen de schermbreedte", () => {
  it.each(["annotaties/AnnotatiesClient.tsx", "werkgebieden/WerkgebiedenClient.tsx", "begrippen/BegrippenOverzichtClient.tsx"])(
    "%s zet elk kaartenraster op een expliciete kolom", (pad) => {
      const rasters = lees(pad).match(/className="grid [^"]*"/g) ?? [];
      expect(rasters.length).toBeGreaterThan(0);
      for (const r of rasters) expect(r).toContain("grid-cols-1");
    });

  it.each(["annotaties/AnnotatieKaart.tsx", "werkgebieden/WerkgebiedKaart.tsx", "begrippen/BegripOverzichtKaart.tsx"])(
    "%s mag krimpen (min-w-0)", (pad) => {
      expect(lees(pad)).toMatch(/<article[^>]*className="flex min-w-0 /s);
    });
});
