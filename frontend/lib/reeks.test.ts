import { describe, expect, it } from "vitest";
import { parseKandidaten, parseKeuze } from "./agentEvents";
import { doelVanKandidaat } from "./annotatie";
import {
  actiefOnderdeel, doelenVanKandidaten, reeksPrompt, reeksSamenvatting, reeksUitBerichten, verwerkReeksEvent, type Reeks,
} from "./reeks";
import type { Bericht } from "./types";

const ART = "urn:bwb:BWBR0004770:artikel:9";
const L1 = `${ART}:lid:1`;
const L2 = `${ART}:lid:2`;
const L3 = `${ART}:lid:3`;

function speel(events: Record<string, unknown>[]): Reeks | null {
  return events.reduce<Reeks | null>((r, e) => verwerkReeksEvent(r, e), null);
}

const START = {
  type: "reeks", fase: "start", run_id: "run-1", totaal: 3,
  ouder: { bron_iri: ART, label: "Invorderingswet 1990 – Artikel 9" },
  onderdelen: [{ bron_iri: L1, label: "Lid 1" }, { bron_iri: L2, label: "Lid 2" }, { bron_iri: L3, label: "Lid 3" }],
};

describe("verwerkReeksEvent", () => {
  it("negeert alles vóór het reeks-start", () => {
    expect(speel([{ type: "status", message: "x", onderdeel: L1 }])).toBeNull();
  });

  it("deelt de stroom per onderdeel in", () => {
    const r = speel([
      START,
      { type: "onderdeel", fase: "start", bron_iri: L1 },
      { type: "status", message: "Bron · lid 1", onderdeel: L1 },
      { type: "tool_execution", run_id: "run-1.1", call_id: "c1", tool: "get_bronnode", phase: "end", status: "ok", onderdeel: L1 },
      { type: "opgeslagen", annotatie_doel: { bron_iri: L1, label: "IW – Artikel 9, Lid 1", snapshot_id: "s" }, onderdeel: L1 },
      { type: "onderdeel", fase: "eind", bron_iri: L1, uitkomst: "klaar", voorstellen: 4 },
      { type: "onderdeel", fase: "start", bron_iri: L2 },
      { type: "status", message: "Bron · lid 2", onderdeel: L2 },
    ])!;
    expect(r.ouder.label).toBe("Invorderingswet 1990 – Artikel 9");
    const [a, b, c] = r.onderdelen;
    expect([a.status, b.status, c.status]).toEqual(["klaar", "bezig", "wacht"]);
    expect(a.denk).toBe("· Bron · lid 1");
    expect(b.denk).toBe("· Bron · lid 2");
    expect(a.voorstellen).toBe(4);
    expect(a.tool_executions).toHaveLength(1);
    expect(a.annotatie_doel?.bron_iri).toBe(L1);
    expect(actiefOnderdeel(r)).toBe(L2);
    expect(reeksSamenvatting(r)).toBe("1 van 3 klaar");
  });

  it("een fout bij één onderdeel raakt alleen dat onderdeel", () => {
    const r = speel([
      START,
      { type: "onderdeel", fase: "start", bron_iri: L1 },
      { type: "error", message: "De bron veranderde.", onderdeel: L1 },
      { type: "onderdeel", fase: "eind", bron_iri: L1, uitkomst: "fout", voorstellen: 0, fout: "De bron veranderde." },
      { type: "onderdeel", fase: "start", bron_iri: L2 },
      { type: "onderdeel", fase: "eind", bron_iri: L2, uitkomst: "hergebruik", voorstellen: 0 },
    ])!;
    expect(r.onderdelen.map((o) => o.status)).toEqual(["fout", "hergebruik", "wacht"]);
    expect(r.onderdelen[0].fout).toBe("De bron veranderde.");
  });

  it("wat niet aan bod kwam staat zo, met de reden", () => {
    const r = speel([
      START,
      { type: "onderdeel", fase: "start", bron_iri: L1 },
      { type: "onderdeel", fase: "eind", bron_iri: L1, uitkomst: "klaar", voorstellen: 1 },
      { type: "reeks", fase: "eind", run_id: "run-1", totaal: 3, verwerkt: 1, overgeslagen: [L2, L3], reden: "budget_op" },
    ])!;
    expect(r.afgerond).toBe(true);
    expect(r.onderdelen.map((o) => o.status)).toEqual(["klaar", "overgeslagen", "overgeslagen"]);
    expect(reeksSamenvatting(r)).toBe("1 van 3 geannoteerd · 2 niet aan bod gekomen (tokenbudget op)");
  });

  it("een onbekend onderdeel of een misvormd event breekt niets", () => {
    const voor = speel([START])!;
    expect(verwerkReeksEvent(voor, { type: "status", message: "x", onderdeel: "urn:bwb:ander" })).toBe(voor);
    expect(verwerkReeksEvent(voor, { type: "tool_execution", onderdeel: L1 })).toBe(voor);
    expect(verwerkReeksEvent(voor, { type: "onderdeel", fase: "raar", bron_iri: L1 })).toBe(voor);
  });

  it("opnieuw afspelen levert hetzelfde blok (aanhaken na een onderbreking)", () => {
    const events = [START, { type: "onderdeel", fase: "start", bron_iri: L1 },
      { type: "status", message: "a", onderdeel: L1 }];
    expect(speel(events)).toEqual(speel(events));
  });
});

