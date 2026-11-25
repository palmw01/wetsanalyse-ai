import { describe, expect, it } from "vitest";

import {
  ankerVoorDatum,
  ankerVoorWeekdag,
  bovenBudgetMelding,
  metOffset,
  budgetHerkomst,
  dagenTotReset,
  resetdatum,
  resetRegel,
  ankerVoorDag,
  ankerVoorMaanddag,
  periodeLabel,
  periodeSoort,
  rolLabel,
  tokens,
  tokensKort,
  verbruikSamenvatting,
  WAARSCHUWINGSDREMPEL,
  wandklok,
} from "./tokenbudget";
import type { Verbruiksstand } from "./types";

/** Een tijdstip op de LOKALE kalenderdag van de draaiende machine.
 *
 *  De helpers rekenen in kalenderdagen ("reset vandaag/morgen"), en dat is per definitie lokaal.
 *  Een vaste UTC-string in een test hangt daardoor van de tijdzone af: `2026-09-06T23:00Z` valt in
 *  UTC op 6 september en in Amsterdam op 7 september. Zo'n test slaagt lokaal en zakt op CI.
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
    rol: "analist",
    gereset_op: null,
    ...over,
  };
}

describe("budget per rol", () => {
  it("zegt welke waarde geldt en waar die vandaan komt", () => {
    expect(budgetHerkomst({ budget: 300_000, rol: "analist" })).toBe("Budget van de rol analist: 300.000 tokens");
  });

  it("zet een rol aan het begin van een regel", () => {
    expect(rolLabel("beheerder")).toBe("Beheerder");
  });
});

describe("resetRegel", () => {
  it("is leeg zolang niemand resette", () => {
    expect(resetRegel({ gereset_op: null, gereset_door: "" })).toBe("");
  });

  it("noemt moment en beheerder", () => {
    const regel = resetRegel({ gereset_op: lokaal(9), gereset_door: "wpalm" });
    expect(regel).toMatch(/^Gereset op .*9 september.* door wpalm$/);
  });
});

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


describe("drempel", () => {
  it("staat gelijk aan de api-drempel", () => {
    // Loopt dit uiteen, dan kleurt de meter op een ander moment dan de melding komt.
    expect(WAARSCHUWINGSDREMPEL).toBe(90);
  });
});

describe("het resetmoment kiezen", () => {
  const NL = "Europe/Amsterdam";

  it("leest de wandklok in de tijdzone van het beleid, niet in die van de machine", () => {
    // Zondag 22 november 23:00 UTC is maandag 23 november 00:00 in Nederland.
    expect(wandklok("2026-11-22T23:00:00Z", NL)).toEqual({ datum: "2026-11-23", dag: 23, weekdag: 0, tijd: "00:00" });
    expect(wandklok("2026-07-05T22:00:00Z", NL)).toEqual({ datum: "2026-07-06", dag: 6, weekdag: 0, tijd: "00:00" });
    expect(wandklok("2026-11-25T20:28:00Z", NL)).toEqual({ datum: "2026-11-25", dag: 25, weekdag: 2, tijd: "21:28" });
  });

  it("kiest de vorige maandag 00:00, niet de volgende", () => {
    // Woensdag 25 november 2026, 21:28 Nederlandse tijd.
    const nu = new Date("2026-11-25T20:28:00Z");
    expect(ankerVoorWeekdag(0, "00:00", NL, nu)).toBe("2026-11-23T00:00:00+01:00");
    expect(ankerVoorWeekdag(3, "09:00", NL, nu)).toBe("2026-11-19T09:00:00+01:00"); // donderdag
  });

  it("neemt vandaag als het moment vandaag al geweest is, anders een week eerder", () => {
    const maandagOchtend = new Date("2026-11-23T08:00:00Z"); // 09:00 in Nederland
    expect(ankerVoorWeekdag(0, "00:00", NL, maandagOchtend)).toBe("2026-11-23T00:00:00+01:00");
    expect(ankerVoorWeekdag(0, "12:00", NL, maandagOchtend)).toBe("2026-11-16T12:00:00+01:00");
  });

  it("rekent over een maandgrens en in de zomertijd", () => {
    expect(ankerVoorWeekdag(0, "00:00", NL, new Date("2026-04-01T10:00:00Z"))).toBe("2026-03-30T00:00:00+02:00");
    // Zondagavond 23:30 zomertijd is in UTC al 21:30: nog steeds dezelfde week.
    expect(ankerVoorWeekdag(0, "00:00", NL, new Date("2026-10-25T22:30:00Z"))).toBe("2026-10-19T00:00:00+02:00");
  });

  it("een anker gaat met de offset van dat moment mee, zodat elke api hetzelfde leest", () => {
    // De regressie: zonder offset las een oudere api "maandag 00:00" als UTC, en dat is 01:00 in Nederland.
    expect(metOffset("2026-11-23T00:00:00", NL)).toBe("2026-11-23T00:00:00+01:00");
    expect(new Date(metOffset("2026-11-23T00:00:00", NL)).toISOString()).toBe("2026-11-22T23:00:00.000Z");
    expect(metOffset("2026-07-06T00:00:00", NL)).toBe("2026-07-06T00:00:00+02:00");
    // De dagen van de overgang: vóór en na het verzetten van de klok.
    expect(metOffset("2026-03-29T01:00:00", NL)).toBe("2026-03-29T01:00:00+01:00");
    expect(metOffset("2026-03-29T04:00:00", NL)).toBe("2026-03-29T04:00:00+02:00");
    expect(metOffset("2026-10-25T00:00:00", NL)).toBe("2026-10-25T00:00:00+02:00");
    expect(metOffset("2026-10-25T12:00:00", NL)).toBe("2026-10-25T12:00:00+01:00");
    expect(metOffset("2026-11-23T00:00:00", "UTC")).toBe("2026-11-23T00:00:00+00:00");
    expect(metOffset("2026-11-23T00:00:00", "America/New_York")).toBe("2026-11-23T00:00:00-05:00");
  });

  it("een datum en tijd gaan als wandkloktijd mee", () => {
    expect(ankerVoorDatum("2026-12-01", "09:30", NL)).toBe("2026-12-01T09:30:00+01:00");
  });

  it("per dag: vandaag als het moment al geweest is, anders gisteren", () => {
    const nu = new Date("2026-11-25T20:28:00Z"); // 21:28
    expect(ankerVoorDag("00:00", NL, nu)).toBe("2026-11-25T00:00:00+01:00");
    expect(ankerVoorDag("22:00", NL, nu)).toBe("2026-11-24T22:00:00+01:00");
    // Kort na middernacht Nederlandse tijd is het in UTC nog de vorige dag.
    expect(ankerVoorDag("00:00", NL, new Date("2026-11-30T23:30:00Z"))).toBe("2026-12-01T00:00:00+01:00");
  });

  it("per maand: deze maand als de dag al geweest is, anders de vorige", () => {
    const nu = new Date("2026-11-25T20:28:00Z");
    expect(ankerVoorMaanddag(1, "00:00", NL, nu)).toBe("2026-11-01T00:00:00+01:00");
    expect(ankerVoorMaanddag(25, "22:00", NL, nu)).toBe("2026-10-25T22:00:00+01:00");
    expect(ankerVoorMaanddag(28, "00:00", NL, nu)).toBe("2026-10-28T00:00:00+01:00");
    // Over de jaargrens.
    expect(ankerVoorMaanddag(15, "00:00", NL, new Date("2027-01-03T10:00:00Z"))).toBe("2026-12-15T00:00:00+01:00");
  });

  it("de periode is een begrijpelijke keuze", () => {
    expect([1, 7, 30].map((d) => periodeSoort({ periode_dagen: d }))).toEqual(["dag", "week", "dagen"]);
    expect(periodeSoort({ periode_dagen: 30, periode_maanden: 1 })).toBe("maand");
    expect(periodeLabel({ periode_dagen: 7 })).toBe("Per week");
    expect(periodeLabel({ periode_dagen: 1 })).toBe("Per dag");
    expect(periodeLabel({ periode_dagen: 30, periode_maanden: 1 })).toBe("Per maand");
    expect(periodeLabel({ periode_dagen: 30, periode_maanden: 3 })).toBe("Per 3 maanden");
    expect(periodeLabel({ periode_dagen: 30 })).toBe("Per 30 dagen");
  });

  it("de resetdatum staat in de tijdzone van het beleid", () => {
    expect(resetdatum("2026-11-29T23:00:00Z", NL)).toBe("maandag 30 november om 00:00");
  });

  it("de melding telt wie boven zijn budget zit", () => {
    expect(bovenBudgetMelding([])).toBe("");
    expect(bovenBudgetMelding(["jdevries"])).toBe("Eén gebruiker zit in het nieuwe venster boven zijn budget: jdevries.");
    expect(bovenBudgetMelding(["a", "b"])).toBe("2 gebruikers zitten in het nieuwe venster boven hun budget: a, b.");
  });
});
