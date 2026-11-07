// Kern van de BFF: forward een request naar de upstream (de api, of met `agent: true` graph-qa) met
// server-side token-injectie, en geef de upstream-status + body ONGEWIJZIGD terug (incl.
// 401/404/409/429/503 en de Retry-After / Location headers), zodat de client correcte
// foutafhandeling houdt. De body stroomt door zonder buffer: een grote export komt zo in delen aan.

import { adminAuthHeader, apiBaseUrl, authHeader, graphQaAuthHeader, graphQaBaseUrl } from "@/lib/config";
import { metTrace } from "@/lib/trace";
import { logger } from "@/lib/logger";

// `content-disposition` hoort erbij zodra een endpoint een bestand teruggeeft (de export):
// zonder die header opent de browser de download als een naamloze blob.
//
// Bewust NIET `content-encoding` en `content-length`: Node's `fetch` pakt een gzip-antwoord (de api
// draait GZipMiddleware) al uit, dus de stroom die we doorgeven is de uitgepakte body. Met die
// headers erbij leest de browser hem als gzip, of breekt hij af op de oude lengte.
const PASS_THROUGH_HEADERS = ["retry-after", "location", "content-type", "content-disposition"];

/** Hoe lang de BFF op de headers van de upstream wacht.
 *
 *  Node's `fetch` kent geen standaardtimeout: een upstream die de verbinding wél accepteert maar niet
 *  antwoordt, houdt zowel deze request als de browser onbeperkt vast. De UI blijft dan in zijn
 *  laadstand hangen – zonder de foutmelding en de "opnieuw proberen"-knop die er speciaal voor zijn.
 *  Dertig seconden is ruim voor elke gewone API-call; wie langer nodig heeft (een modeltest doet een
 *  echte LLM-aanroep) zet `timeoutMs` zelf hoger. De grens geldt tot de headers er zijn, niet voor
 *  de body: een export van een groot werkgebied mag langer doorstromen. */
const STANDAARD_TIMEOUT_MS = 30_000;

interface ProxyInit {
  method?: string;
  /** Rauwe request-body (al als string/Buffer); voor POST met JSON. */
  body?: BodyInit;
  /** Extra headers naar de upstream (bv. Content-Type). */
  headers?: Record<string, string>;
  /** Injecteer het admin-token i.p.v. het gewone client-token (voor /v1/admin/*). */
  admin?: boolean;
  /** De upstream is graph-qa (de agent) in plaats van de api, met het graph-qa-token. */
  agent?: boolean;
  /** Afwijkende wachttijd op de upstream (ms). Default `STANDAARD_TIMEOUT_MS`. */
  timeoutMs?: number;
}

/** Beheer vraagt 2FA: een weigering, of null als deze beheerder door mag.
 *
 *  Bij elke admin-aanroep vers bij de api en niet uit de JWT: de sessiecookie loopt achter (`auth()` in
 *  een route handler schrijft hem niet terug), dus na het koppelen zou beheer anders tot vijf minuten
 *  dicht blijven. Is de api niet te bevragen, dan gaat het beheer dicht. */
async function tweeFactorOntbreekt(userid: string): Promise<Response | null> {
  const { getAccountStatus } = await import("@/lib/server");
  const account = await getAccountStatus(userid);
  if (account.status === "onbekend") {
    return Response.json({ detail: "Je account is nu niet te controleren. Probeer het zo opnieuw." }, { status: 503 });
  }
  if (account.status === "ingetrokken" || account.role !== "beheerder") {
    return Response.json({ detail: "Alleen voor beheerders." }, { status: 403 });
  }
  if (account.tfaNodig) {
    return Response.json(
      { detail: "Koppel eerst tweestapsverificatie aan je account.", code: "2fa_nodig" },
      { status: 403 },
    );
  }
  return null;
}

