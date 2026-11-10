import { describe, expect, it } from "vitest";

import { datumTekst, datumTijd } from "./datum";

describe("datumTijd", () => {
  it("toont een moment in Nederlandse tijd", () => {
    expect(datumTijd("2026-11-05T09:42:00Z")).toBe("5 nov 2026, 10:42");
  });

  it("laat leeg en onleesbaar leeg", () => {
    expect(datumTijd(null)).toBe("");
    expect(datumTijd("geen datum")).toBe("");
  });
});

describe("datumTekst", () => {
  it("schrijft een datum uit een bron voluit, zonder tijdzone", () => {
    expect(datumTekst("2026-10-16")).toBe("16 oktober 2026");
    expect(datumTekst("2021-07-08")).toBe("8 juli 2021");
    expect(datumTekst("")).toBe("");
    expect(datumTekst("2026-13-01")).toBe("2026-13-01");
  });
});
