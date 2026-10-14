import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { isPuntSegment, pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";
type Params = { params: Promise<{ pad: string[] }> };

/** De vormen onder `/v1/werkgebieden/{id}`: het werkgebied zelf, of één van deze deelroutes. */
const DEELROUTES = ["bronnen", "elementen", "audit"];

async function forward(req: Request, { params }: Params) {
  const user = await sessionUserId();
  if (!user) return geenSessie();
  const { pad } = await params;
  // Geen generieke upstream-proxy: `{id}`, `{id}/bronnen[/{selectie}]`, `{id}/elementen`,
  // `{id}/audit`. Een `..` weigert de middleware al; dit is het tweede net.
  if (pad.length > 3 || pad.some(isPuntSegment) || (pad.length > 1 && !DEELROUTES.includes(pad[1]))
    || (pad.length === 3 && pad[1] !== "bronnen"))
    return Response.json({ detail: "Onbekende werkgebiedroute." }, { status: 404 });
  // De query gaat ongewijzigd mee: `verwachte_revisie` bij DELETE, `limit` bij de audit.
  return proxy(`/v1/werkgebieden/${pad.map(pathSegment).join("/")}${new URL(req.url).search}`, {
    method: req.method,
    headers: { "X-User-Id": user, "Content-Type": "application/json" },
    ...(req.method !== "GET" && req.method !== "DELETE" ? { body: await req.text() } : {}),
    // De inventaris haalt per regeling de bronboom uit de graaf; bij een paar grote wetten duurt
    // dat langer dan de standaard 30 s.
    ...(pad[1] === "elementen" ? { timeoutMs: 90_000 } : {}),
  });
}
export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
