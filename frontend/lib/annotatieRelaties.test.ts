import { afterEach, describe, expect, it, vi } from "vitest";

import { apiOpslag, bepalingRevisies, dragerRevisies, type NodeElement, type NodeRelatie, type NodeWeergave } from "./annotatieNode";
import {
  eigenRelatie, relatieAfgehandeld, relatiesBijElement, relatieStatus, typeKeuzes, verbindbaar,
} from "./annotatieNodeAdapter";

const el = (id: string, klasse: string, laag_id: string, extra: Partial<NodeElement> = {}): NodeElement => ({
  id, eigenaar_iri: `urn:${laag_id}`, laag_id, klasse, tekst: id, toelichting: "", ankers: [], lifecycle: "voorgesteld",
  herkomst: "agent", ...extra,
});
const ep = (id: string, soort: "element" | "impliciet" = "element") => ({ soort, id, bestaat: true, tekst: id });
const rel = (id: string, van: string, naar: string, extra: Partial<NodeRelatie> = {}): NodeRelatie => ({
  id, type: "plichthebbende", leesvorm: "is plichthebbende van", lifecycle: "human_approved", herkomst: "mens",
  aangemaakt_door: "jan", laag_id: "L2", veranderd: false, van: ep(van), naar: ep(naar), ...extra,
});

const view: NodeWeergave = {
  schema_versie: 2, doel: { bron_iri: "urn:L1" }, snapshot_id: "s", segmenten: [], verwijzingen: [], dekking: {},
  lagen: [{ id: "L1", bron_iri: "urn:L1", revisie: 3, status: "in_review" }, { id: "L2", bron_iri: "urn:L2", revisie: 7, status: "in_review" }],
  elementen: [
    el("subject", "Rechtssubject", "L1"),
    el("betrekking", "Rechtsbetrekking", "L2"),
    el("weg", "Rechtsobject", "L1", { lifecycle: "rejected" }),
    el("oud", "Rechtsobject", "L1", { verouderd: true }),
    el("leeg", "", "L1"),
  ],
  impliciet: [{ id: "I1", klasse: "Rechtssubject", label: "de ontvanger", toelichting: "volgt uit art. 2", herkomst: "mens",
    aangemaakt_door: "jan", laag_id: "L1" }],
};

describe("dragerRevisies", () => {
  it("neemt bij een bestaande relatie de revisie van haar eigen laag", () => {
    expect(dragerRevisies(view, rel("R1", "subject", "betrekking"))).toEqual({ "urn:L2": 7 });
  });
  it("neemt bij een nieuwe relatie de laag van de dragerkant, ook als die een andere laag is", () => {
    // plichthebbende: drager is `naar` (de rechtsbetrekking, in L2), niet het subject in L1.
    expect(dragerRevisies(view, { van: { soort: "element", id: "subject" }, naar: { soort: "element", id: "betrekking" },
      type: "plichthebbende" })).toEqual({ "urn:L2": 7 });
    // voorwerp: drager is `van`.
    expect(dragerRevisies(view, { van: { soort: "element", id: "betrekking" }, naar: { soort: "element", id: "subject" },
      type: "voorwerp" })).toEqual({ "urn:L2": 7 });
  });
  it("vindt de laag van een impliciete partij", () => {
    expect(dragerRevisies(view, { van: { soort: "impliciet", id: "I1" }, naar: { soort: "element", id: "betrekking" },
      type: "invoer" })).toEqual({ "urn:L2": 7 });
    expect(dragerRevisies(view, { laag_id: "L1" })).toEqual({ "urn:L1": 3 });
  });
  it("laat de revisie weg als de dragerlaag niet in beeld is: dan geeft de api een 412", () => {
    expect(dragerRevisies(view, { laag_id: "elders" })).toEqual({});
    expect(dragerRevisies(view, { van: { soort: "element", id: "subject" }, naar: { soort: "element", id: "onbekend" },
      type: "plichthebbende" })).toEqual({});
    expect(dragerRevisies(view, { van: { soort: "element", id: "subject" }, naar: { soort: "element", id: "betrekking" },
      type: "bestaat-niet" })).toEqual({});
  });
  it("een nieuwe impliciete partij hoort bij de laag van de bepaling, 0 als die er nog niet is", () => {
    expect(bepalingRevisies(view)).toEqual({ "urn:L1": 3 });
    expect(bepalingRevisies({ ...view, doel: { bron_iri: "urn:nieuw" } })).toEqual({ "urn:nieuw": 0 });
  });
});

