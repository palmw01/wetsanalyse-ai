import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { INSTELLINGEN_TABS, instellingenOpWerkplek, isAdminTab, tabUitPad, tabUitParam } from "./instellingen";

const WORTEL = join(__dirname, "..");
const lees = (p: string) => readFileSync(join(WORTEL, p), "utf8");

/** Is dit bestand een client component? Kijkt naar de *directive* op de eerste zinvolle regel, niet
 *  naar de tekst ergens in het bestand – anders telt een toelichting die "use client" noemt al mee. */
function isClientComponent(src: string): boolean {
  const eerste = src.split("\n").find((r) => r.trim() !== "");
  return /^["']use client["'];?$/.test((eerste ?? "").trim());
}

describe("tabUitPad", () => {
  it("leest de tab uit de padsegmenten", () => {
    expect(tabUitPad(["account"])).toBe("account");
    expect(tabUitPad(["beheer", "gebruikers"])).toBe("gebruikers");
    expect(tabUitPad(["beheer", "registraties"])).toBe("registraties");
  });

  it("valt terug op account bij leeg of onbekend", () => {
    expect(tabUitPad(undefined)).toBe("account");
    expect(tabUitPad([])).toBe("account");
    expect(tabUitPad(["bestaat", "niet"])).toBe("account");
  });
});

describe("tabUitParam", () => {
  it("zonder parameter is het venster dicht", () => {
    expect(tabUitParam(null)).toBeNull();
    expect(tabUitParam(undefined)).toBeNull();
  });

  it("leest de sleutel, ook een oud pad, en opent een onbekende waarde op account", () => {
    expect(tabUitParam("gebruikers")).toBe("gebruikers");
    expect(tabUitParam("beheer/gebruikers")).toBe("gebruikers");
    expect(tabUitParam("bestaat-niet")).toBe("account");
    expect(tabUitParam("")).toBe("account");
  });
});

describe("instellingenOpWerkplek", () => {
  it("een oude link opent het venster op de werkplek, en elke sleutel leest terug", () => {
    expect(instellingenOpWerkplek("verbruik")).toBe("/workbench?instellingen=verbruik");
    for (const tab of INSTELLINGEN_TABS) {
      const waarde = new URL(instellingenOpWerkplek(tab.key), "http://x").searchParams.get("instellingen");
      expect(tabUitParam(waarde)).toBe(tab.key);
    }
  });
});

describe("isAdminTab", () => {
  it("markeert alleen de beheer-tabs", () => {
    expect(isAdminTab("account")).toBe(false);
    expect(isAdminTab("beveiliging")).toBe(false);
    expect(isAdminTab("berichten")).toBe(false);
    expect(isAdminTab("verbruik")).toBe(false);
    for (const t of [
      "modelprofielen",
      "gebruikers",
      "registraties",
      "api-tokens",
      "berichtenbeheer",
      "feedback",
    ] as const) {
      expect(isAdminTab(t)).toBe(true);
    }
  });

  // De rolgate in auth.config.ts is één prefix-check op /instellingen/beheer. Een admin-tab die
  // buiten dat pad gaat wonen, is dus onbewaakt: de tabkolom verbergt hem wel voor een analist,
  // maar de directe URL komt er ongehinderd door. Daarom hier de koppeling zelf bewaken in plaats
  // van een lijstje tabnamen – die veroudert bij elke nieuwe tab.
  it("elke admin-tab staat onder beheer/ (anders valt de rolgate weg)", () => {
    for (const tab of INSTELLINGEN_TABS) {
      expect(tab.admin, `tab '${tab.key}' (pad '${tab.pad}')`).toBe(tab.pad.startsWith("beheer/"));
    }
  });

  it("auth.config.ts bewaakt die prefix nog steeds", () => {
    expect(lees("auth.config.ts")).toContain('path.startsWith("/instellingen/beheer")');
  });
});

// Deze helpers worden vanuit server components aangeroepen (de rolgate op beide instellingen-routes).
// Staan ze in een "use client"-module, dan compileert en lint het prima maar crasht de route pas bij
// het renderen: "Attempted to call tabUitPad() from the server but tabUitPad is on the client".
// Die grens is alleen met een structuurcontrole te bewaken.
describe("RSC-grens", () => {
  it("de gedeelde module is niet client-only", () => {
    expect(isClientComponent(lees("lib/instellingen.ts"))).toBe(false);
  });

  it("de doorverwijzing haalt de helpers uit de gedeelde module", () => {
    const src = lees("app/instellingen/[[...tab]]/page.tsx");
    expect(isClientComponent(src)).toBe(false);
    expect(src).toMatch(/import \{[^}]*tabUitPad[^}]*\} from "@\/lib\/instellingen"/);
  });
});

// Het venster is een pop-up over de pagina waar je bent, nooit een eigen pagina. Een gewone link naar `/instellingen`
// zou weer een paginawissel worden (en is nu een doorverwijzing naar de werkplek): links gaan via `InstellingenLink`.
describe("altijd een pop-up", () => {
  it("geen gewone link naar /instellingen in de app", () => {
    const treffers = execSync(`grep -rlE 'href="/instellingen' components app || true`, { cwd: process.cwd() }).toString().trim();
    expect(treffers).toBe("");
  });

  it("geen onderschepte route meer die een tweede vorm van het venster maakt", () => {
    expect(() => lees("app/@modal/(.)instellingen/[[...tab]]/page.tsx")).toThrow();
  });
});
