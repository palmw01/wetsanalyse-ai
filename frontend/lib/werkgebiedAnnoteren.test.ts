import { describe, expect, it } from "vitest";

import { parseBevestiging } from "./werkgebiedAnnoteren";

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
