/**
 * De officiële brontekst, langs de weg van de importer (`tools/bwb-import/app/downloader.py`): de
 * SRU-zoekdienst noemt de toestanden, de repository levert de toestand-XML.
 *
 * Een bevinding over brontekst hoort hierop te rusten en niet op een samenvatting van een webpagina:
 * zo'n samenvatting ziet de structuur niet, en daar ging een eerdere bevinding op mis.
 *
 * Dit is bewust één eerlijke aanroep: een eigen User-Agent, geen tweede poging en geen redirect. Krijgen
 * we iets anders dan XML, dan is dat een uitkomst om te melden, geen hindernis om omheen te werken.
 */
const SRU = "https://zoekservice.overheid.nl/sru/Search";
const REPOSITORY = "https://repository.officiele-overheidspublicaties.nl/";
const USER_AGENT = "wetsanalyse-acceptatie-mcp/0.1";
const VERZOEK_TIMEOUT_MS = 60_000;
/** Eén artikel past hier ruim in; de hele wet hoort niet in de context van een agent. */
const MAX_TEKENS = 40_000;
const MAX_IN_CACHE = 8;
const veld = (xml, naam) => new RegExp(`<(?:\\w+:)?${naam}>([^<]*)<`).exec(xml)?.[1]?.trim() ?? "";
/** Haal de toestanden uit een SRU-antwoord, oudste eerst, zoals `discover_toestanden`. */
export function toestandenUitSru(xml) {
    return xml
        .split(/<gzd[\s>]/)
        .slice(1)
        .map((r) => ({
        locatie: veld(r, "locatie_toestand"),
        titel: veld(r, "title"),
        geldig_vanaf: veld(r, "geldigheidsperiode_startdatum"),
        geldig_tot: veld(r, "geldigheidsperiode_einddatum"),
    }))
        .filter((t) => t.locatie)
        .sort((a, b) => a.geldig_vanaf.localeCompare(b.geldig_vanaf) || a.locatie.localeCompare(b.locatie));
}
export function kiesToestand(toestanden, peildatum) {
    const passend = peildatum
        ? toestanden.filter((t) => t.geldig_vanaf <= peildatum && (!t.geldig_tot || peildatum <= t.geldig_tot))
        : toestanden;
    const gekozen = passend.at(-1);
    if (!gekozen)
        throw new Error(`Geen toestand geldig op ${peildatum}.`);
    return gekozen;
}
/** Het einde van het element dat op `begin` opent. Diepte telt mee: `lid` en `lidnr` zijn verschillend. */
function eindeVan(xml, begin, naam) {
    const tag = new RegExp(`<(/?)${naam}(?=[\\s/>])[^>]*?(/?)>`, "g");
    tag.lastIndex = begin;
    let diepte = 0;
    for (let m = tag.exec(xml); m; m = tag.exec(xml)) {
        if (m[1])
            diepte -= 1;
        else if (!m[2])
            diepte += 1;
        if (diepte === 0)
            return tag.lastIndex;
    }
    throw new Error(`Element ${naam} sluit niet: geen geldige toestand-XML.`);
}
/** De elementen `naam` op het hoogste niveau: een artikel dat in een ander artikel is geciteerd telt niet mee. */
function elementen(xml, naam) {
    const open = new RegExp(`<${naam}(?=[\\s/>])`, "g");
    const uit = [];
    for (let m = open.exec(xml); m; m = open.exec(xml)) {
        const einde = eindeVan(xml, m.index, naam);
        uit.push(xml.slice(m.index, einde));
        open.lastIndex = einde;
    }
    return uit;
}
const nummer = (s) => s.replace(/<[^>]*>/g, "").trim().toLowerCase().replace(/^(artikel|lid)\s+/, "").replace(/\.$/, "");
const eerste = (xml, naam) => nummer(new RegExp(`<${naam}(?:\\s[^>]*)?>([\\s\\S]*?)</${naam}>`).exec(xml)?.[1] ?? "");
/** De leesbare tekst van een fragment, in de volgorde van de XML. Het bewijs blijft de `xml` ernaast. */
export function tekstVan(xml) {
    return xml
        .replace(/<meta-data[\s\S]*?<\/meta-data>/g, "")
        .replace(/\s+/g, " ")
        .replace(/<\/(?:label|lidnr|li\.nr)>/g, " ")
        .replace(/<\/(?:al|kop|lid|li|lijst|tussenkop)>/g, "\n")
        .replace(/<[^>]*>/g, "")
        .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
        .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&quot;/g, '"')
        .replace(/&apos;/g, "'")
        .replace(/&amp;/g, "&")
        .split("\n")
        .map((r) => r.replace(/ +/g, " ").trim())
        .filter(Boolean)
        .join("\n");
}
function treffer(xml, lid) {
    const plaats = /bwb-ng-variabel-deel="([^"]*)"/.exec(xml)?.[1] ?? "";
    return {
        plaats,
        ...(lid ? { lid } : {}),
        tekst: tekstVan(xml).slice(0, MAX_TEKENS),
        xml: xml.slice(0, MAX_TEKENS),
        afgekapt: xml.length > MAX_TEKENS,
    };
}
/** Zoek één artikel (en eventueel één lid) in een toestand. Een nummer kan vaker voorkomen, bijvoorbeeld in een bijlage. */
export function zoekArtikel(toestand, artikel, lid) {
    const gevraagd = nummer(artikel);
    const artikelen = elementen(toestand, "artikel").filter((a) => eerste(a, "nr") === gevraagd);
    if (artikelen.length === 0)
        throw new Error(`Artikel ${artikel} staat niet in deze toestand.`);
    if (!lid)
        return artikelen.map((a) => treffer(a));
    const uit = artikelen.flatMap((a) => elementen(a, "lid")
        .filter((l) => eerste(l, "lidnr") === nummer(lid))
        .map((l) => treffer(l, lid)));
    if (uit.length === 0)
        throw new Error(`Artikel ${artikel} heeft geen lid ${lid} in deze toestand.`);
    return uit;
}
export class BronClient {
    doeFetch;
    cache = new Map();
    constructor(doeFetch = fetch) {
        this.doeFetch = doeFetch;
    }
    async haal(url, herken) {
        const bewaard = this.cache.get(url);
        if (bewaard)
            return bewaard;
        const res = await this.doeFetch(url, {
            redirect: "error",
            headers: { "User-Agent": USER_AGENT, Accept: "application/xml" },
            signal: AbortSignal.timeout(VERZOEK_TIMEOUT_MS),
        });
        // De status zegt hier niets: de SRU-dienst geeft 406 bij een geldig antwoord. De inhoud beslist.
        const tekst = await res.text();
        if (!tekst.includes(herken)) {
            throw new Error(`Geen ${herken} ontvangen (HTTP ${res.status}, ${res.headers.get("content-type") ?? "geen type"}). ` +
                "Probeer het niet langs een andere weg of met een andere identificatie: noteer dit als bevinding.");
        }
        if (this.cache.size >= MAX_IN_CACHE)
            this.cache.delete(this.cache.keys().next().value);
        this.cache.set(url, tekst);
        return tekst;
    }
    async lees(vraag) {
        if (!/^BWB[RV]\d{7}$/.test(vraag.bwb_id))
            throw new Error("bwb_id heeft de vorm BWBR0004770.");
        if (vraag.peildatum && !/^\d{4}-\d{2}-\d{2}$/.test(vraag.peildatum))
            throw new Error("peildatum heeft de vorm JJJJ-MM-DD.");
        const zoek = new URLSearchParams({
            operation: "searchRetrieve",
            version: "2.0",
            "x-connection": "BWB",
            maximumRecords: "1000",
            query: `dcterms.identifier=${vraag.bwb_id}`,
        });
        const toestanden = toestandenUitSru(await this.haal(`${SRU}?${zoek}`, "searchRetrieveResponse"));
        if (toestanden.length === 0)
            throw new Error(`Geen toestanden gevonden voor ${vraag.bwb_id}.`);
        const toestand = kiesToestand(toestanden, vraag.peildatum);
        if (!toestand.locatie.startsWith(REPOSITORY))
            throw new Error(`Onverwachte bronlocatie: ${toestand.locatie}`);
        const xml = await this.haal(toestand.locatie, "<toestand");
        return {
            bwb_id: vraag.bwb_id,
            titel: toestand.titel,
            toestand: { geldig_vanaf: toestand.geldig_vanaf, geldig_tot: toestand.geldig_tot, url: toestand.locatie },
            aantal_toestanden: toestanden.length,
            treffers: zoekArtikel(xml, vraag.artikel, vraag.lid),
        };
    }
}
