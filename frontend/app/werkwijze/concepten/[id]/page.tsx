import { redirect } from "next/navigation";

import { conceptPad } from "@/lib/werkplaats";

/** Een concept stond onder de werkwijze; de pagina woont nu onder Aanpassingen. De querystring (een versie, een
 *  vergelijking, *Loopt achter*, het gekozen bestand) gaat mee. */
export default async function ConceptDoorverwijzing({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(await searchParams)) for (const w of [v].flat()) if (w !== undefined) qs.append(k, w);
  redirect(`${conceptPad(decodeURIComponent(id))}${qs.size ? `?${qs}` : ""}`);
}
