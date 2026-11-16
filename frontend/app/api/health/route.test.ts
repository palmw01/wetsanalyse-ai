import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

const verzoek = (pad: string) => new Request(`http://localhost${pad}`);

function upstream(status: Record<string, number | "weg">, body: Record<string, Record<string, unknown>> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const naam = url.includes("graph-qa") ? "lex" : "api";
      const s = status[naam] ?? 200;
      if (s === "weg") throw new Error("ECONNREFUSED");
      return new Response(JSON.stringify(body[naam] ?? {}), { status: s });
    }),
  );
}

beforeEach(() => {
  vi.stubEnv("API_BASE_URL", "http://api:8000");
  vi.stubEnv("GRAPH_QA_URL", "http://graph-qa:8080");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("/api/health", () => {
  it("blijft 200 zonder parameter, ook als de api weg is (de probes en de HEALTHCHECK)", async () => {
    upstream({ api: "weg" });
    const res = await GET(verzoek("/api/health"));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok", api: "onbereikbaar" });
  });

  it("vraagt graph-qa niet zonder parameter", async () => {
    upstream({});
    await GET(verzoek("/api/health"));
    const urls = vi.mocked(fetch).mock.calls.map((c) => String(c[0]));
    expect(urls).toEqual(["http://api:8000/health"]);
  });

  it("geeft met ?keten=1 200 als api en graph-qa antwoorden", async () => {
    upstream({});
    const res = await GET(verzoek("/api/health?keten=1"));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok", api: "ok", lex: "ok", keten: "ok", database: "onbekend", graaf: "onbekend" });
  });

  it("[R01] vraagt de diepe controle van api en graph-qa, en meldt database en graaf", async () => {
    upstream({}, { api: { database: "ok" }, lex: { graaf: "ok" } });
    const res = await GET(verzoek("/api/health?keten=1"));
    const urls = vi.mocked(fetch).mock.calls.map((c) => String(c[0])).sort();
    expect(urls).toEqual(["http://api:8000/health?keten=1", "http://graph-qa:8080/health?keten=1"]);
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ keten: "ok", database: "ok", graaf: "ok" });
  });

  it("[R01] geeft 503 bij een lege graaf: dan komt een straat niet groen door de uitrol", async () => {
    upstream({ lex: 503 }, { lex: { graaf: "leeg" } });
    const res = await GET(verzoek("/api/health?keten=1"));
    expect(res.status).toBe(503);
    expect(await res.json()).toMatchObject({ lex: "status-503", graaf: "leeg", keten: "onvolledig" });
  });

  it("[R02] geeft 503 als de database van de api niet antwoordt", async () => {
    upstream({ api: 503 }, { api: { database: "onbereikbaar" } });
    const res = await GET(verzoek("/api/health?keten=1"));
    expect(res.status).toBe(503);
    expect(await res.json()).toMatchObject({ api: "status-503", database: "onbereikbaar" });
  });

  it("geeft met ?keten=1 503 als de api niet antwoordt", async () => {
    upstream({ api: "weg" });
    const res = await GET(verzoek("/api/health?keten=1"));
    expect(res.status).toBe(503);
    expect(await res.json()).toMatchObject({ api: "onbereikbaar", lex: "ok", keten: "onvolledig" });
  });

  it("geeft met ?keten=1 503 als graph-qa een fout geeft", async () => {
    upstream({ lex: 502 });
    const res = await GET(verzoek("/api/health?keten=1"));
    expect(res.status).toBe(503);
    expect(await res.json()).toMatchObject({ api: "ok", lex: "status-502" });
  });
});
