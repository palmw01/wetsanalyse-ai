// Health van de frontend, in twee standen.
//
// Zonder parameter: liveness/readiness (Azure-probes) en de Docker HEALTHCHECK. Altijd 200 – de frontend
// leeft zolang dit antwoordt. Hij kijkt wel of de api bereikbaar is (veld `api`), maar faalt daar niet op:
// anders herstart Azure een gezonde frontend omdat de api even weg is.
//
// Met `?keten=1`: de rooktest na een uitrol (.github/actions/wacht-op-revisie). Die toetst de keten
// frontend → api en frontend → graph-qa, met een ruimere time-out voor een koude start (beide kunnen op
// minReplicas 0 staan), en geeft 503 als een van de twee niet antwoordt. graph-qa zit alleen in deze stand:
// de probes vragen elke paar seconden om health, en daarmee zou graph-qa nooit meer naar nul schalen.

import { metTrace } from "@/lib/trace";
import { apiBaseUrl, graphQaBaseUrl } from "@/lib/config";

export const dynamic = "force-dynamic";

async function peil(url: string, timeoutMs: number): Promise<string> {
  try {
    const res = await fetch(url, {
      headers: metTrace(),
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    return res.ok ? "ok" : `status-${res.status}`;
  } catch {
    return "onbereikbaar";
  }
}

export async function GET(request: Request) {
  const keten = new URL(request.url).searchParams.has("keten");
  if (!keten) {
    const api = await peil(`${apiBaseUrl()}/health`, 3000);
    return Response.json({ status: "ok", api });
  }
  const [api, lex] = await Promise.all([
    peil(`${apiBaseUrl()}/health`, 10000),
    peil(`${graphQaBaseUrl()}/health`, 10000),
  ]);
  const heel = api === "ok" && lex === "ok";
  return Response.json(
    { status: "ok", api, lex, keten: heel ? "ok" : "onvolledig" },
    { status: heel ? 200 : 503 },
  );
}
