// BFF-route: meekijken met een lopende run (SSE-passthrough naar graph-qa /v1/runs/{id}/events).
//
// Twee dingen zijn hier anders dan bij de oude agent-route, en beide zijn wezenlijk:
//
//  1. **Geen bovengrens op de duur.** De oude route kapte na 5 minuten af (`AbortSignal.timeout`),
//     wat een kijker afsneed terwijl de run gewoon doorliep. Een kijker mag zo lang blijven kijken
//     als de run duurt.
//  2. **De disconnect blijft lokaal.** `req.signal` gaat niet naar boven: wie wegklikt, koppelt
//     alleen zichzelf los. De run merkt er niets van – dat is de hele omkering.

import { graphQaAuthHeader, graphQaBaseUrl } from "@/lib/config";
import { metTrace } from "@/lib/trace";
import { logger } from "@/lib/logger";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

/** Hoe lang het opzetten van de stroom (tot de headers) mag duren. */
const OPZET_TIMEOUT_MS = 15_000;

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();

  const { id } = await params;
  const vanaf = new URL(req.url).searchParams.get("vanaf") ?? "0";
  const url = `${graphQaBaseUrl()}/v1/runs/${pathSegment(id)}/events?vanaf=${encodeURIComponent(vanaf)}`;

  // Wél een grens op het OPZETTEN van de stroom: een graph-qa die de verbinding aanneemt maar geen
  // headers stuurt, hield deze request anders onbeperkt vast. Zodra de headers er zijn gaat de timer
  // uit – de stroom zelf mag zo lang duren als de run (zie punt 1 hierboven).
  const opzet = new AbortController();
  const opzetTimer = setTimeout(() => opzet.abort(new DOMException("timeout", "TimeoutError")), OPZET_TIMEOUT_MS);
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      // De identiteit gaat mee: graph-qa geeft 404 op andermans run. Zonder deze header zou het
      // run-id zelf de enige beveiliging zijn – een capability in plaats van autorisatie.
      headers: metTrace({ ...graphQaAuthHeader(), "X-User-Id": userid, Accept: "text/event-stream" }),
      cache: "no-store",
      signal: opzet.signal,
    });
  } catch (err) {
    const verlopen = opzet.signal.aborted;
    logger.warn(verlopen ? "Run-events-proxy: geen antwoord op tijd" : "Run-events-proxy: onbereikbaar", {
      fout: (err as Error).message,
    });
    return Response.json(
      { detail: verlopen ? "De agent antwoordde niet op tijd." : `Agent onbereikbaar (${(err as Error).message})` },
      { status: verlopen ? 504 : 502 },
    );
  } finally {
    clearTimeout(opzetTimer);
  }

  // Fouten vóór de stream als JSON, niet als SSE-frame: de client zit dan nog in `if (!res.ok)` en
  // komt aan de frames niet toe. Zelfde afspraak als de agent-route hiernaast.
  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text().catch(() => "");
    const headers = new Headers();
    const ct = upstream.headers.get("content-type");
    if (ct) headers.set("Content-Type", ct);
    return new Response(text || null, { status: upstream.status, headers });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