export async function proxy(path: string, init: ProxyInit = {}): Promise<Response> {
  // Defense-in-depth: de middleware gate't /api/admin al op rol, maar een admin-proxy dwingt de
  // beheerder-rol hier server-side nóg eens af – één matcher-/callback-regressie opent dan niet
  // meteen alle admin-endpoints. Onafhankelijk van, en náást, de middleware.
  if (init.admin) {
    // Dynamische import: houdt de module vrij van de node-only auth-stack (en de unit-test licht);
    // alleen een echte admin-proxy laadt 'm.
    const { auth } = await import("@/auth");
    const session = await auth();
    const user = session?.user as { role?: string; userid?: string; viaToken?: string } | undefined;
    if (user?.role !== "beheerder") {
      return Response.json({ detail: "Alleen voor beheerders." }, { status: 403 });
    }
    // Een sessie uit een accounttoken kan niet koppelen (`buitenTokenSessie` in `auth.config.ts`),
    // dus de plicht zou daar een doodlopende weg zijn.
    if (!user.viaToken) {
      const geweigerd = await tweeFactorOntbreekt(user.userid ?? "");
      if (geweigerd) return geweigerd;
    }
  }
  const upstreamUrl = `${init.agent ? graphQaBaseUrl() : apiBaseUrl()}${path}`;
  const authHeaders = init.agent ? graphQaAuthHeader() : init.admin ? adminAuthHeader() : authHeader();
  const naam = init.agent ? "agent" : "API";
  const method = init.method ?? "GET";
  const timeoutMs = init.timeoutMs ?? STANDAARD_TIMEOUT_MS;
  const start = performance.now();
  // Een eigen timer in plaats van `AbortSignal.timeout`: die bleef ook op de body staan en brak een
  // trage download na `timeoutMs` af. Deze gaat uit zodra de headers binnen zijn, net als bij de
  // events-route.
  const opzet = new AbortController();
  const timer = setTimeout(() => opzet.abort(new DOMException("timeout", "TimeoutError")), timeoutMs);
  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method,
      headers: metTrace({ ...authHeaders, ...(init.headers ?? {}) }),
      body: init.body,
      cache: "no-store",
      signal: opzet.signal,
    });
  } catch (err) {
    // Een timeout is iets anders dan een onbereikbare upstream, en de gebruiker heeft aan "the
    // operation was aborted" niets. 504 zodat de client het als een tijdelijke hapering kan behandelen.
    const verlopen = opzet.signal.aborted;
    logger.error(verlopen ? `BFF-proxy: ${naam} antwoordde niet op tijd` : `BFF-proxy: ${naam} onbereikbaar`, {
      http_method: method,
      http_path: path,
      fout: (err as Error).message,
      timeout_ms: verlopen ? timeoutMs : undefined,
    });
    const wacht = timeoutMs >= 1000 ? `${Math.round(timeoutMs / 1000)} seconden` : `${timeoutMs} ms`;
    return Response.json(
      {
        detail: verlopen
          ? `De ${naam} antwoordde niet binnen ${wacht}.`
          : `${init.agent ? "Agent" : "API"} onbereikbaar: ${(err as Error).message}`,
      },
      { status: verlopen ? 504 : 502 },
    );
  } finally {
    clearTimeout(timer);
  }
  logger.info("BFF-proxy", {
    http_method: method,
    http_path: path,
    http_status: upstream.status,
    duur_ms: Math.round(performance.now() - start),
  });

  // Stuur de body als stroom door, met de status en de headers uit `PASS_THROUGH_HEADERS`. Een
  // status zonder body (204, 304) mag geen stroom dragen: `new Response` weigert dat.
  const headers = new Headers();
  for (const h of PASS_THROUGH_HEADERS) {
    const v = upstream.headers.get(h);
    if (v) headers.set(h, v);
  }
  const zonderBody = [101, 204, 205, 304].includes(upstream.status);
  if (zonderBody) await upstream.body?.cancel().catch(() => {});
  return new Response(zonderBody ? null : upstream.body, {
    status: upstream.status,
    headers,
  });
}

/** Een proxy-antwoord dat de route alleen op zijn status leest (een eigenaarscontrole): sluit de
 *  stroom, anders blijft de upstream-verbinding open tot de garbage collector langskomt. */
export async function sluit(res: Response): Promise<void> {
  await res.body?.cancel().catch(() => {});
}

/** Helper om de JSON-body van een inkomend request door te sturen. */
export async function readBody(req: Request): Promise<string> {
  return req.text();
}
