// Het besluit over één bevinding van een contenttoets (plan contenttoets, C7): eens of oneens met Lex, en het voorstel
// overgenomen, aangepast of afgewezen. Een lege body wist het besluit.
import { proxy, readBody } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string; runId: string; nr: string }> };

export async function PUT(req: Request, { params }: Params) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id, runId, nr } = await params;
  return proxy(`/v1/gesprekken/${pathSegment(id)}/runs/${pathSegment(runId)}/toetsbesluiten/${pathSegment(nr)}`, {
    method: "PUT",
    body: await readBody(req),
    headers: { "Content-Type": "application/json", "X-User-Id": userid },
  });
}
