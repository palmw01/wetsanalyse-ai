#!/usr/bin/env node
/**
 * Wetsanalyse-acceptatie MCP-server (stdio).
 *
 * Bedient de webapp op acceptatie zoals een gebruiker: alles loopt via de BFF, met een sessie uit een
 * accounttoken (`wa_pat_…`). Zo kan een MCP-client een acceptatietest van begin tot eind doen zonder
 * schermen aan te raken, met dezelfde controles als een gebruiker. De rendering test dit niet.
 *
 * Config via env (nooit in de repo):
 *   WETSANALYSE_ACC_URL              – basis-URL van de webapp op acceptatie
 *   WETSANALYSE_ACC_TOKEN            – accounttoken van een analist
 *   WETSANALYSE_ACC_TOKEN_BEHEERDER  – optioneel, accounttoken van een beheerder
 *   WETSANALYSE_ACC_GRAFANA_URL      – optioneel, voor logs_zoek
 *   WETSANALYSE_ACC_GRAFANA_WACHTWOORD – optioneel, het admin-wachtwoord van die Grafana
 *
 * Fail-closed: zonder URL en token weigert de server te starten, en een productie-URL ook. Logs (JSON)
 * gaan naar stderr; tokens worden nooit gelogd. stdout is exclusief voor het MCP-protocol.
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import { AcceptatieClient, controleerUrl } from "./client.js";
import { zoekLogs } from "./logs.js";
const URL_ACC = process.env.WETSANALYSE_ACC_URL ?? "";
const TOKEN_ANALIST = (process.env.WETSANALYSE_ACC_TOKEN ?? "").trim();
const TOKEN_BEHEERDER = (process.env.WETSANALYSE_ACC_TOKEN_BEHEERDER ?? "").trim();
const GRAFANA_URL = (process.env.WETSANALYSE_ACC_GRAFANA_URL ?? "").replace(/\/+$/, "");
const GRAFANA_WACHTWOORD = process.env.WETSANALYSE_ACC_GRAFANA_WACHTWOORD ?? "";
function log(niveau, bericht, velden = {}) {
    process.stderr.write(JSON.stringify({ ts: new Date().toISOString(), niveau, bericht, ...velden }) + "\n");
}
const clients = new Map();
function client(als) {
    const rol = als === "beheerder" ? "beheerder" : "analist";
    const token = rol === "beheerder" ? TOKEN_BEHEERDER : TOKEN_ANALIST;
    if (!token)
        throw new Error("WETSANALYSE_ACC_TOKEN_BEHEERDER is niet gezet.");
    let c = clients.get(rol);
    if (!c) {
        c = new AcceptatieClient(controleerUrl(URL_ACC), token);
        clients.set(rol, c);
    }
    return c;
}
const seg = (s) => encodeURIComponent(String(s));
const S = z.object;
const Als = z.enum(["analist", "beheerder"]).optional();
/** Lees een paar routes samen; een mislukte route blijft zichtbaar in plaats van het geheel te breken. */
async function samen(c, routes) {
    const paren = await Promise.all(Object.entries(routes).map(async ([naam, pad]) => {
        const a = await c.bff("GET", pad);
        return [naam, a.status === 200 ? a.data : { status: a.status, data: a.data }];
    }));
    return Object.fromEntries(paren);
}
const TOOLS = [
    {
        name: "wie_ben_ik",
        description: "Het account en de rol waarmee deze MCP werkt. `als` kiest het analist- of beheerderaccount.",
        input: S({ als: Als }),
        run: (a) => client(a.als).bff("GET", "/api/account/me"),
    },
    {
        name: "bff",
        description: "Eén aanroep op de BFF, zoals een scherm die doet: `pad` begint met /api/. Geeft status, body en " +
            "trace_id; elke status komt terug, dus ook een 403 die een test juist verwacht. Inloggen, tokens " +
            "maken en wachtwoord of 2FA wijzigen kan hier niet.",
        input: S({
            methode: z.enum(["GET", "POST", "PUT", "PATCH", "DELETE"]),
            pad: z.string(),
            body: z.unknown().optional(),
            als: Als,
        }),
        run: (a) => client(a.als).bff(a.methode, a.pad, a.body),
    },
    {
        name: "lex_start",
        description: "Start een beurt van Lex, zoals de werkplek (POST /api/annotatie/run). Maak eerst een gesprek met " +
            "`bff` POST /api/gesprekken. Een klik gaat als `intake_actie` of `actie`, met dezelfde inhoud als de " +
            "knop stuurt; `extra` draagt de overige velden van een run (modus, bevestigd, bereik, deelvraag_id, " +
            "onderwerp, context). Geeft het run_id; volg de beurt met lex_wacht.",
        input: S({
            vraag: z.string(),
            conversation_id: z.string(),
            werkgebied_id: z.string().optional(),
            intake_actie: z.unknown().optional(),
            actie: z.unknown().optional(),
            extra: z.record(z.string(), z.unknown()).optional(),
            als: Als,
        }),
        run: (a) => client(a.als).bff("POST", "/api/annotatie/run", {
            question: a.vraag,
            conversation_id: a.conversation_id,
            ...a.extra,
            ...(a.werkgebied_id ? { werkgebied_id: a.werkgebied_id } : {}),
            ...(a.intake_actie ? { intake_actie: a.intake_actie } : {}),
            ...(a.actie ? { actie: a.actie } : {}),
        }),
    },
    {
        name: "lex_wacht",
        description: "Volg een run tot hij klaar is of tot `max_seconden`. Geeft de tekst van het antwoord en de events " +
            "(vraagkaart, artefact, bevestiging, grounding, sources, …). `klaar: false` betekent dat de wachttijd " +
            "eerder afliep: de run loopt door, vraag opnieuw met de teruggegeven `vanaf`.",
        input: S({
            run_id: z.string(),
            vanaf: z.number().int().min(0).optional(),
            max_seconden: z.number().int().min(1).max(110).optional(),
            als: Als,
        }),
        run: (a) => client(a.als).runEvents(a.run_id, a.vanaf ?? 0, a.max_seconden ?? 90),
    },
    {
        name: "lex_stop",
        description: "Vraag een run te stoppen. Een verzoek, geen feit: hij stopt op de eerstvolgende grens.",
        input: S({ run_id: z.string(), als: Als }),
        run: (a) => client(a.als).bff("POST", `/api/annotatie/run/${seg(a.run_id)}/cancel`),
    },
    {
        name: "werkgebied_lezen",
        description: "Het hele werkgebied in één keer: dossier met deelvragen, dekking, geannoteerde elementen en de audit.",
        input: S({ werkgebied_id: z.string(), als: Als }),
        run: (a) => {
            const wg = `/api/werkgebieden/${seg(a.werkgebied_id)}`;
            return samen(client(a.als), {
                werkgebied: wg,
                dekking: `${wg}/deelvragen/dekking`,
                elementen: `${wg}/elementen`,
                audit: `${wg}/audit`,
            });
        },
    },
    {
        name: "annotatie_lezen",
        description: "Eén geannoteerd element met alles om het te beoordelen: klasse, ankers, bronreferentie, aandachtsniveau, " +
            "herkomst en de bron. De ids staan in de elementen van werkgebied_lezen.",
        input: S({ element_id: z.string(), als: Als }),
        run: (a) => samen(client(a.als), {
            element: `/api/annotatie/v2/elementen/${seg(a.element_id)}`,
            graaf: `/api/annotatie/v2/elementen/${seg(a.element_id)}/graaf`,
        }),
    },
    {
        name: "begrip_lezen",
        description: "Eén begrip: kaart met definitie en status, gekoppelde passages en revisies. Zonder begrip_id alle begrippen van het werkgebied.",
        input: S({ werkgebied_id: z.string(), begrip_id: z.string().optional(), als: Als }),
        run: (a) => {
            const pad = `/api/werkgebieden/${seg(a.werkgebied_id)}/begrippen`;
            if (!a.begrip_id)
                return client(a.als).bff("GET", pad);
            return samen(client(a.als), {
                begrip: `${pad}/${seg(a.begrip_id)}`,
                revisies: `${pad}/${seg(a.begrip_id)}/revisies`,
            });
        },
    },
    {
        name: "logs_zoek",
        description: "Logs van acceptatie: met `trace_id` de hele keten van één aanroep (traces), met `run_id` de logregels " +
            "van een run, zonder beide de fouten en waarschuwingen. Alleen vaste queries. Telemetrie komt met enkele " +
            "minuten vertraging binnen, dus een lege uitslag direct na een actie zegt nog niets.",
        input: S({
            trace_id: z.string().optional(),
            run_id: z.string().optional(),
            minuten: z.number().int().min(1).max(1440).optional(),
        }),
        run: (a) => {
            if (!GRAFANA_URL || !GRAFANA_WACHTWOORD) {
                throw new Error("Zet WETSANALYSE_ACC_GRAFANA_URL en WETSANALYSE_ACC_GRAFANA_WACHTWOORD.");
            }
            return zoekLogs(GRAFANA_URL, GRAFANA_WACHTWOORD, {
                trace_id: a.trace_id,
                run_id: a.run_id,
                minuten: a.minuten ?? 60,
            });
        },
    },
];
function alsJsonSchema(schema) {
    const json = z.toJSONSchema(schema, { io: "input" });
    delete json["$schema"];
    return json;
}
async function main() {
    if (!URL_ACC || !TOKEN_ANALIST) {
        log("error", "Weigering te starten: zet WETSANALYSE_ACC_URL en WETSANALYSE_ACC_TOKEN.");
        process.exit(1);
    }
    controleerUrl(URL_ACC);
    const server = new Server({ name: "wetsanalyse-acceptatie", version: "0.1.0" }, { capabilities: { tools: {} } });
    server.setRequestHandler(ListToolsRequestSchema, async () => ({
        tools: TOOLS.map((t) => ({ name: t.name, description: t.description, inputSchema: alsJsonSchema(t.input) })),
    }));
    server.setRequestHandler(CallToolRequestSchema, async (req) => {
        const def = TOOLS.find((t) => t.name === req.params.name);
        if (!def)
            throw new Error(`Onbekende tool: ${req.params.name}`);
        const args = def.input.parse(req.params.arguments ?? {});
        try {
            const resultaat = await def.run(args);
            log("info", "tool ok", { tool: def.name });
            return { content: [{ type: "text", text: JSON.stringify(resultaat, null, 2) }] };
        }
        catch (e) {
            log("warn", "tool fout", { tool: def.name, fout: e.message });
            return { content: [{ type: "text", text: `Fout: ${e.message}` }], isError: true };
        }
    });
    await server.connect(new StdioServerTransport());
    log("info", "wetsanalyse-acceptatie MCP gestart (stdio)", { tools: TOOLS.length });
}
main().catch((e) => {
    log("error", "fatale startfout", { fout: e.message });
    process.exit(1);
});
