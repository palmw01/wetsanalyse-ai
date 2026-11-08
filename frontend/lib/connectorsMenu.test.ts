import { describe, expect, it } from "vitest";
import { actieveConnectors, beurtBronnen, heeftOnbekend, herkomstVan, menuNaam, menuRegel, metBeschikbaarheid, wissel, zelfAanTeZetten, type ConnectorStand } from "./connectorsMenu";

const KST = { naam: "kamerstukken", label: "Kamerstukken", brontype: "kamerstuk" };
const ECLI = { naam: "rechtspraak", label: "Rechtspraak", brontype: "uitspraak" };

describe("connectorsMenu", () => {
  it("gesprek gaat voor werkgebied, werkgebied voor de standaard", () => {
    const basis: ConnectorStand = { beschikbaar: [KST, ECLI] };
    expect(actieveConnectors(basis)).toEqual(["kamerstukken", "rechtspraak"]);
    expect(actieveConnectors({ ...basis, werkgebied: ["rechtspraak"] })).toEqual(["rechtspraak"]);
    expect(actieveConnectors({ ...basis, werkgebied: ["rechtspraak"], gesprek: [] })).toEqual([]);
    expect(herkomstVan({ ...basis, werkgebied: [] })).toBe("werkgebied");
    expect(herkomstVan({ ...basis, gesprek: [] })).toBe("gesprek");
  });

  it("een beurt stuurt de stand en zijn herkomst mee, zonder menu niets", () => {
    expect(beurtBronnen({ beschikbaar: [] })).toEqual({});
    expect(beurtBronnen({ beschikbaar: [KST], werkgebied: [] })).toEqual({ bronnen: [], bronnen_herkomst: "werkgebied" });
    expect(beurtBronnen({ beschikbaar: [KST] })).toEqual({ bronnen: ["kamerstukken"], bronnen_herkomst: "standaard" });
  });

  it("het menu toont alleen wat de straat aanbiedt, met de beschikbaarheid erbij", () => {
    expect(metBeschikbaarheid([KST, ECLI], [{ naam: "kamerstukken", straat: false }, { naam: "rechtspraak", straat: true }]))
      .toEqual([{ ...ECLI, beschikbaarheid: "aan" }]);
    expect(metBeschikbaarheid([KST], [])).toEqual([]);
  });

  it("zonder graph-qa is de beschikbaarheid onbekend, en dan is er geen schakelaar (review ADR-013, punt 2)", () => {
    const beschikbaar = metBeschikbaarheid([KST, ECLI], null);
    expect(beschikbaar.map((c) => c.beschikbaarheid)).toEqual(["onbekend", "onbekend"]);
    const stand: ConnectorStand = { beschikbaar, gesprek: ["kamerstukken"] };
    expect(heeftOnbekend(stand)).toBe(true);
    // Omzetten doet niets: een schakelaar die niets doet is erger dan geen.
    expect(wissel(stand, "rechtspraak")).toEqual(["kamerstukken"]);
    expect(wissel(stand, "kamerstukken")).toEqual(["kamerstukken"]);
    // De beurt houdt de opgeslagen keuze: graph-qa toetst de straat zelf en noemt dan de juiste reden.
    expect(beurtBronnen(stand)).toEqual({ bronnen: ["kamerstukken"], bronnen_herkomst: "gesprek" });
    // *Zet … aan* na een bron_uit biedt hem niet aan.
    expect(zelfAanTeZetten([{ naam: "kamerstukken", label: "Kamerstukken", reden: "gesprek" }], stand)).toEqual([]);
    expect(menuRegel(stand)).toEqual([{ label: "Wetgeving", aan: true }, { label: "Kamerstukken", aan: false, onbekend: true },
      { label: "Rechtspraak", aan: false, onbekend: true }]);
    expect(menuNaam(stand)).toBe("Bronnen: Wetgeving aan, Kamerstukken onbekend, Rechtspraak onbekend");
  });

  it("een oudere BFF zonder beschikbaarheid telt als aan", () => {
    expect(heeftOnbekend({ beschikbaar: [KST] })).toBe(false);
    expect(wissel({ beschikbaar: [KST] }, "kamerstukken")).toEqual([]);
  });

  it("zet aan alleen wat de jurist zelf kan aanzetten", () => {
    const uit = [{ naam: "kamerstukken", label: "Kamerstukken", reden: "gesprek" }, { naam: "rechtspraak", label: "Rechtspraak", reden: "beheerder" },
      { naam: "eurlex", label: "EUR-Lex", reden: "werkgebied" }];
    expect(zelfAanTeZetten(uit, { beschikbaar: [KST, ECLI] }).map((b) => b.naam)).toEqual(["kamerstukken"]);
  });

  it("wat de beheerder niet aanbiedt, gaat nooit aan", () => {
    expect(actieveConnectors({ beschikbaar: [KST], gesprek: ["kamerstukken", "rechtspraak"] })).toEqual(["kamerstukken"]);
  });

  it("omzetten geeft de nieuwe eigen stand, in een vaste volgorde", () => {
    const stand: ConnectorStand = { beschikbaar: [KST, ECLI], gesprek: ["rechtspraak"] };
    expect(wissel(stand, "kamerstukken")).toEqual(["kamerstukken", "rechtspraak"]);
    expect(wissel(stand, "rechtspraak")).toEqual([]);
  });

  it("de regel op de knop", () => {
    const stand = { beschikbaar: [KST, ECLI], gesprek: ["kamerstukken"] };
    expect(menuRegel(stand)).toEqual([{ label: "Wetgeving", aan: true }, { label: "Kamerstukken", aan: true },
      { label: "Rechtspraak", aan: false }]);
    expect(menuNaam(stand)).toBe("Bronnen: Wetgeving aan, Kamerstukken aan, Rechtspraak uit");
  });
});
