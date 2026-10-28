import { notFound, redirect } from "next/navigation";

import { ArtefactPagina } from "@/components/werkgebieden/DetailPaginas";
import { begripUitParam, weergaveUitParam } from "@/lib/begrippen";
import { artefactPad, begripPad, isArtefactSoort } from "@/lib/werkgebiedPaden";

/** Eén artefact van een werkgebied. Bij de begrippen staan het gekozen begrip (`?begrip=`), of het als
 *  kaart openstaat (`&weergave=kaart`) en de deelweergave (`?deel=samenhang`) in de URL. */
export default async function Pagina({ params, searchParams }: {
  params: Promise<{ id: string; soort: string }>;
  searchParams: Promise<{ begrip?: string; weergave?: string; deel?: string }>;
}) {
  const [{ id, soort }, { begrip, weergave, deel }] = await Promise.all([params, searchParams]);
  if (!isArtefactSoort(soort)) notFound();
  // Spoor L: de bronselectie staat op de tab Bronnen; een oude link (een bladwijzer, een bericht) gaat erheen.
  if (soort === "bronselectie") redirect(artefactPad(id, "bronselectie"));
  // De kaart van één begrip is sinds G3 zijn eigen pagina; een oude link met `&weergave=kaart` gaat erheen.
  const b = begripUitParam(begrip);
  if (soort === "begrippen" && b && weergave === "kaart") redirect(begripPad(id, b));
  return <ArtefactPagina key={soort} soort={soort} begrip={begripUitParam(begrip)} weergave={weergaveUitParam(weergave)}
    deel={deel === "samenhang" ? "samenhang" : "lijst"} />;
}
