import { proxy, readBody } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function PATCH(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const body = await readBody(req);
  return proxy(`/v1/auth/me/rondleiding`, {
    method: "PATCH",
    body,
    headers: { "X-User-Id": userid, "Content-Type": "application/json" },
  });
}
