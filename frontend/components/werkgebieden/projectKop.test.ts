import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const bron = (pad: string) => readFileSync(new URL(pad, import.meta.url), "utf8");

describe("de PDF van het werkgebied", () => {
  it("staat in de kop van het werkgebied", () => {
    expect(bron("./ProjectKop.tsx")).toMatch(/<ExportKnop [^\n]*formaten=\{WERKGEBIED_EXPORT_FORMATEN\}\s+onDownload=\{\(\) => exporteerWerkgebied\(wg\.id\)\}/);
  });

  it("staat in het paneel naast het gesprek, maar niet op een oude versie", () => {
    const paneel = bron("../werkplek/WerkgebiedArtefactPaneel.tsx");
    expect(paneel).toMatch(/formaten: WERKGEBIED_EXPORT_FORMATEN, onDownload: \(\) => exporteerWerkgebied\(id\)/);
    const opname = paneel.slice(paneel.indexOf("if (opname) {"), paneel.indexOf("switch (doel.soort) {\n    case \"werkgebied\":"));
    expect(opname).not.toContain("WERKGEBIED_EXPORT_FORMATEN");
  });
});
