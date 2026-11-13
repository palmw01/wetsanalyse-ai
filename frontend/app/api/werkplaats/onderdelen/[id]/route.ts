// Eén concept met zijn versies (zonder de bestanden). Andermans concept dat niet gedeeld is, geeft bij de api 404.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { isPuntSegment, pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id } = await params;
  if (isPuntSegment(id)) return Response.json({ detail: "Onbekend onderdeel." }, { status: 404 });
  return proxy(`/v1/werkplaats/onderdelen/${pathSegment(id)}${new URL(req.url).search}`, { headers: { "X-User-Id": userid } });
}
