/**
 * Alleen-lezen SPARQL op de kennisgraaf van acceptatie, via de MCP-proxy (`/mcp` met een bearer-token).
 *
 * Daarmee vergelijkt een agent wat er in de graaf staat met de officiële bron. GraphDB heeft op Azure
 * zelf geen beveiliging, dus de controle zit hier: een query is alleen een leesvorm, en de tekst is
 * vooraf ontdaan van literals, IRI's en commentaar, zodat "delete" in een wettekst geen weigering geeft.
 * Zo'n controle op tekst houdt een vergissing tegen; hij is geen slot.
 */
const REPOSITORY = "inning";
const VERZOEK_TIMEOUT_MS = 60_000;
const STANDAARD_LIMIT = 200;
const MAX_TEKENS = 40_000;
const NIET_GELEZEN = /"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|<[^<>\s]*>|#[^\n]*/g;
// SERVICE staat erbij omdat een federatieve query GraphDB iets anders laat bevragen, vanuit het interne netwerk.
const VERBODEN = /\b(INSERT|DELETE|LOAD|CLEAR|DROP|CREATE|ADD|MOVE|COPY|SERVICE)\b/i;
const VORM = /^\s*(?:(?:PREFIX\s+\S*:|BASE)\s*)*(SELECT|ASK|CONSTRUCT|DESCRIBE)\b/i;
const HEEFT_LIMIT = /(?:\bLIMIT\s+\d+(?:\s+OFFSET\s+\d+)?|\bOFFSET\s+\d+\s+LIMIT\s+\d+)\s*$/i;
/** Geef de query terug die wordt uitgevoerd, met een LIMIT als die ontbreekt; weiger al het andere. */
export function controleerSparql(query) {
    const kaal = query.replace(NIET_GELEZEN, " ");
    const vorm = VORM.exec(kaal)?.[1]?.toUpperCase();
    if (!vorm)
        throw new Error("Alleen SELECT, ASK, CONSTRUCT en DESCRIBE.");
    const zonderNamen = kaal.replace(/[?$]\w+/g, " ").replace(/[\w.-]*:[\w.%-]*/g, " ");
    const verboden = VERBODEN.exec(zonderNamen)?.[1];
    if (verboden)
        throw new Error(`Geweigerd: ${verboden.toUpperCase()} hoort niet bij alleen-lezen.`);
    return vorm === "ASK" || HEEFT_LIMIT.test(kaal) ? query : `${query}\nLIMIT ${STANDAARD_LIMIT}`;
}
/** Een antwoord is JSON of SSE, en GraphDB schrijft `data:` zonder spatie. */
export function leesRpc(tekst, contentType) {
    const regels = contentType.includes("text/event-stream")
        ? tekst.split(/\r?\n/).filter((r) => r.startsWith("data:")).map((r) => r.slice(5).trim())
        : [tekst];
    for (const regel of regels) {
        try {
            const bericht = JSON.parse(regel);
            if (bericht.error)
                throw new Error(`Graaf-MCP: ${JSON.stringify(bericht.error).slice(0, 300)}`);
            if (bericht.result)
                return bericht.result;
        }
        catch (e) {
            if (!(e instanceof SyntaxError))
                throw e;
        }
    }
    throw new Error(`Geen bruikbaar antwoord van de graaf: ${tekst.slice(0, 200)}`);
}
/** De SELECT-uitslag is TSV, verpakt als één JSON-string. */
function pelAf(tekst) {
    if (!tekst.startsWith('"'))
        return tekst;
    try {
        return JSON.parse(tekst);
    }
    catch {
        return tekst;
    }
}
export class GraafClient {
    basis;
    token;
    doeFetch;
    sessie;
    constructor(basis, token, doeFetch = fetch) {
        this.basis = basis;
        this.token = token;
        this.doeFetch = doeFetch;
    }
    async post(method, params) {
        return this.doeFetch(`${this.basis}/mcp`, {
            method: "POST",
            headers: {
                Authorization: `Bearer ${this.token}`,
                "Content-Type": "application/json",
                Accept: "application/json, text/event-stream",
                ...(this.sessie ? { "Mcp-Session-Id": this.sessie } : {}),
            },
            body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
            signal: AbortSignal.timeout(VERZOEK_TIMEOUT_MS),
        });
    }
    async handdruk() {
        this.sessie = undefined;
        const res = await this.post("initialize", {
            protocolVersion: "2024-11-05",
            capabilities: {},
            clientInfo: { name: "wetsanalyse-acceptatie", version: "0.1.0" },
        });
        if (!res.ok)
            throw new Error(`De graaf gaf ${res.status} op de handdruk.`);
        this.sessie = res.headers.get("Mcp-Session-Id") ?? undefined;
        await res.text();
    }
    /** GraphDB weigert elke aanroep zonder sessie, en verliest zijn sessies bij een herstart. */
    async lees(query) {
        const uitvoeren = controleerSparql(query);
        if (!this.sessie)
            await this.handdruk();
        const params = { name: "sparql_query", arguments: { query: uitvoeren, repositoryId: REPOSITORY } };
        let res = await this.post("tools/call", params);
        if (res.status === 404) {
            await this.handdruk();
            res = await this.post("tools/call", params);
        }
        const tekst = await res.text();
        if (!res.ok)
            throw new Error(`De graaf gaf ${res.status}: ${tekst.slice(0, 300)}`);
        const resultaat = leesRpc(tekst, res.headers.get("content-type") ?? "");
        const inhoud = (resultaat.content ?? []).map((c) => c.text ?? "").join("");
        if (resultaat.isError)
            throw new Error(`De graaf weigerde de query: ${inhoud.slice(0, 300)}`);
        const uitslag = pelAf(inhoud);
        return { query: uitvoeren, uitslag: uitslag.slice(0, MAX_TEKENS), afgekapt: uitslag.length > MAX_TEKENS };
    }
}
