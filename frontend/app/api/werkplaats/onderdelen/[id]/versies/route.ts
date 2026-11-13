// Een volgende versie van het eigen concept. De api weigert met 409 als er intussen een nieuwere versie is.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { isPuntSegment, pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id } = await params;
  if (isPuntSegment(id)) return Response.json({ detail: "Onbekend onderdeel." }, { status: 404 });
  return proxy(`/v1/werkplaats/onderdelen/${pathSegment(id)}/versies${new URL(req.url).search}`, {
    method: "POST",
    body: await req.text(),
    headers: { "X-User-Id": userid, "Content-Type": "application/json" },
  });
}
