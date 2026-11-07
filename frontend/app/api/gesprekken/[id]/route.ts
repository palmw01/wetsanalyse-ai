import { proxy } from "@/app/api/_lib/proxy";
import { wisAgentGeheugen } from "@/app/api/_lib/agentGeheugen";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { logger } from "@/lib/logger";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: Request, { params }: Params) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id } = await params;
  return proxy(`/v1/gesprekken/${pathSegment(id)}`, { headers: { "X-User-Id": userid } });
}

export async function PATCH(req: Request, { params }: Params) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id } = await params;
  return proxy(`/v1/gesprekken/${pathSegment(id)}`, {
    method: "PATCH",
    body: await req.text(),
    headers: { "X-User-Id": userid, "Content-Type": "application/json" },
  });
}

export async function DELETE(_req: Request, { params }: Params) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id } = await params;
  // Drie stappen achter elkaar, elk met een eigen wachttijd. Ze worden apart getimed omdat de
  // klacht "ik klik verwijderen en er gebeurt niets" anders niet te herleiden is naar een van de
  // drie: `proxy()` logt zijn eigen calls, deze regel legt het totaal ernaast.
  const start = performance.now();
  // Eigenaarschap eerst laten vaststellen door de api, zonder al te verwijderen: pas als dit
  // gesprek van jou is, mag de lopende beurt gestopt worden.
  const eigen = await proxy(`/v1/gesprekken/${pathSegment(id)}`, { headers: { "X-User-Id": userid } });
  // Stoppen vóór verwijderen: andersom bleef er een venster waarin de agent doorwerkte en aan het
  // eind in een gesprek schreef dat al weg was.
  if (eigen.ok) await wisAgentGeheugen(id, userid);
  const res = await proxy(`/v1/gesprekken/${pathSegment(id)}`, {
    method: "DELETE",
    headers: { "X-User-Id": userid },
  });
  logger.info("Gesprek verwijderen", {
    http_status: res.status,
    duur_ms: Math.round(performance.now() - start),
  });
  return res;
}
