import { describe, expect, it } from "vitest";
import { HERPOGINGEN, maakConnectorLijst, type Haal } from "./connectorLijst";

const KST = { naam: "kamerstukken", label: "Kamerstukken", brontype: "kamerstuk", beschikbaarheid: "aan" as const };
const ONBEKEND = { ...KST, beschikbaarheid: "onbekend" as const };

/** Een nep-timer: wat gepland is, staat in `plan`; `volgende()` voert het eerste uit en wacht tot de poging klaar is. */
function nepTijd() {
  const plan: { ms: number; f: () => void }[] = [];
  return {
    plan,
    wacht: (ms: number, f: () => void) => {
      const item = { ms, f };
      plan.push(item);
      return () => { plan.splice(plan.indexOf(item), 1); };
    },
    async volgende() {
      const item = plan.shift();
      if (!item) throw new Error("niets gepland");
      item.f();
      await new Promise((r) => setTimeout(r, 0));
      return item.ms;
    },
  };
}

/** Een haal-functie die per aanroep het volgende antwoord geeft (een Error = een mislukt verzoek). */
function antwoorden(...reeks: (typeof KST | typeof ONBEKEND)[][] | Error[]) {
  let n = 0;
  const haal: Haal & { n: () => number } = Object.assign(async () => {
    const a = (reeks as unknown[])[Math.min(n++, reeks.length - 1)];
    if (a instanceof Error) throw a;
    return { connectors: a as (typeof KST)[] };
  }, { n: () => n });
  return haal;
}

describe("connectorLijst", () => {
  it("houdt de laatst bekende lijst over een nieuwe mount heen", async () => {
    const lijst = maakConnectorLijst(nepTijd());
    expect(lijst.lees()).toEqual({ beschikbaar: [], laden: null, controleert: false });
    await lijst.ververs(antwoorden([KST]));
    expect(lijst.lees()).toEqual({ beschikbaar: [KST], laden: "ok", controleert: false });
  });

  it("onbekend is eerst laden: een reeks herpogingen na 2, 4, 8 en 16 s, en dan pas een oordeel", async () => {
    const tijd = nepTijd();
    const lijst = maakConnectorLijst(tijd);
    const haal = antwoorden([ONBEKEND]);
    await lijst.ververs(haal);
    expect(lijst.lees()).toMatchObject({ beschikbaar: [ONBEKEND], controleert: true });
    const wachttijden = [];
    while (tijd.plan.length) {
      expect(lijst.lees().controleert).toBe(true);
      wachttijden.push(await tijd.volgende());
    }
    expect(wachttijden).toEqual(HERPOGINGEN);
    expect(haal.n()).toBe(1 + HERPOGINGEN.length);
    expect(lijst.lees()).toMatchObject({ beschikbaar: [ONBEKEND], laden: "ok", controleert: false });
  });

  it("een geslaagde poging halverwege stopt de reeks", async () => {
    const tijd = nepTijd();
    const lijst = maakConnectorLijst(tijd);
    await lijst.ververs(antwoorden([ONBEKEND], [ONBEKEND], [KST]));
    await tijd.volgende();
    await tijd.volgende();
    expect(tijd.plan).toEqual([]);
    expect(lijst.lees()).toEqual({ beschikbaar: [KST], laden: "ok", controleert: false });
  });

  it("een fout is tijdens de reeks onzichtbaar; pas daarna is het ophalen mislukt, en de lijst blijft staan", async () => {
    const tijd = nepTijd();
    const lijst = maakConnectorLijst(tijd);
    await lijst.ververs(antwoorden([KST]));
    await lijst.ververs(antwoorden(new Error("504")));
    expect(lijst.lees()).toEqual({ beschikbaar: [KST], laden: "ok", controleert: true });
    while (tijd.plan.length) await tijd.volgende();
    expect(lijst.lees()).toEqual({ beschikbaar: [KST], laden: "mislukt", controleert: false });
  });

  it("mislukt zonder eerdere lijst: tijdens de reeks nog niets, daarna leeg maar wel mislukt", async () => {
    const tijd = nepTijd();
    const lijst = maakConnectorLijst(tijd);
    await lijst.ververs(antwoorden(new Error("502")));
    expect(lijst.lees()).toEqual({ beschikbaar: [], laden: null, controleert: true });
    while (tijd.plan.length) await tijd.volgende();
    expect(lijst.lees()).toEqual({ beschikbaar: [], laden: "mislukt", controleert: false });
  });

  it("geen tweede reeks naast een lopende; na de reeks begint een nieuwe", async () => {
    const tijd = nepTijd();
    const lijst = maakConnectorLijst(tijd);
    const haal = antwoorden([ONBEKEND]);
    await Promise.all([lijst.ververs(haal), lijst.ververs(haal)]);
    expect(haal.n()).toBe(1);
    await lijst.ververs(haal);
    expect(haal.n()).toBe(1);
    expect(tijd.plan).toHaveLength(1);
    while (tijd.plan.length) await tijd.volgende();
    const herstel = antwoorden([KST]);
    await lijst.ververs(herstel);
    expect(herstel.n()).toBe(1);
    expect(lijst.lees()).toEqual({ beschikbaar: [KST], laden: "ok", controleert: false });
  });

  it("luisteraars horen elke wijziging", async () => {
    const lijst = maakConnectorLijst(nepTijd());
    let gehoord = 0;
    lijst.abonneer(() => { gehoord++; });
    await lijst.ververs(antwoorden([KST]));
    expect(gehoord).toBeGreaterThanOrEqual(1);
  });

  it("de bronstand van een beurt: een echte wijziging telt, en register_onleesbaar start een reeks", async () => {
    const tijd = nepTijd();
    const lijst = maakConnectorLijst(tijd);
    const haal = antwoorden([KST]);
    await lijst.ververs(haal);
    let gehoord = 0;
    lijst.abonneer(() => { gehoord++; });
    lijst.legBronstandOver([{ naam: "kamerstukken", reden: "aan" }]);
    expect(gehoord).toBe(0);
    lijst.legBronstandOver([{ naam: "kamerstukken", reden: "register_onleesbaar" }]);
    expect(lijst.lees().controleert).toBe(true);
    await new Promise((r) => setTimeout(r, 0));
    // De herpoging vond hem weer: aan, en geen reeks meer.
    expect(haal.n()).toBe(2);
    expect(lijst.lees()).toEqual({ beschikbaar: [KST], laden: "ok", controleert: false });
  });
});
