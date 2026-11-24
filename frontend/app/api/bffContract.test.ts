import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { context, propagation, ROOT_CONTEXT, trace, TraceFlags, type Context } from "@opentelemetry/api";
import { AsyncLocalStorage } from "node:async_hooks";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

// Het contract van de BFF, voor élke route onder `app/api` tegelijk (kwaliteitsmeting PR #1801: de routes zelf
// hadden geen test, alleen `proxy()` had er een). Een route is dun – sessie, pad, `proxy()` – maar juist in die
// dunne laag zitten de vertrouwensgrenzen uit `frontend/CLAUDE.md`:
//
//  1. zonder sessie gaat er niets naar boven (401, of 403 bij beheer);
//  2. de identiteit naar boven komt uit de sessie, nooit uit wat de browser meestuurt (`X-User-Id`);
//  3. het token komt van de server, nooit uit de browser (`Authorization`);
//  4. elke upstream-aanroep draagt de traceparent (`metTrace`) – vergeten faalt stil (CLAUDE.md §Observability);
//  5. een beheerroute praat alleen met het admin-token, en een gewone route nooit.
//
// De routes worden uit de mappen gelezen, dus een nieuwe route valt er vanzelf onder.

process.env.API_BASE_URL = "http://api.test";
process.env.API_TOKEN = "api-token";
process.env.ADMIN_API_TOKEN = "admin-token";
process.env.GRAPH_QA_URL = "http://agent.test";
process.env.GRAPH_QA_TOKEN = "agent-token";

const nep = vi.hoisted(() => ({
  sessie: null as null | { user: Record<string, unknown> },
}));
vi.mock("@/auth", () => ({ auth: async () => nep.sessie }));
vi.mock("@/lib/server", async (orig) => ({
  ...(await orig<typeof import("@/lib/server")>()),
  getAccountStatus: async () => ({ status: "actief", role: "beheerder", tfaNodig: false }),
}));
// De cookies bestaan alleen binnen een Next-verzoek; de publieke login-routes vallen buiten dit contract.
vi.mock("next/headers", () => ({
  headers: async () => new Headers(),
  cookies: async () => ({ get: () => undefined, set: () => {}, delete: () => {} }),
}));

const API = join(__dirname);

/** Routes die bewust zonder sessie werken, met de reden. Een nieuwe publieke route hoort hier met een zin. */
const PUBLIEK: Record<string, string> = {
  "[...onbekend]": "een 404 voor alles wat geen route is, zonder upstream",
  health: "de gezondheidscontrole van de container en de rooktest na een uitrol",
  "auth/[...nextauth]": "Auth.js zelf",
  "login-verify": "stap A van de login, vóór er een sessie is (eigen test: loginRoutes.test.ts)",
  "login-2fa": "stap B van de login, vóór er een sessie is (eigen test: loginRoutes.test.ts)",
  registreren: "een aanvraag doen kan alleen zonder account",
  setup: "de eerste beheerder, vóór er een account bestaat",
  disclaimer: "alleen een cookie, geen upstream",
};

const METHODES = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const;

interface Route {
  /** Het pad onder `app/api`, zoals in `PUBLIEK`. */
  pad: string;
  bestand: string;
  bron: string;
  /** De dynamische segmenten met een waarde die als een gewone id leest. */
  params: Record<string, string | string[]>;
}

function routes(map = API): Route[] {
  const uit: Route[] = [];
  for (const naam of readdirSync(map)) {
    const vol = join(map, naam);
    if (statSync(vol).isDirectory()) uit.push(...routes(vol));
    else if (naam === "route.ts") {
      const pad = relative(API, map);
      const params: Record<string, string | string[]> = {};
      for (const seg of pad.split("/")) {
        const m = /^\[(\.\.\.)?(\w+)\]$/.exec(seg);
        if (m) params[m[2]] = m[1] ? ["wg-1", "deelvragen"] : `${m[2]}-1`;
      }
      uit.push({ pad, bestand: vol, bron: readFileSync(vol, "utf8"), params });
    }
  }
  return uit.sort((a, b) => a.pad.localeCompare(b.pad));
}

