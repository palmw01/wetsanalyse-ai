import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

// De eigenaarscontrole bij de start van een run (testplan werkplek §3, Lex Bench §20.5). `conversation_id` is ook de
// thread van het agent-geheugen: zonder deze controle kon een vreemd gespreks-id een vraag in andermans geheugen zetten
// en de context teruglezen. Hier vervangen we alleen `fetch` en de sessie; de route en de proxy zijn echt.
process.env.API_BASE_URL = "http://api.test";
process.env.API_TOKEN = "test-token";
process.env.GRAPH_QA_URL = "http://agent.test";
process.env.GRAPH_QA_TOKEN = "agent-token";

const sessie = vi.hoisted(() => ({ auth: vi.fn() }));
vi.mock("@/auth", () => ({ auth: sessie.auth }));

let route: typeof import("./route");

beforeAll(async () => {
  route = await import("./route");
});

beforeEach(() => {
  sessie.auth.mockResolvedValue({ user: { userid: "jurist-a", role: "analist" } });
});

afterEach(() => {
  vi.unstubAllGlobals();
  sessie.auth.mockReset();
});

type Aanroep = { url: string; methode: string; userId: string | null; body: string | null };

/** Een nep-upstream die per host antwoordt en elke aanroep vastlegt. Een onbekende host is een fout, geen stille 200. */
function upstream(api: () => Response, agent: () => Response = () => Response.json({ run_id: "r1" })) {
  const aanroepen: Aanroep[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      aanroepen.push({
        url,
        methode: init?.method ?? "GET",
        userId: headers.get("X-User-Id"),
        body: typeof init?.body === "string" ? init.body : null,
      });
      if (url.startsWith("http://api.test/")) return api();
      if (url.startsWith("http://agent.test/")) return agent();
      throw new Error(`onverwachte aanroep: ${url}`);
    }),
  );
  return aanroepen;
}

function start(body: unknown): Request {
  return new Request("http://werkplek.test/api/annotatie/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const naarAgent = (a: Aanroep[]) => a.filter((x) => x.url.startsWith("http://agent.test/"));

describe("[R12] POST /api/annotatie/run – de eigenaarscontrole", () => {
  it("start niets bij een gesprek dat niet van jou is", async () => {
    const aanroepen = upstream(() => Response.json({ detail: "niet gevonden" }, { status: 404 }));

    const res = await route.POST(start({ conversation_id: "andermans-gesprek", question: "Wat staat er in artikel 9?" }));

    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({ detail: "Onbekend gesprek." });
    expect(aanroepen[0]).toMatchObject({ url: "http://api.test/v1/gesprekken/andermans-gesprek", userId: "jurist-a" });
    expect(naarAgent(aanroepen)).toEqual([]);
  });

  it("leest een storing bij de api niet als een onbekend gesprek, en start ook dan niets", async () => {
    const aanroepen = upstream(() => Response.json({ detail: "even weg" }, { status: 503 }));

    const res = await route.POST(start({ conversation_id: "g1", question: "x" }));

    expect(res.status).toBe(503);
    expect(await res.json()).not.toEqual({ detail: "Onbekend gesprek." });
    expect(naarAgent(aanroepen)).toEqual([]);
  });

  it("start bij een eigen gesprek de run met de identiteit uit de sessie, niet uit de body", async () => {
    const aanroepen = upstream(() => Response.json({ id: "g1" }));
    const body = { conversation_id: "g1", question: "x", user_id: "iemand-anders" };

    const res = await route.POST(start(body));

    expect(res.status).toBe(200);
    const [run] = naarAgent(aanroepen);
    expect(run).toMatchObject({ url: "http://agent.test/v1/runs", methode: "POST", userId: "jurist-a" });
    expect(run.body).toBe(JSON.stringify(body));
  });

  it("geeft een 409 van de agent ongewijzigd door: de werkplek haakt dan aan bij de lopende run", async () => {
    upstream(
      () => Response.json({ id: "g1" }),
      () => Response.json({ detail: { run_id: "loopt-al" } }, { status: 409 }),
    );

    const res = await route.POST(start({ conversation_id: "g1", question: "x" }));

    expect(res.status).toBe(409);
    expect(await res.json()).toEqual({ detail: { run_id: "loopt-al" } });
  });

  it("vraagt zonder sessie niets aan de api of de agent", async () => {
    sessie.auth.mockResolvedValue(null);
    const aanroepen = upstream(() => Response.json({}));

    const res = await route.POST(start({ conversation_id: "g1", question: "x" }));

    expect(res.status).toBe(401);
    expect(aanroepen).toEqual([]);
  });
});

describe("[R12] GET /api/annotatie/run – lezen alleen als eigenaar", () => {
  it("zet de identiteit op de lijst van lopende runs", async () => {
    const aanroepen = upstream(() => Response.json({}), () => Response.json([]));

    await route.GET(new Request("http://werkplek.test/api/annotatie/run?actief=1"));

    expect(aanroepen).toEqual([
      expect.objectContaining({ url: "http://agent.test/v1/runs?actief=true", userId: "jurist-a" }),
    ]);
  });

  it("zet de identiteit op de vraag naar de run van een gesprek", async () => {
    const aanroepen = upstream(() => Response.json({}), () => Response.json(null));

    await route.GET(new Request("http://werkplek.test/api/annotatie/run?gesprek=g1"));

    expect(aanroepen).toEqual([
      expect.objectContaining({ url: "http://agent.test/v1/conversations/g1/run", userId: "jurist-a" }),
    ]);
  });

  it("geeft bij een storing van de agent geen null: dat zou zeggen dat er niets loopt", async () => {
    upstream(
      () => Response.json({}),
      () => {
        throw new TypeError("fetch failed");
      },
    );

    const res = await route.GET(new Request("http://werkplek.test/api/annotatie/run?gesprek=g1"));

    expect(res.status).toBe(502);
  });

  it("vraagt niets bij een padsegment als '..'", async () => {
    const aanroepen = upstream(() => Response.json({}));

    const res = await route.GET(new Request("http://werkplek.test/api/annotatie/run?gesprek=.."));

    expect(await res.json()).toBeNull();
    expect(aanroepen).toEqual([]);
  });

  it("vraagt zonder sessie niets", async () => {
    sessie.auth.mockResolvedValue(null);
    const aanroepen = upstream(() => Response.json({}));

    const res = await route.GET(new Request("http://werkplek.test/api/annotatie/run?actief=1"));

    expect(res.status).toBe(401);
    expect(aanroepen).toEqual([]);
  });
});
