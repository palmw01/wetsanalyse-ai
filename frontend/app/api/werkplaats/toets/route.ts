// Poort 1 van de werkplaats zonder op te slaan: wat de controle van deze bestanden vindt (live in de editor).
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy(`/v1/werkplaats/toets${new URL(req.url).search}`, {
    method: "POST",
    body: await req.text(),
    headers: { "X-User-Id": userid, "Content-Type": "application/json" },
  });
}
