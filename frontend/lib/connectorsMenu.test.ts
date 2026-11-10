import { describe, expect, it } from "vitest";
import { actieveConnectors, beurtBronnen, herkomstVan, menuMelding, menuNaam, menuRegel, metBeschikbaarheid, moetVerversen, toonMenu, uitBronstand, wissel, zelfAanTeZetten, type ConnectorStand } from "./connectorsMenu";

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

  it("wat de straat niet aanbiedt staat er, als niet aangeboden: nooit stil weg, nooit aan", () => {
    expect(metBeschikbaarheid([KST, ECLI], [{ naam: "kamerstukken", straat: false }, { naam: "rechtspraak", straat: true }]))
      .toEqual([{ ...KST, beschikbaarheid: "niet_aangeboden" }, { ...ECLI, beschikbaarheid: "aan" }]);
    expect(metBeschikbaarheid([KST], [])).toEqual([{ ...KST, beschikbaarheid: "niet_aangeboden" }]);
    const stand: ConnectorStand = { beschikbaar: metBeschikbaarheid([KST, ECLI], [{ naam: "rechtspraak", straat: true }]) };
    expect(toonMenu(stand)).toBe(true);
    // Incident 8 nov 2026: nooit aan, en dus niet in de beurt.
    expect(actieveConnectors(stand)).toEqual(["rechtspraak"]);
    expect(beurtBronnen(stand)).toEqual({ bronnen: ["rechtspraak"], bronnen_herkomst: "standaard" });
    expect(wissel(stand, "kamerstukken")).toEqual(["kamerstukken", "rechtspraak"]);
    expect(zelfAanTeZetten([{ naam: "kamerstukken", label: "Kamerstukken", reden: "gesprek" }], stand)).toEqual([]);
    expect(menuRegel(stand)).toEqual([{ label: "Wetgeving", stand: "aan" }, { label: "Kamerstukken", stand: "niet_aangeboden" },
      { label: "Rechtspraak", stand: "aan" }]);
    expect(menuNaam(stand)).toBe("Bronnen: Wetgeving aan, Kamerstukken niet beschikbaar, Rechtspraak aan");
    expect(menuMelding(stand)).toBe("Kamerstukken staat aan, maar is hier niet beschikbaar. Lex gebruikt deze bron dan niet.");
    // Een vaste stand van de omgeving: geen reden om te blijven peilen.
    expect(moetVerversen(stand)).toBe(false);
  });

  it("een keuze voor een niet-aangeboden bron blijft bewaard als je een andere omzet", () => {
    const stand: ConnectorStand = {
      beschikbaar: [{ ...KST, beschikbaarheid: "niet_aangeboden" }, { ...ECLI, beschikbaarheid: "aan" }],
      gesprek: ["kamerstukken", "rechtspraak"],
    };
    expect(wissel(stand, "rechtspraak")).toEqual(["kamerstukken"]);
    expect(wissel(stand, "kamerstukken")).toEqual(["kamerstukken", "rechtspraak"]);
  });

  it("mislukt ophalen: het menu blijft, met de laatst bekende stand en een melding", () => {
    expect(toonMenu({ beschikbaar: [] })).toBe(false);
    const leeg: ConnectorStand = { beschikbaar: [], laden: "mislukt" };
    expect(toonMenu(leeg)).toBe(true);
    expect(moetVerversen(leeg)).toBe(true);
    expect(menuRegel(leeg)).toEqual([{ label: "Wetgeving", stand: "aan" }]);
    expect(menuMelding(leeg)).toBe("Lex kan de bronnen nu niet controleren.");
    expect(menuNaam(leeg)).toBe("Bronnen: Wetgeving aan (nu niet te controleren)");
    const oud: ConnectorStand = { beschikbaar: [{ ...KST, beschikbaarheid: "aan" }], laden: "mislukt" };
    expect(menuMelding(oud)).toBe("Lex kan de bronnen nu niet controleren. Je ziet de laatst bekende stand.");
    // De laatst bekende keuze gaat gewoon mee met de beurt.
    expect(beurtBronnen(oud)).toEqual({ bronnen: ["kamerstukken"], bronnen_herkomst: "standaard" });
  });

  it("laden is geen oordeel: onbekend tijdens het controleren is neutraal, zonder melding", () => {
    const NEP = { naam: "nep", label: "Nepbron", brontype: "nep", beschikbaarheid: "onbekend" as const };
    const bezig: ConnectorStand = { beschikbaar: [{ ...KST, beschikbaarheid: "onbekend" }, NEP], controleert: true };
    expect(menuRegel(bezig)).toEqual([{ label: "Wetgeving", stand: "aan" }, { label: "Kamerstukken", stand: "laden" },
      { label: "Nepbron", stand: "laden" }]);
    expect(menuNaam(bezig)).toBe("Bronnen: Wetgeving aan, Kamerstukken wordt gecontroleerd, Nepbron wordt gecontroleerd");
    expect(menuMelding(bezig)).toBeNull();
    // Geen schakelaar zolang het niet vaststaat; de beurt houdt de opgeslagen keuze.
    expect(wissel({ ...bezig, gesprek: ["kamerstukken"] }, "nep")).toEqual(["kamerstukken"]);
    expect(beurtBronnen(bezig)).toEqual({ bronnen: ["kamerstukken", "nep"], bronnen_herkomst: "standaard" });
    // Na de reeks: wel het oordeel, met de melding.
    const klaar: ConnectorStand = { ...bezig, controleert: false };
    expect(menuRegel(klaar)[1]).toEqual({ label: "Kamerstukken", stand: "onbekend" });
    expect(menuMelding(klaar)).toBe("Lex kan nu niet nagaan of Kamerstukken en Nepbron bereikbaar zijn.");
    // Een vaste stand wacht niet op de reeks.
    const weg: ConnectorStand = { beschikbaar: [{ ...KST, beschikbaarheid: "niet_aangeboden" }], controleert: true };
    expect(menuRegel(weg)[1]).toEqual({ label: "Kamerstukken", stand: "niet_aangeboden" });
  });

  it("een mislukte lijst tijdens een nieuwe reeks: menu blijft, maar zonder melding", () => {
    const opnieuw: ConnectorStand = { beschikbaar: [], laden: "mislukt", controleert: true };
    expect(toonMenu(opnieuw)).toBe(true);
    expect(menuMelding(opnieuw)).toBeNull();
    expect(menuNaam(opnieuw)).toBe("Bronnen: Wetgeving aan");
    // Zonder eerdere lijst en zonder uitkomst (eerste reeks) is er geen menu.
    expect(toonMenu({ beschikbaar: [], controleert: true })).toBe(false);
  });

  it("de bronstand van een beurt werkt de beschikbaarheid bij, generiek per connector", () => {
    const NEP = { naam: "nep", label: "Nepbron", brontype: "nep" };
    const lijst = [{ ...KST, beschikbaarheid: "aan" as const }, { ...ECLI, beschikbaarheid: "onbekend" as const }, NEP];
    const na = uitBronstand(lijst, [
      { naam: "kamerstukken", reden: "straat" },
      { naam: "rechtspraak", reden: "aan" },
      { naam: "nep", reden: "register_onleesbaar" },
    ]);
    expect(na.map((c) => c.beschikbaarheid)).toEqual(["niet_aangeboden", "aan", "onbekend"]);
    // Uitgezet in gesprek, werkgebied of door de beheerder zegt niets over de omgeving.
    const zelfde = uitBronstand(lijst, [{ naam: "kamerstukken", reden: "gesprek" }, { naam: "rechtspraak", reden: "beheerder" }]);
    expect(zelfde[0]).toBe(lijst[0]);
    expect(zelfde[1]).toBe(lijst[1]);
  });

  it("zonder graph-qa is de beschikbaarheid onbekend, en dan is er geen schakelaar (review ADR-013, punt 2)", () => {
    const beschikbaar = metBeschikbaarheid([KST, ECLI], null);
    expect(beschikbaar.map((c) => c.beschikbaarheid)).toEqual(["onbekend", "onbekend"]);
    const stand: ConnectorStand = { beschikbaar, gesprek: ["kamerstukken"] };
    expect(moetVerversen(stand)).toBe(true);
    // Omzetten doet niets: een schakelaar die niets doet is erger dan geen.
    expect(wissel(stand, "rechtspraak")).toEqual(["kamerstukken"]);
    expect(wissel(stand, "kamerstukken")).toEqual(["kamerstukken"]);
    // De beurt houdt de opgeslagen keuze: graph-qa toetst de straat zelf en noemt dan de juiste reden.
    expect(beurtBronnen(stand)).toEqual({ bronnen: ["kamerstukken"], bronnen_herkomst: "gesprek" });
    // *Zet … aan* na een bron_uit biedt hem niet aan.
    expect(zelfAanTeZetten([{ naam: "kamerstukken", label: "Kamerstukken", reden: "gesprek" }], stand)).toEqual([]);
    expect(menuRegel(stand)).toEqual([{ label: "Wetgeving", stand: "aan" }, { label: "Kamerstukken", stand: "onbekend" },
      { label: "Rechtspraak", stand: "onbekend" }]);
    expect(menuMelding(stand)).toBe("Lex kan nu niet nagaan of Kamerstukken en Rechtspraak bereikbaar zijn.");
    expect(menuNaam(stand)).toBe("Bronnen: Wetgeving aan, Kamerstukken onbekend, Rechtspraak onbekend");
  });

  it("een oudere BFF zonder beschikbaarheid telt als aan", () => {
    expect(moetVerversen({ beschikbaar: [KST] })).toBe(false);
    expect(menuMelding({ beschikbaar: [KST] })).toBeNull();
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

  it("de toelichting zegt in de je-vorm wat er geldt, zonder beheertaal", () => {
    const teksten = [menuMelding({ beschikbaar: [], laden: "mislukt" }),
      menuMelding({ beschikbaar: [{ ...KST, beschikbaarheid: "niet_aangeboden" }] }),
      menuMelding({ beschikbaar: [{ ...KST, beschikbaarheid: "onbekend" }] })];
    for (const t of teksten) expect(t).not.toMatch(/beheerder|omgeving|straat|register|connector/i);
  });

  it("de regel op de knop", () => {
    const stand = { beschikbaar: [KST, ECLI], gesprek: ["kamerstukken"] };
    expect(menuRegel(stand)).toEqual([{ label: "Wetgeving", stand: "aan" }, { label: "Kamerstukken", stand: "aan" },
      { label: "Rechtspraak", stand: "uit" }]);
    expect(menuNaam(stand)).toBe("Bronnen: Wetgeving aan, Kamerstukken aan, Rechtspraak uit");
  });
});
