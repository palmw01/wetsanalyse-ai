import { describe, expect, it } from "vitest";
import { gevolgVoorWerkplek } from "./gesprekkenGewijzigd";
import { aantalGesprekken, bevestigVerwijderen, uitkomstZin } from "./gesprekkenOpruimen";
import { INSTELLINGEN_TABS, isAdminTab, tabUitParam } from "./instellingen";

describe("gesprekken opruimen", () => {
  it("telt in gewone taal", () => {
    expect(aantalGesprekken(0)).toBe("Geen gesprekken");
    expect(aantalGesprekken(1)).toBe("1 gesprek");
    expect(bevestigVerwijderen(71)).toBe("71 gesprekken verwijderen?");
    expect(uitkomstZin("verwijderd", 71)).toBe("71 gesprekken verwijderd.");
    expect(uitkomstZin("gearchiveerd", 1)).toBe("1 gesprek gearchiveerd.");
    expect(uitkomstZin("verwijderd", 0)).toBe("Er was niets te verwijderen.");
  });

  it("sluit het open gesprek alleen als het verwijderd is", () => {
    expect(gevolgVoorWerkplek({ soort: "verwijderd", ids: ["a", "b"] }, "b")).toEqual({ sluit: true });
    expect(gevolgVoorWerkplek({ soort: "verwijderd", ids: ["a"] }, "b")).toEqual({ sluit: false });
    expect(gevolgVoorWerkplek({ soort: "gearchiveerd", ids: ["b"] }, "b")).toEqual({ sluit: false });
    expect(gevolgVoorWerkplek({ soort: "verwijderd", ids: ["b"] }, null)).toEqual({ sluit: false });
  });

  it("heeft een eigen tab Gesprekken, voor iedereen, na Verbruik", () => {
    const keys = INSTELLINGEN_TABS.map((t) => t.key);
    expect(keys.indexOf("gesprekken")).toBe(keys.indexOf("verbruik") + 1);
    expect(isAdminTab("gesprekken")).toBe(false);
    expect(tabUitParam("gesprekken")).toBe("gesprekken");
  });
});
