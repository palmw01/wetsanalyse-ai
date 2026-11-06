import { describe, expect, it } from "vitest";
import type { Samenhang, SamenhangKnoop, SamenhangRelatie } from "@/lib/samenhang";
import { layoutSleutel, leesLayout, naarReeksen, uitReeksen } from "./cache";
import { berekenLayout, layoutKeten, plaatsAnnotaties, startposities, structuurVan, type Posities } from "./layout";
import { bouwModel, type GraafBron } from "./model";
import { proefgraaf } from "./proefgraaf";
import { layoutVoor } from "./rekenaar";
import { ketenZin } from "./ketenZin";
import { BEGRIPKLEUR, eigenKleur, GEDIMD, NADRUK_LIJN, WETBEGRIPKLEUR } from "./stijl";
import { focusVan, ketenFocus, knoopBeeld, lagenVoor, lijnBeeld, STANDAARD_LAGEN, verborgenKnopen, weergaveContext, type WeergaveStand } from "./weergave";

const IW = "urn:bwb:BWBR0004770";
const H = `${IW}:hoofdstuk:II`, A9 = `${IW}:artikel:9`, L1 = `${A9}:lid:1`, L2 = `${A9}:lid:2`, A10 = `${IW}:artikel:10`;
const AWB = "urn:bwb:BWBR0005537:artikel:4%3A94a";

function knoop(id: string, soort: SamenhangKnoop["soort"], label: string, extra: Partial<SamenhangKnoop> = {}): SamenhangKnoop {
  return { id, soort, label, tekst: "", klasse: "", lifecycle: "", element_id: "", bwb_id: "BWBR0004770", artikel: "", lid: "", rand: false, ...extra };
}
const rel = (bron: string, soort: SamenhangRelatie["soort"], doel: string): SamenhangRelatie => ({
  bron, doel, soort, anker_tekst: "",
  groep: soort === "bevat" ? "structuur" : soort === "verwijst_naar" ? "verwijzingen" : "annotaties",
});

/** Iw hoofdstuk II met artikel 9 (twee leden) en 10; lid 1 verwijst naar Awb 4:94a (rand) en draagt
 *  twee markeringen. */
const BRON: GraafBron = {
  knopen: [
    knoop(IW, "regeling", "Invorderingswet 1990"), knoop(H, "deel", "Hoofdstuk II"),
    knoop(A9, "artikel", "Artikel 9", { artikel: "9" }), knoop(A10, "artikel", "Artikel 10", { artikel: "10" }),
    knoop(L1, "lid", "Lid 1", { artikel: "9", lid: "1" }), knoop(L2, "lid", "Lid 2", { artikel: "9", lid: "2" }),
    knoop(AWB, "artikel", "Artikel 4:94a", { rand: true, bwb_id: "BWBR0005537" }),
    knoop("element:1", "markering", "de ontvanger", { klasse: "Rechtssubject", lifecycle: "voorgesteld", bwb_id: "" }),
    knoop("element:2", "markering", "vordert in", { klasse: "Rechtsfeit", lifecycle: "human_approved", herkomst: "mens", bwb_id: "" }),
    knoop("klasse:Rechtssubject", "klasse", "Rechtssubject", { klasse: "Rechtssubject", bwb_id: "" }),
    knoop("klasse:Rechtsfeit", "klasse", "Rechtsfeit", { klasse: "Rechtsfeit", bwb_id: "" }),
  ],
  relaties: [
    rel(IW, "bevat", H), rel(H, "bevat", A9), rel(H, "bevat", A10), rel(A9, "bevat", L1), rel(A9, "bevat", L2),
    rel(L1, "verwijst_naar", AWB),
    rel("element:1", "markeert", L1), rel("element:1", "heeft_klasse", "klasse:Rechtssubject"),
    rel("element:2", "markeert", L1), rel("element:2", "heeft_klasse", "klasse:Rechtsfeit"),
  ],
};

const gelijk = (a: Posities, b: Posities) => [...a].every(([id, [x, y]]) => b.get(id)?.[0] === x && b.get(id)?.[1] === y) && a.size === b.size;

