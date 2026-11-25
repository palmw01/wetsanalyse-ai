import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { PLUGINS } from "./plugins";

// De bron van de spiegel: `bronmodel/plugins.py`.
const bron = readFileSync(new URL("../../packages/bronmodel/bronmodel/plugins.py", import.meta.url), "utf8");

describe("de spiegel van bronmodel/plugins.py", () => {
  it("kent dezelfde plugins met dezelfde velden", () => {
    const blokken = [...bron.matchAll(/^\w+ = Plugin\(([\s\S]*?)^\)/gm)].map((m) =>
      Object.fromEntries([...m[1].matchAll(/(\w+)="([^"]*)"/g)].map((x) => [x[1], x[2]])));
    expect(blokken.map((b) => b.naam)).toEqual(PLUGINS.map((p) => p.naam));
    for (const p of PLUGINS) {
      const { hulp: _hulp, ...velden } = p;
      expect(blokken.find((b) => b.naam === p.naam)).toEqual(velden);
    }
  });
});

import { actievePlugins, beurtPlugins, parsePlugins, wisselPlugin } from "./plugins";

const CT = { naam: "contenttoets", label: "Contenttoets", beschrijving: "", commando: "contenttoets" };

describe("de pluginstand van een gesprek", () => {
  it("zonder eigen keuze staat aan wat de beheerder aanbiedt", () => {
    expect(actievePlugins({ aangeboden: [CT], gesprek: null })).toEqual(["contenttoets"]);
    expect(actievePlugins({ aangeboden: [], gesprek: ["contenttoets"] })).toEqual([]);
  });

  it("een keuze van het gesprek gaat voor, en wisselen zet hem om", () => {
    expect(actievePlugins({ aangeboden: [CT], gesprek: [] })).toEqual([]);
    expect(wisselPlugin({ aangeboden: [CT], gesprek: null }, "contenttoets")).toEqual([]);
    expect(wisselPlugin({ aangeboden: [CT], gesprek: [] }, "contenttoets")).toEqual(["contenttoets"]);
    expect(wisselPlugin({ aangeboden: [CT], gesprek: [] }, "onbekend")).toEqual([]);
  });

  it("de beurt draagt de stand alleen als er iets aangeboden is", () => {
    expect(beurtPlugins({ aangeboden: [], gesprek: null })).toEqual({});
    expect(beurtPlugins({ aangeboden: [CT], gesprek: [] })).toEqual({ plugins: [] });
  });

  it("leest streng wat de BFF teruggaf", () => {
    expect(parsePlugins({ plugins: [CT, { naam: "onbekend", label: "x" }, { label: "zonder naam" }] })).toEqual([CT]);
    expect(parsePlugins([])).toEqual([]);
    expect(parsePlugins(null)).toEqual([]);
  });
});
