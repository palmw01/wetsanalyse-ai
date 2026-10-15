import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

// Werkgebieden zijn gedeeld tussen analisten, zoals de annotaties; de api zet de ingelogde
// gebruiker (X-User-Id uit de sessie) als actor in de audit.

export async function GET(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy(`/v1/werkgebieden${new URL(req.url).search}`, { headers: { "X-User-Id": userid } });
}

export async function POST(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy("/v1/werkgebieden", {
    method: "POST",
    body: await req.text(),
    headers: { "X-User-Id": userid, "Content-Type": "application/json" },
  });
}
