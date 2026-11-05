import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { isPuntSegment, pathSegment } from "@/lib/url";
import { isGeneriekRoute } from "@/lib/werkgebied";

export const dynamic = "force-dynamic";
type Params = { params: Promise<{ pad: string[] }> };

// Generieke begrippen (ADR-006): alleen de vormen uit `isGeneriekRoute`, geen generieke upstream-proxy.
async function forward(req: Request, { params }: Params) {
  const user = await sessionUserId();
  if (!user) return geenSessie();
  const { pad } = await params;
  if (pad.some(isPuntSegment) || !isGeneriekRoute(pad))
    return Response.json({ detail: "Onbekende begriproute." }, { status: 404 });
  return proxy(`/v1/begrippen/${pad.map(pathSegment).join("/")}${new URL(req.url).search}`, {
    method: req.method,
    headers: { "X-User-Id": user, "Content-Type": "application/json" },
    ...(req.method !== "GET" && req.method !== "DELETE" ? { body: await req.text() } : {}),
  });
}
export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
