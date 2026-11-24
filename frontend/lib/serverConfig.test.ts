import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// De twee server-only modules waar het token en de cookies van de login wonen: `lib/config.ts` (tokens uit env of
// `*_FILE`) en `lib/authCookies.ts` (het login-ticket, het vertrouwde apparaat, de disclaimer). Ze hadden geen test.

const koek = vi.hoisted(() => ({
  gezet: [] as { naam: string; waarde: string; opties: Record<string, unknown> }[],
  winkel: new Map<string, string>(),
}));
vi.mock("next/headers", () => ({
  cookies: async () => ({
    set: (naam: string, waarde: string, opties: Record<string, unknown>) => {
      koek.gezet.push({ naam, waarde, opties });
      koek.winkel.set(naam, waarde);
    },
    get: (naam: string) => (koek.winkel.has(naam) ? { value: koek.winkel.get(naam)! } : undefined),
  }),
}));

const map = mkdtempSync(join(tmpdir(), "wa-config-"));
afterAll(() => rmSync(map, { recursive: true, force: true }));

const ENV = ["API_BASE_URL", "API_TOKEN", "API_TOKEN_FILE", "ADMIN_API_TOKEN", "ADMIN_API_TOKEN_FILE",
  "GRAPH_QA_URL", "GRAPH_QA_TOKEN", "GRAPH_QA_TOKEN_FILE"] as const;
const bewaard = Object.fromEntries(ENV.map((k) => [k, process.env[k]]));

beforeEach(() => {
  for (const k of ENV) delete process.env[k];
  vi.resetModules();
});
afterEach(() => {
  for (const k of ENV) {
    if (bewaard[k] === undefined) delete process.env[k];
    else process.env[k] = bewaard[k];
  }
  vi.unstubAllEnvs();
});

const laad = () => import("./config");

describe("lib/config", () => {
  it("zonder env de interne standaardadressen, zonder token geen Authorization-header", async () => {
    const c = await laad();
    expect(c.apiBaseUrl()).toBe("http://wetsanalyse-api:3000");
    expect(c.graphQaBaseUrl()).toBe("http://graph-qa:8080");
    expect(c.authHeader()).toEqual({});
    expect(c.adminAuthHeader()).toEqual({});
    expect(c.graphQaAuthHeader()).toEqual({});
  });

  it("knipt slashes achter een basisadres af, zodat een pad niet met // begint", async () => {
    process.env.API_BASE_URL = "http://api.test///";
    process.env.GRAPH_QA_URL = "http://agent.test/";
    const c = await laad();
    expect(c.apiBaseUrl()).toBe("http://api.test");
    expect(c.graphQaBaseUrl()).toBe("http://agent.test");
  });

  it("een *_FILE gaat voor de env-waarde, en spaties en de regeleinde vallen weg", async () => {
    for (const [naam, waarde] of [["api", "uit-bestand\n"], ["admin", "  admin-bestand "], ["agent", "agent-bestand\n"]]) {
      writeFileSync(join(map, naam), waarde);
    }
    Object.assign(process.env, {
      API_TOKEN: "uit-env", API_TOKEN_FILE: join(map, "api"),
      ADMIN_API_TOKEN: "x", ADMIN_API_TOKEN_FILE: join(map, "admin"),
      GRAPH_QA_TOKEN: "y", GRAPH_QA_TOKEN_FILE: join(map, "agent"),
    });
    const c = await laad();
    expect(c.authHeader()).toEqual({ Authorization: "Bearer uit-bestand" });
    expect(c.adminAuthHeader()).toEqual({ Authorization: "Bearer admin-bestand" });
    expect(c.graphQaAuthHeader()).toEqual({ Authorization: "Bearer agent-bestand" });
  });

  it("het token wordt één keer gelezen (gecachet)", async () => {
    process.env.API_TOKEN = " eerste ";
    const c = await laad();
    expect(c.authHeader()).toEqual({ Authorization: "Bearer eerste" });
    process.env.API_TOKEN = "tweede";
    expect(c.authHeader()).toEqual({ Authorization: "Bearer eerste" });
  });

  it.each([
    ["API_TOKEN_FILE", "authHeader"],
    ["ADMIN_API_TOKEN_FILE", "adminAuthHeader"],
    ["GRAPH_QA_TOKEN_FILE", "graphQaAuthHeader"],
  ] as const)("een onleesbare %s faalt hard met het pad, niet stil zonder token", async (sleutel, functie) => {
    process.env[sleutel] = join(map, "bestaat-niet");
    const c = await laad();
    expect(() => c[functie]()).toThrow(new RegExp(`Kan ${sleutel} niet lezen \\(.*bestaat-niet\\)`));
  });
});

describe("lib/authCookies", () => {
  const { gezet, winkel } = koek;
  beforeEach(() => {
    gezet.length = 0;
    winkel.clear();
  });

  it("het login-ticket: httpOnly, vijf minuten, en na de login meteen weg", async () => {
    const c = await import("./authCookies");
    await c.setLoginTicketCookie("t1");
    expect(await c.getLoginTicketCookie()).toBe("t1");
    expect(gezet[0]).toEqual({
      naam: "wa-login-ticket", waarde: "t1",
      opties: { httpOnly: true, sameSite: "lax", secure: false, path: "/", maxAge: 300 },
    });
    await c.clearLoginTicketCookie();
    expect(gezet[1].opties.maxAge).toBe(0);
    expect(gezet[1].waarde).toBe("");
  });

  it("het vertrouwde apparaat: dertig dagen; de disclaimer: een sessiecookie zonder maxAge", async () => {
    const c = await import("./authCookies");
    await c.setTrustedDeviceCookie("d1");
    expect(await c.getTrustedDeviceCookie()).toBe("d1");
    expect(gezet[0].opties.maxAge).toBe(30 * 24 * 60 * 60);
    expect(await c.isDisclaimerGeaccepteerd()).toBe(false);
    await c.setDisclaimerCookie();
    expect(gezet[1].opties).not.toHaveProperty("maxAge");
    expect(await c.isDisclaimerGeaccepteerd()).toBe(true);
    await c.clearDisclaimerCookie();
    expect(gezet[2].opties.maxAge).toBe(0);
  });

  it("in productie: __Secure-namen en alleen over https", async () => {
    vi.stubEnv("NODE_ENV", "production");
    const c = await import("./authCookies");
    expect(c.LOGIN_TICKET_COOKIE).toBe("__Secure-wa-login-ticket");
    expect(c.TRUSTED_DEVICE_COOKIE).toBe("__Secure-wa-trusted-device");
    await c.setTrustedDeviceCookie("d1");
    expect(gezet[0]).toMatchObject({ naam: "__Secure-wa-trusted-device", opties: { secure: true, httpOnly: true } });
  });
});
