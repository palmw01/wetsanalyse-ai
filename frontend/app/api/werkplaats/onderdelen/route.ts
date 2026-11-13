// De concepten van de werkplaats (ADR-016 deel B): de eigen en gedeelde concepten, en een nieuw concept (leeg, of
// met `uit_image` de versie die draait). De api zet de ingelogde gebruiker (X-User-Id uit de sessie) als eigenaar.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy(`/v1/werkplaats/onderdelen${new URL(req.url).search}`, { headers: { "X-User-Id": userid } });
}

export async function POST(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy(`/v1/werkplaats/onderdelen${new URL(req.url).search}`, {
    method: "POST",
    body: await req.text(),
    headers: { "X-User-Id": userid, "Content-Type": "application/json" },
  });
}
