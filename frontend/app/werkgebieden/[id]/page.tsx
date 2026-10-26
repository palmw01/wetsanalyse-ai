import { redirect } from "next/navigation";

import { OverzichtTab } from "@/components/werkgebieden/OverzichtTab";
import { oudeTabNaar } from "@/lib/werkgebiedPaden";

/** Het overzicht van een werkgebied. Een oude link met `?tab=` (van vóór G2: bladwijzers, berichten) gaat
 *  naar de plek waar die tab nu staat. */
export default async function WerkgebiedPagina({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string; begrip?: string; weergave?: string }>;
}) {
  const [{ id }, zoek] = await Promise.all([params, searchParams]);
  const naar = oudeTabNaar(id, zoek);
  if (naar) redirect(naar);
  return <OverzichtTab />;
}
