import { encode } from "next-auth/jwt";
import { NextRequest } from "next/server";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { DISCLAIMER_COOKIE } from "@/lib/disclaimer";

// De echte `proxy.ts`, dus `authorized` samen met de CSP-handler. `auth.config.test.ts` roept alleen
// de callback aan, en daar is niet te zien wat next-auth met de uitkomst doet: met een handler telt
// een `false` niet, en de pagina wordt gewoon gerenderd.

const GEHEIM = "proxy-gate-test-geheim";
const COOKIE = "authjs.session-token"; // de naam buiten productie, zie auth.config.ts

let proxy: (req: NextRequest, ctx: object) => Promise<Response>;

beforeAll(async () => {
  vi.stubEnv("AUTH_SECRET", GEHEIM);
  vi.stubEnv("AUTH_TRUST_HOST", "true");
  proxy = ((await import("./proxy")).default as unknown) as typeof proxy;
});

async function sessie(role: "analist" | "beheerder"): Promise<string> {
  const token = await encode({
    token: { sub: "1", name: "Test", userid: "test", role },
    secret: GEHEIM,
    salt: COOKIE,
  });
  return `${COOKIE}=${token}; ${DISCLAIMER_COOKIE}=1`;
}

function verzoek(pad: string, cookie?: string): NextRequest {
  return new NextRequest(`http://localhost:3000${pad}`, { headers: cookie ? { cookie } : {} });
}

function doorgelaten(res: Response): boolean {
  return res.headers.get("x-middleware-next") === "1";
}

describe("de routegate met de CSP-handler", () => {
  it("stuurt een pagina zonder sessie naar de login, met de bestemming erbij", async () => {
    for (const pad of [
      "/workbench?gesprek=g1",
      "/werkgebieden",
      "/annotaties",
      "/begrippen",
      "/instellingen",
      "/instellingen/beheer/gebruikers",
      "/beheer",
    ]) {
      const res = await proxy(verzoek(pad), {});
      expect(res.status, pad).toBeGreaterThanOrEqual(300);
      expect(res.status, pad).toBeLessThan(400);
      expect(doorgelaten(res), pad).toBe(false);
      const naar = new URL(res.headers.get("location") ?? "");
      expect(naar.pathname, pad).toBe("/login");
      expect(naar.searchParams.get("callbackUrl"), pad).toBe(pad);
    }
  });

  it("geeft de startpagina zonder sessie geen bestemming mee", async () => {
    const res = await proxy(verzoek("/"), {});
    expect(res.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("geeft een BFF-route zonder sessie een 401, geen omleiding", async () => {
    const res = await proxy(verzoek("/api/gesprekken"), {});
    expect(res.status).toBe(401);
  });

  it("laat een openbaar pad door, met de CSP en het nonce", async () => {
    const res = await proxy(verzoek("/login"), {});
    expect(doorgelaten(res)).toBe(true);
    const csp = res.headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/'nonce-[^']+'/);
    expect(res.headers.get("x-middleware-request-x-nonce")).toBeTruthy();
  });

  it("laat een pagina met sessie door, met de CSP", async () => {
    const res = await proxy(verzoek("/workbench", await sessie("analist")), {});
    expect(doorgelaten(res)).toBe(true);
    expect(res.headers.get("content-security-policy")).toMatch(/'nonce-[^']+'/);
  });

  it("houdt een analist uit het beheer en laat een beheerder erin", async () => {
    for (const pad of ["/beheer", "/instellingen/beheer/gebruikers"]) {
      const analist = await proxy(verzoek(pad, await sessie("analist")), {});
      expect(doorgelaten(analist), pad).toBe(false);
      expect(new URL(analist.headers.get("location") ?? "").pathname, pad).toBe("/");
      expect(doorgelaten(await proxy(verzoek(pad, await sessie("beheerder")), {})), pad).toBe(true);
    }
    const bff = await proxy(verzoek("/api/admin/users", await sessie("analist")), {});
    expect(bff.status).toBe(403);
  });
});
