// BFF-route: Lex deelvragen laten voorstellen bij een werkgebied (optioneel; open keuze 4).
//
// Anders dan `bronnen-run` en `begrippen-run` maakt de api hier geen run: graph-qa legt de analysevraag
// uiteen (één modelaanroep) en zet de vragen zelf als voorstel bij de api (`…/deelvragen/voorstellen`).
// Meekijken en stoppen gaan via de gewone run-routes; de runstore-sleutel is
// `werkgebied:<id>:deelvragen`. Een statische route, om dezelfde reden als `begrippen-run`.

import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { lopendeWerkgebiedRun, type RunSoort } from "@/app/api/_lib/werkgebiedRun";
import { graphQaAuthHeader, graphQaBaseUrl } from "@/lib/config";
import { logger } from "@/lib/logger";
import { metTrace } from "@/lib/trace";

export const dynamic = "force-dynamic";

const START_TIMEOUT_MS = 45_000;
const ID = /^[A-Za-z0-9-]{1,64}$/;
const SOORT: RunSoort = { pad: "deelvragen-runs", sleutel: (w) => `werkgebied:${w}:deelvragen`, naam: "Deelvragenrun" };

export async function POST(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  let werkgebied = "";
  try {
    const body = (await req.json()) as { werkgebied_id?: unknown };
    werkgebied = typeof body.werkgebied_id === "string" ? body.werkgebied_id : "";
  } catch {
    /* hieronder afgevangen */
  }
  if (!ID.test(werkgebied)) return Response.json({ detail: "Geef een werkgebied." }, { status: 422 });
  try {
    const upstream = await fetch(`${graphQaBaseUrl()}/v1/deelvragen-runs`, {
      method: "POST",
      headers: metTrace({ ...graphQaAuthHeader(), "X-User-Id": userid, "Content-Type": "application/json" }),
      body: JSON.stringify({ werkgebied_id: werkgebied }),
      cache: "no-store",
      signal: AbortSignal.timeout(START_TIMEOUT_MS),
    });
    const data = (await upstream.json().catch(() => ({}))) as Record<string, unknown> & {
      detail?: { reden?: string; run_id?: string } | string;
    };
    // Er loopt er al een voor dit werkgebied: daarop aanhaken.
    if (upstream.status === 409 && typeof data.detail === "object" && data.detail?.run_id)
      return Response.json({ run_id: data.detail.run_id, conversation_id: SOORT.sleutel(werkgebied), status: "loopt" });
    // Een 429 (budget op) draagt een melding: ongewijzigd door, zoals de proxy doet.
    return Response.json(data, { status: upstream.status });
  } catch (err) {
    logger.warn("Deelvragenrun: agent onbereikbaar", { fout: (err as Error).message });
    return Response.json({ detail: `Lex is onbereikbaar (${(err as Error).message})` }, { status: 502 });
  }
}

export async function GET(req: Request) {
  return lopendeWerkgebiedRun(req, SOORT);
}
