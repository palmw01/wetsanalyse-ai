import { redirect } from "next/navigation";
import { instellingenOpWerkplek, tabUitPad } from "@/lib/instellingen";

/** Een oude link of bladwijzer naar `/instellingen/…`: het instellingenvenster is geen pagina meer maar een pop-up over
 *  de pagina waar je bent (`?instellingen=`). Deze route opent hem op de werkplek. De rolgate voor `/instellingen/beheer`
 *  in `auth.config.ts` blijft staan; het venster toont een beheer-tab hoe dan ook alleen aan een beheerder. */
export default async function NaarInstellingenVenster({ params }: { params: Promise<{ tab?: string[] }> }) {
  const { tab } = await params;
  redirect(instellingenOpWerkplek(tabUitPad(tab)));
}
