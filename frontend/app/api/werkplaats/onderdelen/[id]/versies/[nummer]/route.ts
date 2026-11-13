// Eén versie van een concept, met de bestanden.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { isPuntSegment, pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

export async function GET(req: Request, { params }: { params: Promise<{ id: string; nummer: string }> }) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id, nummer } = await params;
  if (isPuntSegment(id) || !/^[1-9][0-9]{0,5}$/.test(nummer)) return Response.json({ detail: "Onbekende versie." }, { status: 404 });
  return proxy(`/v1/werkplaats/onderdelen/${pathSegment(id)}/versies/${nummer}${new URL(req.url).search}`,
    { headers: { "X-User-Id": userid } });
}
