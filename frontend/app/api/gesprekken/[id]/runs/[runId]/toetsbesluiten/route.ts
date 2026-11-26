// De besluiten over een contenttoets (plan contenttoets, C7): api `GET /v1/gesprekken/{id}/runs/{run_id}/toetsbesluiten`.
// De api toetst dat het gesprek van deze gebruiker is.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string; runId: string }> };

export async function GET(_req: Request, { params }: Params) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id, runId } = await params;
  return proxy(`/v1/gesprekken/${pathSegment(id)}/runs/${pathSegment(runId)}/toetsbesluiten`, { headers: { "X-User-Id": userid } });
}
