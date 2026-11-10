import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

/** Hoeveel gesprekken er per groep staan (instellingen → Gesprekken): `{recent, archief}`. */
export async function GET() {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy(`/v1/gesprekken/telling`, { headers: { "X-User-Id": userid } });
}
