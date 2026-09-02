// Verbruik per gebruiker, zwaarste eerst.
import { proxy } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxy(`/v1/admin/verbruik`, { admin: true });
}