describe("model", () => {
  it("noemt een lid naar zijn artikel en houdt het kaartlabel kort", () => {
    const g = bouwModel([BRON]);
    expect(g.getNodeAttributes(L1)).toMatchObject({ naam: "Artikel 9 · lid 1", kort: "Lid 1" });
    expect(g.getNodeAttribute(IW, "kort")).toBe("Invorderingswet 1990");
  });

  it("noemt een onderdeel naar zijn vindplaats uit de boom, niet naar het kale label", () => {
    const LR = "urn:bwb:BWBR0024096", O = `${LR}:artikel:9:o:d`;
    const bron: GraafBron = {
      knopen: [knoop(O, "onderdeel", "Onderdeel d.", { bwb_id: "BWBR0024096", artikel: "9.2", vindplaats: "Artikel 9.2, onderdeel d" })],
      relaties: [],
    };
    expect(bouwModel([bron]).getNodeAttributes(O)).toMatchObject({ naam: "Artikel 9.2, onderdeel d", kort: "Onderdeel d." });
    const zonder: GraafBron = { knopen: [knoop(O, "onderdeel", "Onderdeel d.", { bwb_id: "BWBR0024096" })], relaties: [] };
    expect(bouwModel([zonder]).getNodeAttribute(O, "naam")).toBe("Onderdeel d.");
  });

  it("een knoop is alleen rand als hij dat in élk antwoord is", () => {
    const awb: GraafBron = { knopen: [knoop(AWB, "artikel", "Artikel 4:94a", { bwb_id: "BWBR0005537", tekst: "Kwijtschelding." })], relaties: [] };
    expect(bouwModel([BRON, awb]).getNodeAttribute(AWB, "rand")).toBe(false);
    expect(bouwModel([awb, BRON]).getNodeAttribute(AWB, "tekst")).toBe("Kwijtschelding.");
  });

  it("is onafhankelijk van de volgorde van knopen en relaties, en laat losse relaties vallen", () => {
    const omgekeerd: GraafBron = { knopen: [...BRON.knopen].reverse(), relaties: [...BRON.relaties, rel(L2, "verwijst_naar", "urn:bwb:weg")].reverse() };
    const a = bouwModel([BRON]), b = bouwModel([omgekeerd]);
    expect(b.nodes()).toEqual(a.nodes());
    expect(b.edges()).toEqual(a.edges());
  });
});

describe("layout", () => {
  it("is deterministisch, ook bij een andere volgorde van de invoer", () => {
    const a = berekenLayout(structuurVan(bouwModel([BRON])));
    const b = berekenLayout(structuurVan(bouwModel([{ knopen: [...BRON.knopen].reverse(), relaties: [...BRON.relaties].reverse() }])));
    expect(gelijk(a, b)).toBe(true);
    expect([...a.values()].every(([x, y]) => Number.isFinite(x) && Number.isFinite(y))).toBe(true);
  });

  it("houdt bij bijladen de bestaande kaart vast en plaatst alleen het nieuwe", () => {
    const voor = berekenLayout(structuurVan(bouwModel([BRON])));
    const extra: GraafBron = { knopen: [knoop(`${A10}:lid:1`, "lid", "Lid 1", { artikel: "10", lid: "1" })], relaties: [rel(A10, "bevat", `${A10}:lid:1`)] };
    const na = berekenLayout(structuurVan(bouwModel([BRON, extra])), { vast: voor });
    for (const [id, p] of voor) expect(na.get(id)).toEqual(p);
    expect(na.has(`${A10}:lid:1`)).toBe(true);
  });

  it("een randbepaling start naast de bepaling die naar haar verwijst", () => {
    const s = structuurVan(bouwModel([BRON]));
    const pos = startposities(s);
    const [lx, ly] = pos.get(L1)!, [rx, ry] = pos.get(AWB)!;
    const [ix, iy] = pos.get(IW)!;
    expect(Math.hypot(rx - lx, ry - ly)).toBeLessThan(Math.hypot(rx - ix, ry - iy) + 1e-9);
  });

  it("legt de hele kennisgraaf in één keer: elke regeling een eigen gebied", { timeout: 60_000 }, () => {
    const p = proefgraaf();
    const g = bouwModel([p]);
    const s = structuurVan(g);
    expect(g.order).toBeGreaterThan(6000);
    const begin = performance.now();
    const pos = berekenLayout(s);
    // Ruim boven de ~3,5 s die het lokaal kost: dit vangt een terugval naar kwadratisch, geen ruis.
    expect(performance.now() - begin).toBeLessThan(30_000);
    expect(pos.size).toBe(s.knopen.length);
    // Een artikel ligt dichter bij zijn eigen regeling dan bij welke andere ook.
    const regelingen = s.knopen.filter((k) => k.soort === "regeling").map((k) => k.id);
    const artikelen = s.knopen.filter((k) => k.soort === "artikel").map((k) => k.id);
    const thuis = artikelen.filter((a) => {
      const [x, y] = pos.get(a)!;
      const dichtst = regelingen.reduce((best, r) => {
        const [rx, ry] = pos.get(r)!;
        return Math.hypot(rx - x, ry - y) < best.d ? { r, d: Math.hypot(rx - x, ry - y) } : best;
      }, { r: "", d: Infinity });
      return a.startsWith(dichtst.r + ":");
    });
    expect(thuis.length / artikelen.length).toBeGreaterThan(0.95);
  });
});

