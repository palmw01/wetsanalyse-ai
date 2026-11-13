// De versie van een skill of profiel die nu draait, met de bestanden: om een concept dat achterloopt te vergelijken met
// wat er intussen veranderde (ADR-016 §B7). Alleen lezen.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { isPuntSegment, pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

export async function GET(req: Request, { params }: { params: Promise<{ soort: string; naam: string }> }) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { soort, naam } = await params;
  if (isPuntSegment(soort) || isPuntSegment(naam)) return Response.json({ detail: "Onbekend onderdeel." }, { status: 404 });
  return proxy(`/v1/werkplaats/image/onderdelen/${pathSegment(soort)}/${pathSegment(naam)}${new URL(req.url).search}`,
    { headers: { "X-User-Id": userid } });
}
