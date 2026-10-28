import { WerkgebiedProject } from "@/components/werkgebieden/WerkgebiedProject";

export const metadata = { title: "Werkgebied · Wetsanalyse" };

/** Eén werkgebied als project (spoor G2). Deze laag laadt het werkgebied één keer voor alle pagina's
 *  eronder – de vier tabs (Overzicht, Gesprekken, Bronnen, Artefacten) en de detailpagina's – en blijft
 *  staan bij een wissel van tab. Een `key` per werkgebied: een ander werkgebied begint met verse state. */
export default async function WerkgebiedLayout({ children, params }: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <WerkgebiedProject key={id} id={id}>{children}</WerkgebiedProject>;
}
