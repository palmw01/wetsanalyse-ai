import { describe, expect, it } from "vitest";
import { bronLabel, koppelBron, markeerCitaties, vindVermeldingen } from "./citaties";
import { parseBronnen } from "./agentEvents";
import type { HastKnoop } from "./markering";
import type { Bron } from "./types";

const B = "urn:bwb:BWBR0004770";
const bron = (pad: string) => ({ label: `${B}:${pad}`, uri: `${B}:${pad}` });

describe("vindVermeldingen", () => {
  it("herkent artikel, lid en rangtelwoord", () => {
    const tekst = "Volgens artikel 9 lid 2 en art. 10a, derde lid geldt artikel 3.1.";
    expect(vindVermeldingen(tekst).map(({ artikel, lid }) => ({ artikel, lid }))).toEqual([
      { artikel: "9", lid: "2" }, { artikel: "10a", lid: "3" }, { artikel: "3.1", lid: undefined },
    ]);
    const [eerste] = vindVermeldingen(tekst);
    expect(tekst.slice(eerste.start, eerste.eind)).toBe("artikel 9 lid 2");
  });
  it("leest Awb-nummers en achtervoegsels helemaal, niet alleen het eerste getal", () => {
    const tekst = "Artikel 4:94a Awb, artikel 31bis Awir, artikel 27quinquies en art. 3:40, tweede lid.";
    expect(vindVermeldingen(tekst).map(({ artikel, lid }) => ({ artikel, lid }))).toEqual([
      { artikel: "4:94a", lid: undefined }, { artikel: "31bis", lid: undefined },
      { artikel: "27quinquies", lid: undefined }, { artikel: "3:40", lid: "2" },
    ]);
  });
});

describe("koppelBron", () => {
  const bronnen = [bron("artikel:9:lid:1"), bron("artikel:9:lid:2"), bron("artikel:10")];
  it("koppelt alleen éénduidig", () => {
    expect(koppelBron({ start: 0, eind: 0, artikel: "9", lid: "2" }, bronnen)).toBe(1);
    expect(koppelBron({ start: 0, eind: 0, artikel: "10" }, bronnen)).toBe(2);
    // "artikel 9" zonder lid: twee leden, geen hele-artikelbron – geen chip.
    expect(koppelBron({ start: 0, eind: 0, artikel: "9" }, bronnen)).toBe(-1);
    expect(koppelBron({ start: 0, eind: 0, artikel: "11" }, bronnen)).toBe(-1);
    // Eén lid onder een artikel: dan is "artikel 9" wél dat lid.
    expect(koppelBron({ start: 0, eind: 0, artikel: "9" }, [bron("artikel:9:lid:1")])).toBe(0);
  });
});

describe("markeerCitaties", () => {
  it("wikkelt de vermelding in, zonder tekst toe te voegen of weg te halen", () => {
    const boom: HastKnoop = { type: "root", children: [{ type: "element", tagName: "p", children: [
      { type: "text", value: "Zie artikel 9 lid 2 en artikel 11." }] }] };
    markeerCitaties([bron("artikel:9:lid:2")])()(boom);
    const p = boom.children![0];
    expect(p.children!.map((k) => k.tagName ?? "text")).toEqual(["text", "cite", "text"]);
    expect(p.children![1].properties).toEqual({ dataBron: "0" });
    const tekst = (k: HastKnoop): string => k.value ?? (k.children ?? []).map(tekst).join("");
    expect(tekst(p)).toBe("Zie artikel 9 lid 2 en artikel 11.");
  });

  it("laat code en links met rust", () => {
    const boom: HastKnoop = { type: "root", children: [{ type: "element", tagName: "code", children: [
      { type: "text", value: "artikel 9 lid 2" }] }] };
    markeerCitaties([bron("artikel:9:lid:2")])()(boom);
    expect(boom.children![0].children![0].type).toBe("text");
  });
});

describe("bronLabel", () => {
  it("maakt een leesbaar label van een graaf-IRI en laat de rest staan", () => {
    expect(bronLabel(bron("artikel:9:lid:2"))).toBe("Artikel 9, lid 2");
    expect(bronLabel({ label: "iets", uri: "https://example.org" })).toBe("iets");
  });
});

