import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

// De versies van één artefact (`?sleutel=`), alleen lezen. De api legt ze zelf vast bij een beurt van Lex; er is
// geen schrijfpad vanuit de browser. De query gaat ongewijzigd door.
export async function GET(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy(`/v1/artefact-versies${new URL(req.url).search}`, { headers: { "X-User-Id": userid } });
}
