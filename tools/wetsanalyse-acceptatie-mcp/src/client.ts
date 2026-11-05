/**
 * De client van de acceptatie-MCP: praat met de webapp zoals een browser dat doet.
 *
 * Hij wisselt een accounttoken in voor een gewone Auth.js-sessie en gebruikt daarna de BFF. Daardoor
 * gelden dezelfde controles als voor een gebruiker: sessie, rol, eigenaarschap en tokenbudget. Dit
 * bestand kent geen MCP, zodat scenario's het later ook buiten een MCP-client kunnen gebruiken.
 */

import { randomBytes } from "node:crypto";

/** Een koude start van graph-qa duurt tot zo'n 15 s, en de BFF wacht tot 45 s op de start van een run. */
const VERZOEK_TIMEOUT_MS = 60_000;

// Niet als accounttoken: die weigert de server ook, maar hier is de fout duidelijker. De rest
// (inloggen, registreren) hoort niet bij wat een ingelogde gebruiker op een scherm doet.
const GEBLOKKEERD = [
  "/api/auth",
  "/api/setup",
  "/api/registreren",
  "/api/login-",
  "/api/admin/api-tokens",
  "/api/account/password",
  "/api/account/2fa",
];

export interface BffAntwoord {
  status: number;
  trace_id: string;
  data: unknown;
}

export interface RunEvents {
  run_id: string;
  /** De stroom is gesloten: de run is af. False = de wachttijd liep eerder af; vraag opnieuw met `vanaf`. */
  klaar: boolean;
  vanaf: number;
  /** De tekst van de `token`-events, aan elkaar. */
  tekst: string;
  /** Alle andere events, behalve `reason` en `status`. */
  events: Record<string, unknown>[];
}

/** Een URL van de productiestraat weigeren we hier al, los van de vlag op de server. */
export function controleerUrl(url: string): string {
  const basis = new URL(url);
  if (/(^|[-.])prd([-.]|$)/i.test(basis.hostname)) {
    throw new Error("Deze MCP werkt alleen op acceptatie, niet op productie.");
  }
  return basis.origin;
}

export function controleerPad(pad: string): void {
  if (!pad.startsWith("/api/") || pad.split(/[/?]/).some((s) => s === ".." || s === ".")) {
    throw new Error(`Ongeldig BFF-pad: ${pad}`);
  }
  if (GEBLOKKEERD.some((p) => pad.startsWith(p))) throw new Error(`Niet via deze MCP: ${pad}`);
}

/** Haal de events uit een SSE-tekst. sse-starlette scheidt frames met \r\n; de rest blijft in de buffer. */
export function leesFrames(buffer: string): { events: Record<string, unknown>[]; rest: string } {
  const delen = buffer.replace(/\r/g, "").split("\n\n");
  const rest = delen.pop() ?? "";
  const events: Record<string, unknown>[] = [];
  for (const frame of delen) {
    const data = frame
      .split("\n")
      .filter((r) => r.startsWith("data:"))
      .map((r) => r.slice(5).trim())
      .join("");
    if (!data) continue;
    try {
      events.push(JSON.parse(data) as Record<string, unknown>);
    } catch {
      /* een half of ongeldig frame slaan we over, zoals de werkplek */
    }
  }
  return { events, rest };
}

export class AcceptatieClient {
  private readonly cookies = new Map<string, string>();

  constructor(
    private readonly basis: string,
    private readonly token: string,
    private readonly doeFetch: typeof fetch = fetch,
  ) {}

  private cookieHeader(): string {
    return [...this.cookies].map(([k, v]) => `${k}=${v}`).join("; ");
  }

  private bewaarCookies(res: Response): void {
    for (const regel of res.headers.getSetCookie()) {
      const [paar] = regel.split(";");
      const scheiding = paar.indexOf("=");
      if (scheiding > 0) this.cookies.set(paar.slice(0, scheiding), paar.slice(scheiding + 1));
    }
  }

  private heeftSessie(): boolean {
    return [...this.cookies.keys()].some((k) => k.includes("session-token"));
  }

