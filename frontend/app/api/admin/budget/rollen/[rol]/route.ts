// Het tokenbudget van één rol. Via `proxy()`, dus met `metTrace` en de server-side rolcontrole.
import { proxy, readBody } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ rol: string }> };

// De api wil weten wie dit doet: naast het admin-token gaat de beheerder uit de sessie mee.
export async function PUT(req: Request, { params }: Params) {
  const door = await sessionUserId();
  if (!door) return geenSessie();
  const { rol } = await params;
  const body = await readBody(req);
  return proxy(`/v1/admin/budget/rollen/${pathSegment(rol)}`, {
    method: "PUT",
    body,
    admin: true,
    headers: { "Content-Type": "application/json", "X-User-Id": door },
  });
}
