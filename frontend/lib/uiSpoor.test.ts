import { describe, expect, it } from "vitest";

import { isRuisfout, leesBrowserfout, leesSpoor, UI_ACTIES, UI_UITKOMSTEN } from "@/lib/uiSpoor";

describe("leesBrowserfout", () => {
  it("neemt plek, naam en digest over", () => {
    expect(leesBrowserfout({ soort: "fout", plek: "belofte", naam: "TypeError", digest: "1234-abc" })).toEqual({
      plek: "belofte", naam: "TypeError", digest: "1234-abc",
    });
  });

  it("weigert een onbekende plek", () => {
    expect(leesBrowserfout({ plek: "waar dan ook" })).toBeNull();
    expect(leesBrowserfout(null)).toBeNull();
  });

  it("laat vrije tekst niet door, ook niet in de naam of de digest", () => {
    const fout = leesBrowserfout({
      plek: "script", naam: "de vraag van de jurist", digest: "een zin met spaties", melding: "geheim", stack: "geheim",
    });
    expect(fout).toEqual({ plek: "script" });
  });

  it("telt een afgebroken verzoek niet als crash", () => {
    expect(isRuisfout({ name: "AbortError" })).toBe(true);
    expect(isRuisfout(new TypeError("x"))).toBe(false);
    expect(isRuisfout(undefined)).toBe(false);
  });
});

describe("leesSpoor", () => {
  it("neemt een geldige melding over", () => {
    expect(leesSpoor({ actie: "gesprek_verwijderen", uitkomst: "gelukt", duur_ms: 1234 })).toEqual({
      actie: "gesprek_verwijderen",
      uitkomst: "gelukt",
      duur_ms: 1234,
    });
  });

  it("weigert een actie die niet in de lijst staat", () => {
    // De gesloten lijst is de reden dat er geen gebruikersinhoud in een logregel kan belanden.
    expect(leesSpoor({ actie: "Belastingvraag over artikel 36", uitkomst: "gelukt" })).toBeNull();
    expect(leesSpoor({ actie: "gesprek_verwijderen", uitkomst: "vrolijk" })).toBeNull();
  });

  it("laat velden vallen die er niet toe doen of niet kloppen", () => {
    const spoor = leesSpoor({
      actie: "review_beslissing",
      uitkomst: "mislukt",
      duur_ms: -5,
      status: 9000,
      titel: "Aangifte inkomstenbelasting 2025",
    });
    expect(spoor).toEqual({ actie: "review_beslissing", uitkomst: "mislukt" });
  });

  it("begrenst een duur uit een tabblad dat dagen open stond", () => {
    expect(leesSpoor({ actie: "gesprek_hernoemen", uitkomst: "gelukt", duur_ms: 1e12 })?.duur_ms)
      .toBe(86_400_000);
  });

  it("houdt een http-status vast bij een mislukking", () => {
    expect(leesSpoor({ actie: "annotatie_verwijderen", uitkomst: "mislukt", status: 504 })).toEqual({
      actie: "annotatie_verwijderen",
      uitkomst: "mislukt",
      status: 504,
    });
  });

  it("weigert wat geen object is", () => {
    for (const rommel of [null, undefined, "gesprek_verwijderen", 42, []]) {
      expect(leesSpoor(rommel)).toBeNull();
    }
  });

  it("kent de vier uitkomsten, en `gestart` hoort erbij", () => {
    // Een `gestart` zonder vervolgregel is het signaal dat een handeling bleef hangen; zonder die
    // waarde is de klacht "ik klik en er gebeurt niets" niet te onderscheiden van een trage call.
    expect(UI_UITKOMSTEN).toContain("gestart");
    expect(UI_ACTIES.length).toBeGreaterThan(0);
  });
});