  /** Wissel het token in. Auth.js geeft bij een weigering géén sessiecookie, wat de status ook is. */
  private async login(): Promise<void> {
    this.cookies.clear();
    const csrf = await this.doeFetch(`${this.basis}/api/auth/csrf`, {
      signal: AbortSignal.timeout(VERZOEK_TIMEOUT_MS),
    });
    this.bewaarCookies(csrf);
    const { csrfToken } = (await csrf.json()) as { csrfToken: string };
    const res = await this.doeFetch(`${this.basis}/api/auth/callback/api-token`, {
      method: "POST",
      redirect: "manual",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Cookie: this.cookieHeader() },
      body: new URLSearchParams({ csrfToken, token: this.token, callbackUrl: this.basis }),
      signal: AbortSignal.timeout(VERZOEK_TIMEOUT_MS),
    });
    this.bewaarCookies(res);
    if (!this.heeftSessie()) {
      throw new Error("Inloggen met het accounttoken is geweigerd (ingetrokken, verlopen, of niet aan op deze omgeving).");
    }
  }

  private async metSessie(pad: string, init: RequestInit): Promise<{ res: Response; trace_id: string }> {
    if (!this.heeftSessie()) await this.login();
    const trace_id = randomBytes(16).toString("hex");
    const verstuur = () =>
      this.doeFetch(`${this.basis}${pad}`, {
        ...init,
        redirect: "manual",
        headers: {
          ...(init.headers as Record<string, string> | undefined),
          Cookie: this.cookieHeader(),
          traceparent: `00-${trace_id}-${randomBytes(8).toString("hex")}-01`,
        },
      });
    let res = await verstuur();
    if (res.status === 401) {
      // De sessie duurt een uur; na het verlopen logt de client zelf opnieuw in.
      await this.login();
      res = await verstuur();
    }
    this.bewaarCookies(res);
    return { res, trace_id };
  }

  /** Eén BFF-aanroep. Elke status komt terug: een 403 kan precies zijn wat een test wil zien. */
  async bff(methode: string, pad: string, body?: unknown): Promise<BffAntwoord> {
    controleerPad(pad);
    const { res, trace_id } = await this.metSessie(pad, {
      method: methode,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(VERZOEK_TIMEOUT_MS),
    });
    const tekst = await res.text();
    let data: unknown = tekst;
    try {
      data = tekst ? JSON.parse(tekst) : null;
    } catch {
      /* geen JSON: de ruwe tekst, bijvoorbeeld een export */
    }
    return { status: res.status, trace_id, data };
  }

  /** Volg een run tot hij klaar is, of tot `maxSeconden`. De run loopt daarna gewoon door. */
  async runEvents(runId: string, vanaf: number, maxSeconden: number): Promise<RunEvents & { trace_id: string; status: number }> {
    const pad = `/api/annotatie/run/${encodeURIComponent(runId)}/events?vanaf=${vanaf}`;
    const afbreken = new AbortController();
    const timer = setTimeout(() => afbreken.abort(), maxSeconden * 1000);
    const uit: RunEvents = { run_id: runId, klaar: false, vanaf, tekst: "", events: [] };
    let status = 0;
    let trace_id = "";
    try {
      const gestart = await this.metSessie(pad, { signal: afbreken.signal });
      ({ trace_id } = gestart);
      status = gestart.res.status;
      if (!gestart.res.ok || !gestart.res.body) {
        return { ...uit, trace_id, status, events: [{ type: "fout", detail: await gestart.res.text() }] };
      }
      const decoder = new TextDecoder();
      let buffer = "";
      for await (const stuk of gestart.res.body) {
        const gelezen = leesFrames(buffer + decoder.decode(stuk as Uint8Array, { stream: true }));
        buffer = gelezen.rest;
        for (const ev of gelezen.events) {
          if (typeof ev.seq === "number") uit.vanaf = ev.seq;
          if (ev.type === "token") uit.tekst += String(ev.content ?? "");
          else if (ev.type !== "reason" && ev.type !== "status") uit.events.push(ev);
        }
      }
      uit.klaar = true;
    } catch (e) {
      if (!afbreken.signal.aborted) throw e;
    } finally {
      clearTimeout(timer);
    }
    return { ...uit, trace_id, status };
  }
}
