// De bronconnectors (ADR-013): welke er zijn en of ze aanstaan. Achter `admin: true`.
import { proxy } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxy(`/v1/admin/connectors`, { admin: true });
}
