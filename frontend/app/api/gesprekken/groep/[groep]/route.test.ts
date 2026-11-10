import { afterEach, describe, expect, it, vi } from "vitest";

// De volgorde is de bescherming: eerst de ids, dan het geheugen van Lex (en de lopende beurten), dan de api met
// precies die ids. Een koude graph-qa mag de verwijdering niet tegenhouden.
const stappen: string[] = [];
const verzoeken: { pad: string; init?: { method?: string; body?: string } }[] = [];
let geheugenFaalt = false;

vi.mock("@/app/api/_lib/session", () => ({ sessionUserId: async () => "u1", geenSessie: () => new Response(null, { status: 401 }) }));
vi.mock("@/app/api/_lib/agentGeheugen", () => ({
  wisAgentGeheugenBulk: async (ids: string[], userid: string) => {
    stappen.push(`geheugen:${ids.join(",")}:${userid}`);
    if (geheugenFaalt) return; // best-effort: de echte helper vangt zijn eigen fout
  },
}));
vi.mock("@/app/api/_lib/proxy", () => ({
  proxy: async (pad: string, init?: { method?: string; body?: string }) => {
    stappen.push(`api:${init?.method ?? "GET"} ${pad}`);
    verzoeken.push({ pad, init });
    if (pad === "/v1/gesprekken/groep/archief") return Response.json({ ids: ["a", "b"] });
    if (pad === "/v1/gesprekken/groep/recent") return Response.json({ detail: "kapot" }, { status: 503 });
    const { ids } = JSON.parse(init?.body ?? "{}");
    return Response.json({ aantal: ids.length, ids });
  },
}));

const { DELETE } = await import("./route");
const { POST } = await import("./archiveren/route");
const params = (groep: string) => ({ params: Promise.resolve({ groep }) });

afterEach(() => { stappen.length = 0; verzoeken.length = 0; geheugenFaalt = false; });

describe("/api/gesprekken/groep/[groep]", () => {
  it("verwijdert in volgorde: ids, geheugen, api met die ids", async () => {
    const res = await DELETE(new Request("http://x"), params("archief"));
    expect(await res.json()).toEqual({ aantal: 2, ids: ["a", "b"] });
    expect(stappen).toEqual(["api:GET /v1/gesprekken/groep/archief", "geheugen:a,b:u1", "api:POST /v1/gesprekken/verwijderen"]);
    expect(JSON.parse(verzoeken[1].init!.body!)).toEqual({ groep: "archief", ids: ["a", "b"] });
  });

  it("een falend geheugen houdt de verwijdering niet op", async () => {
    geheugenFaalt = true;
    expect((await DELETE(new Request("http://x"), params("archief"))).status).toBe(200);
  });

  it("lukt de lijst niet, dan gebeurt er niets", async () => {
    const res = await DELETE(new Request("http://x"), params("recent"));
    expect(res.status).toBe(503);
    expect(stappen).toEqual(["api:GET /v1/gesprekken/groep/recent"]);
  });

  it("een onbekende groep is 404", async () => {
    expect((await DELETE(new Request("http://x"), params("werkgebied"))).status).toBe(404);
    expect(stappen).toEqual([]);
  });

  it("archiveren raakt het geheugen niet", async () => {
    await POST(new Request("http://x"), params("archief"));
    expect(stappen).toEqual(["api:GET /v1/gesprekken/groep/archief", "api:POST /v1/gesprekken/archiveren"]);
  });
});
