import { describe, expect, it } from "vitest";
import type { Samenhang, SamenhangKnoop } from "@/lib/samenhang";
import { hoofdactie, hoortBijWeergave, knopenInWeergave, paneelDoel, relatieGroepen, telling, tellingTekst, zoekKnopen } from "./bediening";
import { bouwModel } from "./model";

const LAW = "urn:bwb:BWBR0004770", ART = `${LAW}:artikel:9`, L1 = `${ART}:lid:1`, L2 = `${ART}:lid:2`;
const A10 = `${LAW}:artikel:10`;
function knoop(id: string, soort: SamenhangKnoop["soort"], extra: Partial<SamenhangKnoop> = {}): SamenhangKnoop {
  return { id, soort, label: id, tekst: "", klasse: "", lifecycle: "", element_id: "", bwb_id: "BWBR0004770",
    artikel: "", lid: "", rand: false, ...extra };
}
function samenhang(knopen?: SamenhangKnoop[]): Samenhang {
  return {
    schema_versie: 1, doel: { bron_iri: ART }, snapshot_id: "s", artikel_iri: ART, verwijzingen_beschikbaar: true, afgekapt: false,
    knopen: knopen ?? [knoop(LAW, "regeling", { label: "Invorderingswet 1990" }), knoop(ART, "artikel", { label: "Artikel 9" }),
      knoop(L1, "lid", { label: "Lid 1", lid: "1", artikel: "9" }), knoop(L2, "lid", { label: "Lid 2", lid: "2", artikel: "9" }),
      knoop("element:e1", "markering", { klasse: "Rechtssubject", element_id: "e1" }),
      knoop("klasse:Rechtssubject", "klasse", { klasse: "Rechtssubject" }), knoop(A10, "artikel", { label: "Artikel 10", rand: true, artikel: "10" })],
    relaties: [
      { bron: LAW, doel: ART, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: ART, doel: L1, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: ART, doel: L2, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: L2, doel: L1, soort: "verwijst_naar", groep: "verwijzingen", anker_tekst: "het eerste lid" },
      { bron: L1, doel: A10, soort: "verwijst_naar", groep: "verwijzingen", anker_tekst: "artikel 10" },
      { bron: "element:e1", doel: L1, soort: "markeert", groep: "annotaties", anker_tekst: "" },
      { bron: "element:e1", doel: "klasse:Rechtssubject", soort: "heeft_klasse", groep: "annotaties", anker_tekst: "" },
    ],
  };
}
const g = bouwModel([samenhang()]);

