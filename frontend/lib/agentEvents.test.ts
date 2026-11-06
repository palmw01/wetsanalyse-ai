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
    expect(parseGrounding({ grounded: false })).toEqual({
      niveau: "ongegrond", grounded: false, cited: 0, unsupported: [], niet_letterlijk: [] });
  });
});
