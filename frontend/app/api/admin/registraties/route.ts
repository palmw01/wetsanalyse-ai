// Beheer van zelfregistratie-aanvragen. Achter `admin: true`: proxy() controleert de beheerdersrol
// server-side en gebruikt het aparte admin-token, dat de browser nooit ziet.
import { proxy } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  // Het statusfilter moet mee, anders krijgt de beheertab altijd álle aanvragen terug.
  const status = new URL(req.url).searchParams.get("status");
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return proxy(`/v1/admin/registraties${q}`, { admin: true });
}
