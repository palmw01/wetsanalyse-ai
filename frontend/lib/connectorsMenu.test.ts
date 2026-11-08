import { describe, expect, it } from "vitest";
import { actieveConnectors, herkomstVan, menuNaam, menuRegel, wissel, type ConnectorStand } from "./connectorsMenu";

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
