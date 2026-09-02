// Het systeembrede budgetbeleid. Achter `admin: true`: proxy() controleert de beheerdersrol
// server-side en gebruikt het aparte admin-token.
import { proxy, readBody } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxy(`/v1/admin/budget`, { admin: true });
}

export async function PUT(req: Request) {
  const body = await readBody(req);
  return proxy(`/v1/admin/budget`, {
    method: "PUT",
    body,
    admin: true,
    headers: { "Content-Type": "application/json" },
  });
}
