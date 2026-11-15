import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { aanpassingPad, onderdeelPad, tabVoorSoort, werkwijzeDoorverwijzing } from "./aanpassingen";
import { SOORTEN } from "./catalogus";
import { INSTELLINGEN_TABS, tabUitParam } from "./instellingen";

const WORTEL = join(__dirname, "..");
const params = (pad: string) => new URL(pad, "http://x").searchParams;

describe("tabVoorSoort", () => {
  it("elke soort van de catalogus heeft een tab die bestaat (een nieuwe soort in het bronmodel moet hier een plek krijgen)", () => {
    const tabs = INSTELLINGEN_TABS.map((t) => t.key as string);
    for (const s of SOORTEN) expect(tabs, s).toContain(tabVoorSoort(s));
  });

  it("methodes en rollen bij Methodes, agentprofielen bij Agents, connectors bij Connectors", () => {
    expect(tabVoorSoort("methode")).toBe("methodes");
    expect(tabVoorSoort("rol")).toBe("methodes");
    expect(tabVoorSoort("agentprofiel")).toBe("agents");
    expect(tabVoorSoort("connector")).toBe("connectors");
    expect(tabVoorSoort("workflow")).toBe("agents");
  });
});

describe("de doorverwijzing van de werkwijze", () => {
  it("een onderdeel met een eigen plek opent open in zijn tab", () => {
    const p = params(werkwijzeDoorverwijzing("methode", "wetsanalyse"));
    expect(p.get("instellingen")).toBe("methodes");
    expect(p.get("onderdeel")).toBe("methode/wetsanalyse");
    expect(params(werkwijzeDoorverwijzing("rol", "duiding")).get("onderdeel")).toBe("rol/duiding");
    expect(params(werkwijzeDoorverwijzing("agentprofiel", "definitie")).get("instellingen")).toBe("agents");
  });

  it("wat niet meer in de app staat (ketens, routes, controles) opent Agents zonder onderdeel", () => {
    for (const soort of ["workflow", "route", "controle", "tool", "regelset", "agent", "sjabloon"]) {
      const p = params(werkwijzeDoorverwijzing(soort, "x"));
      expect(p.get("instellingen"), soort).toBe("agents");
      expect(p.get("onderdeel"), soort).toBeNull();
    }
    expect(werkwijzeDoorverwijzing("onzin", "x")).toBe(aanpassingPad("agents"));
    expect(werkwijzeDoorverwijzing(undefined, undefined)).toBe("/workbench?instellingen=agents");
  });

  it("onderdeelPad geeft hetzelfde als de doorverwijzing, en het venster leest de tab terug", () => {
    expect(onderdeelPad("agentprofiel/definitie")).toBe(werkwijzeDoorverwijzing("agentprofiel", "definitie"));
    expect(onderdeelPad("onzin")).toBe(aanpassingPad("agents"));
    expect(tabUitParam(params(onderdeelPad("methode/wetsanalyse")).get("instellingen"))).toBe("methodes");
  });

  it("de pagina's onder /werkwijze zijn alleen nog doorverwijzingen", () => {
    for (const f of ["app/werkwijze/page.tsx", "app/werkwijze/[soort]/[naam]/page.tsx", "app/werkwijze/concepten/[id]/page.tsx"]) {
      const src = readFileSync(join(WORTEL, f), "utf8");
      expect(src, f).toContain("redirect(");
      expect(src, f).not.toMatch(/^["']use client["']/);
    }
  });
});

describe("de werkwijze is weg", () => {
  it("geen component, sidebaritem of link naar /werkwijze meer", () => {
    expect(() => readFileSync(join(WORTEL, "components/werkwijze/WerkwijzeClient.tsx"))).toThrow();
    const treffers = execSync(`grep -rlE '"/werkwijze|/werkwijze/' components lib --include=*.tsx --include=*.ts || true`, { cwd: WORTEL })
      .toString().trim().split("\n").filter((f) => f && !f.endsWith(".test.ts") && f !== "lib/aanpassingen.ts");
    expect(treffers).toEqual([]);
  });
});
