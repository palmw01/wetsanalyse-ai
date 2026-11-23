import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

// `lib/server.ts` draagt de login en de periodieke herverificatie van de sessie (`auth.ts`). Elke fout hier heeft een
// eigen, bewuste uitkomst: een storing is geen afgewezen wachtwoord, een onbereikbare api trekt een sessie niet in, en
// een onbereikbare api opent de eenmalige registratie niet.

process.env.API_BASE_URL = "http://api.test";
process.env.API_TOKEN = "api-token";

const nep = vi.hoisted(() => ({ headers: new Headers() as Headers | null }));
vi.mock("next/headers", () => ({
  headers: async () => {
    if (!nep.headers) throw new Error("buiten een verzoek");
    return nep.headers;
  },
}));

let server: typeof import("./server");
beforeAll(async () => {
  vi.spyOn(process.stdout, "write").mockImplementation(() => true);
  server = await import("./server");
});

afterEach(() => {
  vi.unstubAllGlobals();
  nep.headers = new Headers();
});

function upstream(res: Response | (() => Promise<Response>)) {
  const f = vi.fn(async () => (typeof res === "function" ? res() : res.clone()));
  vi.stubGlobal("fetch", f);
  return f;
}
const init = (f: ReturnType<typeof upstream>, i = 0) => (f.mock.calls[i] as unknown as [string, RequestInit])[1];

describe("postAuthVerify", () => {
  it("geeft de volle respons door, met het token van de server en het client-IP voor de inlogrem", async () => {
    nep.headers = new Headers({ "x-forwarded-for": "10.0.0.1, 192.0.2.7" });
    const f = upstream(Response.json({ ok: true, code: "", userid: "ann", email: "a@x", role: "analist", ticket: "t" }));
    const uit = await server.postAuthVerify({ userid: "ann", password: "pw" });
    expect(uit).toEqual({ status: 200, body: { ok: true, code: "", userid: "ann", email: "a@x", role: "analist", ticket: "t" } });
    const h = new Headers(init(f).headers);
    expect(h.get("authorization")).toBe("Bearer api-token");
    expect(h.get("x-client-ip")).toBe("192.0.2.7");
    expect(JSON.parse(init(f).body as string)).toEqual({ userid: "ann", password: "pw" });
  });

  it("buiten een verzoek gaat er geen client-IP mee (en faalt niets)", async () => {
    nep.headers = null;
    const f = upstream(Response.json({ ok: false, code: "invalid" }));
    await server.postAuthVerify({});
    expect(new Headers(init(f).headers).has("x-client-ip")).toBe(false);
  });

  it.each([
    ["onbereikbaar", new TypeError("fetch failed"), 502],
    ["te laat", Object.assign(new Error("timeout"), { name: "TimeoutError" }), 504],
  ])("api %s: een storing (code onbereikbaar), geen afgewezen wachtwoord", async (_n, fout, status) => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw fout; }));
    const uit = await server.postAuthVerify({});
    expect(uit.status).toBe(status);
    expect(uit.body.code).toBe("onbereikbaar");
  });

  it("429 wordt de code rate, 503 (bcrypt-wachtrij vol) onbereikbaar", async () => {
    upstream(new Response("", { status: 429 }));
    expect(await server.postAuthVerify({})).toMatchObject({ status: 429, body: { code: "rate" } });
    upstream(new Response("", { status: 503 }));
    expect(await server.postAuthVerify({})).toMatchObject({ status: 503, body: { code: "onbereikbaar" } });
  });

  it("een onleesbaar antwoord is een afgewezen poging", async () => {
    upstream(new Response("<html>", { status: 200 }));
    expect((await server.postAuthVerify({})).body).toMatchObject({ ok: false, code: "invalid" });
  });
});

