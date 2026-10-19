// Een run van Lex op een werkgebied: begrippen voorstellen (levering 3a) of bronnen zoeken (fase A).
//
// Twee diensten, één handeling. De api legt de invoer vast en maakt de run (of geeft de bestaande op
// dezelfde stand terug); graph-qa rekent erop en zet de uitkomst terug bij de api. Meekijken en stoppen
// gaan daarna via de gewone run-routes (`/api/annotatie/run/{id}/events|cancel`): dat is een graph-qa-run
// als elke andere. Beide routes (`app/api/begrippen-run`, `app/api/bronnen-run`) zijn hier één vorm.

import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { graphQaAuthHeader, graphQaBaseUrl } from "@/lib/config";
import { logger } from "@/lib/logger";
import { metTrace } from "@/lib/trace";
import { pathSegment } from "@/lib/url";

/** Zelfde grens als het starten van een beurt: graph-qa kan koud starten (`minReplicas: 0`). */
const START_TIMEOUT_MS = 45_000;
/** De invoer vastleggen kan per regeling de bronboom uit de graaf vragen, net als de inventaris. */
const INVOER_TIMEOUT_MS = 90_000;
const ID = /^[A-Za-z0-9-]{1,64}$/;

export interface RunSoort {
  /** Het pad onder `/v1/werkgebieden/{id}/` bij de api, en onder `/v1/` bij graph-qa. Deelvragen hebben
   *  geen run bij de api (`app/api/deelvragen-run` start zelf); daar telt alleen de sleutel. */
  pad: "begrippen-runs" | "bronnen-runs" | "deelvragen-runs";
  /** De runstore-sleutel bij graph-qa, om na herladen aan te haken. */
  sleutel: (werkgebied: string) => string;
  naam: string;
}

export async function startWerkgebiedRun(req: Request, soort: RunSoort): Promise<Response> {
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

  // 1. De api: invoer vastleggen en de run maken, of de bestaande op dezelfde stand teruggeven. Een fout
  //    (404 werkgebied, 409 met een melding) gaat ongewijzigd door.
  const api = await proxy(`/v1/werkgebieden/${pathSegment(werkgebied)}/${soort.pad}`, {
    method: "POST",
    headers: { "X-User-Id": userid, "Content-Type": "application/json" },
    body: "{}",
    timeoutMs: INVOER_TIMEOUT_MS,
  });
  if (!api.ok) return api;
  const run = (await api.json()) as { id: string; status: string };
  // Al klaar op deze stand: niets te rekenen. De werkplek zegt dat, in plaats van te doen alsof.
  if (run.status === "klaar") return Response.json({ run, agent_run_id: null });

  // 2. graph-qa: rekenen. Een 409 betekent dat er voor dit werkgebied al een loopt; dan haakt de
  //    werkplek daarop aan.
  try {
    const upstream = await fetch(`${graphQaBaseUrl()}/v1/${soort.pad}`, {
      method: "POST",
      headers: metTrace({ ...graphQaAuthHeader(), "X-User-Id": userid, "Content-Type": "application/json" }),
      body: JSON.stringify({ werkgebied_id: werkgebied, run_id: run.id }),
      cache: "no-store",
      signal: AbortSignal.timeout(START_TIMEOUT_MS),
    });
    const data = (await upstream.json().catch(() => ({}))) as {
      run_id?: string;
      detail?: { reden?: string; run_id?: string } | string;
    };
    if (upstream.status === 409 && typeof data.detail === "object" && data.detail?.run_id)
      return Response.json({ run, agent_run_id: data.detail.run_id });
    if (!upstream.ok)
      return Response.json({ detail: typeof data.detail === "string" ? data.detail : "Lex kon niet beginnen." },
        { status: upstream.status });
    return Response.json({ run, agent_run_id: data.run_id ?? null }, { status: 201 });
  } catch (err) {
    logger.warn(`${soort.naam}: agent onbereikbaar`, { fout: (err as Error).message });
    return Response.json({ detail: `Lex is onbereikbaar (${(err as Error).message})` }, { status: 502 });
  }
}

/** `?werkgebied=<id>` → de lopende run om op aan te haken, of `null`. Een fout is géén `null` (zie
 *  `app/api/annotatie/run/route.ts`): dan weten we het niet. */
export async function lopendeWerkgebiedRun(req: Request, soort: RunSoort): Promise<Response> {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const werkgebied = new URL(req.url).searchParams.get("werkgebied") ?? "";
  if (!ID.test(werkgebied)) return Response.json(null);
  try {
    const upstream = await fetch(
      `${graphQaBaseUrl()}/v1/conversations/${encodeURIComponent(soort.sleutel(werkgebied))}/run`,
      { headers: metTrace({ ...graphQaAuthHeader(), "X-User-Id": userid }), cache: "no-store",
        signal: AbortSignal.timeout(10_000) },
    );
    const text = await upstream.text();
    return new Response(text || null, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch (err) {
    logger.warn(`${soort.naam}: lopende run niet op te halen`, { fout: (err as Error).message });
    return Response.json({ detail: "Lopende run niet op te halen." }, { status: 502 });
  }
}
