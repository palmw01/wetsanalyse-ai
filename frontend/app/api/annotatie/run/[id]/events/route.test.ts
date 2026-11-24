import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

// De enige route zonder `proxy()` (frontend/CLAUDE.md §Lagen): de SSE-stroom van een run gaat rauw door. Wat ze
// anders doet dan de proxy, staat hier vast: geen grens op de duur, wel op het opzetten; een fout vóór de stroom als
// JSON; de identiteit naar graph-qa; en de disconnect van de kijker blijft lokaal.

process.env.GRAPH_QA_URL = "http://agent.test";
process.env.GRAPH_QA_TOKEN = "agent-token";

const nep = vi.hoisted(() => ({ userid: "u1" as string | null }));
vi.mock("@/app/api/_lib/session", () => ({
  sessionUserId: async () => nep.userid,
  geenSessie: () => Response.json({ detail: "Niet ingelogd." }, { status: 401 }),
}));

let GET: typeof import("./route").GET;
beforeAll(async () => {
  vi.spyOn(process.stdout, "write").mockImplementation(() => true);
  ({ GET } = await import("./route"));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  nep.userid = "u1";
});

const params = (id: string) => ({ params: Promise.resolve({ id }) });

function sse(...frames: string[]) {
  return new ReadableStream<Uint8Array>({
    start(c) {
      for (const f of frames) c.enqueue(new TextEncoder().encode(f));
      c.close();
    },
  });
}

describe("GET /api/annotatie/run/[id]/events", () => {
  it("zonder sessie: 401 en geen verbinding met graph-qa", async () => {
    nep.userid = null;
    const f = vi.fn();
    vi.stubGlobal("fetch", f);
    expect((await GET(new Request("http://x/api/annotatie/run/r1/events"), params("r1"))).status).toBe(401);
    expect(f).not.toHaveBeenCalled();
  });

  it("geeft de stroom ongewijzigd door, met de headers die bufferen tegenhouden", async () => {
    const f = vi.fn(async () => new Response(sse("data: {\"type\":\"token\"}\r\n\r\n", "data: {\"type\":\"done\"}\r\n\r\n"), {
      headers: { "content-type": "text/event-stream" },
    }));
    vi.stubGlobal("fetch", f);
    const res = await GET(new Request("http://x/api/annotatie/run/r1/events?vanaf=12"), params("r1"));
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toMatch(/^text\/event-stream/);
    expect(res.headers.get("x-accel-buffering")).toBe("no");
    expect(res.headers.get("cache-control")).toContain("no-transform");
    expect(await res.text()).toBe("data: {\"type\":\"token\"}\r\n\r\ndata: {\"type\":\"done\"}\r\n\r\n");

    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    // Opnieuw aanhaken begint waar de kijker was; het run-id gaat als één padsegment.
    expect(url).toBe("http://agent.test/v1/runs/r1/events?vanaf=12");
    const h = new Headers(init.headers);
    expect(h.get("x-user-id")).toBe("u1");
    expect(h.get("authorization")).toBe("Bearer agent-token");
  });

  it("begint zonder `vanaf` bij 0 en codeert een vreemd run-id als segment", async () => {
    const f = vi.fn(async () => new Response(sse(), { headers: { "content-type": "text/event-stream" } }));
    vi.stubGlobal("fetch", f);
    await GET(new Request("http://x/api/annotatie/run/x/events"), params("../admin"));
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe("http://agent.test/v1/runs/..%2Fadmin/events?vanaf=0");
  });

  it("de disconnect van de kijker gaat niet naar boven: het signaal van het verzoek reist niet mee", async () => {
    const f = vi.fn(async () => new Response(sse(), { headers: { "content-type": "text/event-stream" } }));
    vi.stubGlobal("fetch", f);
    const kijker = new AbortController();
    await GET(new Request("http://x/api/annotatie/run/r1/events", { signal: kijker.signal }), params("r1"));
    const init = (f.mock.calls[0] as unknown as [string, RequestInit])[1];
    kijker.abort();
    expect(init.signal?.aborted).toBe(false);
  });

  it("een fout vóór de stroom komt als JSON met de status van graph-qa (andermans run: 404)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: "Onbekende run." }, { status: 404 })));
    const res = await GET(new Request("http://x/api/annotatie/run/r1/events"), params("r1"));
    expect(res.status).toBe(404);
    expect(res.headers.get("content-type")).toBe("application/json");
    expect(await res.json()).toEqual({ detail: "Onbekende run." });
  });

  it("graph-qa onbereikbaar: 502 met de reden", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    const res = await GET(new Request("http://x/api/annotatie/run/r1/events"), params("r1"));
    expect(res.status).toBe(502);
    expect((await res.json()).detail).toMatch(/onbereikbaar.*fetch failed/);
  });

  it("geen headers binnen de opzetgrens: 504, en de stroom zelf heeft geen grens", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn((_u: string, init?: RequestInit) => new Promise<Response>((_r, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("timeout", "TimeoutError")));
    })));
    const bezig = GET(new Request("http://x/api/annotatie/run/r1/events"), params("r1"));
    await vi.advanceTimersByTimeAsync(15_000);
    const res = await bezig;
    expect(res.status).toBe(504);
    expect((await res.json()).detail).toMatch(/niet op tijd/);
  });

  it("de opzettimer gaat uit zodra de headers er zijn: een lange stroom wordt niet afgebroken", async () => {
    vi.useFakeTimers();
    let signaal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
      signaal = init?.signal ?? undefined;
      return new Response(new ReadableStream(), { headers: { "content-type": "text/event-stream" } });
    }));
    const res = await GET(new Request("http://x/api/annotatie/run/r1/events"), params("r1"));
    expect(res.status).toBe(200);
    await vi.advanceTimersByTimeAsync(60 * 60_000);
    expect(signaal?.aborted).toBe(false);
  });
});
