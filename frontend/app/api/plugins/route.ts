// De plugins voor het menu *Bronnen en tools* en de commando's (plan contenttoets, C4): wat de beheerder aanbiedt, uit
// het register bij de api. Faalt het, dan krijgt de werkplek een lege lijst: een storing kost de plugins, niet het gesprek.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function GET() {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  return proxy(`/v1/plugins`, { headers: { "X-User-Id": userid } });
}
