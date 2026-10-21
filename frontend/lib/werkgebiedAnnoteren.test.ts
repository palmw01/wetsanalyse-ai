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
  it.each([
    [null], [{}], [{ soort: "iets", werkgebied_id: "wg1", aantal: 1 }],
    [{ soort: "werkgebied_annoteren", werkgebied_id: "", aantal: 1 }],
    [{ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: -1 }],
    [{ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 1.5 }],
  ])("weigert %j", (ruw) => expect(parseBevestiging(ruw)).toBeUndefined());
});
