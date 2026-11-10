// De bronconnectors voor het menu *Bronnen en tools* boven het invoerveld (ADR-013): wat de beheerder aanzette (het
// register bij de api), met per connector of deze straat hem aanbiedt (graph-qa `GET /v1/bronnen`). Is graph-qa niet
// te lezen, dan is die beschikbaarheid `onbekend`; biedt de straat hem niet aan, dan `niet_aangeboden`. Het menu toont
// beide met de reden, zonder schakelaar (`lib/connectorsMenu.ts`).
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { metBeschikbaarheid } from "@/lib/connectorsMenu";

export const dynamic = "force-dynamic";

/** graph-qa staat op `minReplicas: 0`. Een koude start mag het menu niet de volle proxygrens (30 s) ophouden: na deze
 *  wachttijd is de beschikbaarheid `onbekend`, en de werkplek vraagt het opnieuw bij het openen van het menu en na een
 *  beurt. */
const STRAAT_TIMEOUT_MS = 8_000;

export async function GET() {
  if (!(await sessionUserId())) return geenSessie();
  const [register, straat] = await Promise.all([
    proxy(`/v1/connectors`),
    proxy(`/v1/bronnen`, { agent: true, timeoutMs: STRAAT_TIMEOUT_MS }),
  ]);
  // Zonder register weet niemand wat de beheerder aanzette. De werkplek houdt dan de laatst bekende stand en zegt dat de
  // bronnen nu niet te controleren zijn.
  if (!register.ok) {
    return Response.json({ detail: "De lijst met bronnen is nu niet te lezen." }, { status: 503 });
  }
  const data = (await register.json()) as { connectors?: { naam: string }[] };
  const bronnen = straat.ok
    ? ((await straat.json().catch(() => ({}))) as { bronnen?: { naam: string; straat: boolean }[] }).bronnen ?? null
    : null;
  return Response.json({ ...data, connectors: metBeschikbaarheid(data.connectors ?? [], bronnen) });
}
