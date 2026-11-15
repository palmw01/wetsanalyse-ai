import { describe, expect, it } from "vitest";

import { datumKort, datumLang, datumTekst, datumTijd, momentKort, tijd, tijdOfDag } from "./datum";

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

describe("de vaste vormen", () => {
  const iso = "2026-11-05T09:42:00Z";
  it("rekenen allemaal in Nederlandse tijd", () => {
    expect(datumKort(iso)).toBe("5 nov 2026");
    expect(datumLang(iso)).toBe("5 november 2026");
    expect(momentKort(iso)).toMatch(/^5 nov\.?,? 10:42$/);
    expect(tijd(iso)).toBe("10:42");
    // Om 23:30 UTC is het in Amsterdam al de volgende dag.
    expect(datumKort("2026-11-05T23:30:00Z")).toBe("6 nov 2026");
  });

  it("tonen in de gesprekkenlijst vandaag de tijd en anders de dag", () => {
    expect(tijdOfDag(iso, new Date("2026-11-05T15:00:00Z"))).toBe("10:42");
    expect(tijdOfDag(iso, new Date("2026-11-08T15:00:00Z"))).toMatch(/^5 nov\.?$/);
  });

  it("laten leeg en onleesbaar leeg", () => {
    for (const f of [datumKort, datumLang, momentKort, tijd, tijdOfDag]) {
      expect(f(null)).toBe("");
      expect(f("geen datum")).toBe("");
    }
  });
});
