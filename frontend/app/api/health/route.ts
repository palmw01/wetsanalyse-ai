// Health van de frontend, in twee standen.
//
// Zonder parameter: liveness/readiness (Azure-probes) en de Docker HEALTHCHECK. Altijd 200 – de frontend
// leeft zolang dit antwoordt. Hij kijkt wel of de api bereikbaar is (veld `api`), maar faalt daar niet op:
// anders herstart Azure een gezonde frontend omdat de api even weg is.
//
// Met `?keten=1`: de rooktest na een uitrol (.github/actions/wacht-op-revisie). Die toetst de keten
// frontend → api (met zijn database) en frontend → graph-qa (met een graaf die regelingen heeft), met een ruimere time-out voor een koude start (beide kunnen op
// minReplicas 0 staan), en geeft 503 als een van de twee niet antwoordt. graph-qa zit alleen in deze stand:
// de probes vragen elke paar seconden om health, en daarmee zou graph-qa nooit meer naar nul schalen.

import { metTrace } from "@/lib/trace";
import { apiBaseUrl, graphQaBaseUrl } from "@/lib/config";

export const dynamic = "force-dynamic";

async function peil(url: string, timeoutMs: number): Promise<string> {
  return (await peilMet(url, timeoutMs)).stand;
}

/** De stand én het antwoord: in de keten-stand meldt de api `database` en graph-qa `graaf` (een 503 als het niet werkt).
 *  Een oudere backend kent `?keten` niet en geeft 200 zonder dat veld; dan telt alleen dat hij antwoordt (N-1). */
async function peilMet(url: string, timeoutMs: number): Promise<{ stand: string; body: Record<string, unknown> }> {
  try {
    const res = await fetch(url, {
      headers: metTrace(),
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    return { stand: res.ok ? "ok" : `status-${res.status}`, body: body && typeof body === "object" ? body : {} };
  } catch {
    return { stand: "onbereikbaar", body: {} };
  }
}

export async function GET(request: Request) {
  const keten = new URL(request.url).searchParams.has("keten");
  if (!keten) {
    const api = await peil(`${apiBaseUrl()}/health`, 3000);
    return Response.json({ status: "ok", api });
  }
  // Diep: de api zegt of zijn database antwoordt, graph-qa of de graaf regelingen heeft. Een straat met een lege graaf
  // komt zo niet meer groen door de uitrol (plan Lex Bench §20.5 stap 5).
  const [api, lex] = await Promise.all([
    peilMet(`${apiBaseUrl()}/health?keten=1`, 10000),
    peilMet(`${graphQaBaseUrl()}/health?keten=1`, 10000),
  ]);
  const heel = api.stand === "ok" && lex.stand === "ok";
  return Response.json(
    {
      status: "ok", api: api.stand, lex: lex.stand, keten: heel ? "ok" : "onvolledig",
      database: typeof api.body.database === "string" ? api.body.database : "onbekend",
      graaf: typeof lex.body.graaf === "string" ? lex.body.graaf : "onbekend",
    },
    { status: heel ? 200 : 503 },
  );
}
