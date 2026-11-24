import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

// Het laagcontract tussen de client-helpers (`lib/api.ts`) en de BFF-routes (`app/api/**`). De browsertests mocken
// `/api/**` (frontend/CLAUDE.md §De poort), dus een pad- of methodefout tussen deze twee lagen zag tot nu toe niemand:
// de helper roept `/api/werkgebieden/{id}/bronen` aan, de mock antwoordt, en pas op acceptatie komt de 404.
//
// Hier roept elke helper de échte route aan, met een sessie, en die praat weer met een nep-upstream. Getoetst:
//  1. de helper praat alleen met de eigen origin (`/api/…`) en stuurt nooit een Authorization-header (de BFF-regel);
//  2. er bestaat een route voor dat pad, en die exporteert de methode;
//  3. de route laat het verzoek door – een catch-all met een allowlist (`isWerkgebiedRoute`, `isGeneriekRoute`, de
//     annotatie-allowlist) geeft anders een 404, net als een onbekend pad;
//  4. de route stuurt het door naar een upstream.
//
// De argumenten zijn plaatshouders ("a1", "a2", …); waar een helper een andere vorm eist, staat hij in `ARGUMENTEN`.

process.env.API_BASE_URL = "http://api.test";
process.env.API_TOKEN = "api-token";
process.env.ADMIN_API_TOKEN = "admin-token";
process.env.GRAPH_QA_URL = "http://agent.test";
process.env.GRAPH_QA_TOKEN = "agent-token";

vi.mock("@/auth", () => ({ auth: async () => ({ user: { userid: "sessie-1", role: "beheerder" } }) }));
vi.mock("@/lib/server", async (orig) => ({
  ...(await orig<typeof import("@/lib/server")>()),
  getAccountStatus: async () => ({ status: "actief", role: "beheerder", tfaNodig: false }),
}));
vi.mock("next/headers", () => ({
  headers: async () => new Headers(),
  cookies: async () => ({ get: () => undefined, set: () => {}, delete: () => {} }),
}));

const API = join(__dirname, "..", "app", "api");
const METHODES = ["GET", "POST", "PUT", "PATCH", "DELETE"];

interface Route { segmenten: string[]; bestand: string; methodes: string[] }

function routes(map = API): Route[] {
  const uit: Route[] = [];
  for (const naam of readdirSync(map)) {
    const vol = join(map, naam);
    if (statSync(vol).isDirectory()) uit.push(...routes(vol));
    else if (naam === "route.ts") {
      const bron = readFileSync(vol, "utf8");
      const methodes = METHODES.filter((m) => new RegExp(`export\\s+(async\\s+function\\s+${m}\\b|const\\s+${m}\\s*=)`).test(bron));
      const pad = relative(API, map);
      // De vangnetroute (`[...onbekend]`, een 404 voor alles) telt niet als bestemming.
      if (pad !== "[...onbekend]") uit.push({ segmenten: pad ? pad.split("/") : [], bestand: vol, methodes });
    }
  }
  return uit;
}

/** De route die Next voor deze segmenten kiest: statisch gaat voor dynamisch, dynamisch voor catch-all. */
function zoekRoute(alle: Route[], delen: string[]): { route: Route; params: Record<string, string | string[]> } | null {
  let beste: { route: Route; params: Record<string, string | string[]>; score: number[] } | null = null;
  for (const route of alle) {
    const params: Record<string, string | string[]> = {};
    const score: number[] = [];
    let i = 0;
    let past = true;
    for (const seg of route.segmenten) {
      const catchAll = /^\[\[?\.\.\.(\w+)\]\]?$/.exec(seg);
      const dyn = /^\[(\w+)\]$/.exec(seg);
      if (catchAll) {
        const rest = delen.slice(i);
        if (rest.length === 0 && !seg.startsWith("[[")) { past = false; break; }
        params[catchAll[1]] = rest;
        i = delen.length;
        score.push(0);
      } else if (dyn) {
        if (i >= delen.length) { past = false; break; }
        params[dyn[1]] = delen[i++];
        score.push(1);
      } else {
        if (delen[i] !== seg) { past = false; break; }
        i++;
        score.push(2);
      }
    }
    if (!past || i !== delen.length) continue;
    const beter = !beste || score.join(",").localeCompare(beste.score.join(","), undefined, { numeric: true }) > 0;
    if (beter) beste = { route, params, score };
  }
  return beste;
}

