// Server-side helpers voor Server Components: praten rechtstreeks (server→server) met de API,
// zodat de initiële render geen extra self-fetch via de BFF-route nodig heeft. Het token komt
// uit lib/config (server-only). NOOIT importeren vanuit een Client Component.
//
// Elke fetch hier loopt door `metTrace()`, net als de BFF-routes: zonder die header start een
// Server-Component-render of een auth-herverificatie een lósse trace, en breekt de keten
// frontend → API → graph-qa precies op de plek waar hij begint.

import "server-only";
import { apiBaseUrl, authHeader } from "./config";
import { logger } from "./logger";
import { metTrace } from "./trace";

/** Wachttijd voor de gewone server-fetches. Node's `fetch` kent geen standaardtimeout: een API die
 *  de verbinding wél accepteert maar niet antwoordt, laat de aanroep onbeperkt hangen – en daarmee de
 *  `auth()` eraan, en dus de hele render. Dezelfde reden als `STANDAARD_TIMEOUT_MS` in de BFF-proxy. */
const SERVER_TIMEOUT_MS = 10_000;

/** Ruimer voor de login: de api schaalt naar nul replica's, dus de eerste poging na een stille
 *  periode betaalt een koude start. Een login die daarop afknapt is erger dan een login die even
 *  duurt. Gelijk aan de default van de BFF-proxy. */
const AUTH_VERIFY_TIMEOUT_MS = 30_000;

async function serverGet<T>(path: string): Promise<T> {
  const res = await fetch(`${apiBaseUrl()}${path}`, {
    headers: metTrace({ ...authHeader() }),
    cache: "no-store",
    signal: AbortSignal.timeout(SERVER_TIMEOUT_MS),
  });
  if (!res.ok) {
    logger.warn("Server-fetch niet-ok", { http_path: path, http_status: res.status });
    const err = new Error(`API ${res.status} op ${path}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return (await res.json()) as T;
}

// --- Auth (server→server; aangeroepen door auth.ts en de login/setup-pagina's) ---------------

export interface VerifyResult {
  ok: boolean;
  code: string; // "" | "invalid" | "totp_required" | "rate" | "onbereikbaar"
  userid: string;
  email: string;
  role: "beheerder" | "analist" | "";
  // Server→server-only (via httpOnly cookies gezet door de BFF; nooit naar de browser-JS).
  ticket?: string | null; // bij totp_required: bewijs voor het aparte 2FA-scherm
  trusted_token?: string | null; // bij ok + remember: 30-daags "dit apparaat onthouden"-token
}

/** Alternatieve bewijzen naast het wachtwoord, uit de httpOnly cookies (server-side gelezen). */
export interface VerifyOpts {
  ticket?: string | null;
  trusted_token?: string | null;
  remember?: boolean;
}

/** Lage-niveau POST naar `/v1/auth/verify` – geeft de VOLLEDIGE respons (incl. ticket/trusted_token)
 *  zodat de BFF-login-routes de cookies kunnen zetten. Server→server; nooit vanuit een client.
 *
 *  Een transportfout wordt hier – net als de 429 hieronder – een gestructureerd antwoord in plaats
 *  van een throw, met de status die `proxy()` er ook aan geeft: 504 als de API niet op tijd
 *  antwoordde, 502 als hij onbereikbaar was. De login-routes geven die status door, zodat de client
 *  een storing kan onderscheiden van een afgewezen wachtwoord. */
export async function postAuthVerify(
  payload: Record<string, unknown>,
): Promise<{ status: number; body: VerifyResult }> {
  let res: Response;
  try {
    res = await fetch(`${apiBaseUrl()}/v1/auth/verify`, {
      method: "POST",
      headers: metTrace({ ...authHeader(), "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(AUTH_VERIFY_TIMEOUT_MS),
    });
  } catch (err) {
    const verlopen = (err as Error).name === "TimeoutError";
    logger.error(verlopen ? "Auth-verify: API antwoordde niet op tijd" : "Auth-verify: API onbereikbaar", {
      http_path: "/v1/auth/verify",
      fout: (err as Error).message,
      timeout_ms: verlopen ? AUTH_VERIFY_TIMEOUT_MS : undefined,
    });
    return {
      status: verlopen ? 504 : 502,
      body: { ok: false, code: "onbereikbaar", userid: "", email: "", role: "" },
    };
  }
  if (res.status === 429) {
    return { status: 429, body: { ok: false, code: "rate", userid: "", email: "", role: "" } };
  }
  const body = (await res
    .json()
    .catch(() => ({ ok: false, code: "invalid", userid: "", email: "", role: "" }))) as VerifyResult;
  return { status: res.status, body };
}

/** Valideer inloggegevens (op userid) bij de API. Gebruikt door de Auth.js Credentials-provider;
 *  `opts` draagt de httpOnly-cookie-bewijzen (login-ticket / trusted-device) die authorize meestuurt. */
export async function verifyCredentials(
  userid: string,
  password: string,
  totp?: string,
  opts: VerifyOpts = {},
): Promise<VerifyResult> {
  const { body } = await postAuthVerify({
    userid,
    password,
    totp: totp ?? null,
    ticket: opts.ticket ?? null,
    trusted_token: opts.trusted_token ?? null,
    remember: opts.remember ?? false,
  });
  return body;
}

/** Actuele accountstatus voor de periodieke sessie-herverificatie (jwt-callback in auth.ts). */
export type AccountStatus =
  | { status: "actief"; role: "beheerder" | "analist"; email: string; sessionsValidFrom?: number }
  | { status: "ingetrokken" } // 401: account inactief of verwijderd → sessie invalideren
  | { status: "onbekend" }; // API tijdelijk onbereikbaar → sessie laten staan (maxAge begrenst)

/** Raadpleeg `/v1/auth/me` (identiteit via de vertrouwde X-User-Id, zoals de account-routes). */
export async function getAccountStatus(userid: string): Promise<AccountStatus> {
  try {
    const res = await fetch(`${apiBaseUrl()}/v1/auth/me`, {
      headers: metTrace({ ...authHeader(), "X-User-Id": userid }),
      cache: "no-store",
      // Zonder deze grens houdt een hangende API elke `auth()` vast – en daarmee elke render. De
      // catch hieronder maakt er "onbekend" van: de sessie blijft staan, de herverificatie schuift op.
      signal: AbortSignal.timeout(SERVER_TIMEOUT_MS),
    });
    if (res.status === 401) return { status: "ingetrokken" };
    if (!res.ok) return { status: "onbekend" };
    const me = (await res.json()) as {
      role: "beheerder" | "analist";
      email: string;
      sessions_valid_from?: string | null;
    };
    const svf = me.sessions_valid_from ? Date.parse(me.sessions_valid_from) : NaN;
    return {
      status: "actief",
      role: me.role,
      email: me.email,
      sessionsValidFrom: Number.isNaN(svf) ? undefined : svf,
    };
  } catch {
    return { status: "onbekend" };
  }
}

/** Is er nog geen enkel account? Dan staat de eenmalige registratie open. */
export async function getSetupStatus(): Promise<{ needs_setup: boolean }> {
  try {
    return await serverGet<{ needs_setup: boolean }>(`/v1/auth/setup-status`);
  } catch {
    // API onbereikbaar: ga uit van "geen setup nodig" zodat we niet onbedoeld registratie openen.
    return { needs_setup: false };
  }
}
