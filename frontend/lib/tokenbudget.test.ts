import { describe, expect, it } from "vitest";

import {
  dagenTotReset,
  resetdatum,
  tokens,
  tokensKort,
  toonWaarschuwing,
  verbruikSamenvatting,
  WAARSCHUWINGSDREMPEL,
} from "./tokenbudget";
import type { Verbruiksstand } from "./types";

/** Een tijdstip op de LOKALE kalenderdag van de draaiende machine.
 *
 *  De helpers rekenen in kalenderdagen ("reset vandaag/morgen"), en dat is per definitie lokaal.
 *  Een vaste UTC-string in een test hangt daardoor van de tijdzone af: `2026-09-06T23:00Z` valt in
 *  UTC op 6 september en in Amsterdam op 7 september. Die test slaagde lokaal en zakte op CI.
 */
function lokaal(dag: number, uur = 12): string {
  return new Date(2026, 8, dag, uur, 0, 0).toISOString();
}

function stand(over: Partial<Verbruiksstand> = {}): Verbruiksstand {
  return {
    userid: "palmw01",
    gebruikt: 250_000,
    budget: 500_000,
    percentage: 50,
    resterend: 250_000,
    reset_op: lokaal(9),
    waarschuwing: false,
    geblokkeerd: false,
    actief: true,
    eigen_budget: false,
    ...over,
  };
}

describe("tokens", () => {
  it("maakt grote getallen leesbaar in nl-NL", () => {
    expect(tokens(437500)).toBe("437.500");
    expect(tokens(0)).toBe("0");
  });

  it("gaat niet onder nul en rondt af", () => {
    expect(tokens(-5)).toBe("0");
    expect(tokens(1234.6)).toBe("1.235");
  });
});

describe("tokensKort", () => {
  it("kort duizendtallen en miljoenen af", () => {
    expect(tokensKort(950)).toBe("950");
    expect(tokensKort(437_500)).toBe("438k");
    expect(tokensKort(1_250_000)).toBe("1,3 mln");
  });
});

describe("resetdatum", () => {
  it("schrijft de datum voluit, met weekdag", () => {
    const tekst = resetdatum(lokaal(9));
    expect(tekst).toBe("woensdag 9 september om 12:00");
  });

  it("geeft niets terug bij een onleesbare datum", () => {
    expect(resetdatum("geen datum")).toBe("");
  });
});

describe("dagenTotReset", () => {
  const nu = new Date(lokaal(6));

  it("telt kalenderdagen", () => {
    expect(dagenTotReset(lokaal(9), nu)).toBe(3);
  });

  it("noemt later vandaag nog vandaag, niet morgen", () => {
    // Op 24-uursblokken afronden zou hier 1 geven ("morgen"), terwijl de teller vanavond al reset.
    expect(dagenTotReset(lokaal(6, 23), nu)).toBe(0);
    expect(dagenTotReset(lokaal(7, 1), nu)).toBe(1);
  });

  it("wordt nooit negatief", () => {
    expect(dagenTotReset(lokaal(1), nu)).toBe(0);
  });
});

describe("verbruikSamenvatting", () => {
  const nu = new Date(lokaal(6));

  it("noemt het percentage en wanneer het reset", () => {
    expect(verbruikSamenvatting(stand(), nu)).toBe("50% gebruikt · reset over 3 dagen");
  });

  it("schrijft vandaag en morgen uit in plaats van in dagen te tellen", () => {
    expect(verbruikSamenvatting(stand({ reset_op: lokaal(6, 23) }), nu)).toContain("reset vandaag");
    expect(verbruikSamenvatting(stand({ reset_op: lokaal(7, 11) }), nu)).toContain("reset morgen");
  });
});

describe("toonWaarschuwing", () => {
  it("volgt de server, niet een eigen drempelberekening", () => {
    // De api zet `waarschuwing`; zou de browser zelf rekenen, dan kan de balk op een ander moment
    // verkleuren dan waarop de melding verschijnt.
    expect(toonWaarschuwing(stand({ waarschuwing: true, percentage: 91 }))).toBe(true);
    expect(toonWaarschuwing(stand({ waarschuwing: false, percentage: 95 }))).toBe(false);
  });

  it("zwijgt als de begrenzing uitstaat", () => {
    expect(toonWaarschuwing(stand({ waarschuwing: true, actief: false }))).toBe(false);
  });

  it("zwijgt zonder stand", () => {
    expect(toonWaarschuwing(null)).toBe(false);
  });
});

describe("drempel", () => {
  it("staat gelijk aan de api-drempel", () => {
    // Loopt dit uiteen, dan kleurt de meter op een ander moment dan de melding komt.
    expect(WAARSCHUWINGSDREMPEL).toBe(90);
  });
});
