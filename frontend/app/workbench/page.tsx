import { WerkplekVenster } from "@/components/werkplek/WerkplekVenster";

export const metadata = { title: "Lex · Wetsanalyse" };

/** De werkplek. De schil zelf (inclusief de hoogte-container) zit in `WerkplekVenster`, omdat
 *  `app/default.tsx` precies dezelfde boom moet renderen – zie het commentaar daar. */
export default async function WerkplekPagina({
  searchParams,
}: {
  searchParams: Promise<{ gesprek?: string }>;
}) {
  // Deep-link vanuit het annotatie-overzicht: open dit gesprek.
  const { gesprek } = await searchParams;
  return <WerkplekVenster beginGesprekId={gesprek ?? null} />;
}