describe("reeksUitBerichten", () => {
  const bericht = (index: number, extra: Partial<Bericht> = {}): Bericht => ({
    rol: "assistant", tekst: "", denk: `· stap ${index}`, bronnen: [], annotatie_slug: "", annotatie_titel: "",
    run_id: `run-1.${index + 1}`, reeks: { run_id: "run-1", index, totaal: 3, ouder: "Artikel 9" },
    annotatie_doel: { bron_iri: [L1, L2, L3][index], label: `Lid ${index + 1}` }, ...extra,
  });

  it("bouwt het blok na herladen; een ontbrekend bericht is niet aan bod gekomen", () => {
    const r = reeksUitBerichten([bericht(0), bericht(1, { hergebruik: { slug: L2, leden: [], volledig: true, bijgewerkt: "", telling: {} } })])!;
    expect(r.runId).toBe("run-1");
    expect(r.ouder.label).toBe("Artikel 9");
    expect(r.onderdelen.map((o) => o.status)).toEqual(["klaar", "hergebruik", "overgeslagen"]);
    expect(r.onderdelen[0].denk).toBe("· stap 0");
    expect(r.afgerond).toBe(true);
  });

  it("zonder reeks geen blok", () => {
    expect(reeksUitBerichten([bericht(0, { reeks: null })])).toBeNull();
  });
});

describe("keuzekaart", () => {
  const ruw = [
    { bwbId: "BWBR0004770", artikel: "9", lid: "1", bron_iri: L1, nummer: "1", soort: "Lid", label: "Lid 1",
      fragment: "De belastingschuldige…", stand: { status: "te_beoordelen", voorstellen: 3, te_beoordelen: 2 }, gekozen: true },
    { bwbId: "BWBR0004770", artikel: "9", lid: "2", bron_iri: L2, soort: "Lid", label: "Lid 2",
      stand: { status: "onzin" } },
  ];

  it("leest bron_iri, stand en gekozen; een onbekende stand vervalt", () => {
    const [a, b] = parseKandidaten(ruw)!;
    expect(a).toMatchObject({ bron_iri: L1, label: "Lid 1", soort: "Lid", gekozen: true,
      stand: { status: "te_beoordelen", voorstellen: 3, te_beoordelen: 2 } });
    expect(b.stand).toBeUndefined();
    expect(b.gekozen).toBeUndefined();
  });

  it("kent alleen de twee keuzesoorten", () => {
    expect(parseKeuze({ soort: "onderdeel", ouder: "Artikel 9", alles: true })).toEqual({ soort: "onderdeel", ouder: "Artikel 9", alles: true });
    expect(parseKeuze({ soort: "iets" })).toBeUndefined();
    expect(parseKeuze(undefined)).toBeUndefined();
  });

  it("een gekozen onderdeel wijst de bronnode zelf aan", () => {
    const [a] = parseKandidaten(ruw)!;
    expect(doelVanKandidaat(a)).toMatchObject({ bron_iri: L1, bwbId: "BWBR0004770", artikel: "9", lid: "1" });
  });

  it("meerdere gekozen onderdelen worden de doelen van één reeks", () => {
    const ks = parseKandidaten(ruw)!;
    expect(doelenVanKandidaten(ks).map((d) => d.bron_iri)).toEqual([L1, L2]);
    expect(doelenVanKandidaten([{ bwbId: "B", artikel: "36" }])).toEqual([]);
    expect(reeksPrompt("Artikel 9", ks)).toBe("Annoteer Artikel 9: Lid 1 en Lid 2");
  });
});
