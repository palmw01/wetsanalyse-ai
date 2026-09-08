import { proxy } from "@/app/api/_lib/proxy";
import { metTrace } from "@/lib/trace";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { graphQaAuthHeader, graphQaBaseUrl } from "@/lib/config";
import { logger } from "@/lib/logger";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

/** Hoe lang deze route op graph-qa wacht bij het wissen van het agent-geheugen.
 *
 *  Node's `fetch` kent geen standaardtimeout – dezelfde reden waarom `proxy()` er een heeft. Hier
 *  weegt dat zwaarder dan daar, want deze stap is *best-effort* en zat tóch tussen de klik en het
 *  antwoord in: bleef graph-qa hangen (koude start bij `minReplicas: 0`, of een beurt die nog op een
 *  nodegrens moet stoppen), dan bleef het gesprek in beeld staan alsof de klik niet was aangekomen.
 *  Vijf seconden is ruim voor een gezonde dienst; wat langer duurt hoort de verwijdering niet op te
 *  houden. De checkpointer-thread blijft dan hooguit ongebruikt staan. */
const AGENT_GEHEUGEN_TIMEOUT_MS = 5_000;

/** Stop de lopende beurt en wis het agent-geheugen (graph-qa checkpointer-thread) van dit gesprek.
 *  Best-effort: een falen mag de UI-delete niet blokkeren – de checkpointer-thread ruimt anders later
 *  op (of blijft hooguit ongebruikt staan). */
async function wisAgentGeheugen(id: string, userid: string): Promise<void> {
  const start = performance.now();
  try {
    const res = await fetch(`${graphQaBaseUrl()}/v1/conversations/${pathSegment(id)}`, {
      method: "DELETE",
      // De identiteit gaat mee, net als op de run-routes: deze delete stopt ook een lopende beurt,
      // en graph-qa weigert dat voor een run van iemand anders. De api heeft het eigenaarschap dan
      // al vastgesteld – dit is het tweede net, niet het eerste.
      headers: metTrace({ ...graphQaAuthHeader(), "X-User-Id": userid }),
      cache: "no-store",
      signal: AbortSignal.timeout(AGENT_GEHEUGEN_TIMEOUT_MS),
    });
    logger.info("Gesprek verwijderen: agent-geheugen", {
      http_status: res.status,
      duur_ms: Math.round(performance.now() - start),
    });
  } catch (err) {
    const verlopen = (err as Error).name === "TimeoutError";
    logger.warn(verlopen ? "Agent-geheugen wissen duurde te lang" : "Agent-geheugen wissen mislukt", {
      fout: (err as Error).message,
      duur_ms: Math.round(performance.now() - start),
      timeout_ms: verlopen ? AGENT_GEHEUGEN_TIMEOUT_MS : undefined,
    });
  }
}

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
