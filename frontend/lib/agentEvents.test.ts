import { describe, expect, it } from "vitest";

import { parseGrounding, parseUitkomst } from "./agentEvents";

describe("parseUitkomst", () => {
  it("leest status en melding; een onbekende vorm is een gewone beurt", () => {
    expect(parseUitkomst({ status: "mislukt", melding: "Stuk." })).toEqual({ status: "mislukt", melding: "Stuk." });
    expect(parseUitkomst({ status: "gestopt", melding: "" })).toEqual({ status: "gestopt" });
    expect(parseUitkomst({ status: "anders" })).toBeUndefined();
    expect(parseUitkomst(undefined)).toBeUndefined();
  });
});

describe("parseGrounding", () => {
  it("een leeg object van een ouder bericht is geen oordeel", () => {
    expect(parseGrounding({})).toBeUndefined();
    expect(parseGrounding(undefined)).toBeUndefined();
  });

  it("neemt afgekapt mee en valt terug op grounded bij een oudere agent", () => {
    expect(parseGrounding({ niveau: "gegrond", grounded: true, afgekapt: true })?.afgekapt).toBe(true);
    expect(parseGrounding({ niveau: "onbepaald", grounded: true, onbevestigd: ["artikel 999", 3] })?.onbevestigd).toEqual(["artikel 999"]);
    expect(parseGrounding({ niveau: "gegrond", onbevestigd: [] })).not.toHaveProperty("onbevestigd");
    expect(parseGrounding({ niveau: "gegrond", interpretatie: ["Een zin.", 4] })?.interpretatie).toEqual(["Een zin."]);
    expect(parseGrounding({ niveau: "gegrond", interpretatie: [] })).not.toHaveProperty("interpretatie");
    // Een artikel in gewone taal dat in het opgehaalde staat (acceptatie 19 nov 2026, art. 475 Rv bij "derdenbeslag").
    expect(parseGrounding({ niveau: "onbepaald", vermeld: ["artikel 475", 1] })?.vermeld).toEqual(["artikel 475"]);
    expect(parseGrounding({ niveau: "onbepaald", vermeld: [] })).not.toHaveProperty("vermeld");
    expect(parseGrounding({ grounded: false })).toEqual({
      niveau: "ongegrond", grounded: false, cited: 0, unsupported: [], niet_letterlijk: [] });
  });
});
