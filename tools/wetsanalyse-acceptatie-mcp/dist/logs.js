/**
 * Logs en traces van acceptatie, via de Azure Monitor-datasource van Grafana.
 *
 * Waarom via Grafana: die draagt de SP-credentials al als datasource-auth, dus hier hoeft alleen het
 * Grafana-wachtwoord te staan en geen secret met rechten op beide straten. Een service-account-token kan
 * niet: Grafana heeft geen persistente opslag, dus zo'n token overleeft een herstart niet.
 *
 * Alleen vaste KQL-sjablonen en alleen de datasource van acceptatie. Een vrije query zou deze tool een
 * algemene toegang tot de workspace maken.
 */
const DATASOURCE = "azmon-acceptatie";
export function bouwQuery({ trace_id, run_id }) {
    if (trace_id) {
        if (!/^[0-9a-f]{32}$/.test(trace_id))
            throw new Error("trace_id moet 32 hex-tekens zijn.");
        return ("union AppRequests, AppDependencies, AppTraces, AppExceptions\n" +
            `| where OperationId == '${trace_id}'\n` +
            "| project TimeGenerated, Type, AppRoleName, Name, ResultCode, DurationMs, Message\n" +
            "| order by TimeGenerated asc\n| take 200");
    }
    if (run_id) {
        if (!/^[A-Za-z0-9-]{1,64}$/.test(run_id))
            throw new Error("Ongeldig run_id.");
        return (`ContainerAppConsoleLogs_CL\n| where Log_s has '${run_id}'\n` +
            "| project TimeGenerated, ContainerAppName_s, Log_s\n| order by TimeGenerated asc\n| take 200");
    }
    return ("ContainerAppConsoleLogs_CL\n| extend j = parse_json(Log_s)\n" +
        "| where tolower(tostring(j.level)) in ('error', 'warning', 'warn') or tolower(tostring(j.niveau)) in ('error', 'warn')\n" +
        "| project TimeGenerated, ContainerAppName_s, Log_s\n| order by TimeGenerated desc\n| take 200");
}
/** Zet de kolommen van een Grafana-frame om in rijen. */
export function rijen(frames) {
    return frames.flatMap((f) => {
        const namen = (f.schema?.fields ?? []).map((v) => v.name);
        const kolommen = f.data?.values ?? [];
        return (kolommen[0] ?? []).map((_, i) => Object.fromEntries(namen.map((n, k) => [n, kolommen[k]?.[i]])));
    });
}
export async function zoekLogs(basis, wachtwoord, vraag, doeFetch = fetch) {
    const query = bouwQuery(vraag);
    const headers = {
        Authorization: `Basic ${Buffer.from(`admin:${wachtwoord}`).toString("base64")}`,
        "Content-Type": "application/json",
    };
    const ds = await doeFetch(`${basis}/api/datasources/uid/${DATASOURCE}`, { headers });
    if (!ds.ok)
        throw new Error(`Grafana gaf ${ds.status} op de datasource.`);
    const { jsonData } = (await ds.json());
    const nu = Date.now();
    const res = await doeFetch(`${basis}/api/ds/query`, {
        method: "POST",
        headers,
        body: JSON.stringify({
            from: String(nu - vraag.minuten * 60_000),
            to: String(nu),
            queries: [
                {
                    refId: "A",
                    datasource: { uid: DATASOURCE },
                    queryType: "Azure Log Analytics",
                    azureLogAnalytics: {
                        query,
                        resultFormat: "table",
                        resources: [jsonData.logAnalyticsDefaultWorkspace],
                    },
                },
            ],
        }),
    });
    if (!res.ok)
        throw new Error(`Grafana gaf ${res.status} op de query: ${(await res.text()).slice(0, 300)}`);
    const body = (await res.json());
    if (body.results.A.error)
        throw new Error(body.results.A.error);
    return { query, rijen: rijen(body.results.A.frames ?? []) };
}