describe("annotaties", () => {
  const g = bouwModel([BRON]);
  const bron = berekenLayout(structuurVan(g));
  const pos = plaatsAnnotaties(g, bron);

  it("laat de wettekst staan en zet een markering bij haar anker", () => {
    for (const [id, p] of bron) expect(pos.get(id)).toEqual(p);
    const [lx, ly] = pos.get(L1)!, [mx, my] = pos.get("element:1")!;
    const [ix, iy] = pos.get(IW)!;
    expect(Math.hypot(mx - lx, my - ly)).toBeLessThan(Math.hypot(mx - ix, my - iy));
  });

  it("een nieuwe markering verschuift de bestaande niet", () => {
    const extra: GraafBron = {
      knopen: [knoop("element:3", "markering", "uitstel", { klasse: "Rechtsfeit", bwb_id: "" })],
      relaties: [rel("element:3", "markeert", L1), rel("element:3", "heeft_klasse", "klasse:Rechtsfeit")],
    };
    const na = plaatsAnnotaties(bouwModel([BRON, extra]), bron);
    expect(na.get("element:1")).toEqual(pos.get("element:1"));
    expect(na.get("element:2")).toEqual(pos.get("element:2"));
  });

  it("zet de klassen op een ring om de kaart", () => {
    const [kx, ky] = pos.get("klasse:Rechtssubject")!;
    const midden = [...bron.values()].reduce(([sx, sy], [x, y]) => [sx + x / bron.size, sy + y / bron.size], [0, 0]);
    const verst = Math.max(...[...bron.values()].map(([x, y]) => Math.hypot(x - midden[0], y - midden[1])));
    expect(Math.hypot(kx - midden[0], ky - midden[1])).toBeGreaterThan(verst);
  });
});

describe("cache", () => {
  it("de sleutel hangt alleen af van de structuur", async () => {
    const a = await layoutSleutel(structuurVan(bouwModel([BRON])));
    const omgekeerd = await layoutSleutel(structuurVan(bouwModel([{ knopen: [...BRON.knopen].reverse(), relaties: [...BRON.relaties].reverse() }])));
    const zonderMarkering = await layoutSleutel(structuurVan(bouwModel([{ ...BRON, knopen: BRON.knopen.filter((k) => k.id !== "element:2") }])));
    const anders = await layoutSleutel(structuurVan(bouwModel([{ ...BRON, relaties: BRON.relaties.filter((r) => r.doel !== L2) }])));
    expect(omgekeerd).toBe(a);
    expect(zonderMarkering).toBe(a);
    expect(anders).not.toBe(a);
  });

  it("posities gaan heen en weer door de platte reeksen", () => {
    const pos: Posities = new Map([["a", [1.5, -2]], ["b", [0, 3.25]]]);
    const { ids, xy } = naarReeksen(pos);
    expect(uitReeksen(ids, xy)).toEqual(pos);
  });

  it("zonder opslag is lezen gewoon een misser", async () => {
    expect(await leesLayout("bestaat-niet")).toBeUndefined();
  });

  it("een vervallen vraag levert niets op, ook niet na het wachten op de cache", async () => {
    // Afgebroken terwijl de sleutel en de cache nog lopen: daarna geen uitkomst, maar een AbortError –
    // anders zet een oude run zijn kaart over een nieuwere heen.
    const afbreken = new AbortController();
    const belofte = layoutVoor(bouwModel([BRON]), { signal: afbreken.signal });
    afbreken.abort();
    await expect(belofte).rejects.toMatchObject({ name: "AbortError" });
  });

  it("een vaste stand zonder nieuwe wettekst rekent niets en verschuift niets", async () => {
    const g = bouwModel([BRON]);
    const vast = berekenLayout(structuurVan(g));
    const { posities, uitCache } = await layoutVoor(g, { vast });
    expect(uitCache).toBe(true);
    for (const [id, p] of vast) expect(posities.get(id)).toEqual(p);
  });
});

