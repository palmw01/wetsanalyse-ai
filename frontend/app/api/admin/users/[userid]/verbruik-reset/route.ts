// Geef een gebruiker zijn volledige budget terug voor dit venster. Het journaal blijft intact.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ userid: string }> };

// De api wil weten wie dit doet: naast het admin-token gaat de beheerder uit de sessie mee.
export async function POST(_req: Request, { params }: Params) {
  const door = await sessionUserId();
  if (!door) return geenSessie();
  const { userid } = await params;
  return proxy(`/v1/admin/users/${pathSegment(userid)}/verbruik/reset`, {
    method: "POST",
    admin: true,
    headers: { "X-User-Id": door },
  });
}
