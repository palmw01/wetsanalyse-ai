import { describe, expect, it } from "vitest";

import type { ThreadItem } from "./threadItem";
import { afgehandeld, parseBevestiging, parseBevestigingKeuze } from "./werkgebiedAnnoteren";

describe("parseBevestiging", () => {
  it("neemt een geldige bevestiging over", () => {
    expect(parseBevestiging({ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 3, schatting: 9000 }))
      .toEqual({ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 3, schatting: 9000 });
    expect(parseBevestiging({ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 3 })?.schatting).toBeNull();
  });
  it("kent ook het meedenken over de begrippen (fase C)", () => {
    expect(parseBevestiging({ soort: "begrippen_verdiepen", werkgebied_id: "wg1", aantal: 4, schatting: null }))
      .toEqual({ soort: "begrippen_verdiepen", werkgebied_id: "wg1", aantal: 4, schatting: null });
  });
  it("houdt het bereik van de deelvragen vast (de knop annoteert na herladen hetzelfde)", () => {
    const basis = { soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 3, schatting: null };
    expect(parseBevestiging({ ...basis, bereik: "deelvragen", deelvraag_id: "" }))
      .toEqual({ ...basis, bereik: "deelvragen" });
    expect(parseBevestiging({ ...basis, bereik: "deelvragen", deelvraag_id: "dv-2" }))
      .toEqual({ ...basis, bereik: "deelvragen", deelvraag_id: "dv-2" });
    // Het hele werkgebied, of een onbekend bereik: geen bereik, zoals een oud bericht.
    expect(parseBevestiging({ ...basis, bereik: "werkgebied", deelvraag_id: "" })).toEqual(basis);
    expect(parseBevestiging({ ...basis, bereik: "alles", deelvraag_id: "dv-2" })).toEqual(basis);
    expect(parseBevestiging({ ...basis, bereik: "deelvragen", deelvraag_id: "../x" })).toEqual({ ...basis, bereik: "deelvragen" });
  });
  it.each([
    [null], [{}], [{ soort: "iets", werkgebied_id: "wg1", aantal: 1 }],
    [{ soort: "werkgebied_annoteren", werkgebied_id: "", aantal: 1 }],
    [{ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: -1 }],
    [{ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 1.5 }],
  ])("weigert %j", (ruw) => expect(parseBevestiging(ruw)).toBeUndefined());
});

describe("het antwoord op een bevestiging", () => {
  const b = { soort: "werkgebied_annoteren" as const, werkgebied_id: "wg1", aantal: 3, schatting: null };
  const voorstel = (id: string): ThreadItem => ({ id, type: "antwoord", tekst: "…", bevestiging: b });
  const vraag = (id: string, keuze?: "gestart" | "geannuleerd"): ThreadItem =>
    ({ id, type: "user", tekst: "x", ...(keuze ? { bevestigingKeuze: keuze } : {}) });

  it("leest alleen de twee keuzes", () => {
    expect(parseBevestigingKeuze({ keuze: "geannuleerd" })).toBe("geannuleerd");
    expect(parseBevestigingKeuze({ keuze: "gestart" })).toBe("gestart");
    expect(parseBevestigingKeuze({ keuze: "later" })).toBeUndefined();
    expect(parseBevestigingKeuze(null)).toBeUndefined();
  });

  it("hoort bij het laatste voorstel ervóór, en een gewone vraag beantwoordt niets", () => {
    const items = [voorstel("a"), vraag("v1"), vraag("v2", "geannuleerd"), voorstel("b"), voorstel("c"), vraag("v3", "gestart")];
    const uit = afgehandeld(items);
    expect(Object.fromEntries(uit)).toEqual({ a: "geannuleerd", c: "gestart" });
    expect(uit.has("b")).toBe(false);              // een ouder voorstel houdt zijn knoppen
  });

  it("een antwoord zonder open voorstel telt niet", () => {
    expect(afgehandeld([vraag("v", "gestart"), voorstel("a")]).size).toBe(0);
  });
});
