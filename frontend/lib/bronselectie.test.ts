import { describe, expect, it } from "vitest";

import { bronselectieVanKaart } from "./artefact";
import {
  bronnenZin, deelvraagStand, parseBronselectie, slotZin, voortgangToon, voortgangZin, zoekBeperkingen,
} from "./bronselectie";
import { parseVraagkaart } from "./vraagkaart";

const deelvraag = (id: string, over: Record<string, unknown> = {}) => ({
  id, nr: Number(id.slice(1)), vraag: `Vraag ${id}?`, status: "niet_gestart", fase: "kern", open_punten: [], revisie: 0,
  opnieuw_bekijken: false, klaar: false, bronnen: [], kandidaten: [],
  telling: { voorgesteld: 0, niet_gekozen: 0, uitgesloten: 0, opgenomen: 0 }, beoordelen: { mag: true, redenen: [] }, ...over,
});
const RUW = {
  werkgebied_id: "wg1", naam: "Betalingstermijnen", revisie: 3, modus: "deelvragen", actief: "d2", volgende: "d3",
  alle_klaar: false, zonder_deelvraag: [],
  deelvragen: [
    deelvraag("d1", { status: "voorlopig_afgerond", klaar: true,
      bronnen: [{ selectie_id: "s1", bron_iri: "urn:bwb:BWBR0004770:artikel:9", label: "Artikel 9", rol: "context" }] }),
    deelvraag("d2", { status: "in_behandeling", open_punten: [{ tekst: "Bijzondere invorderbaarheid" }],
      kandidaten: [{ id: "K1", bron_iri: "urn:bwb:BWBR0004770:artikel:10", label: "Artikel 10", rol: "kern",
        bewijs_soorten: ["verwijzing", "onzin"], stand: "niet_gekozen", overal: false }] }),
    deelvraag("d3"), { geen: "id" },
  ],
  zoekdekking: { gezocht: true, verouderd: false, volledig: false, onvolledig: ["deelvraag"], reden: "" },
};

describe("bronselectie", () => {
  it("leest het overzicht streng waar het telt", () => {
    const o = parseBronselectie(RUW)!;
    expect(o.deelvragen.map((d) => d.id)).toEqual(["d1", "d2", "d3"]);
    expect(o.deelvragen[0].bronnen[0].rol).toBe("context");
    expect(o.deelvragen[1].kandidaten[0]).toMatchObject({ stand: "niet_gekozen", bewijs_soorten: ["verwijzing"] });
    expect(parseBronselectie({ deelvragen: [] })).toBeUndefined();
    expect(voortgangZin(o)).toBe("1 van 3 deelvragen afgerond");
  });

  it("een afgekapte zoekopdracht staat er, en de slotzin zegt nooit 'volledig'", () => {
    const o = parseBronselectie(RUW)!;
    expect(zoekBeperkingen(o.zoekdekking)).toEqual(["Niet alles is doorzocht (deelvraag): de voorstellen kunnen onvolledig zijn."]);
    expect(slotZin(o)).toMatch(/nog niet beoordeeld/);
    const klaar = parseBronselectie({ ...RUW, deelvragen: [deelvraag("d1", { status: "beoordeeld", klaar: true })],
      zoekdekking: { gezocht: true, volledig: true, onvolledig: [] } })!;
    expect(slotZin(klaar)).toMatch(/binnen de vastgestelde afbakening en de beschikbare bronnen/);
    expect(slotZin(klaar)).toMatch(/geen oordeel dat de analyse juridisch volledig is/);
  });

  it("kleur alleen bij een oordeel", () => {
    expect(voortgangToon({ status: "beoordeeld", opnieuw_bekijken: false })).toBe("groen");
    expect(voortgangToon({ status: "beoordeeld", opnieuw_bekijken: true })).toBe("geel");
    expect(voortgangToon({ status: "in_behandeling", opnieuw_bekijken: false })).toBe("neutraal");
  });

  it("een kaartje van de bronselectie wijst naar het paneel van zijn werkgebied", () => {
    const k = parseVraagkaart({ intake_id: "bs-wg1", modus: "bronselectie", stap: "bs_afronden", deelvraag_id: "d2",
      vraag: "Hoe rond je deelvraag 2 af?" });
    expect(bronselectieVanKaart(k)).toEqual({ soort: "bronselectie", werkgebied_id: "wg1", run_id: "", deelvraag_id: "d2", titel: "Bronselectie" });
    expect(bronselectieVanKaart(parseVraagkaart({ intake_id: "ik1", stap: "naam", vraag: "Naam?" }))).toBeUndefined();
  });
});

describe("de stand van een deelvraag in een rij (spoor K)", () => {
  it("is de voortgang van de bronselectie, geen begrip", () => {
    expect(deelvraagStand(undefined)).toBeNull();
    expect(deelvraagStand({ status: "voorlopig_afgerond", opnieuw_bekijken: false })).toEqual({ label: "Voorlopig afgerond", toon: "neutraal" });
    expect(deelvraagStand({ status: "beoordeeld", opnieuw_bekijken: false })).toEqual({ label: "Beoordeeld", toon: "groen" });
    expect(deelvraagStand({ status: "beoordeeld", opnieuw_bekijken: true })).toEqual({ label: "Opnieuw bekijken", toon: "geel" });
  });

  it("telt bronnen in gewone woorden", () => {
    expect([bronnenZin(0), bronnenZin(1), bronnenZin(3)]).toEqual(["nog geen bronnen", "1 bron", "3 bronnen"]);
  });
});
