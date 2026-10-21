import { WerkgebiedClient } from "@/components/werkgebieden/WerkgebiedClient";
import { begripUitParam, weergaveUitParam } from "@/lib/begrippen";
import { tabUitParam } from "@/lib/werkgebied";

export const metadata = { title: "Werkgebied · Wetsanalyse" };

/** Eén werkgebied. De tab staat in de URL (`?tab=elementen`), en op de tab Begrippen ook het gekozen
 *  begrip (`&begrip=<id>`) en of het als kaart openstaat (`&weergave=kaart`), zodat terugbladeren en
 *  delen werken. */
export default async function WerkgebiedPagina({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string; begrip?: string; weergave?: string }>;
}) {
  const [{ id }, { tab, begrip, weergave }] = await Promise.all([params, searchParams]);
  // Een `key` per werkgebied: een soft navigation naar een ander werkgebied begint met verse state.
  return <WerkgebiedClient key={id} id={id} beginTab={tabUitParam(tab)} beginBegrip={begripUitParam(begrip)}
    beginWeergave={weergaveUitParam(weergave)} />;
}
