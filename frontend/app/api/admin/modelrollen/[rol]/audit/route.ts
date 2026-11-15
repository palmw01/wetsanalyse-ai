// Wie welk modelprofiel wanneer aan een rol van Lex gaf.
import { proxy } from "@/app/api/_lib/proxy";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ rol: string }> };

export async function GET(_req: Request, { params }: Params) {
  const { rol } = await params;
  return proxy(`/v1/admin/modelrollen/${pathSegment(rol)}/audit`, { admin: true });
}
