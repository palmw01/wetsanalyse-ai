import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

// De gedeelde annotatielagen: één per artikel, voor iedereen. De identiteit gaat toch mee als
// X-User-Id – de api heeft hem nodig voor `mijn=true` (lagen waar je zelf iets aan deed) en voor de
// audit. Alle query-parameters (`mijn`, `bwbId`, `limit`, `offset`) gaan ongewijzigd door: een
// parameter die hier sneuvelt faalt stil (zie het lid-filter van #190).

export async function GET(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const qs = new URL(req.url).search;
  return proxy(`/v1/annotatie/lagen${qs}`, { headers: { "X-User-Id": userid } });
}
