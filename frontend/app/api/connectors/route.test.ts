import { afterEach, describe, expect, it, vi } from "vitest";

// De BFF combineert het register (api) en de straat (graph-qa) tot één leesmodel (review ADR-013, punt 2).
const antwoorden: Record<string, Response> = {};
vi.mock("@/app/api/_lib/session", () => ({ sessionUserId: async () => "u1", geenSessie: () => new Response(null, { status: 401 }) }));
const opties: Record<string, unknown> = {};
vi.mock("@/app/api/_lib/proxy", () => ({
  proxy: async (pad: string, init?: unknown) => { opties[pad] = init; return antwoorden[pad].clone(); },
}));

const { GET } = await import("./route");

const KST = { naam: "kamerstukken", label: "Kamerstukken", brontype: "kamerstuk" };

function zet(straat: Response) {
  antwoorden["/v1/connectors"] = Response.json({ aan: ["kamerstukken"], connectors: [KST] });
  antwoorden["/v1/bronnen"] = straat;
}

afterEach(() => { for (const k of Object.keys(antwoorden)) delete antwoorden[k]; });

describe("/api/connectors", () => {
  it("graph-qa onbereikbaar: de beschikbaarheid is onbekend, niet aan", async () => {
    zet(Response.json({ detail: "Agent onbereikbaar" }, { status: 502 }));
    expect((await (await GET()).json()).connectors).toEqual([{ ...KST, beschikbaarheid: "onbekend" }]);
  });

  it("de straat biedt hem niet aan: hij staat er, als niet aangeboden", async () => {
    zet(Response.json({ bronnen: [{ naam: "kamerstukken", straat: false }] }));
    expect((await (await GET()).json()).connectors).toEqual([{ ...KST, beschikbaarheid: "niet_aangeboden" }]);
  });

  it("het register faalt: 503 met een reden, niet de kale upstreamstatus", async () => {
    zet(Response.json({ bronnen: [] }));
    antwoorden["/v1/connectors"] = Response.json({ detail: "Upstream onbereikbaar" }, { status: 502 });
    const res = await GET();
    expect(res.status).toBe(503);
    expect((await res.json()).detail).toMatch(/niet te lezen/);
  });

  it("een koude graph-qa houdt het menu niet de volle proxygrens op", async () => {
    zet(Response.json({ bronnen: [{ naam: "kamerstukken", straat: true }] }));
    await GET();
    const t = (opties["/v1/bronnen"] as { timeoutMs?: number }).timeoutMs;
    expect(t).toBeLessThanOrEqual(10_000);
  });

  it("de straat biedt hem aan: aan", async () => {
    zet(Response.json({ bronnen: [{ naam: "kamerstukken", straat: true }] }));
    expect((await (await GET()).json()).connectors).toEqual([{ ...KST, beschikbaarheid: "aan" }]);
  });

  it("een onleesbaar antwoord van graph-qa is ook onbekend", async () => {
    zet(new Response("geen json", { status: 200 }));
    expect((await (await GET()).json()).connectors).toEqual([{ ...KST, beschikbaarheid: "onbekend" }]);
  });
});
