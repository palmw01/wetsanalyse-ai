// Een wijziging van een methodesectie voorstellen als concept-PR (ADR-014 C7). De api wil een beheerder mét 2FA: die
// gaat uit de sessie mee, zoals bij de connectors.
import { proxy, readBody } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const door = await sessionUserId();
  if (!door) return geenSessie();
  const body = await readBody(req);
  return proxy(`/v1/admin/catalogus/voorstellen`, {
    method: "POST",
    body,
    admin: true,
    headers: { "Content-Type": "application/json", "X-User-Id": door },
  });
}
