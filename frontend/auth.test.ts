import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// `auth.ts` is de Node-kant van de login (kwaliteitsmeting PR #1801: 0% gedekt). De edge-kant staat in
// `auth.config.test.ts`. Hier: wat `authorize` als bewijs accepteert, hoe de jwt-callback een sessie herverifieert
// (intrekken, degraderen, een wachtwoordwijziging, een api-hapering) en hoe lang een sessie leeft.
//
// `NextAuth` is vervangen door een vanger: we toetsen de configuratie die `auth.ts` opgeeft, niet Auth.js zelf.

const nep = vi.hoisted(() => ({
  config: null as null | Record<string, any>,
  encode: vi.fn(async (p: unknown) => p),
  verifyCredentials: vi.fn(),
  verifyApiToken: vi.fn(),
  getAccountStatus: vi.fn(),
  getTokenStatus: vi.fn(),
  ticket: undefined as string | undefined,
  trusted: undefined as string | undefined,
  clearTicket: vi.fn(async () => {}),
}));

vi.mock("next-auth", () => ({
  default: (config: Record<string, any>) => {
    nep.config = config;
    return { handlers: {}, auth: vi.fn(), signIn: vi.fn(), signOut: vi.fn() };
  },
}));
vi.mock("next-auth/jwt", () => ({ encode: nep.encode }));
vi.mock("next-auth/providers/credentials", () => ({ default: (opties: Record<string, unknown>) => ({ id: "credentials", ...opties }) }));
vi.mock("@/lib/server", () => ({
  verifyCredentials: nep.verifyCredentials,
  verifyApiToken: nep.verifyApiToken,
  getAccountStatus: nep.getAccountStatus,
  getTokenStatus: nep.getTokenStatus,
}));
vi.mock("@/lib/authCookies", () => ({
  getLoginTicketCookie: async () => nep.ticket,
  getTrustedDeviceCookie: async () => nep.trusted,
  clearLoginTicketCookie: nep.clearTicket,
}));

async function laad(env: Record<string, string> = {}) {
  vi.resetModules();
  for (const [k, v] of Object.entries(env)) vi.stubEnv(k, v);
  await import("./auth");
  return nep.config!;
}

const VIJF_MINUTEN = 5 * 60 * 1000;
const ok = { ok: true, code: "", userid: "ann", email: "a@x", role: "analist" };

beforeEach(() => {
  for (const f of [nep.encode, nep.verifyCredentials, nep.verifyApiToken, nep.getAccountStatus, nep.getTokenStatus, nep.clearTicket]) f.mockClear();
  nep.ticket = undefined;
  nep.trusted = undefined;
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.useRealTimers();
});

describe("authorize (gebruikersnaam en wachtwoord)", () => {
  const authorize = async (cred: Record<string, string>) => (await laad()).providers[0].authorize(cred);

  it("zonder gebruikersnaam, of zonder wachtwoord én zonder login-ticket: geen poging bij de api", async () => {
    expect(await authorize({ password: "pw" })).toBeNull();
    expect(await authorize({ userid: "ann" })).toBeNull();
    expect(nep.verifyCredentials).not.toHaveBeenCalled();
  });

  it("een afgewezen poging (ook rate-limit) geeft geen sessie", async () => {
    nep.verifyCredentials.mockResolvedValue({ ok: false, code: "rate" });
    expect(await authorize({ userid: "ann", password: "pw" })).toBeNull();
  });

  it("met wachtwoord: de identiteit van de api, met de keuze om ingelogd te blijven", async () => {
    nep.verifyCredentials.mockResolvedValue(ok);
    nep.trusted = "apparaat";
    const user = await authorize({ userid: "ann", password: "pw", totp: "123456", remember: "1" });
    expect(nep.verifyCredentials).toHaveBeenCalledWith("ann", "pw", "123456", { ticket: null, trusted_token: "apparaat" });
    expect(user).toEqual({ id: "ann", userid: "ann", name: "ann", email: "a@x", role: "analist", rememberMe: true });
    expect(nep.clearTicket).not.toHaveBeenCalled();
  });

  it("met een login-ticket (het 2FA-scherm): geen wachtwoord nodig, en het ticket gaat daarna weg", async () => {
    nep.ticket = "twee-fa-ticket";
    nep.verifyCredentials.mockResolvedValue(ok);
    const user = await authorize({ userid: "ann" });
    expect(user).toMatchObject({ userid: "ann", rememberMe: false });
    expect(nep.clearTicket).toHaveBeenCalledTimes(1);
  });
});

