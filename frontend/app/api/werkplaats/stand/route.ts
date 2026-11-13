// De werkplaats (ADR-016 deel B): staat ze op deze omgeving aan, en wat mag deze gebruiker. Zonder de vlag
// `WERKPLAATS` antwoordt de api `{aan: false}`; de andere routes bestaan dan niet (404).
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy(`/v1/werkplaats/stand${new URL(req.url).search}`, { headers: { "X-User-Id": userid } });
}
