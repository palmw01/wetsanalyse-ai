import { WerkgebiedClient } from "@/components/werkgebieden/WerkgebiedClient";
import { tabUitParam } from "@/lib/werkgebied";

export const metadata = { title: "Werkgebied · Wetsanalyse" };

/** Eén werkgebied. De tab staat in de URL (`?tab=elementen`), zodat terugbladeren en delen werken. */
export default async function WerkgebiedPagina({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const [{ id }, { tab }] = await Promise.all([params, searchParams]);
  // Een `key` per werkgebied: een soft navigation naar een ander werkgebied begint met verse state.
  return <WerkgebiedClient key={id} id={id} beginTab={tabUitParam(tab)} />;
}
