// Wie een bronconnector wanneer aan- of uitzette.
import { proxy } from "@/app/api/_lib/proxy";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ naam: string }> };

export async function GET(_req: Request, { params }: Params) {
  const { naam } = await params;
  return proxy(`/v1/admin/connectors/${pathSegment(naam)}/audit`, { admin: true });
}
