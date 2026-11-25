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
