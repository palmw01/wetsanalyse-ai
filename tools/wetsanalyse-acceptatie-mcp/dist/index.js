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
 *   WETSANALYSE_ACC_TOKEN            – accounttoken van het account waarmee getest wordt (docs/acceptatie/testaccount.md)
 *   WETSANALYSE_ACC_ACCOUNT          – optioneel, de userid van dat account; wie_ben_ik meldt of het token erbij hoort
 *   WETSANALYSE_ACC_TOKEN_BEHEERDER  – optioneel, accounttoken van een beheerder
 *   WETSANALYSE_ACC_TOKEN_TEST_ANALIST – optioneel, accounttoken van het analistaccount voor K10 (`als: "test-analist"`)
 *   WETSANALYSE_ACC_GRAFANA_URL      – optioneel, voor logs_zoek
 *   WETSANALYSE_ACC_GRAFANA_WACHTWOORD – optioneel, het admin-wachtwoord van die Grafana
 *   WETSANALYSE_ACC_GRAAF_URL        – optioneel, voor graaf_lezen: de MCP-proxy van acceptatie
 *   WETSANALYSE_ACC_GRAAF_TOKEN      – optioneel, het bearer-token van die proxy
 *
 * Fail-closed: zonder URL en token weigert de server te starten, en een productie-URL ook. Logs (JSON)
 * gaan naar stderr; tokens worden nooit gelogd. stdout is exclusief voor het MCP-protocol.
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { inleveren, opdrachtLezen, pythonControle } from "./bench.js";
import { lexStart } from "./beurt.js";
import { BronClient } from "./bron.js";
import { AcceptatieClient, controleerUrl } from "./client.js";
import { GraafClient } from "./graaf.js";
import { aanvullen, lezen, ROLLEN, SOORTEN, standaardMap } from "./logboek.js";
import { zoekLogs } from "./logs.js";
import { isVerwijderend, leesRuimte, opruimplan, toetsVerwijderen, voerUit } from "./runruimte.js";
import { auditStaart, inventarisOverzicht } from "./vorm.js";
const URL_ACC = process.env.WETSANALYSE_ACC_URL ?? "";
const TOKEN_ANALIST = (process.env.WETSANALYSE_ACC_TOKEN ?? "").trim();
const TOKEN_BEHEERDER = (process.env.WETSANALYSE_ACC_TOKEN_BEHEERDER ?? "").trim();
const TOKEN_TEST_ANALIST = (process.env.WETSANALYSE_ACC_TOKEN_TEST_ANALIST ?? "").trim();
const GRAFANA_URL = (process.env.WETSANALYSE_ACC_GRAFANA_URL ?? "").replace(/\/+$/, "");
const GRAFANA_WACHTWOORD = process.env.WETSANALYSE_ACC_GRAFANA_WACHTWOORD ?? "";
const GRAAF_URL = process.env.WETSANALYSE_ACC_GRAAF_URL ?? "";
const GRAAF_TOKEN = (process.env.WETSANALYSE_ACC_GRAAF_TOKEN ?? "").trim();
const ACCOUNT = (process.env.WETSANALYSE_ACC_ACCOUNT ?? "").trim();
const REPO = fileURLToPath(new URL("../../../", import.meta.url));
const LOGBOEK_MAP = standaardMap(REPO);
const BENCH_CONTROLE = pythonControle(join(REPO, "tools", "graph-qa"));
function log(niveau, bericht, velden = {}) {
    process.stderr.write(JSON.stringify({ ts: new Date().toISOString(), niveau, bericht, ...velden }) + "\n");
}
const clients = new Map();
function client(als) {
    const rol = als === "beheerder" || als === "test-analist" ? als : "analist";
    const token = { analist: TOKEN_ANALIST, beheerder: TOKEN_BEHEERDER, "test-analist": TOKEN_TEST_ANALIST }[rol];
    if (!token) {
        throw new Error(`${rol === "beheerder" ? "WETSANALYSE_ACC_TOKEN_BEHEERDER" : "WETSANALYSE_ACC_TOKEN_TEST_ANALIST"} is niet gezet.`);
    }
    let c = clients.get(rol);
    if (!c) {
        c = new AcceptatieClient(controleerUrl(URL_ACC), token);
        clients.set(rol, c);
    }
    return c;
}
const ikPerRol = new Map();
/** De userid achter een client, één keer opgevraagd. */
async function ik(c) {
    let wie = ikPerRol.get(c);
    if (!wie) {
        const me = await c.bff("GET", "/api/account/me");
        wie = me.status === 200 ? String(me.data?.userid ?? "") : "";
        if (wie)
            ikPerRol.set(c, wie);
    }
    return wie;
}
/** `bff` langs de vangrail: verwijderen alleen in de ruimte van een testrun (runruimte.ts). */
async function bffMetVangrail(c, methode, pad, body) {
    if (isVerwijderend(methode, pad)) {
        const oordeel = await toetsVerwijderen(c, methode, pad, await ik(c));
        if (!oordeel.mag)
            throw new Error(`Geweigerd door de vangrail: ${oordeel.reden}`);
    }
    return c.bff(methode, pad, body);
}
const bron = new BronClient();
let graaf;
function graafClient() {
    if (!GRAAF_URL || !GRAAF_TOKEN) {
        throw new Error("Zet WETSANALYSE_ACC_GRAAF_URL en WETSANALYSE_ACC_GRAAF_TOKEN; dat doet de gebruiker, niet een agent.");
    }
    graaf ??= new GraafClient(controleerUrl(GRAAF_URL), GRAAF_TOKEN);
    return graaf;
}
const seg = (s) => encodeURIComponent(String(s));
const S = z.object;
const Als = z.enum(["analist", "beheerder", "test-analist"]).optional();
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
        run: async (a) => {
            const me = await client(a.als).bff("GET", "/api/account/me");
            const userid = me.data?.userid;
            const account_verwacht = !ACCOUNT
                ? "niet ingesteld (WETSANALYSE_ACC_ACCOUNT)"
                : userid === ACCOUNT ? "ja" : `nee: het token hoort bij ${String(userid)}, niet bij ${ACCOUNT}`;
            return { ...me, account_verwacht };
        },
    },
    {
        name: "bff",
        description: "Eén aanroep op de BFF, zoals een scherm die doet: `pad` begint met /api/. Geeft status, body en " +
            "trace_id; elke status komt terug, dus ook een 403 die een test juist verwacht. Inloggen, tokens " +
            "maken en wachtwoord of 2FA wijzigen kan hier niet. Verwijderen gaat langs een vangrail: alleen een gesprek of " +
            "werkgebied van een testrun (naam begint met `lex-bench-keten · `, `acc-test-` of `Bench `, werkgebied door dit account gemaakt); " +
            "een bulkroute en alles wat gedeeld is, weigert hij. Ruim een run op met `opruimen`.",
        input: S({
            methode: z.enum(["GET", "POST", "PUT", "PATCH", "DELETE"]),
            pad: z.string(),
            body: z.unknown().optional(),
            als: Als,
        }),
        run: (a) => bffMetVangrail(client(a.als), a.methode, a.pad, a.body),
    },
    {
        name: "opruimen",
        description: "Ruim op wat een testrun maakte: werkgebieden met het `voorvoegsel` die dit account maakte, en elk eigen gesprek " +
            "met dat voorvoegsel of in zo'n werkgebied, met hun deelgesprekken. Het voorvoegsel begint met `lex-bench-keten · `, " +
            "`acc-test-` of `Bench ` (bijvoorbeeld `acc-test-2026-11-16-a`). Zonder `bevestig: true` geeft hij alleen de lijst; met " +
            "bevestiging wist hij eerst de gesprekken (deelgesprekken vóór hun ouder), dan de werkgebieden, elk langs de vangrail.",
        input: S({ voorvoegsel: z.string().min(4), bevestig: z.boolean().optional(), als: Als }),
        run: async (a) => {
            const c = client(a.als);
            const ruimte = await leesRuimte(c);
            const plan = opruimplan(a.voorvoegsel, ruimte.ik, ruimte.werkgebieden, ruimte.gesprekken);
            const lijst = {
                voorvoegsel: plan.voorvoegsel,
                werkgebieden: plan.werkgebieden.map((w) => ({ id: w.id, naam: w.naam })),
                gesprekken: plan.gesprekken.map((g) => ({ id: g.id, titel: g.titel })),
            };
            if (!a.bevestig)
                return { ...lijst, uitgevoerd: false, toelichting: "Alleen de lijst; geef bevestig: true om te wissen." };
            return { ...lijst, uitgevoerd: true, ...(await voerUit(c, plan, ruimte.ik)) };
        },
    },
    {
        name: "lex_start",
        description: "Start een beurt van Lex, zoals de werkplek: eerst de vraag als user-bericht in het gesprek " +
            "(POST /api/gesprekken/<id>/berichten), dan de run (POST /api/annotatie/run). Zo ziet wie meekijkt de vraag " +
            "of klik én het antwoord. Maak eerst een gesprek met `bff` POST /api/gesprekken. Een klik gaat als " +
            "`intake_actie` of `actie`, met dezelfde inhoud als de knop stuurt; `extra` draagt de overige velden van een " +
            "run (modus, bevestigd, bereik, deelvraag_id, onderwerp, context). `vraag_bewaren: false` start alleen de run. " +
            "Geeft het run_id (en in `vraag` hoe het bewaren ging); volg de beurt met lex_wacht.",
        input: S({
            vraag: z.string(),
            conversation_id: z.string(),
            werkgebied_id: z.string().optional(),
            intake_actie: z.unknown().optional(),
            actie: z.unknown().optional(),
            extra: z.record(z.string(), z.unknown()).optional(),
            vraag_bewaren: z.boolean().optional(),
            als: Als,
        }),
        run: (a) => lexStart(client(a.als), a),
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
        description: "Het werkgebied: dossier met deelvragen, dekking, en een overzicht van de geannoteerde elementen (tellingen per " +
            "bepaling, klasse en lifecycle) met de laatste auditregels. Met `bron_iri` de elementen van die bepaling in korte " +
            "vorm; beoordelen doe je met weergave_lezen. `volledig: true` geeft alles zoals de api het levert (groot: na een " +
            "annotatie honderdduizenden tekens).",
        input: S({ werkgebied_id: z.string(), bron_iri: z.string().optional(), volledig: z.boolean().optional(), als: Als }),
        run: async (a) => {
            const wg = `/api/werkgebieden/${seg(a.werkgebied_id)}`;
            const routes = { werkgebied: wg, dekking: `${wg}/deelvragen/dekking`, elementen: `${wg}/elementen`, audit: `${wg}/audit` };
            const uit = await samen(client(a.als), routes);
            if (a.volledig)
                return uit;
            const inv = uit.elementen;
            return {
                ...uit,
                elementen: inv && Array.isArray(inv.elementen) ? inventarisOverzicht(inv, a.bron_iri) : inv,
                audit: auditStaart(uit.audit),
            };
        },
    },
    {
        name: "weergave_lezen",
        description: "De annotatie van één bepaling (artikel, lid of onderdeel) als lijst: per element id, klasse, tekst, ankers, " +
            "lifecycle, herkomst en aandacht, plus de lagen met hun revisie en de relaties. Hiermee beoordeel je de annotatie " +
            "bepaling voor bepaling; annotatie_lezen geeft één element met alles erbij.",
        input: S({ bron_iri: z.string(), als: Als }),
        run: (a) => client(a.als).bff("GET", `/api/annotatie/v2/weergave?bron_iri=${encodeURIComponent(String(a.bron_iri))}&vorm=lijst`),
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
        description: "Eén begrip: kaart met definitie en status, gekoppelde passages en revisies. Zonder begrip_id alle begrippen " +
            "van het werkgebied, met de NL-SBB-conformiteit en de samenhang (koppelingen, relaties en voorstellen).",
        input: S({ werkgebied_id: z.string(), begrip_id: z.string().optional(), als: Als }),
        run: (a) => {
            const pad = `/api/werkgebieden/${seg(a.werkgebied_id)}/begrippen`;
            if (!a.begrip_id) {
                return samen(client(a.als), { begrippen: pad, conformiteit: `${pad}/conformiteit`, samenhang: `${pad}/samenhang` });
            }
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
    {
        name: "bron_lezen",
        description: "De officiële tekst van één artikel of lid uit de BWB-repository: de letterlijke XML, de tekst in dezelfde " +
            "volgorde, en de toestand met url. Hierop rust elke bevinding over brontekst, niet op een samenvatting. " +
            "Zonder peildatum de nieuwste toestand, dezelfde die de importer in de graaf zet.",
        input: S({
            bwb_id: z.string(),
            artikel: z.string(),
            lid: z.string().optional(),
            peildatum: z.string().optional(),
        }),
        run: (a) => bron.lees({
            bwb_id: a.bwb_id,
            artikel: a.artikel,
            lid: a.lid,
            peildatum: a.peildatum,
        }),
    },
    {
        name: "graaf_lezen",
        description: "Alleen-lezen SPARQL op de kennisgraaf van acceptatie, om te zien wat er echt staat: SELECT, ASK, CONSTRUCT of " +
            "DESCRIBE, zonder SERVICE. Zonder LIMIT komt er LIMIT 200 bij. Voor de beoordeling, niet om een stap van het " +
            "scenario te vervangen: wat een gebruiker aan Lex vraagt, vraag je aan Lex.",
        input: S({ query: z.string() }),
        run: (a) => graafClient().lees(a.query),
    },
    {
        name: "logboek_aanvullen",
        description: "Voeg één regel toe aan het gedeelde logboek van een run. Bestaande regels veranderen niet. Noteer beslissingen, " +
            "id's, overleg, bevindingen en omwegen, kort; geen tokens. Bij soort `onenigheid` is `argumenten` verplicht.",
        input: S({
            run: z.string(),
            rol: z.enum(ROLLEN),
            soort: z.enum(SOORTEN),
            stap: z.number().int().min(0).max(9).optional(),
            tekst: z.string().min(1).max(4000),
            ids: z.array(z.string()).max(50).optional(),
            argumenten: S({ jurist: z.string(), gegevensspecialist: z.string() }).optional(),
        }),
        run: (a) => aanvullen(LOGBOEK_MAP, a),
    },
    {
        name: "logboek_lezen",
        description: "Lees het logboek van een run. Geef de teruggekregen `vanaf` mee om alleen te lezen wat er sindsdien bij kwam.",
        input: S({ run: z.string(), vanaf: z.number().int().min(0).optional() }),
        run: (a) => lezen(LOGBOEK_MAP, a.run, a.vanaf),
    },
    {
        name: "bench_opdracht_lezen",
        description: "Lex Bench: lees je opdracht van de run uit je prompt. Is `klaar` false, lees dan verder met de teruggekregen `vanaf`.",
        input: S({ run: z.string(), vanaf: z.number().int().min(0).optional() }),
        run: (a) => opdrachtLezen(LOGBOEK_MAP, a.run, a.vanaf),
    },
    {
        name: "bench_inleveren",
        description: "Lex Bench: lever je formulier in als JSON-object. De controle zegt meteen of het klopt; herstel de fouten en lever " +
            "opnieuw in. Een geldig formulier ligt vast. Elke poging blijft bewaard.",
        input: S({ run: z.string(), formulier: z.record(z.string(), z.unknown()) }),
        run: (a) => inleveren(LOGBOEK_MAP, a.run, a.formulier, BENCH_CONTROLE),
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
