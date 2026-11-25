// De plugins (plan contenttoets, C4): welke er zijn en of de beheerder ze aanbiedt. Achter `admin: true`.
import { proxy } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxy(`/v1/admin/plugins`, { admin: true });
}
