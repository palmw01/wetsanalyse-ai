// De bronconnectors die de beheerder aanzette (ADR-013), voor het menu *Bronnen en tools* boven het invoerveld.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function GET() {
  if (!(await sessionUserId())) return geenSessie();
  return proxy(`/v1/connectors`);
}
