// De bronconnectors voor het menu *Bronnen en tools* boven het invoerveld (ADR-013): wat de beheerder aanzette (het
// register bij de api), beperkt tot wat deze straat aanbiedt (graph-qa `GET /v1/bronnen`).
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { alleenInDeStraat } from "@/lib/connectorsMenu";

export const dynamic = "force-dynamic";

export async function GET() {
  if (!(await sessionUserId())) return geenSessie();
  const [register, straat] = await Promise.all([proxy(`/v1/connectors`), proxy(`/v1/bronnen`, { agent: true })]);
  if (!register.ok) return register;
  const data = (await register.json()) as { connectors?: { naam: string }[] };
  const bronnen = straat.ok ? ((await straat.json()) as { bronnen?: { naam: string; straat: boolean }[] }).bronnen ?? null : null;
  return Response.json({ ...data, connectors: alleenInDeStraat(data.connectors ?? [], bronnen) });
}
