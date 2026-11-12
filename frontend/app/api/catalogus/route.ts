// De catalogus van Lex (ADR-014): wat Lex kan, afgeleid uit de registers van graph-qa (`GET /v1/catalogus`). Alleen
// lezen, voor elke ingelogde gebruiker; het token blijft hier.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function GET() {
  if (!(await sessionUserId())) return geenSessie();
  // graph-qa kan koud starten (`minReplicas: 0`): ruimer dan de standaard.
  return proxy(`/v1/catalogus`, { agent: true, timeoutMs: 60_000 });
}