describe("verifyCredentials", () => {
  it("stuurt de bewijzen uit de cookies mee, met lege waarden als null", async () => {
    const f = upstream(Response.json({ ok: true, code: "" }));
    await server.verifyCredentials("ann", "pw", undefined, { ticket: "t" });
    expect(JSON.parse(init(f).body as string)).toEqual({
      userid: "ann", password: "pw", totp: null, ticket: "t", trusted_token: null, remember: false,
    });
  });
});

describe("getAccountStatus (de herverificatie van de sessie)", () => {
  it("actief: rol, e-mail, de 2FA-plicht en het moment vanaf wanneer sessies gelden", async () => {
    const f = upstream(Response.json({
      role: "beheerder", email: "b@x", tfa_nodig: true, sessions_valid_from: "2026-11-01T00:00:00Z",
    }));
    expect(await server.getAccountStatus("bea")).toEqual({
      status: "actief", role: "beheerder", email: "b@x", tfaNodig: true, sessionsValidFrom: Date.parse("2026-11-01T00:00:00Z"),
    });
    expect(new Headers(init(f).headers).get("x-user-id")).toBe("bea");
  });

  it("een onleesbare of ontbrekende sessiegrens telt niet; 2FA alleen bij een echte true", async () => {
    upstream(Response.json({ role: "analist", email: "a@x", tfa_nodig: "ja", sessions_valid_from: "geen datum" }));
    expect(await server.getAccountStatus("ann")).toEqual({
      status: "actief", role: "analist", email: "a@x", tfaNodig: false, sessionsValidFrom: undefined,
    });
  });

  it("401 trekt de sessie in; elke andere fout of storing laat haar staan (onbekend)", async () => {
    upstream(new Response("", { status: 401 }));
    expect(await server.getAccountStatus("ann")).toEqual({ status: "ingetrokken" });
    upstream(new Response("", { status: 500 }));
    expect(await server.getAccountStatus("ann")).toEqual({ status: "onbekend" });
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    expect(await server.getAccountStatus("ann")).toEqual({ status: "onbekend" });
  });
});

describe("accounttokens", () => {
  it("getTokenStatus: 401 ingetrokken, ok actief, anders of bij storing onbekend; het id als één segment", async () => {
    const f = upstream(new Response("", { status: 200 }));
    expect(await server.getTokenStatus("a/b")).toEqual({ status: "actief" });
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe("http://api.test/v1/auth/api-token/a%2Fb/status");
    upstream(new Response("", { status: 401 }));
    expect(await server.getTokenStatus("t")).toEqual({ status: "ingetrokken" });
    upstream(new Response("", { status: 502 }));
    expect(await server.getTokenStatus("t")).toEqual({ status: "onbekend" });
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("weg"); }));
    expect(await server.getTokenStatus("t")).toEqual({ status: "onbekend" });
  });

  it("verifyApiToken: alleen een ok-antwoord levert een identiteit, de rest null", async () => {
    const id = { ok: true, token_id: "t1", userid: "ann", email: "a@x", role: "analist" };
    upstream(Response.json(id));
    expect(await server.verifyApiToken("wa_pat_x")).toEqual(id);
    upstream(Response.json({ ...id, ok: false }));
    expect(await server.verifyApiToken("wa_pat_x")).toBeNull();
    upstream(new Response("", { status: 401 }));
    expect(await server.verifyApiToken("wa_pat_x")).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("weg"); }));
    expect(await server.verifyApiToken("wa_pat_x")).toBeNull();
  });
});

describe("getSetupStatus", () => {
  it("geeft de stand van de api door", async () => {
    upstream(Response.json({ needs_setup: true }));
    expect(await server.getSetupStatus()).toEqual({ needs_setup: true });
  });

  it("een onbereikbare of foute api opent de registratie niet", async () => {
    upstream(new Response("", { status: 500 }));
    expect(await server.getSetupStatus()).toEqual({ needs_setup: false });
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("weg"); }));
    expect(await server.getSetupStatus()).toEqual({ needs_setup: false });
  });
});
