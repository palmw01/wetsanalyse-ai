import { describe, expect, it } from "vitest";
import vectoren from "./jci-vectoren.json";
import { bouwGraaf, bronDoel, clusterPlek, hoofdactie, paneelDoel, vindplaatsVan, isDubbelklik, relatieGroepen, samenvatting, uitklapbaar, voegSamen, zichtbareGraaf, zoekKnopen, type Samenhang, type SamenhangKnoop } from "./samenhang";

const LAW = "urn:bwb:BWBR0004770", ART = `${LAW}:artikel:9`, L1 = `${ART}:lid:1`, L2 = `${ART}:lid:2`;
const A10 = `${LAW}:artikel:10`;
function knoop(id: string, soort: SamenhangKnoop["soort"], extra: Partial<SamenhangKnoop> = {}): SamenhangKnoop {
  return { id, soort, label: id, tekst: "", klasse: "", lifecycle: "", element_id: "", bwb_id: "BWBR0004770",
    artikel: "", lid: "", rand: false, ...extra };
}
function samenhang(artikel = ART, extra: Partial<Samenhang> = {}): Samenhang {
  return {
    schema_versie: 1, doel: { bron_iri: artikel }, snapshot_id: "s", artikel_iri: artikel, verwijzingen_beschikbaar: true, afgekapt: false,
    knopen: [knoop(LAW, "regeling"), knoop(ART, "artikel"), knoop(L1, "lid", { lid: "1", artikel: "9" }),
      knoop(L2, "lid", { lid: "2", artikel: "9" }), knoop("element:e1", "markering", { klasse: "Rechtssubject", element_id: "e1" }),
      knoop("klasse:Rechtssubject", "klasse", { klasse: "Rechtssubject" }), knoop(A10, "artikel", { rand: true, artikel: "10" })],
    relaties: [
      { bron: LAW, doel: ART, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: ART, doel: L1, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: ART, doel: L2, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: L2, doel: L1, soort: "verwijst_naar", groep: "verwijzingen", anker_tekst: "het eerste lid" },
      { bron: L1, doel: A10, soort: "verwijst_naar", groep: "verwijzingen", anker_tekst: "artikel 10" },
      { bron: "element:e1", doel: L1, soort: "markeert", groep: "annotaties", anker_tekst: "" },
      { bron: "element:e1", doel: "klasse:Rechtssubject", soort: "heeft_klasse", groep: "annotaties", anker_tekst: "" },
    ],
    ...extra,
  };
}
const ALLES = { structuur: true, verwijzingen: true, annotaties: true };

