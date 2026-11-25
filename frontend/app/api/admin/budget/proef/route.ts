// Wat een budgetbeleid zou doen, zonder het op te slaan. Leest alleen, dus geen beheerder in de header:
// proxy() controleert de beheerdersrol server-side en gebruikt het aparte admin-token.
import { proxy, readBody } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await readBody(req);
  return proxy(`/v1/admin/budget/proef`, {
    method: "POST",
    body,
    admin: true,
    headers: { "Content-Type": "application/json" },
  });
}
