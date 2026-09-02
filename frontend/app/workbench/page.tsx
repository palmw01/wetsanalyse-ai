import { WerkplekVenster } from "@/components/werkplek/WerkplekVenster";

export const metadata = { title: "Lex · Wetsanalyse" };

/** De werkplek. De schil zelf (inclusief de hoogte-container) zit in `WerkplekVenster`, omdat
 *  `app/default.tsx` precies dezelfde boom moet renderen – zie het commentaar daar. */
export default async function WerkplekPagina({
  searchParams,
}: {
  searchParams: Promise<{ gesprek?: string; annotatie?: string }>;
}) {
  // Deep-links vanuit het annotatie-overzicht: open dit gesprek, en/of dit artefact.
  const { gesprek, annotatie } = await searchParams;
  return <WerkplekVenster beginGesprekId={gesprek ?? null} beginArtefact={annotatie} />;
}
