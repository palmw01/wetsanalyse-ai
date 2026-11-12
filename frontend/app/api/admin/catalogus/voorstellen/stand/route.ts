// Staan voorstellen voor de methode aan in deze omgeving (ADR-014 C7)? Achter `admin: true`: een analist krijgt 403
// en ziet de knop dus niet.
import { proxy } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxy(`/v1/admin/catalogus/voorstellen/stand`, { admin: true });
}
