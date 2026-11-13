// Het eigen concept intrekken. De versies blijven te lezen; de naam is daarna weer vrij.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { isPuntSegment, pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id } = await params;
  if (isPuntSegment(id)) return Response.json({ detail: "Onbekend onderdeel." }, { status: 404 });
  return proxy(`/v1/werkplaats/onderdelen/${pathSegment(id)}/intrekken${new URL(req.url).search}`, {
    method: "POST",
    headers: { "X-User-Id": userid },
  });
}