describe("het blok Relaties", () => {
  const relaties = [rel("R1", "subject", "betrekking"), rel("R2", "betrekking", "x", { veranderd: true, type: "voorwerp",
    leesvorm: "heeft als voorwerp" }), rel("R3", "a", "b"), rel("R4", "subject", "y", { veranderd: true })];
  it("toont de relaties van of naar dit element, met een veranderde relatie bovenaan", () => {
    expect(relatiesBijElement({ relaties }, "betrekking").map((r) => [r.relatie.id, r.richting, r.zin])).toEqual([
      ["R2", "uit", "heeft als voorwerp"], ["R1", "in", "heeft als plichthebbende"]]);
    expect(relatiesBijElement({ relaties }, "subject").map((r) => r.relatie.id)).toEqual(["R4", "R1"]);
    expect(relatiesBijElement({ relaties }, "betrekking")[1].ander.id).toBe("subject");
    expect(relatiesBijElement({}, "subject")).toEqual([]);
  });
  it("zegt herkomst en oordeel in mensentaal", () => {
    expect(relatieStatus(rel("R", "a", "b"), "jan")).toBe("door jou gelegd");
    expect(relatieStatus(rel("R", "a", "b"), "piet")).toBe("door jan gelegd");
    expect(relatieStatus(rel("R", "a", "b", { herkomst: "agent", lifecycle: "voorgesteld" }))).toBe("voorstel van Lex");
    expect(relatieStatus(rel("R", "a", "b", { herkomst: "agent" }))).toBe("akkoord bevonden");
    expect(relatieStatus(rel("R", "a", "b", { lifecycle: "rejected" }))).toBe("afgewezen");
    expect(relatieAfgehandeld({ lifecycle: "voorgesteld" })).toBe(false);
  });
  it("laat alleen een eigen relatie wissen", () => {
    expect(eigenRelatie(rel("R", "a", "b"), "jan")).toBe(true);
    expect(eigenRelatie(rel("R", "a", "b"), "piet")).toBe(false);
    expect(eigenRelatie(rel("R", "a", "b", { herkomst: "agent" }), "jan")).toBe(false);
    expect(eigenRelatie(rel("R", "a", "b"))).toBe(false);
  });
  it("biedt alleen actuele markeringen met een klasse en de impliciete partijen aan", () => {
    expect(verbindbaar(view).map((k) => k.ref.id)).toEqual(["subject", "betrekking", "I1"]);
    expect(verbindbaar(view).at(-1)).toMatchObject({ impliciet: true, naam: "de ontvanger", klasse: "Rechtssubject" });
  });
  it("biedt de typen in beide richtingen aan, met de volgorde alleen waar die bestaat", () => {
    const [subject, betrekking] = verbindbaar(view);
    const vanuitBetrekking = typeKeuzes(betrekking, subject);
    expect(vanuitBetrekking).toContainEqual({ code: "plichthebbende", richting: "in", leesvorm: "is plichthebbende van", volgorde: false });
    expect(typeKeuzes(subject, betrekking).filter((k) => k.code === "plichthebbende").map((k) => k.richting)).toEqual(["uit"]);
    expect(typeKeuzes(subject, betrekking).find((k) => k.code === "invoer")).toBeUndefined();
    const afleiding = { klasse: "Afleidingsregel", subtype: "" };
    expect(typeKeuzes(afleiding, subject).find((k) => k.code === "invoer")).toMatchObject({ richting: "in", volgorde: true });
  });
});

describe("de routes van de opslag", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("stuurt relaties en impliciete partijen naar de BFF, met de lichamen van de api", async () => {
    const fetch = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    const r = { verwachte_revisies: { "urn:L2": 7 } };
    await apiOpslag.legRelatie!({ van: { soort: "element", id: "a" }, naar: { soort: "impliciet", id: "I1" }, type: "invoer",
      volgorde: 2, toelichting: "", ...r });
    await apiOpslag.beslisRelatie!("R/1", { type: "reject", comment: "past niet", ...r });
    await apiOpslag.wisRelatie!("R1", r);
    await apiOpslag.maakImpliciet!({ doel: { bron_iri: "urn:L1" }, snapshot_id: "s", label: "x", toelichting: "y", ...r });
    await apiOpslag.wisImpliciet!("I1", r);
    const calls = fetch.mock.calls as unknown as [string, RequestInit][];
    expect(calls.map(([url, init]) => [url, init.method])).toEqual([
      ["/api/annotatie/v2/relaties", "POST"],
      ["/api/annotatie/v2/relaties/R%2F1/beslissing", "POST"],
      ["/api/annotatie/v2/relaties/R1/wis", "POST"],
      ["/api/annotatie/v2/impliciet", "POST"],
      ["/api/annotatie/v2/impliciet/I1/wis", "POST"],
    ]);
    expect(JSON.parse(String(calls[0][1].body))).toEqual({ van: { soort: "element", id: "a" }, naar: { soort: "impliciet", id: "I1" },
      type: "invoer", volgorde: 2, toelichting: "", verwachte_revisies: { "urn:L2": 7 } });
    expect(JSON.parse(String(calls[1][1].body))).toEqual({ type: "reject", comment: "past niet", verwachte_revisies: { "urn:L2": 7 } });
    expect(JSON.parse(String(calls[2][1].body))).toEqual({ verwachte_revisies: { "urn:L2": 7 } });
  });
});
