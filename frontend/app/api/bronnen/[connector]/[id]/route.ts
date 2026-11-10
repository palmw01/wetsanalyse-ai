// Eén stuk uit een bronconnector voor het bronvenster (ADR-013, het bronvenster-plan PR 6): doorgegeven aan graph-qa
// (`GET /v1/bronnen/{connector}/stukken/{id}`), die de leestool uit de beschrijving draait en zijn cache deelt met Lex.
// De connector is een naam of een brontype, alleen kleine letters; `offset` (het vervolg van een lang stuk) en `tabel`
// gaan mee. De straat beslist of de connector er is (404); het token blijft hier.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

const NAAM = /^[a-z][a-z0-9_]{0,39}$/;

export async function GET(req: Request, { params }: { params: Promise<{ connector: string; id: string }> }) {
  if (!(await sessionUserId())) return geenSessie();
  const { connector, id } = await params;
  if (!NAAM.test(connector) || !id || id.length > 200) return Response.json({ reden: "ongeldig" }, { status: 400 });
  const vraag = new URL(req.url).searchParams;
  const door = new URLSearchParams();
  for (const sleutel of ["offset", "tabel"]) {
    const w = vraag.get(sleutel);
    if (w !== null && /^\d{1,6}$/.test(w)) door.set(sleutel, w);
  }
  const q = door.toString();
  // Een stuk ophalen kost een rondgang naar de bron (KOOP): ruimer dan de standaard.
  return proxy(`/v1/bronnen/${pathSegment(connector)}/stukken/${pathSegment(id)}${q ? `?${q}` : ""}`,
    { agent: true, timeoutMs: 60_000 });
}