describe("bouwGraaf", () => {
  it("geeft vaste, herhaalbare posities zonder samenvallende knopen", () => {
    const a = bouwGraaf([samenhang()]), b = bouwGraaf([samenhang()]);
    expect(a).toEqual(b);
    const plekken = a.nodes.map((n) => `${n.x}|${n.y}|${n.z}`);
    expect(new Set(plekken).size).toBe(plekken.length);
    expect(a.nodes.every((n) => n.fx === n.x && n.fy === n.y && n.fz === n.z)).toBe(true);
  });
  it("labelt leden met artikel en kleurt markeringen naar hun klasse", () => {
    const g = bouwGraaf([samenhang()]);
    expect(g.nodes.find((n) => n.id === L2)?.label).toBe("Artikel 9 · lid 2");
    expect(g.nodes.find((n) => n.id === "element:e1")?.kleur).toMatch(/^#/);
  });
  it("verschuift de bestaande kaart niet als een artikel wordt bijgeladen", () => {
    const tweede = samenhang(A10, { knopen: [knoop(LAW, "regeling"), knoop(A10, "artikel", { artikel: "10" }),
      knoop(`${A10}:lid:1`, "lid", { lid: "1", artikel: "10" })],
      relaties: [{ bron: LAW, doel: A10, soort: "bevat", groep: "structuur", anker_tekst: "" },
        { bron: A10, doel: `${A10}:lid:1`, soort: "bevat", groep: "structuur", anker_tekst: "" }] });
    const voor = bouwGraaf([samenhang()]), na = bouwGraaf([samenhang(), tweede]);
    for (const n of voor.nodes) {
      const m = na.nodes.find((x) => x.id === n.id)!;
      expect([m.x, m.y, m.z]).toEqual([n.x, n.y, n.z]);
    }
    expect(na.nodes.find((n) => n.id === A10)?.rand).toBe(false);
    expect(na.nodes.some((n) => n.id === `${A10}:lid:1`)).toBe(true);
  });
  it("legt veel losse artikelen in een raster, niet op één lijn", () => {
    // "Welke artikelen gaan over invordering?" opende acht artikelen uit vier wetten zonder onderlinge
    // relatie: op één lijn een streep van ruim 5000 eenheden, en na het inpassen elk cluster een stip.
    const delen = Array.from({ length: 8 }, (_, i) => {
      const art = `${LAW}:artikel:${100 + i}`;
      return samenhang(art, { knopen: [knoop(art, "artikel", { artikel: String(100 + i) }),
        knoop(`${art}:lid:1`, "lid", { lid: "1", artikel: String(100 + i) })],
      relaties: [{ bron: art, doel: `${art}:lid:1`, soort: "bevat", groep: "structuur", anker_tekst: "" }] });
    });
    const g = bouwGraaf(delen);
    const xs = g.nodes.map((n) => n.x), ys = g.nodes.map((n) => n.y);
    const breed = Math.max(...xs) - Math.min(...xs), hoog = Math.max(...ys) - Math.min(...ys);
    expect(breed / hoog).toBeLessThan(2.5);
    expect(clusterPlek(4)).toEqual([760, -680]);
  });
  it("geeft een straal per soort", () => {
    const g = bouwGraaf([samenhang()]);
    const straal = (id: string) => g.nodes.find((n) => n.id === id)!.straal;
    expect(straal(ART)).toBeGreaterThan(straal(L1));
    expect(straal(L1)).toBeGreaterThan(straal("element:e1"));
    expect(straal(A10)).toBeLessThan(straal(L1));
  });
});

describe("voegSamen", () => {
  it("is idempotent", () => {
    const een = voegSamen([samenhang()]);
    expect(voegSamen([samenhang(), samenhang()])).toEqual(een);
  });
});

describe("zichtbareGraaf", () => {
  const g = bouwGraaf([samenhang()]);
  it("toont bronstructuur en annotaties meteen; uitklappen toont verwijzingen", () => {
    const begin = zichtbareGraaf(g, [], ALLES).nodes.map((n) => n.id);
    expect(begin).toEqual(expect.arrayContaining([ART, L1, L2, LAW, "element:e1", "klasse:Rechtssubject"]));
    expect(begin).not.toContain(A10);
    expect(zichtbareGraaf(g, [L1], ALLES).nodes.map((n) => n.id)).toContain(A10);
  });
  it("het markeringsfilter verbergt markeringen en klassen die niets meer markeren, nooit structuur", () => {
    const met = (extra: object) => bouwGraaf([{ ...samenhang(), knopen: samenhang().knopen.map((k) =>
      k.soort === "markering" ? { ...k, lifecycle: "voorgesteld", herkomst: "agent", aandacht: "geel", twijfel: false, ...extra } : k) }]);
    const ids = (gr: ReturnType<typeof bouwGraaf>, f: Parameters<typeof zichtbareGraaf>[3]) => zichtbareGraaf(gr, [], ALLES, f).nodes.map((n) => n.id);
    expect(ids(met({}), "aandacht")).toEqual(expect.arrayContaining(["element:e1", "klasse:Rechtssubject"]));
    expect(ids(met({}), "te_beoordelen")).toContain("element:e1");
    const zonder = ids(met({}), "jurist");
    expect(zonder).not.toContain("element:e1");
    expect(zonder).not.toContain("klasse:Rechtssubject");
    expect(zonder).toEqual(expect.arrayContaining([ART, L1, L2, LAW]));
    expect(ids(met({ twijfel: true }), "twijfel")).toContain("element:e1");
    expect(ids(met({}), "alle")).toContain("element:e1");
  });
  it("filters verbergen annotaties en randknopen", () => {
    const zonder = zichtbareGraaf(g, [L1, "element:e1"], { ...ALLES, annotaties: false, verwijzingen: false });
    expect(zonder.nodes.some((n) => n.soort === "markering" || n.rand)).toBe(false);
    expect(zonder.links.every((l) => l.groep === "structuur")).toBe(true);
  });
});

describe("bronDoel", () => {
  it("gooit niet bij een kapotte percent-encoding, maar geeft niets terug", () => {
    expect(() => bronDoel("urn:bwb:BWBR0004770:artikel:10%")).not.toThrow();
    expect(bronDoel("urn:bwb:BWBR0004770:artikel:10%")).toBeUndefined();
  });

  it("vertaalt jci en graaf-IRI naar een bronnode", () => {
    expect(bronDoel("jci1.3:c:BWBR0004770&artikel=9&lid=2&z=2026-01-01&g=2026-01-01")).toMatchObject(
      { bron_iri: L2, bwb_id: "BWBR0004770", artikel: "9", lid: "2" });
    expect(bronDoel(ART)?.bron_iri).toBe(ART);
    // Een graaf-IRI blijft heel, ook met een ge-escapete dubbele punt in het artikelnummer.
    expect(bronDoel("urn:bwb:BWBR0005537:artikel:3%3A40")?.bron_iri).toBe("urn:bwb:BWBR0005537:artikel:3%3A40");
  });
  it.each(vectoren.vectoren)("$ref → $iri (zelfde regel als importer en agent)", ({ ref, iri, soort, label }) => {
    const doel = bronDoel(ref);
    // Een hele regeling of een verwijzing zonder eigen node is geen bronnode om te openen.
    if (soort === null || soort === "regeling") return expect(doel).toBeUndefined();
    expect(doel?.bron_iri).toBe(iri);
    expect(doel?.label).toBe(label);
  });
  it.each(vectoren.vectoren)("vindplaatsVan $ref (spiegel van bronmodel.vindplaats)", ({ ref, iri, soort, label }) => {
    const vp = vindplaatsVan(ref);
    if (soort === null) return expect(vp).toBeUndefined();
    expect([vp?.bron_iri, vp?.soort, vp?.label]).toEqual([iri, soort, label]);
  });
  it("weigert een hele regeling, een id-knoop en vreemde bronnen", () => {
    expect(bronDoel("jci1.3:c:BWBR0004770")).toBeUndefined();
    expect(bronDoel(`${LAW}:id:abc`)).toBeUndefined();
    expect(bronDoel("https://example.org")).toBeUndefined();
  });
  it("randknopen zijn alleen uitklapbaar als ze geïmporteerd zijn", () => {
    expect(uitklapbaar({ rand: true, soort: "artikel", bwb_id: "BWBR1" })).toBe(true);
    expect(uitklapbaar({ rand: true, soort: "extern", bwb_id: "BWBR1" })).toBe(false);
  });
});

describe("bouwGraaf op de schaal van een echt artikel", () => {
  // Naar de vorm van IW 1990 art. 9 op acceptatie: 12 leden, 4 onderdelen onder lid 9, een
  // hoofdstuk erboven, veel inkomende verwijzingen op het artikel en enkele uit losse leden.
  const H = `${LAW}:hoofdstuk:IV`;
  const leden = Array.from({ length: 12 }, (_, i) => `${ART}:lid:${i + 1}`);
  const onderdelen = ["a", "b", "c", "d"].map((o) => `${ART}:lid:9:onderdeel:${o}`);
  const inkomend = Array.from({ length: 25 }, (_, i) => `urn:bwb:BWBR0002320:artikel:30${String.fromCharCode(97 + i)}`);
  const uitgaand = [3, 4, 4, 8, 9, 10].map((l, i) => [`${ART}:lid:${l}`, `${LAW}:artikel:${60 + i}`] as const);
  const groot: Samenhang = {
    schema_versie: 1, doel: { bron_iri: leden[0] }, snapshot_id: "s", artikel_iri: ART, verwijzingen_beschikbaar: true, afgekapt: false,
    knopen: [knoop(LAW, "regeling"), knoop(H, "deel"), knoop(ART, "artikel"),
      ...leden.map((id, i) => knoop(id, "lid", { lid: String(i + 1), artikel: "9" })),
      ...onderdelen.map((id) => knoop(id, "onderdeel")),
      knoop("element:m1", "markering", { klasse: "Rechtsobject" }), knoop("element:m2", "markering", { klasse: "Tijdsaanduiding" }),
      knoop("klasse:Rechtsobject", "klasse", { klasse: "Rechtsobject" }), knoop("klasse:Tijdsaanduiding", "klasse", { klasse: "Tijdsaanduiding" }),
      ...inkomend.map((id) => knoop(id, "artikel", { rand: true, bwb_id: "BWBR0002320" })),
      ...uitgaand.map(([, id]) => knoop(id, "artikel", { rand: true }))],
    relaties: [
      { bron: LAW, doel: H, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: H, doel: ART, soort: "bevat", groep: "structuur", anker_tekst: "" },
      ...leden.map((id) => ({ bron: ART, doel: id, soort: "bevat" as const, groep: "structuur" as const, anker_tekst: "" })),
      ...onderdelen.map((id) => ({ bron: leden[8], doel: id, soort: "bevat" as const, groep: "structuur" as const, anker_tekst: "" })),
      ...["m1", "m2"].map((m) => ({ bron: `element:${m}`, doel: leden[0], soort: "markeert" as const, groep: "annotaties" as const, anker_tekst: "" })),
      { bron: "element:m1", doel: "klasse:Rechtsobject", soort: "heeft_klasse", groep: "annotaties", anker_tekst: "" },
      { bron: "element:m2", doel: "klasse:Tijdsaanduiding", soort: "heeft_klasse", groep: "annotaties", anker_tekst: "" },
      ...inkomend.map((id) => ({ bron: id, doel: ART, soort: "verwijst_naar" as const, groep: "verwijzingen" as const, anker_tekst: "" })),
      ...uitgaand.map(([van, naar]) => ({ bron: van, doel: naar, soort: "verwijst_naar" as const, groep: "verwijzingen" as const, anker_tekst: "" })),
    ],
  };
  const g = bouwGraaf([groot]);
  const afstand = (a: { x: number; y: number; z: number }, b: typeof a) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

  it("houdt afstand tussen alle knopen", () => {
    let min = Infinity;
    for (const [i, a] of g.nodes.entries()) for (const b of g.nodes.slice(i + 1)) min = Math.min(min, afstand(a, b));
    expect(min).toBeGreaterThan(20);
  });
  it("is geen hoge kolom: de kaart past in een breed paneel", () => {
    const xs = g.nodes.map((n) => n.x), ys = g.nodes.map((n) => n.y);
    const breed = Math.max(...xs) - Math.min(...xs), hoog = Math.max(...ys) - Math.min(...ys);
    expect(breed / hoog).toBeGreaterThan(0.8);
    expect(hoog).toBeLessThan(900);
  });
  it("heeft echte diepte en houdt verwijzingen verder weg dan de leden", () => {
    const p = (id: string) => g.nodes.find((n) => n.id === id)!;
    const zs = g.nodes.map((n) => n.z);
    expect(Math.max(...zs) - Math.min(...zs)).toBeGreaterThan(120);
    const tot = (id: string) => afstand(p(id), p(ART));
    const gem = (ids: string[]) => ids.reduce((s, id) => s + tot(id), 0) / ids.length;
    expect(gem(inkomend)).toBeGreaterThan(gem(leden));
  });
});

describe("bouwGraaf na een annotatiewijziging", () => {
  const extra = (s: Samenhang): Samenhang => ({ ...s,
    knopen: [...s.knopen, knoop("element:e2", "markering", { klasse: "Tijdsaanduiding", element_id: "e2" }),
      knoop("klasse:Tijdsaanduiding", "klasse", { klasse: "Tijdsaanduiding" })],
    relaties: [...s.relaties, { bron: "element:e2", doel: L2, soort: "markeert", groep: "annotaties", anker_tekst: "" },
      { bron: "element:e2", doel: "klasse:Tijdsaanduiding", soort: "heeft_klasse", groep: "annotaties", anker_tekst: "" }] });
  const plek = (g: ReturnType<typeof bouwGraaf>, id: string) => { const n = g.nodes.find((x) => x.id === id)!; return [n.x, n.y, n.z]; };

  it("houdt bestaande knopen op hun plek als er een markering bijkomt", () => {
    const voor = bouwGraaf([samenhang()]);
    const na = bouwGraaf([extra(samenhang())], voor);
    for (const n of voor.nodes) expect(plek(na, n.id)).toEqual(plek(voor, n.id));
    const nieuw = na.nodes.find((n) => n.id === "element:e2")!;
    expect(voor.nodes.every((n) => Math.hypot(n.x - nieuw.x, n.y - nieuw.y, n.z - nieuw.z) > 5)).toBe(true);
  });
  it("laat een weggehaalde markering verdwijnen zonder de rest te verschuiven", () => {
    const voor = bouwGraaf([extra(samenhang())]);
    const na = bouwGraaf([samenhang()], voor);
    expect(na.nodes.some((n) => n.id === "element:e2")).toBe(false);
    for (const n of na.nodes) expect(plek(na, n.id)).toEqual(plek(voor, n.id));
  });
});

describe("bediening", () => {
  const g = bouwGraaf([samenhang()]);
  it("zoekt over alle knopen, diakritiek-ongevoelig, begin vóór bevat", () => {
    const benoemd = bouwGraaf([samenhang(ART, { knopen: [
      knoop(LAW, "regeling", { label: "Invorderingswet 1990" }), knoop(ART, "artikel", { label: "Artikel 9" }),
      knoop(L1, "lid", { lid: "1", artikel: "9" }), knoop(L2, "lid", { lid: "2", artikel: "9" }),
      knoop("urn:x", "extern", { label: "Algemene wet bestuursrécht", rand: true }),
      knoop(A10, "artikel", { label: "Artikel 10", rand: true })] })]);
    expect(zoekKnopen(benoemd, "artikel").map((n) => n.id).slice(0, 2)).toEqual([ART, L1]);
    expect(zoekKnopen(benoemd, "lid 2").map((n) => n.id)).toEqual([L2]);
    expect(zoekKnopen(benoemd, "bestuursrecht").map((n) => n.id)).toEqual(["urn:x"]);
    expect(zoekKnopen(benoemd, "10").map((n) => n.id)).toContain(A10);
    expect(zoekKnopen(benoemd, "  ")).toEqual([]);
  });
  it("groepeert relaties per soort en richting, ook naar verborgen buren", () => {
    expect(relatieGroepen(g, L2).map((x) => x.naam)).toEqual(["Onderdeel van", "Verwijst naar"]);
    const lid1 = relatieGroepen(g, L1);
    expect(lid1.map((x) => x.naam)).toEqual(["Onderdeel van", "Markeringen", "Verwijst naar", "Wordt verwezen door"]);
    expect(lid1.find((x) => x.naam === "Verwijst naar")?.regels.map((r) => r.knoop.id)).toEqual([A10]);
    expect(lid1.find((x) => x.naam === "Wordt verwezen door")?.regels[0].anker_tekst).toBe("het eerste lid");
  });
  it("opent een knoop uit een ander geladen artikel in het paneel, niet in de tekst", () => {
    const k = (id: string, soort: SamenhangKnoop["soort"] = "lid") => ({ id, soort, rand: false, bwb_id: "BWBR0004770" });
    const inPaneel = new Set([ART, L1]);
    expect(hoofdactie(k(L1), [ART, A10], inPaneel)).toBe("tekst");
    expect(hoofdactie(k(`${A10}:lid:1`), [ART, A10], inPaneel)).toBe("wissel");
    expect(hoofdactie(k(LAW, "regeling"), [ART, A10], inPaneel)).toBe(null);
    // Zonder haak: het oude gedrag.
    expect(hoofdactie(k(`${A10}:lid:1`), [ART, A10])).toBe("tekst");
  });
  it("paneelDoel: de bronnode zelf, of voor een markering zijn artikel", () => {
    expect(paneelDoel({ id: L1, bwb_id: "BWBR0004770", artikel: "9", label: "Lid 1" })?.bron_iri).toBe(L1);
    expect(paneelDoel({ id: "element:e1", bwb_id: "BWBR0005537", artikel: "4:94a", label: "x" })?.bron_iri)
      .toBe("urn:bwb:BWBR0005537:artikel:4%3A94a");
    expect(paneelDoel({ id: "klasse:Rechtssubject", bwb_id: "", artikel: "", label: "x" })).toBeUndefined();
  });
  it("kiest één hoofdactie per soort", () => {
    const k = (id: string) => g.nodes.find((n) => n.id === id)!;
    expect(hoofdactie(k(L1), [ART])).toBe("tekst");
    expect(hoofdactie(k("element:e1"), [ART])).toBe("tekst");
    expect(hoofdactie(k("klasse:Rechtssubject"), [ART])).toBe(null);
    expect(hoofdactie(k(A10), [ART])).toBe("openen");
    expect(hoofdactie(k(A10), [ART, A10])).toBe(null);
  });
  it("vat samen en herkent een dubbelklik", () => {
    expect(samenvatting(g)).toEqual({ leden: 2, markeringen: 1, verwijzingen: 2 });
    expect(isDubbelklik({ id: "a", tijd: 1000 }, "a", 1250)).toBe(true);
    expect(isDubbelklik({ id: "a", tijd: 1000 }, "b", 1100)).toBe(false);
    expect(isDubbelklik({ id: "a", tijd: 1000 }, "a", 1400)).toBe(false);
    expect(isDubbelklik(null, "a", 1)).toBe(false);
  });
});
