// Het modelprofiel per rol van Lex: welke rollen er zijn en welk profiel ze volgen. Achter `admin: true`.
import { proxy } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxy(`/v1/admin/modelrollen`, { admin: true });
}
