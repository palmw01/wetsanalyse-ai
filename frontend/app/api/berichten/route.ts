import { proxy } from "../_lib/proxy";
import { geenSessie, sessionUserId } from "../_lib/session";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { searchParams } = new URL(req.url);
  const pagina = searchParams.get("pagina");
  const qs = pagina ? `?pagina=${encodeURIComponent(pagina)}` : "";
  return proxy(`/v1/berichten${qs}`, { headers: { "X-User-Id": userid } });
}