describe("weergave", () => {
  const g = bouwModel([BRON]);
  const stand = (s: Partial<WeergaveStand> = {}): WeergaveStand => ({
    lagen: STANDAARD_LAGEN, markering: "alle", selectie: null, focus: null, ongedekt: new Set(), ...s,
  });
  const beeld = (id: string, s: WeergaveStand) => knoopBeeld(id, g.getNodeAttributes(id), weergaveContext(g, s));

  it("lagen bepalen wat zichtbaar is; een keuze verandert dat nooit", () => {
    expect(verborgenKnopen(g, { ...STANDAARD_LAGEN, leden: false }, "alle")).toEqual(new Set([L1, L2, "element:1", "element:2", "klasse:Rechtssubject", "klasse:Rechtsfeit"]));
    expect(verborgenKnopen(g, { ...STANDAARD_LAGEN, verwijzingen: false }, "alle")).toEqual(new Set([AWB]));
    const zonder = weergaveContext(g, stand()).verborgen, met = weergaveContext(g, stand({ selectie: A10 })).verborgen;
    expect([...met]).toEqual([...zonder]);
  });

  it("het markeringsfilter laat een klasse zonder markering verdwijnen", () => {
    expect(verborgenKnopen(g, STANDAARD_LAGEN, "jurist")).toEqual(new Set(["element:1", "klasse:Rechtssubject"]));
  });

  it("nadruk: de keuze met haar buren gaat voor de focus, de focus voor alles", () => {
    const focus = focusVan(g, [A9]);
    expect([...focus.bereik].sort()).toEqual([A9, L1, L2, AWB, "element:1", "element:2", "klasse:Rechtsfeit", "klasse:Rechtssubject"].sort());
    expect(weergaveContext(g, stand()).nadruk).toBeNull();
    expect(beeld(A10, stand({ focus })).gedimd).toBe(true);
    expect(beeld(L1, stand({ focus })).gedimd).toBe(false);
    const gekozen = stand({ focus, selectie: A10 });
    expect(beeld(A10, gekozen)).toMatchObject({ gekozen: true, altijdLabel: true, niveau: 3 });
    expect(beeld(H, gekozen)).toMatchObject({ gedimd: false, altijdLabel: true });
    expect(beeld(L1, gekozen)).toMatchObject({ gedimd: true, kleur: GEDIMD, label: null });
    // De keuze opheffen (klik op de achtergrond) brengt de focus terug.
    expect(beeld(L1, stand({ focus, selectie: null })).gedimd).toBe(false);
  });

  it("de focus van een bepaling neemt haar verwijzingen mee, die van een hoofdstuk niet", () => {
    expect(focusVan(g, [L2]).bereik).toEqual(new Set([L2]));
    expect(focusVan(g, [L1]).bereik).toEqual(new Set([L1, AWB, "element:1", "element:2", "klasse:Rechtsfeit", "klasse:Rechtssubject"]));
    expect(focusVan(g, [H]).bereik.has(AWB)).toBe(false);
    // Hoort een bepaling ook bij een hoofdstuk-doel, dan houdt ze haar verwijzingen.
    expect(focusVan(g, [H, A9]).bereik.has(AWB)).toBe(true);
  });

  it("zonder keuze is de focus het beeld; de keuze opheffen brengt het begin terug", () => {
    const focus = focusVan(g, [L1]);
    const begin = weergaveContext(g, stand({ focus }));
    expect(begin.nadruk).toEqual(focus.bereik);
    expect([...begin.vastLabel]).toEqual([L1]);
    expect(weergaveContext(g, stand({ focus, selectie: null })).nadruk).toEqual(begin.nadruk);
  });

  it("een randbepaling heeft een omtrek, de laag Dekking een okeromtrek", () => {
    expect(beeld(AWB, stand()).omtrek).not.toBeNull();
    expect(beeld(L1, stand()).omtrek).toBeNull();
    expect(beeld(L1, stand({ lagen: { ...STANDAARD_LAGEN, dekking: true }, ongedekt: new Set([L1]) })).omtrek).not.toBeNull();
  });

  it("lijnen naar een klasse alleen bij een gekozen markering; lijnen van de keuze krijgen nadruk", () => {
    const lijn = (sleutel: string, s: WeergaveStand) => lijnBeeld(g.getEdgeAttributes(sleutel), g.source(sleutel), g.target(sleutel), weergaveContext(g, s));
    const klasse = "element:1|heeft_klasse|klasse:Rechtssubject";
    expect(lijn(klasse, stand()).verborgen).toBe(true);
    expect(lijn(klasse, stand({ selectie: "element:1" }))).toMatchObject({ verborgen: false, kleur: NADRUK_LIJN });
    expect(lijn(`${L1}|verwijst_naar|${AWB}`, stand()).pijl).toBe(true);
    expect(lijn(`${L1}|verwijst_naar|${AWB}`, stand({ lagen: { ...STANDAARD_LAGEN, verwijzingen: false } })).verborgen).toBe(true);
  });

  it("wie een verborgen knoop kiest (zoeken, inspector), zet alleen de nodige laag aan", () => {
    const uit = { ...STANDAARD_LAGEN, leden: false, annotaties: false, verwijzingen: false };
    expect(lagenVoor(g, "element:1", uit, "alle").lagen).toEqual({ ...uit, leden: true, annotaties: true });
    expect(lagenVoor(g, AWB, uit, "alle").lagen).toEqual({ ...uit, verwijzingen: true });
    expect(lagenVoor(g, "element:1", STANDAARD_LAGEN, "jurist")).toEqual({ lagen: STANDAARD_LAGEN, markering: "alle" });
    expect(lagenVoor(g, A10, uit, "jurist")).toEqual({ lagen: uit, markering: "jurist" });
  });
});

