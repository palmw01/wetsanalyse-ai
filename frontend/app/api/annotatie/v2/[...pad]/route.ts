import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";
type Params = { params: Promise<{ pad: string[] }> };
async function forward(req: Request, { params }: Params) {
  const user = await sessionUserId();
  if (!user) return geenSessie();
  const { pad } = await params;
  // Alleen de expliciete node-API; dit is geen generieke upstream-proxy.
  if (!pad.length || !["weergave", "elementen", "lagen", "node-lagen"].includes(pad[0]))
    return Response.json({ detail: "Onbekende annotatieroute." }, { status: 404 });
  return proxy(`/v1/annotatie/${pad.map(pathSegment).join("/")}${new URL(req.url).search}`, {
    method: req.method,
    headers: { "X-User-Id": user, "Content-Type": "application/json" },
    ...(req.method !== "GET" ? { body: await req.text() } : {}),
  });
}
export const GET = forward;
export const POST = forward;
export const DELETE = forward;
