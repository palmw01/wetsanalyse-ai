import { proxy, readBody } from "@/app/api/_lib/proxy";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function POST(req: Request, { params }: Params) {
  const { id } = await params;
  const body = await readBody(req);
  return proxy(`/v1/admin/registraties/${pathSegment(id)}/afwijzen`, {
    method: "POST",
    body,
    admin: true,
    headers: { "Content-Type": "application/json" },
  });
}