describe("begrippen (fase F3)", () => {
  const begrippen: GraafBron = {
    knopen: [knoop("begrip:a", "begrip", "ontvanger", { bwb_id: "", status: "geaccordeerd" }),
      knoop("begrip:b", "begrip", "invordering", { bwb_id: "", status: "concept" })],
    relaties: [
      { bron: "begrip:a", doel: "element:1", soort: "duidt", groep: "begrippen", anker_tekst: "duidt het begrip aan" },
      { bron: "begrip:a", doel: "begrip:b", soort: "begripsrelatie", groep: "begrippen", anker_tekst: "ontvanger omvat ook invordering" },
    ],
  };
  const g = bouwModel([BRON, begrippen]);
  const stand = (s: Partial<WeergaveStand> = {}): WeergaveStand =>
    ({ lagen: STANDAARD_LAGEN, markering: "alle", selectie: null, focus: null, ongedekt: new Set(), ...s });

  it("een begrip is geen wettekst: de layout van de bron verandert er niet door", () => {
    expect(structuurVan(g)).toEqual(structuurVan(bouwModel([BRON])));
    const bron = berekenLayout(structuurVan(g));
    const pos = plaatsAnnotaties(g, bron);
    const [ax, ay] = pos.get("begrip:a")!, [mx, my] = pos.get("element:1")!, [ix, iy] = pos.get(IW)!;
    // Bij zijn passage, niet ergens op de kaart; een begrip zonder passage krijgt ook een plek.
    expect(Math.hypot(ax - mx, ay - my)).toBeLessThan(Math.hypot(ax - ix, ay - iy));
    expect(pos.get("begrip:b")).toBeDefined();
    expect(plaatsAnnotaties(g, bron).get("begrip:a")).toEqual(pos.get("begrip:a"));      // deterministisch
  });

  it("de laag Begrippen verbergt begrippen en hun lijnen; kiezen zet hem aan", () => {
    const uit = { ...STANDAARD_LAGEN, begrippen: false };
    expect(verborgenKnopen(g, uit, "alle")).toEqual(new Set(["begrip:a", "begrip:b"]));
    const lijn = (sleutel: string, s: WeergaveStand) => lijnBeeld(g.getEdgeAttributes(sleutel), g.source(sleutel), g.target(sleutel), weergaveContext(g, s));
    expect(lijn("begrip:a|begripsrelatie|begrip:b", stand())).toMatchObject({ verborgen: false, pijl: true });
    expect(lijn("begrip:a|begripsrelatie|begrip:b", stand({ lagen: uit })).verborgen).toBe(true);
    // Een begrip op een verborgen markering blijft staan, zijn lijn ernaar niet.
    expect(lijn("begrip:a|duidt|element:1", stand({ lagen: { ...STANDAARD_LAGEN, annotaties: false } })).verborgen).toBe(true);
    expect(lagenVoor(g, "begrip:a", uit, "alle").lagen).toEqual(STANDAARD_LAGEN);
  });
});