const ALLE = routes();
const BESCHERMD = ALLE.filter((r) => !(r.pad in PUBLIEK));
const isBeheer = (r: Route) => /admin:\s*true/.test(r.bron);

// --- Een actieve span, zodat `metTrace` iets in te voegen heeft ---------------------------------------------
// Zonder contextmanager is `context.with` een no-op; zonder propagator voegt `propagation.inject` niets toe.
// Beide zijn hier met de hand, zodat de test niet van een tweede OTel-pakket afhangt.
const opslag = new AsyncLocalStorage<Context>();
const TRACE_ID = "0af7651916cd43dd8448eb211c80319c";
const SPAN_ID = "b7ad6b7169203331";
const TRACEPARENT = `00-${TRACE_ID}-${SPAN_ID}-01`;

beforeAll(() => {
  // De logregels van `proxy()` zijn hier ruis (één per aanroep, honderden).
  vi.spyOn(process.stdout, "write").mockImplementation(() => true);
  context.setGlobalContextManager({
    active: () => opslag.getStore() ?? ROOT_CONTEXT,
    with: (ctx, fn, thisArg, ...args) => opslag.run(ctx, () => fn.call(thisArg, ...args)),
    bind: (_ctx, doel) => doel,
    enable() { return this; },
    disable() { return this; },
  });
  propagation.setGlobalPropagator({
    inject(ctx, carrier, setter) {
      const sc = trace.getSpanContext(ctx);
      if (sc) setter.set(carrier, "traceparent", `00-${sc.traceId}-${sc.spanId}-0${sc.traceFlags}`);
    },
    extract: (ctx) => ctx,
    fields: () => ["traceparent"],
  });
});

afterAll(() => {
  context.disable();
  propagation.disable();
});

interface Aanroep { url: string; headers: Record<string, string> }
let aanroepen: Aanroep[] = [];

function stubUpstream() {
  aanroepen = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    aanroepen.push({ url: String(url), headers: Object.fromEntries(new Headers(init?.headers).entries()) });
    return Response.json({ ok: true });
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  nep.sessie = null;
});

/** Roep één handler aan zoals Next dat doet, binnen een span, met een browser die zich als iemand anders voordoet. */
async function roepAan(r: Route, methode: string): Promise<Response> {
  const mod = (await import(r.bestand)) as Record<string, unknown>;
  const handler = mod[methode] as (req: Request, ctx: { params: Promise<unknown> }) => Promise<Response> | Response;
  const req = new Request(`http://werkplek.test/api/${r.pad}?vanaf=3&limit=7`, {
    method: methode,
    headers: { "X-User-Id": "indringer", Authorization: "Bearer uit-de-browser", "Content-Type": "application/json" },
    ...(methode === "GET" || methode === "DELETE" ? {} : { body: "{}" }),
  });
  const span = trace.setSpanContext(ROOT_CONTEXT, { traceId: TRACE_ID, spanId: SPAN_ID, traceFlags: TraceFlags.SAMPLED });
  return context.with(span, async () => handler(req, { params: Promise.resolve(r.params) }));
}

function handlers(mod: Record<string, unknown>) {
  return METHODES.filter((m) => typeof mod[m] === "function");
}

