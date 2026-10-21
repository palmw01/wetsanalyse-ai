import { describe, expect, it } from "vitest";

import { VERWIJDER_UITLEG, verwijderdUit, verwijderdZin, verwijderLabel } from "./verwijderen";

describe("verwijderen", () => {
  it("leest de verwijderd-stand uit een 404 van de api", () => {
    const e = { status: 404, detail: "Werkgebied is verwijderd.",
      data: { fout: "verwijderd", soort: "werkgebied", op: "2026-10-21T10:00:00+00:00", door: "jurist-a" } };
    expect(verwijderdUit(e)).toEqual({ soort: "werkgebied", op: "2026-10-21T10:00:00+00:00", door: "jurist-a" });
    expect(verwijderdZin(verwijderdUit(e)!)).toBe("Dit werkgebied is verwijderd op 21 okt 2026 door jurist-a.");
    expect(verwijderdZin({ soort: "begrip", op: "", door: "" })).toBe("Dit begrip is verwijderd.");
  });

  it("een andere fout is geen verwijderd-stand", () => {
    expect(verwijderdUit({ status: 404, detail: "Werkgebied bestaat niet." })).toBeNull();
    expect(verwijderdUit({ status: 412, detail: "x", data: { fout: "verwijderd", soort: "begrip", op: "x" } })).toBeNull();
    expect(verwijderdUit(new Error("weg"))).toBeNull();
    expect(verwijderdUit(null)).toBeNull();
  });

  it("één knoptekst per soort, en de annotatie houdt haar oude uitleg", () => {
    expect(verwijderLabel("annotatie")).toBe("Annotatie verwijderen");
    expect(verwijderLabel("werkgebied")).toBe("Werkgebied verwijderen");
    expect(VERWIJDER_UITLEG.annotatie).toBe("Verwijdert alle markeringen en beoordelingen van deze bepaling, ook uit de kennisgraaf");
  });
});
