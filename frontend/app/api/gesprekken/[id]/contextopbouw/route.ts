import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

/** De boom van de contextweergave: de contextopbouw van de deelgesprekken van één gesprek (api
 *  `GET /v1/gesprekken/{id}/contextopbouw`). Alleen lezen; de api toetst dat het gesprek van deze gebruiker is. De
 *  query gaat ongewijzigd mee, en `proxy()` zet de trace-header (`metTrace`). */
export async function GET(req: Request, { params }: Params) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id } = await params;
  return proxy(`/v1/gesprekken/${pathSegment(id)}/contextopbouw${new URL(req.url).search}`, { headers: { "X-User-Id": userid } });
}
