import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

// De BFF-proxy praat met de echte API; hier vervangen we alleen `fetch`. De env-waarden zetten we
// vóór de import, want `lib/config.ts` leest ze bij de eerste aanroep en cachet het token.
process.env.API_BASE_URL = "http://api.test";
process.env.API_TOKEN = "test-token";

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
