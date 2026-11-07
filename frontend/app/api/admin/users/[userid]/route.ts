import { proxy, readBody } from "@/app/api/_lib/proxy";
import { wisAgentGeheugen } from "@/app/api/_lib/agentGeheugen";
import { pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ userid: string }> };

export async function PATCH(req: Request, { params }: Params) {
  const { userid } = await params;
  const body = await readBody(req);
  return proxy(`/v1/admin/users/${pathSegment(userid)}`, {
    method: "PATCH",
    body,
    admin: true,
    headers: { "Content-Type": "application/json" },
  });
}

/** Het account en zijn gesprekken gaan weg bij de api; die noemt de gesprekken, en hun agent-geheugen (checkpoint en
 *  runs bij graph-qa) wist deze route daarna, zoals bij één gesprek. */
export async function DELETE(_req: Request, { params }: Params) {
  const { userid } = await params;
  const res = await proxy(`/v1/admin/users/${pathSegment(userid)}`, { method: "DELETE", admin: true });
  if (!res.ok) return res;
  const { gesprekken = [] } = (await res.json().catch(() => ({}))) as { gesprekken?: string[] };
  await Promise.all(gesprekken.map((id) => wisAgentGeheugen(id, userid)));
  return new Response(null, { status: 204 });
}
