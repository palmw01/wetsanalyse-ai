import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

// De BFF-proxy praat met de echte API; hier vervangen we alleen `fetch`. De env-waarden zetten we
// vóór de import, want `lib/config.ts` leest ze bij de eerste aanroep en cachet het token.
process.env.API_BASE_URL = "http://api.test";
process.env.API_TOKEN = "test-token";
process.env.GRAPH_QA_URL = "http://agent.test";
process.env.GRAPH_QA_TOKEN = "agent-token";

const sessie = vi.hoisted(() => ({ auth: vi.fn(), getAccountStatus: vi.fn() }));
vi.mock("@/auth", () => ({ auth: sessie.auth }));
vi.mock("@/lib/server", () => ({ getAccountStatus: sessie.getAccountStatus }));

let proxy: typeof import("./proxy").proxy;

beforeAll(async () => {
  ({ proxy } = await import("./proxy"));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Een upstream die de verbinding aanneemt maar nooit antwoordt – precies het geval waar Node's
 *  `fetch` uit zichzelf eeuwig op blijft wachten. Rejecten doet hij alleen op het abort-signaal. */
function hangendeUpstream() {
  return vi.fn((_url: string, init?: RequestInit) => {
    return new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => {
        const fout = new Error("The operation was aborted due to timeout");
        fout.name = "TimeoutError";
        reject(fout);
      });
    });
  });
}

describe("proxy – timeout", () => {
  it("geeft 504 met een leesbare reden als de upstream niet op tijd antwoordt", async () => {
    vi.stubGlobal("fetch", hangendeUpstream());

    const res = await proxy("/v1/gesprekken", { timeoutMs: 30 });

    expect(res.status).toBe(504);
    expect(await res.json()).toEqual({ detail: "De API antwoordde niet binnen 30 ms." });
  });

  it("geeft het abort-signaal door aan de upstream", async () => {
    const nep = hangendeUpstream();
    vi.stubGlobal("fetch", nep);

    await proxy("/v1/gesprekken", { timeoutMs: 30 });

    // Zonder signal zou de fetch nooit afgebroken worden en bleef deze test hangen; expliciet
    // controleren zodat een refactor die het signal laat vallen hier stukloopt in plaats van in
    // productie.
    expect(nep.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal);
  });

  it("houdt een onbereikbare API op 502 – dat is iets anders dan te traag", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("fetch failed"))));

    const res = await proxy("/v1/gesprekken");

    expect(res.status).toBe(502);
    expect((await res.json()).detail).toContain("API onbereikbaar");
  });

  it("laat een normaal antwoord ongemoeid", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ ok: true }), {
            status: 201,
            headers: { "Content-Type": "application/json", Location: "/v1/x/1" },
          }),
        ),
      ),
    );

    const res = await proxy("/v1/gesprekken", { method: "POST", body: "{}" });

    expect(res.status).toBe(201);
    expect(res.headers.get("Location")).toBe("/v1/x/1");
    expect(await res.json()).toEqual({ ok: true });
  });
});

describe("proxy – beheer vraagt 2FA", () => {
  const beheerder = { user: { userid: "baas", role: "beheerder" } };
  const actief = { status: "actief", role: "beheerder", email: "b@example.test", tfaNodig: false };

  function upstream() {
    const nep = vi.fn((_url: string, _init?: RequestInit) => Promise.resolve(new Response("{}", { status: 200 })));
    vi.stubGlobal("fetch", nep);
    return nep;
  }

  it("laat een beheerder met 2FA door", async () => {
    const nep = upstream();
    sessie.auth.mockResolvedValue(beheerder);
    sessie.getAccountStatus.mockResolvedValue(actief);

    expect((await proxy("/v1/admin/users", { admin: true })).status).toBe(200);
    expect(sessie.getAccountStatus).toHaveBeenCalledWith("baas");
    expect(nep).toHaveBeenCalledOnce();
  });

  it("houdt een beheerder zonder 2FA tegen, met een code die de client kan lezen", async () => {
    const nep = upstream();
    sessie.auth.mockResolvedValue(beheerder);
    sessie.getAccountStatus.mockResolvedValue({ ...actief, tfaNodig: true });

    const res = await proxy("/v1/admin/users", { admin: true });

    expect(res.status).toBe(403);
    expect((await res.json()).code).toBe("2fa_nodig");
    expect(nep).not.toHaveBeenCalled();
  });

  it("gaat dicht als het account niet te controleren is", async () => {
    const nep = upstream();
    sessie.auth.mockResolvedValue(beheerder);
    sessie.getAccountStatus.mockResolvedValue({ status: "onbekend" });

    expect((await proxy("/v1/admin/users", { admin: true })).status).toBe(503);
    expect(nep).not.toHaveBeenCalled();
  });

  it.each([{ status: "ingetrokken" }, { ...actief, role: "analist" }])("weigert %o, ook met een oude rol in de sessie", async (status) => {
    const nep = upstream();
    sessie.auth.mockResolvedValue(beheerder);
    sessie.getAccountStatus.mockResolvedValue(status);

    expect((await proxy("/v1/admin/users", { admin: true })).status).toBe(403);
    expect(nep).not.toHaveBeenCalled();
  });

  it("laat een sessie uit een accounttoken buiten de plicht: die kan niet koppelen", async () => {
    upstream();
    sessie.getAccountStatus.mockClear();
    sessie.auth.mockResolvedValue({ user: { ...beheerder.user, viaToken: "token-1" } });

    expect((await proxy("/v1/admin/users", { admin: true })).status).toBe(200);
    expect(sessie.getAccountStatus).not.toHaveBeenCalled();
  });

  it("vraagt niets extra's bij een gewone aanroep", async () => {
    upstream();
    sessie.getAccountStatus.mockClear();

    expect((await proxy("/v1/gesprekken")).status).toBe(200);
    expect(sessie.getAccountStatus).not.toHaveBeenCalled();
  });
});

