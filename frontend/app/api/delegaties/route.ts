import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

// De delegaties van een eigen gesprek of van een werkgebied (ADR-016 §A5, ADR-012): alleen lezen. Starten en sluiten doet
// graph-qa zelf bij de api. Alle query-params gaan ongewijzigd door (`gesprek_id`, `werkgebied_id`, `limit`); de api
// eist er precies één van de eerste twee. De identiteit komt uit de sessie, nooit uit de browser.
export async function GET(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const qs = new URL(req.url).search;
  return proxy(`/v1/delegaties${qs}`, { headers: { "X-User-Id": userid } });
}
