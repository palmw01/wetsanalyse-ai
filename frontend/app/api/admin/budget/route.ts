// Het systeembrede budgetbeleid. Achter `admin: true`: proxy() controleert de beheerdersrol
// server-side en gebruikt het aparte admin-token.
import { proxy, readBody } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxy(`/v1/admin/budget`, { admin: true });
}

// De api wil weten wie dit doet: naast het admin-token gaat de beheerder uit de sessie mee.
export async function PUT(req: Request) {
  const door = await sessionUserId();
  if (!door) return geenSessie();
  const body = await readBody(req);
  return proxy(`/v1/admin/budget`, {
    method: "PUT",
    body,
    admin: true,
    headers: { "Content-Type": "application/json", "X-User-Id": door },
  });
}
