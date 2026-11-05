import { notFound, redirect } from "next/navigation";

import { ArtefactPagina } from "@/components/werkgebieden/DetailPaginas";
import { begripUitParam } from "@/lib/begrippen";
import { artefactPad, begripPad, isArtefactSoort } from "@/lib/werkgebiedPaden";

/** Eén artefact van een werkgebied. Bij de begrippen staat de deelweergave (`?deel=samenhang`) in de URL. */
export default async function Pagina({ params, searchParams }: {
  params: Promise<{ id: string; soort: string }>;
  searchParams: Promise<{ begrip?: string; deel?: string }>;
}) {
  const [{ id, soort }, { begrip, deel }] = await Promise.all([params, searchParams]);
  if (!isArtefactSoort(soort)) notFound();
  // Spoor L: de bronselectie staat op de tab Bronnen; een oude link (een bladwijzer, een bericht) gaat erheen.
  if (soort === "bronselectie") redirect(artefactPad(id, "bronselectie"));
  // Eén begrip is zijn eigen pagina (spoor N); een oude link met `?begrip=` gaat erheen.
  const b = begripUitParam(begrip);
  if (soort === "begrippen" && b) redirect(begripPad(id, b));
  return <ArtefactPagina key={soort} soort={soort} deel={deel === "samenhang" ? "samenhang" : "lijst"} />;
}