describe("een genoemde regeling", () => {
  const AWB = "urn:bwb:BWBR0005537";
  const iw = { ...bron("artikel:9"), regeling: "Invorderingswet 1990", afkortingen: ["IW", "Iw 1990"] };
  const awb = { label: `${AWB}:artikel:9`, uri: `${AWB}:artikel:9`, regeling: "Algemene wet bestuursrecht", afkortingen: ["Awb"] };
  const koppel = (tekst: string, bronnen: Parameters<typeof koppelBron>[1]) => koppelBron(vindVermeldingen(tekst)[0], bronnen);

  it("leest wat er achter de vermelding staat", () => {
    expect(vindVermeldingen("artikel 9 van de Algemene wet bestuursrecht geldt hier")[0].regeling?.slice(0, 2))
      .toEqual(["algemene", "wet"]);
    expect(vindVermeldingen("artikel 9, tweede lid, Awb")[0].regeling).toEqual(["awb"]);
    expect(vindVermeldingen("artikel 9 Iw 1990. Daarna")[0].regeling?.[0]).toBe("iw");
  });
  it("ziet in kleine letters of een verwijzing naar de eigen wet geen regeling", () => {
    expect(vindVermeldingen("artikel 9 van deze wet")[0].regeling).toBeUndefined();
    expect(vindVermeldingen("artikel 9 en artikel 10.")[0].regeling).toBeUndefined();
    expect(vindVermeldingen("artikel 9. De ontvanger")[0].regeling).toBeUndefined();
  });
  it("geeft geen chip als de genoemde regeling niet de bron is", () => {
    expect(koppel("artikel 9 van de Algemene wet bestuursrecht", [iw])).toBe(-1);
    expect(koppel("artikel 9 Awb", [iw])).toBe(-1);
    expect(koppel("artikel 9 van de Algemene wet inzake rijksbelastingen", [awb])).toBe(-1);
  });
  it("geeft een chip bij de citeertitel, zonder jaartal en bij de afkorting", () => {
    expect(koppel("artikel 9 van de Invorderingswet 1990", [iw])).toBe(0);
    expect(koppel("artikel 9 van de Invorderingswet geldt", [iw])).toBe(0);
    expect(koppel("artikel 9 Iw", [iw])).toBe(0);
    expect(koppel("artikel 9 IW 1990", [iw])).toBe(0);
    expect(koppel("artikel 9 Leidr. Inv.", [{ ...iw, regeling: "Leidraad Invordering 2008", afkortingen: ["Leidr. Inv."] }])).toBe(0);
  });
  it("laat de regeling beslissen als twee wetten hetzelfde nummer hebben", () => {
    expect(koppel("artikel 9 Awb", [iw, awb])).toBe(1);
    expect(koppel("artikel 9 Iw", [iw, awb])).toBe(0);
    expect(koppel("artikel 9", [iw, awb])).toBe(-1);
  });
  it("koppelt zonder genoemde regeling zoals altijd", () => {
    expect(koppel("artikel 9 van deze wet", [iw])).toBe(0);
  });
  it("geeft geen chip als de naam van de bron onbekend is", () => {
    expect(koppel("artikel 9 Awb", [bron("artikel:9")])).toBe(-1);
  });
});

describe("de bron uit de live stroom", () => {
  it("houdt de velden waarmee een vermelding gekoppeld wordt", () => {
    const [bron] = parseBronnen([{ label: "Artikel 9", uri: `${B}:artikel:9`, bron_iri: `${B}:artikel:9`, jci: null, bwb_id: "BWBR0004770",
      soort: "artikel", regeling: "Invorderingswet 1990", afkortingen: ["IW", "Iw 1990"], origin_tool: "get_artikel" }]) as Bron[];
    expect(bron).toEqual({ label: "Artikel 9", uri: `${B}:artikel:9`, bron_iri: `${B}:artikel:9`, bwb_id: "BWBR0004770",
      soort: "artikel", regeling: "Invorderingswet 1990", afkortingen: ["IW", "Iw 1990"] });
    expect(koppelBron(vindVermeldingen("artikel 9 Iw")[0], [bron])).toBe(0);
  });
});
