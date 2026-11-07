// BFF-route: een lopende run stoppen (graph-qa /v1/runs/{id}/cancel).
//
// Stoppen is nu een expliciete handeling in plaats van een dichtvallende socket. Dat onderscheid is
// het punt: wegklikken laat de beurt doorlopen, alleen deze knop beëindigt hem. Het antwoord is 202
// en geen 204 – de agent-nodes zijn synchroon, dus een lopende LLM-call maakt zichzelf af en de run
// eindigt pas op de eerstvolgende grens. Dit is een verzoek, geen feit.

import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();

  const { id } = await params;
  return proxy(`/v1/runs/${pathSegment(id)}/cancel`, {
    agent: true,
    method: "POST",
    // Alleen je eigen beurt stoppen: graph-qa toetst deze header.
    headers: { "X-User-Id": userid },
    timeoutMs: 10_000,
  });
}
