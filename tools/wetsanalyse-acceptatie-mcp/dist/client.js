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
/** Een URL van de productiestraat weigeren we hier al, los van de vlag op de server. */
export function controleerUrl(url) {
    const basis = new URL(url);
    if (/(^|[-.])prd([-.]|$)/i.test(basis.hostname)) {
        throw new Error("Deze MCP werkt alleen op acceptatie, niet op productie.");
    }
    return basis.origin;
}
export function controleerPad(pad) {
    if (!pad.startsWith("/api/") || pad.split(/[/?]/).some((s) => s === ".." || s === ".")) {
        throw new Error(`Ongeldig BFF-pad: ${pad}`);
    }
    if (GEBLOKKEERD.some((p) => pad.startsWith(p)))
        throw new Error(`Niet via deze MCP: ${pad}`);
}
/** Haal de events uit een SSE-tekst. sse-starlette scheidt frames met \r\n; de rest blijft in de buffer. */
export function leesFrames(buffer) {
    const delen = buffer.replace(/\r/g, "").split("\n\n");
    const rest = delen.pop() ?? "";
    const events = [];
    for (const frame of delen) {
        const data = frame
            .split("\n")
            .filter((r) => r.startsWith("data:"))
            .map((r) => r.slice(5).trim())
            .join("");
        if (!data)
            continue;
        try {
            events.push(JSON.parse(data));
        }
        catch {
            /* een half of ongeldig frame slaan we over, zoals de werkplek */
        }
    }
    return { events, rest };
}
export class AcceptatieClient {
    basis;
    token;
    doeFetch;
    cookies = new Map();
    constructor(basis, token, doeFetch = fetch) {
        this.basis = basis;
        this.token = token;
        this.doeFetch = doeFetch;
    }
    cookieHeader() {
        return [...this.cookies].map(([k, v]) => `${k}=${v}`).join("; ");
    }
    bewaarCookies(res) {
        for (const regel of res.headers.getSetCookie()) {
            const [paar] = regel.split(";");
            const scheiding = paar.indexOf("=");
            if (scheiding > 0)
                this.cookies.set(paar.slice(0, scheiding), paar.slice(scheiding + 1));
        }
    }
    heeftSessie() {
        return [...this.cookies.keys()].some((k) => k.includes("session-token"));
    }
    /** Wissel het token in. Auth.js geeft bij een weigering géén sessiecookie, wat de status ook is. */
    async login() {
        this.cookies.clear();
        const csrf = await this.doeFetch(`${this.basis}/api/auth/csrf`, {
            signal: AbortSignal.timeout(VERZOEK_TIMEOUT_MS),
        });
        this.bewaarCookies(csrf);
        const { csrfToken } = (await csrf.json());
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
    async metSessie(pad, init) {
        if (!this.heeftSessie())
            await this.login();
        const trace_id = randomBytes(16).toString("hex");
        const verstuur = () => this.doeFetch(`${this.basis}${pad}`, {
            ...init,
            redirect: "manual",
            headers: {
                ...init.headers,
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
    async bff(methode, pad, body) {
        controleerPad(pad);
        const { res, trace_id } = await this.metSessie(pad, {
            method: methode,
            headers: body === undefined ? {} : { "Content-Type": "application/json" },
            body: body === undefined ? undefined : JSON.stringify(body),
            signal: AbortSignal.timeout(VERZOEK_TIMEOUT_MS),
        });
        const tekst = await res.text();
        let data = tekst;
        try {
            data = tekst ? JSON.parse(tekst) : null;
        }
        catch {
            /* geen JSON: de ruwe tekst, bijvoorbeeld een export */
        }
        return { status: res.status, trace_id, data };
    }
    /** Volg een run tot hij klaar is, of tot `maxSeconden`. De run loopt daarna gewoon door. */
    async runEvents(runId, vanaf, maxSeconden) {
        const pad = `/api/annotatie/run/${encodeURIComponent(runId)}/events?vanaf=${vanaf}`;
        const afbreken = new AbortController();
        const timer = setTimeout(() => afbreken.abort(), maxSeconden * 1000);
        const uit = { run_id: runId, klaar: false, vanaf, tekst: "", events: [] };
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
                const gelezen = leesFrames(buffer + decoder.decode(stuk, { stream: true }));
                buffer = gelezen.rest;
                for (const ev of gelezen.events) {
                    if (typeof ev.seq === "number")
                        uit.vanaf = ev.seq;
                    if (ev.type === "token")
                        uit.tekst += String(ev.content ?? "");
                    else if (ev.type !== "reason" && ev.type !== "status")
                        uit.events.push(ev);
                }
            }
            uit.klaar = true;
        }
        catch (e) {
            if (!afbreken.signal.aborted)
                throw e;
        }
        finally {
            clearTimeout(timer);
        }
        return { ...uit, trace_id, status };
    }
}
