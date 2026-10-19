import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

// Begrippen over werkgebieden heen (fase F4): alleen lezen. De query gaat ongewijzigd door – een
// filter dat hier wegvalt, filtert stil niet.
export async function GET(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy(`/v1/begrippen${new URL(req.url).search}`, { headers: { "X-User-Id": userid } });
}
