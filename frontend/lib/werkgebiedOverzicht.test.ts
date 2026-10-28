import { describe, expect, it } from "vitest";

import type { WerkgebiedSamenvatting } from "./types";
import { metStatus, perStatus, statusUitParam, zoek } from "./werkgebiedOverzicht";

const wg = (id: string, naam: string, status: WerkgebiedSamenvatting["status"], over: Partial<WerkgebiedSamenvatting> = {}) =>
  ({ id, naam, status, analysevraag: "", afbakening: "", peildatum: null, revisie: 1, aangemaakt_door: "t",
    aangemaakt: "", gewijzigd: "", gearchiveerd: null, ...over }) as WerkgebiedSamenvatting;

const LIJST = [wg("a", "Invorderbaarheid", "actief", { analysevraag: "Wanneer is een aanslag invorderbaar?" }),
  wg("b", "Bezwaar", "in_voorbereiding", { context: "Ontvankelijkheid van het bezwaarschrift" }),
  wg("c", "Box 3", "actief")];

describe("werkgebiedOverzicht", () => {
  it("zoekt in naam, analysevraag en context, zonder hoofdletters en diakrieten", () => {
    expect(zoek(LIJST, "aanslag").map((w) => w.id)).toEqual(["a"]);
    expect(zoek(LIJST, "ONTVANKELIJKHÉID bezwaar").map((w) => w.id)).toEqual(["b"]);
    expect(zoek(LIJST, "  ")).toHaveLength(3);
  });

  it("telt per status en filtert erop", () => {
    expect(perStatus(LIJST)).toEqual({ alle: 3, in_voorbereiding: 1, actief: 2, afgerond: 0 });
    expect(metStatus(LIJST, "actief").map((w) => w.id)).toEqual(["a", "c"]);
    expect(metStatus(LIJST, "alle")).toHaveLength(3);
  });

  it("leest de status uit de URL; onzin is alle", () => {
    expect(statusUitParam("afgerond")).toBe("afgerond");
    expect(statusUitParam("gearchiveerd")).toBe("alle");
    expect(statusUitParam(null)).toBe("alle");
  });
});
