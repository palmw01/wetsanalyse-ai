import { notFound } from "next/navigation";

import { BronPagina } from "@/components/bronnen/BronPagina";

export const metadata = { title: "Bepaling · Wetsanalyse" };

/** Eén bepaling uit de graaf (`?bron_iri=`), optioneel in de context van een werkgebied (`&werkgebied=`). */
export default async function Pagina({ searchParams }: { searchParams: Promise<{ bron_iri?: string; werkgebied?: string }> }) {
  const { bron_iri, werkgebied } = await searchParams;
  if (!bron_iri || !bron_iri.startsWith("urn:bwb:")) notFound();
  const wg = werkgebied && /^[A-Za-z0-9-]{1,64}$/.test(werkgebied) ? werkgebied : undefined;
  return <BronPagina key={`${bron_iri}|${wg ?? ""}`} bronIri={bron_iri} werkgebiedId={wg} />;
}
