import { notFound } from "next/navigation";

import { OnderdeelPagina } from "@/components/werkwijze/OnderdeelPagina";
import { SOORTEN, type Soort } from "@/lib/catalogus";

export const metadata = { title: "Werkwijze van Lex · Wetsanalyse" };

export default async function OnderdeelRoute({ params }: { params: Promise<{ soort: string; naam: string }> }) {
  const { soort, naam } = await params;
  if (!(SOORTEN as readonly string[]).includes(soort)) notFound();
  return <OnderdeelPagina soort={soort as Soort} naam={decodeURIComponent(naam)} />;
}