describe("BFF-contract over alle routes", () => {
  it("kent de routes: elke route onder app/api is beschermd of staat met een reden in PUBLIEK", () => {
    expect(ALLE.length).toBeGreaterThan(50);
    for (const pad of Object.keys(PUBLIEK)) expect(ALLE.map((r) => r.pad)).toContain(pad);
  });

  it.each(BESCHERMD.map((r) => [r.pad, r] as const))("%s: zonder sessie gaat er niets naar boven", async (_p, r) => {
    stubUpstream();
    const mod = (await import(r.bestand)) as Record<string, unknown>;
    const ms = handlers(mod);
    expect(ms.length).toBeGreaterThan(0);
    for (const m of ms) {
      const res = await roepAan(r, m);
      expect([401, 403], `${m} ${r.pad}`).toContain(res.status);
    }
    expect(aanroepen).toEqual([]);
  });

  it.each(BESCHERMD.filter(isBeheer).map((r) => [r.pad, r] as const))(
    "%s: een analist komt niet bij beheer",
    async (_p, r) => {
      stubUpstream();
      nep.sessie = { user: { userid: "analist-1", role: "analist" } };
      const mod = (await import(r.bestand)) as Record<string, unknown>;
      for (const m of handlers(mod)) expect((await roepAan(r, m)).status, `${m} ${r.pad}`).toBe(403);
      expect(aanroepen).toEqual([]);
    },
  );

  it.each(BESCHERMD.map((r) => [r.pad, r] as const))(
    "%s: identiteit en token van de server, met de traceparent",
    async (_p, r) => {
      stubUpstream();
      nep.sessie = { user: { userid: "sessie-1", role: "beheerder" } };
      const mod = (await import(r.bestand)) as Record<string, unknown>;
      for (const m of handlers(mod)) await roepAan(r, m);
      for (const a of aanroepen) {
        const waar = `${a.url} (${r.pad})`;
        // 2. Wat de browser over zichzelf zegt, gaat nooit mee.
        if ("x-user-id" in a.headers) expect(a.headers["x-user-id"], waar).toBe("sessie-1");
        // 3. Het token is altijd dat van de server, en past bij de upstream.
        const verwacht = a.url.startsWith("http://agent.test")
          ? "Bearer agent-token"
          : isBeheer(r) && a.url.includes("/v1/admin/")
            ? "Bearer admin-token"
            : "Bearer api-token";
        expect(a.headers.authorization, waar).toBe(verwacht);
        // 4. De keten frontend → API → graph-qa blijft één trace.
        expect(a.headers.traceparent, waar).toBe(TRACEPARENT);
      }
    },
  );

  it("draagt de identiteit mee op elke route die de sessie leest (geen stille route zonder X-User-Id)", async () => {
    // Een route die `sessionUserId()` vraagt maar de waarde niet doorgeeft, laat de api raden van wie een gesprek
    // is. Dat kan bewust zijn (gedeelde lagen); dan staat de route hier met een reden.
    const ZONDER_IDENTITEIT: Record<string, string> = {
      catalogus: "de catalogus van Lex is voor iedereen dezelfde; de sessie is alleen de toegangspoort",
      connectors: "het register van de beheerder en de straat zijn niet per gebruiker",
      modelkeuzes: "welk model per stap geldt, is niet per gebruiker",
    };
    const missend: string[] = [];
    for (const r of BESCHERMD.filter((r) => r.bron.includes("sessionUserId") && !isBeheer(r))) {
      stubUpstream();
      nep.sessie = { user: { userid: "sessie-1", role: "analist" } };
      const mod = (await import(r.bestand)) as Record<string, unknown>;
      for (const m of handlers(mod)) await roepAan(r, m);
      if (aanroepen.length > 0 && aanroepen.some((a) => !("x-user-id" in a.headers)) && !(r.pad in ZONDER_IDENTITEIT))
        missend.push(r.pad);
    }
    expect(missend).toEqual([]);
  });

  it.each(ALLE.filter((r) => r.pad in PUBLIEK && !r.pad.startsWith("login") && r.pad !== "auth/[...nextauth]")
    .map((r) => [r.pad, r] as const))(
    "%s (publiek): neemt geen identiteit of token van de browser over",
    async (_p, r) => {
      stubUpstream();
      const mod = (await import(r.bestand)) as Record<string, unknown>;
      for (const m of handlers(mod)) await roepAan(r, m);
      for (const a of aanroepen) {
        expect(a.headers["x-user-id"]).toBeUndefined();
        expect(a.headers.authorization).not.toBe("Bearer uit-de-browser");
      }
    },
  );
});