const ALLE_ROUTES = routes();

interface Aanroep {
  helper: string;
  url: string;
  methode: string;
  authorization: string | null;
  route?: string;
  status?: number;
  upstream: string[];
  fout?: string;
}
const aanroepen: Aanroep[] = [];
let huidig = "";

beforeAll(() => {
  vi.spyOn(process.stdout, "write").mockImplementation(() => true);
  vi.stubGlobal("fetch", async (invoer: string | URL | Request, init?: RequestInit) => {
    const url = String(invoer);
    // De upstream (api of graph-qa): een leeg, geldig antwoord.
    if (url.startsWith("http://api.test") || url.startsWith("http://agent.test")) {
      aanroepen.at(-1)?.upstream.push(url);
      return Response.json({});
    }
    const methode = (init?.method ?? "GET").toUpperCase();
    const a: Aanroep = {
      helper: huidig, url, methode, upstream: [],
      authorization: new Headers(init?.headers).get("authorization"),
    };
    aanroepen.push(a);
    if (!url.startsWith("/api/")) return Response.json({});
    const pad = new URL(url, "http://werkplek.test").pathname.slice("/api/".length);
    const delen = pad.split("/").filter(Boolean).map(decodeURIComponent);
    const gevonden = zoekRoute(ALLE_ROUTES, delen);
    if (!gevonden) {
      a.fout = "geen route";
      return Response.json({ detail: "Onbekende route." }, { status: 404 });
    }
    a.route = relative(API, gevonden.route.bestand);
    if (!gevonden.route.methodes.includes(methode)) {
      a.fout = `route kent ${methode} niet`;
      return new Response(null, { status: 405 });
    }
    const mod = (await import(gevonden.route.bestand)) as Record<string, (r: Request, c: unknown) => Promise<Response>>;
    const res = await mod[methode](new Request(`http://werkplek.test${url}`, { ...init, method: methode }), {
      params: Promise.resolve(gevonden.params),
    });
    a.status = res.status;
    return res;
  });
  // Een download maakt een link in het document; in node is er geen document, en dat hoort niet bij dit contract.
  vi.stubGlobal("document", undefined);
});

afterAll(() => vi.unstubAllGlobals());

/** Helpers die geen aanroep zijn: pure functies, of een registratie zonder verzoek. */
const GEEN_AANROEP = new Set([
  "parseError", "naarInloggen", "isApiError", "foutTekst", "bestandsnaamUit", "voorstellenPad",
  "vergeetDelegaties", "luisterNaarDelegaties", "GESPREKKEN_PER_VERZOEK", "downloadAntwoord", "downloadTekst", "downloadBlob",
]);

/** De helpers in `lib/annotatieNode.ts` die een verzoek doen; de rest van die module is rekenwerk. */
const NODE_AANROEPEN = new Set([
  "haalElement", "haalElementDetail", "beslisElement", "haalElementGraaf", "haalPlaatsen", "haalNodeWeergave",
  "verwijderAnnotatie",
]);

const ELEMENT_DETAIL = { element: { id: "e1", eigenaar_iri: "urn:bwb:x" }, laag: { revisie: 2 }, snapshot_id: "s1" };
const DOEL = { bron_iri: "urn:bwb:BWBR0004770:artikel:9", snapshot_id: "s1" };

