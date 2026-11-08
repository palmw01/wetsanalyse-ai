import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const bron = (pad: string) => readFileSync(new URL(pad, import.meta.url), "utf8");

describe("de PDF van het werkgebied", () => {
  it("staat in de kop van het werkgebied", () => {
    expect(bron("./ProjectKop.tsx")).toMatch(/<ExportKnop [^\n]*formaten=\{WERKGEBIED_EXPORT_FORMATEN\}\s+onDownload=\{\(f, o\) => exporteerWerkgebied\(wg\.id, f, o\)\} voorstellenKeuze/);
  });

  it("staat in het paneel naast het gesprek, maar niet op een oude versie", () => {
    const paneel = bron("../werkplek/WerkgebiedArtefactPaneel.tsx");
    expect(paneel).toMatch(/formaten: WERKGEBIED_EXPORT_FORMATEN, onDownload: \(f, o\) => exporteerWerkgebied\(id, f, o\), voorstellenKeuze: true/);
    const opname = paneel.slice(paneel.indexOf("if (opname) {"), paneel.indexOf("switch (doel.soort) {\n    case \"werkgebied\":"));
    expect(opname).not.toContain("WERKGEBIED_EXPORT_FORMATEN");
  });

  it("vraagt standaard alleen wat een jurist beoordeelde (WA TRM H1, 8 nov 2026)", () => {
    const api = bron("../../lib/api.ts");
    expect(api).toMatch(/inhoud: opties\?\.metVoorstellen \? "alles" : "beoordeeld"/);
    expect(bron("../werkplek/ExportKnop.tsx")).toContain("Met de voorstellen van Lex");
  });
});