describe("inloggen met een accounttoken", () => {
  it("staat standaard uit", async () => {
    const config = await laad();
    expect(config.providers.map((p: { id: string }) => p.id)).toEqual(["credentials"]);
  });

  it("met API_TOKEN_LOGIN: het token wordt een gewone sessie die viaToken draagt; een geweigerd token niets", async () => {
    const config = await laad({ API_TOKEN_LOGIN: "true" });
    const provider = config.providers.find((p: { id: string }) => p.id === "api-token");
    nep.verifyApiToken.mockResolvedValueOnce({ token_id: "t1", userid: "ann", email: "a@x", role: "analist" });
    expect(await provider.authorize({ token: "wa_pat_x" })).toEqual({
      id: "ann", userid: "ann", name: "ann", email: "a@x", role: "analist", viaToken: "t1",
    });
    nep.verifyApiToken.mockResolvedValueOnce(null);
    expect(await provider.authorize({ token: "wa_pat_x" })).toBeNull();
  });
});

describe("jwt-callback: de sessie herverifiëren", () => {
  let jwt: (a: { token: Record<string, unknown>; user?: Record<string, unknown> }) => Promise<Record<string, unknown> | null>;
  beforeEach(async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-23T10:00:00Z"));
    jwt = (await laad()).callbacks.jwt;
  });

  it("bij het inloggen: de identiteit, het moment van verifiëren en van inloggen", async () => {
    const token = await jwt({ token: {}, user: { userid: "ann", role: "analist", email: "a@x", rememberMe: true } });
    expect(token).toEqual({
      userid: "ann", role: "analist", email: "a@x", rememberMe: true, viaToken: undefined,
      verifiedAt: Date.now(), loginAt: Date.now(),
    });
  });

  it("binnen vijf minuten na de laatste verificatie: geen vraag aan de api", async () => {
    const token = { userid: "ann", verifiedAt: Date.now() - VIJF_MINUTEN + 1 };
    expect(await jwt({ token })).toBe(token);
    expect(nep.getAccountStatus).not.toHaveBeenCalled();
  });

  it("een ingetrokken account beëindigt de sessie", async () => {
    nep.getAccountStatus.mockResolvedValue({ status: "ingetrokken" });
    expect(await jwt({ token: { userid: "u-ingetrokken", verifiedAt: 0 } })).toBeNull();
  });

  it("een rolwijziging (degradatie) geldt meteen, met een verse verificatie", async () => {
    nep.getAccountStatus.mockResolvedValue({ status: "actief", role: "analist", email: "nieuw@x", tfaNodig: false });
    const token = await jwt({ token: { userid: "u-gedegradeerd", role: "beheerder", verifiedAt: 0, loginAt: 1 } });
    expect(token).toMatchObject({ role: "analist", email: "nieuw@x", verifiedAt: Date.now() });
  });

  it("een wachtwoordwijziging ná het inloggen trekt deze sessie in", async () => {
    nep.getAccountStatus.mockResolvedValue({ status: "actief", role: "analist", email: "a@x", tfaNodig: false, sessionsValidFrom: 2000 });
    expect(await jwt({ token: { userid: "u-nieuw-wachtwoord", verifiedAt: 0, loginAt: 1000 } })).toBeNull();
  });

  it("een api-hapering (onbekend) laat de sessie staan, zonder de verificatie te verversen", async () => {
    nep.getAccountStatus.mockResolvedValue({ status: "onbekend" });
    const token = await jwt({ token: { userid: "u-hapering", role: "beheerder", verifiedAt: 0 } });
    expect(token).toMatchObject({ role: "beheerder", verifiedAt: 0 });
  });

  it("een sessie uit een ingetrokken accounttoken vervalt, ook als het account nog actief is", async () => {
    nep.getTokenStatus.mockResolvedValue({ status: "ingetrokken" });
    nep.getAccountStatus.mockResolvedValue({ status: "actief", role: "analist", email: "a@x", tfaNodig: false });
    expect(await jwt({ token: { userid: "u-token", viaToken: "t-weg", verifiedAt: 0 } })).toBeNull();
  });
});

describe("de duur van een sessie", () => {
  it("12 uur, 30 dagen als je ingelogd blijft, een uur voor een accounttoken", async () => {
    const config = await laad();
    const duur = async (token: Record<string, unknown>) =>
      ((await config.jwt.encode({ token, secret: "s", salt: "z" })) as { maxAge: number }).maxAge;
    expect(await duur({})).toBe(12 * 60 * 60);
    expect(await duur({ rememberMe: true })).toBe(30 * 24 * 60 * 60);
    expect(await duur({ rememberMe: true, viaToken: "t1" })).toBe(60 * 60);
  });
});
