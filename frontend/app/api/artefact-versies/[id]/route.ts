import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

// Eén versie van een artefact met haar plek ertussen (n van m, vorige, volgende), alleen lezen.
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { id } = await params;
  return proxy(`/v1/artefact-versies/${pathSegment(id)}`, { headers: { "X-User-Id": userid } });
}