describe("de ketting", () => {
  const knoop = (id: string, soort: SamenhangKnoop["soort"], extra: Partial<SamenhangKnoop> = {}): SamenhangKnoop => ({
    id, soort, label: id, tekst: "", klasse: "", lifecycle: "", element_id: "", bwb_id: "", artikel: "", lid: "", rand: false, ...extra });
  const rel = (bron: string, soort: SamenhangRelatie["soort"], doel: string): SamenhangRelatie => ({ bron, soort, doel, groep: "structuur", anker_tekst: "" });
  const bron = (): Samenhang => ({ schema_versie: 1, doel: { bron_iri: "lid" } as Samenhang["doel"], snapshot_id: "s", artikel_iri: "art", keten: true, doelen: ["lid"],
    verwijzingen_beschikbaar: true, afgekapt: false, begrippen_beschikbaar: true, ingekort: { kinderen: {}, markeringen: {}, begrippen: 0, onzekere_verwijzingen: 0 },
    knopen: [knoop("wet", "regeling", { label: "Invorderingswet 1990" }), knoop("art", "artikel"), knoop("lid", "lid", { vindplaats: "Artikel 9, lid 1" }),
      knoop("m", "markering"), knoop("b", "begrip", { begrip_bron: "wet" }), knoop("def", "onderdeel", { rand: true }), knoop("x", "extern", { rand: true })],
    relaties: [rel("wet", "bevat", "art"), rel("art", "bevat", "lid"), rel("m", "markeert", "lid"), rel("b", "komt_voor_in", "m"), rel("def", "definieert", "b"), rel("lid", "verwijst_naar", "x")] });

  it("zet elke knoop op een eigen regel, ingesprongen naar zijn diepte", () => {
    const pos = layoutKeten(bouwModel([bron()]));
    expect([...pos.keys()]).toEqual(["wet", "art", "lid", "m", "b", "def", "x"]);
    expect(new Set([...pos.values()].map((p) => p[1])).size).toBe(7);
    expect(pos.get("art")![0]).toBeGreaterThan(pos.get("wet")![0]);
    expect(pos.get("def")![0]).toBeGreaterThan(pos.get("b")![0]);
  });

  it("is deterministisch", () => {
    expect([...layoutKeten(bouwModel([bron()]))]).toEqual([...layoutKeten(bouwModel([bron()]))]);
  });

  it("plaatst ook wat nergens aan hangt", () => {
    const b = bron();
    b.knopen.push(knoop("los", "begrip"));
    expect(layoutKeten(bouwModel([b])).has("los")).toBe(true);
  });

  it("licht de ketting op in een groter model", () => {
    const k = bron();
    const g = bouwModel([k, { knopen: [knoop("ander", "artikel")], relaties: [] }]);
    const f = ketenFocus(g, ["lid", "weg"], k.knopen);
    expect([...f.doelen]).toEqual(["lid"]);
    expect(f.bereik.has("ander")).toBe(false);
    expect(f.bereik.has("b")).toBe(true);
  });

  it("zegt wat je ziet", () => {
    expect(ketenZin(bron())).toBe("Je ziet de weg van Invorderingswet 1990 naar Artikel 9, lid 1, met 1 markering, 1 begrip en 1 verwijzing. De rest van de regeling staat er niet bij.");
  });

  it("zegt het eerlijk als er niets is, of iets niet is opgehaald", () => {
    const geen = { ...bron(), knopen: bron().knopen.filter((k) => k.soort !== "begrip") };
    expect(ketenZin(geen)).toContain("Geen wettelijke definitie in de graaf");
    expect(ketenZin({ ...geen, begrippen_beschikbaar: false })).toContain("De begrippen zijn nu niet opgehaald.");
    expect(ketenZin({ ...geen, begrippen_beschikbaar: false })).not.toContain("Geen wettelijke definitie");
    expect(ketenZin(bron(), true)).toContain("Lex noemt geen bepaling");
  });

  it("noemt wat er niet bij staat", () => {
    const b = { ...bron(), ingekort: { kinderen: {}, markeringen: { lid: 40 }, begrippen: 2, onzekere_verwijzingen: 1 } };
    const zin = ketenZin(b);
    expect(zin).toContain("40 markeringen staan er niet bij");
    expect(zin).toContain("2 begrippen staan er niet bij");
    expect(zin).toContain("1 verwijzing met een onzeker doel staat er niet bij");
  });

  it("een wettelijk begrip heeft een eigen kleur", () => {
    expect(eigenKleur({ soort: "begrip", klasse: "", label: "", rand: false, begrip_bron: "wet" })).toBe(WETBEGRIPKLEUR);
    expect(eigenKleur({ soort: "begrip", klasse: "", label: "", rand: false, status: "concept" })).toBe(BEGRIPKLEUR.concept);
  });
});