/** Helpers die een andere vorm van argumenten eisen dan plaatshouders. */
const ARGUMENTEN: Record<string, unknown[]> = {
  haalOnderdeel: ["methode", "wetsanalyse"],
  haalConceptVersie: ["a1", 2],
  toetsConcept: [{ soort: "skill", naam: "a1", bestanden: {} }],
  verwijderGesprekkenGroep: ["recent"],
  archiveerGesprekkenGroep: ["recent"],
  besluitGroep: ["a1", "a2", "afwijzen"],
  laadGesprekken: [{}, 3],
  omhangOpenPunt: ["a1", "a2", 1, []],
  beslisElement: [ELEMENT_DETAIL, { type: "approve" }],
  haalPlaatsen: [["urn:bwb:a", "urn:bwb:b"]],
  haalNodeWeergave: [DOEL],
  verwijderAnnotatie: [DOEL],
  "apiOpslag.weergave": [DOEL],
  "apiOpslag.exporteer": [{ formaat: "json" }],
};

/** Routes die terecht niet naar boven gaan: alleen een cookie, of een stap die een cookie eist die hier niet is. */
const ZONDER_UPSTREAM: Record<string, string> = {
  accepteerDisclaimer: "zet alleen een sessiecookie",
  wisDisclaimer: "wist alleen een sessiecookie",
  login2fa: "zonder login-ticket (een httpOnly cookie uit stap A) weigert de route terecht",
};

/** Roept één helper aan en wacht kort; een helper die blijft luisteren (een stroom) laat zijn eerste aanroep achter. */
async function roep(naam: string, f: (...a: unknown[]) => unknown) {
  huidig = naam;
  const args = ARGUMENTEN[naam] ?? Array.from({ length: Math.max(f.length, 3) }, (_, i) => `a${i + 1}`);
  try {
    await Promise.race([Promise.resolve(f(...args)), new Promise((r) => setTimeout(r, 200))]);
  } catch {
    // Een helper mag op een leeg antwoord ({}) een vormfout geven; dat toetst `api.test.ts`. Hier telt de aanroep.
  }
}

describe("laagcontract lib/api.ts ⇄ app/api", () => {
  let helpers: [string, (...a: unknown[]) => unknown][] = [];

  beforeAll(async () => {
    const api = (await import("./api")) as Record<string, unknown>;
    // De annotatielagen hebben hun eigen client (`lib/annotatieNode.ts`, de opslag van het paneel) achter de
    // allowlist van `annotatie/v2/[...pad]`.
    const node = (await import("./annotatieNode")) as Record<string, unknown>;
    const opslag = Object.fromEntries(Object.entries(node.apiOpslag as Record<string, unknown>).map(([n, f]) => [`apiOpslag.${n}`, f]));
    const nodeHelpers = Object.fromEntries(Object.entries(node).filter(([n]) => NODE_AANROEPEN.has(n)));
    helpers = Object.entries({ ...api, ...nodeHelpers, ...opslag })
      .filter(([n, f]) => typeof f === "function" && !GEEN_AANROEP.has(n)) as typeof helpers;
    for (const [n, f] of helpers) await roep(n, f);
  });

  it("roept vrijwel elke helper aan (de meting zelf werkt)", () => {
    const met = new Set(aanroepen.map((a) => a.helper));
    const zonder = helpers.map(([n]) => n).filter((n) => !met.has(n));
    expect(helpers.length).toBeGreaterThan(180);
    expect(zonder).toEqual([]);
  });

  it("praat alleen met de eigen origin, zonder Authorization-header", () => {
    expect(aanroepen.filter((a) => !a.url.startsWith("/api/")).map((a) => `${a.helper}: ${a.url}`)).toEqual([]);
    expect(aanroepen.filter((a) => a.authorization).map((a) => a.helper)).toEqual([]);
  });

  it("elk pad heeft een route die de methode kent", () => {
    expect(aanroepen.filter((a) => a.fout).map((a) => `${a.helper}: ${a.methode} ${a.url} – ${a.fout}`)).toEqual([]);
  });

  it("de route laat het verzoek door naar een upstream (geen 404 van een allowlist)", () => {
    const tegengehouden = aanroepen
      .filter((a) => a.route && !a.fout && a.upstream.length === 0 && !(a.helper in ZONDER_UPSTREAM))
      .map((a) => `${a.helper}: ${a.methode} ${a.url} → ${a.status} (${a.route})`);
    expect(tegengehouden).toEqual([]);
  });
});