describe("proxy – de body stroomt door", () => {
  /** Een upstream die eerst de headers stuurt en de body daarna in delen, op het tempo van de test. */
  function stromendeUpstream(headers: Record<string, string> = {}) {
    let zend!: ReadableStreamDefaultController<Uint8Array>;
    const body = new ReadableStream<Uint8Array>({ start: (c) => { zend = c; } });
    const nep = vi.fn((_url: string, _init?: RequestInit) =>
      Promise.resolve(new Response(body, { status: 200, headers: { "Content-Type": "application/pdf", ...headers } })),
    );
    vi.stubGlobal("fetch", nep);
    return { nep, deel: (t: string) => zend.enqueue(new TextEncoder().encode(t)), klaar: () => zend.close() };
  }

  it("geeft de delen door voordat de upstream klaar is", async () => {
    const up = stromendeUpstream();
    const res = await proxy("/v1/werkgebieden/w1/rapport.pdf");
    const lezer = res.body!.getReader();

    up.deel("eerste ");
    // Met een buffer zou deze read pas na `klaar()` terugkomen, en de test hangen.
    expect(new TextDecoder().decode((await lezer.read()).value)).toBe("eerste ");
    up.deel("tweede");
    up.klaar();
    expect(new TextDecoder().decode((await lezer.read()).value)).toBe("tweede");
    expect((await lezer.read()).done).toBe(true);
  });

  it("geeft content-encoding en content-length niet door: fetch heeft de body al uitgepakt", async () => {
    const up = stromendeUpstream({
      "Content-Encoding": "gzip",
      "Content-Length": "12",
      "Content-Disposition": 'attachment; filename="rapport.pdf"',
    });
    const res = await proxy("/v1/werkgebieden/w1/rapport.pdf");
    up.klaar();

    expect(res.headers.get("content-encoding")).toBeNull();
    expect(res.headers.get("content-length")).toBeNull();
    expect(res.headers.get("content-disposition")).toBe('attachment; filename="rapport.pdf"');
    expect(res.headers.get("content-type")).toBe("application/pdf");
  });

  it("de time-out geldt tot de headers, niet voor de body", async () => {
    const up = stromendeUpstream();
    const res = await proxy("/v1/werkgebieden/w1/rapport.pdf", { timeoutMs: 20 });
    const signaal = up.nep.mock.calls[0][1]?.signal as AbortSignal;

    await new Promise((r) => setTimeout(r, 60));
    expect(signaal.aborted).toBe(false);
    up.deel("na de grens");
    up.klaar();
    expect(await res.text()).toBe("na de grens");
  });

  it("geeft een 204 zonder body door", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(null, { status: 204 }))));
    const res = await proxy("/v1/gesprekken/g1", { method: "DELETE" });
    expect(res.status).toBe(204);
    expect(res.body).toBeNull();
  });
});

describe("proxy – de agent als upstream", () => {
  it("praat met graph-qa en zijn token, niet met de api", async () => {
    const nep = vi.fn((_url: string, _init?: RequestInit) => Promise.resolve(new Response("{}", { status: 202 })));
    vi.stubGlobal("fetch", nep);

    const res = await proxy("/v1/runs/r1/cancel", { agent: true, method: "POST", headers: { "X-User-Id": "jan" } });

    expect(res.status).toBe(202);
    expect(nep.mock.calls[0][0]).toBe("http://agent.test/v1/runs/r1/cancel");
    const headers = nep.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer agent-token");
    expect(headers["X-User-Id"]).toBe("jan");
  });

  it("noemt de agent in de foutmelding", async () => {
    vi.stubGlobal("fetch", hangendeUpstream());
    const res = await proxy("/v1/runs", { agent: true, method: "POST", timeoutMs: 30 });
    expect(res.status).toBe(504);
    expect((await res.json()).detail).toBe("De agent antwoordde niet binnen 30 ms.");
  });
});
