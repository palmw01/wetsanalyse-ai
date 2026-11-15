// Wie welk modelprofiel koos voor een agentprofiel of stap, nieuwste eerst. Achter `admin: true`.
import { proxy } from "@/app/api/_lib/proxy";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ sleutel: string }> };

export async function GET(_req: Request, { params }: Params) {
  const { sleutel } = await params;
  return proxy(`/v1/admin/modelkeuzes/${pathSegment(sleutel)}/audit`, { admin: true });
}