describe("bediening", () => {
  it("zoekt over alle knopen, diakritiek-ongevoelig, begin vóór bevat, natuurlijk op nummer", () => {
    const benoemd = bouwModel([samenhang([
      knoop(LAW, "regeling", { label: "Invorderingswet 1990" }), knoop(ART, "artikel", { label: "Artikel 9" }),
      knoop(L1, "lid", { lid: "1", artikel: "9" }), knoop(L2, "lid", { lid: "2", artikel: "9" }),
      knoop("urn:x", "extern", { label: "Algemene wet bestuursrécht", rand: true }),
      knoop(A10, "artikel", { label: "Artikel 10", rand: true })])]);
    expect(zoekKnopen(benoemd, "artikel").slice(0, 2)).toEqual([ART, L1]);
    expect(zoekKnopen(benoemd, "lid 2")).toEqual([L2]);
    expect(zoekKnopen(benoemd, "bestuursrecht")).toEqual(["urn:x"]);
    expect(zoekKnopen(benoemd, "10")).toContain(A10);
    expect(zoekKnopen(benoemd, "  ")).toEqual([]);
  });

  it("groepeert relaties per soort en richting", () => {
    expect(relatieGroepen(g, L2).map((x) => x.naam)).toEqual(["Onderdeel van", "Verwijst naar"]);
    const lid1 = relatieGroepen(g, L1);
    expect(lid1.map((x) => x.naam)).toEqual(["Onderdeel van", "Markeringen", "Verwijst naar", "Wordt verwezen door"]);
    expect(lid1.find((x) => x.naam === "Verwijst naar")?.regels.map((r) => r.id)).toEqual([A10]);
    expect(lid1.find((x) => x.naam === "Wordt verwezen door")?.regels[0].anker_tekst).toBe("het eerste lid");
    expect(relatieGroepen(g, "bestaat-niet")).toEqual([]);
  });

  it("kiest één hoofdactie: tekst, wissel, laden of niets", () => {
    const a = (id: string) => g.getNodeAttributes(id);
    expect(hoofdactie(a(L1), L1)).toBe("tekst");
    expect(hoofdactie(a("element:e1"), "element:e1")).toBe("tekst");
    expect(hoofdactie(a("klasse:Rechtssubject"), "klasse:Rechtssubject")).toBe(null);
    expect(hoofdactie(a(A10), A10)).toBe("laden");
    expect(hoofdactie({ soort: "extern", rand: true, bwb_id: "" }, "urn:x")).toBe(null);
    const inPaneel = new Set([ART, L1]);
    expect(hoofdactie(a(L1), L1, inPaneel)).toBe("tekst");
    expect(hoofdactie(a(L2), L2, inPaneel)).toBe("wissel");
    expect(hoofdactie(a(LAW), LAW, inPaneel)).toBe(null);
  });

  it("paneelDoel: de bronnode zelf, of voor een markering haar artikel", () => {
    expect(paneelDoel(L1, { bwb_id: "BWBR0004770", artikel: "9", naam: "Artikel 9 · lid 1" })?.bron_iri).toBe(L1);
    expect(paneelDoel("element:e1", { bwb_id: "BWBR0005537", artikel: "4:94a", naam: "x" })?.bron_iri)
      .toBe("urn:bwb:BWBR0005537:artikel:4%3A94a");
    expect(paneelDoel("klasse:Rechtssubject", { bwb_id: "", artikel: "", naam: "x" })).toBeUndefined();
  });

  it("telt wat geladen is, zonder randbepalingen, in gewone woorden", () => {
    const t = telling(g);
    expect(t).toEqual({ regelingen: 1, bepalingen: 3, markeringen: 1, verwijzingen: 2, begrippen: 0 });
    expect(tellingTekst(t)).toBe("1 regeling · 3 bepalingen · 1 markering · 2 verwijzingen");
    expect(tellingTekst({ regelingen: 7, bepalingen: 5513, markeringen: 0, verwijzingen: 3488 })).toBe("7 regelingen · 5.513 bepalingen · 3.488 verwijzingen");
    expect(tellingTekst({ regelingen: 1, bepalingen: 2, markeringen: 1, verwijzingen: 0, begrippen: 2 })).toBe("1 regeling · 2 bepalingen · 1 markering · 2 begrippen");
  });
});

describe("wat het paneel toont", () => {
  // Het paneel staat op lid 1; de graaf heeft heel artikel 9.
  const w = {
    doel: { bron_iri: L1 },
    segmenten: [{ bron_iri: L1, type: "Lid", label: "", tekst: "De ontvanger.", bron_hash: "h", volgorde: 1 }],
    elementen: [{ id: "e1" }] as never[],
  };

  it("het doel, alles eronder en zijn markeringen horen erbij; het artikel en de andere leden niet", () => {
    expect(hoortBijWeergave(L1, w)).toBe(true);
    expect(hoortBijWeergave(`${L1}:onderdeel:a`, w)).toBe(true);
    expect(hoortBijWeergave("element:e1", w)).toBe(true);
    expect(hoortBijWeergave(ART, w)).toBe(false);
    expect(hoortBijWeergave(L2, w)).toBe(false);
    expect(hoortBijWeergave("element:e9", w)).toBe(false);
    // "lid:1" is geen voorvoegsel van "lid:10".
    expect(hoortBijWeergave(`${ART}:lid:10`, w)).toBe(false);
  });

  it("buiten de weergave wordt de hoofdactie: open in het paneel", () => {
    const g = bouwModel([samenhang()]);
    const inPaneel = knopenInWeergave(g, w);
    expect([...inPaneel].sort()).toEqual([L1, "element:e1"].sort());
    expect(hoofdactie(g.getNodeAttributes(L2), L2, inPaneel)).toBe("wissel");
    expect(hoofdactie(g.getNodeAttributes(L1), L1, inPaneel)).toBe("tekst");
  });

  it("een paneel op een deel bevat de artikelen eronder, ook al hangen hun IRI's er niet onder", () => {
    const H = `${LAW}:hoofdstuk:II`;
    const rel = (bron: string, doel: string) => ({ bron, doel, soort: "bevat" as const, groep: "structuur" as const, anker_tekst: "" });
    const g = bouwModel([{ knopen: [knoop(LAW, "regeling"), knoop(H, "deel"), knoop(ART, "artikel"), knoop(L1, "lid"), knoop(A10, "artikel")],
      relaties: [rel(LAW, H), rel(H, ART), rel(ART, L1), rel(LAW, A10)] }]);
    const opHoofdstuk = knopenInWeergave(g, { doel: { bron_iri: H }, segmenten: [], elementen: [] });
    expect([...opHoofdstuk].sort()).toEqual([H, ART, L1].sort());
  });
});
