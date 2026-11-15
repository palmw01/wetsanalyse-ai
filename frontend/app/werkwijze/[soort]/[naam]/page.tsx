import { redirect } from "next/navigation";

import { werkwijzeDoorverwijzing } from "@/lib/aanpassingen";

/** Een oude link naar een onderdeel van de werkwijze: de tab in Instellingen › Aanpassingen waar het nu staat, met het
 *  onderdeel open als het daar een eigen plek heeft (`werkwijzeDoorverwijzing`). */
export default async function OnderdeelRoute({ params }: { params: Promise<{ soort: string; naam: string }> }) {
  const { soort, naam } = await params;
  redirect(werkwijzeDoorverwijzing(soort, decodeURIComponent(naam)));
}
