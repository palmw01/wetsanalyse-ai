// Bulk-goedkeuring. Staat naast [id]/goedkeuren; Next.js geeft dit statische segment voorrang
// boven de dynamische [id], dus "goedkeuren" wordt nooit als aanvraag-id gelezen.
import { proxy, readBody } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await readBody(req);
  return proxy(`/v1/admin/registraties/goedkeuren`, {
    method: "POST",
    body,
    admin: true,
    headers: { "Content-Type": "application/json" },
  });
}
