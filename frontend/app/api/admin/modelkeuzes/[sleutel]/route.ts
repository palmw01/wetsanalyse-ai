// Een modelprofiel kiezen voor een agentprofiel of een stap, of terug naar de standaard (`{ profiel: null }`). De api
// wil een beheerder mét 2FA: die gaat uit de sessie mee, zoals bij de connectors.
import { proxy, readBody } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ sleutel: string }> };

export async function PUT(req: Request, { params }: Params) {
  const door = await sessionUserId();
  if (!door) return geenSessie();
  const { sleutel } = await params;
  const body = await readBody(req);
  return proxy(`/v1/admin/modelkeuzes/${pathSegment(sleutel)}`, {
    method: "PUT",
    body,
    admin: true,
    headers: { "Content-Type": "application/json", "X-User-Id": door },
  });
}
