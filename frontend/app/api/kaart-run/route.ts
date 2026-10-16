// BFF-route: Lex naast de kaart (spoor D, fase E) – één actie van Lex op één begrip.
//
// Dezelfde vorm als `app/api/begrippen-run` (`_lib/werkgebiedRun.ts`), met een begrip en een actie
// erbij: de api legt de invoer vast en maakt de run (of geeft een lopende of open run terug), graph-qa
// rekent en zet de voorstellen terug bij de api. Meekijken en stoppen gaan via de gewone run-routes.
// Een statische route, om dezelfde reden als `begrippen-run` (`app/routes.test.ts`).

import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { graphQaAuthHeader, graphQaBaseUrl } from "@/lib/config";
import { logger } from "@/lib/logger";
import { metTrace } from "@/lib/trace";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

const START_TIMEOUT_MS = 45_000;
/** De invoer vastleggen bouwt het manifest van het werkgebied, met de bronboom uit de graaf. */
const INVOER_TIMEOUT_MS = 90_000;
const ID = /^[A-Za-z0-9-]{1,64}$/;
const ACTIES = new Set(["brondefinitie", "scherper", "betekenisverschil", "voorbeelden"]);

export async function POST(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  let body: { werkgebied_id?: unknown; begrip_id?: unknown; actie?: unknown; ander_begrip_id?: unknown } = {};
  try {
    body = (await req.json()) as typeof body;
  } catch {
    /* hieronder afgevangen */
  }
  const tekst = (v: unknown) => (typeof v === "string" ? v : "");
  const [werkgebied, begrip, actie, ander] = [tekst(body.werkgebied_id), tekst(body.begrip_id), tekst(body.actie),
    tekst(body.ander_begrip_id)];
  if (!ID.test(werkgebied) || !ID.test(begrip) || !ACTIES.has(actie) || (ander && !ID.test(ander)))
    return Response.json({ detail: "Geef een werkgebied, een begrip en een actie." }, { status: 422 });

  // 1. De api: invoer vastleggen en de run maken, of de lopende teruggeven. Een fout (404, 409 met een
  //    melding, 422) gaat ongewijzigd door.
  const api = await proxy(`/v1/werkgebieden/${pathSegment(werkgebied)}/begrippen/${pathSegment(begrip)}/kaart-runs`, {
    method: "POST",
    headers: { "X-User-Id": userid, "Content-Type": "application/json" },
    body: JSON.stringify({ actie, ...(ander ? { ander_begrip_id: ander } : {}) }),
    timeoutMs: INVOER_TIMEOUT_MS,
  });
  if (!api.ok) return api;
  const run = (await api.json()) as { id: string; status: string };
  // Klaar met open voorstellen: niets te rekenen. De werkplek toont die voorstellen.
  if (run.status === "klaar") return Response.json({ run, agent_run_id: null });

  // 2. graph-qa: rekenen. Een 409 betekent dat er op dit begrip al een actie loopt; daarop haakt de
  //    werkplek aan.
  try {
    const upstream = await fetch(`${graphQaBaseUrl()}/v1/kaart-runs`, {
      method: "POST",
      headers: metTrace({ ...graphQaAuthHeader(), "X-User-Id": userid, "Content-Type": "application/json" }),
      body: JSON.stringify({ werkgebied_id: werkgebied, begrip_id: begrip, run_id: run.id }),
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
    logger.warn("Kaartrun: agent onbereikbaar", { fout: (err as Error).message });
    return Response.json({ detail: `Lex is onbereikbaar (${(err as Error).message})` }, { status: 502 });
  }
}

/** `?begrip=<id>` → de lopende actie op dit begrip om op aan te haken, of `null`. */
export async function GET(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const begrip = new URL(req.url).searchParams.get("begrip") ?? "";
  if (!ID.test(begrip)) return Response.json(null);
  try {
    const upstream = await fetch(
      `${graphQaBaseUrl()}/v1/conversations/${encodeURIComponent(`begrip:${begrip}:kaart`)}/run`,
      { headers: metTrace({ ...graphQaAuthHeader(), "X-User-Id": userid }), cache: "no-store",
        signal: AbortSignal.timeout(10_000) },
    );
    const text = await upstream.text();
    return new Response(text || null, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch (err) {
    logger.warn("Kaartrun: lopende run niet op te halen", { fout: (err as Error).message });
    return Response.json({ detail: "Lopende run niet op te halen." }, { status: 502 });
  }
}
