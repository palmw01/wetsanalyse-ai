// De eigen verbruiksstand: meter, resetdatum, waarschuwing en blokkade.
// Per-gebruiker gescopet via de vertrouwde X-User-Id uit de sessie – niemand ziet andermans stand.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function GET() {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy(`/v1/verbruik`, { headers: { "X-User-Id": userid } });
}
