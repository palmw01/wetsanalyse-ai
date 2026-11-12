// Eén onderdeel van de catalogus (ADR-014) met zijn inhoud: methodetekst, regels met hun voorbeeldzinnen, de
// beschrijving van een bron. Doorgegeven aan graph-qa `GET /v1/catalogus/{soort}/{naam}`.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { SOORTEN } from "@/lib/catalogus";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

const NAAM = /^[a-z0-9_.-]{1,80}$/;

export async function GET(_req: Request, { params }: { params: Promise<{ soort: string; naam: string }> }) {
  if (!(await sessionUserId())) return geenSessie();
  const { soort, naam } = await params;
  if (!(SOORTEN as readonly string[]).includes(soort) || !NAAM.test(naam)) {
    return Response.json({ reden: "ongeldig" }, { status: 400 });
  }
  return proxy(`/v1/catalogus/${pathSegment(soort)}/${pathSegment(naam)}`, { agent: true, timeoutMs: 60_000 });
}
