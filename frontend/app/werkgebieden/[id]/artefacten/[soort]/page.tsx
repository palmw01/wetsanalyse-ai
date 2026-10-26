import { notFound } from "next/navigation";

import { ArtefactPagina } from "@/components/werkgebieden/DetailPaginas";
import { begripUitParam, weergaveUitParam } from "@/lib/begrippen";
import { isArtefactSoort } from "@/lib/werkgebiedPaden";

/** Eén artefact van een werkgebied. Bij de begrippen staan het gekozen begrip (`?begrip=`), of het als
 *  kaart openstaat (`&weergave=kaart`) en de deelweergave (`?deel=samenhang`) in de URL. */
export default async function Pagina({ params, searchParams }: {
  params: Promise<{ soort: string }>;
  searchParams: Promise<{ begrip?: string; weergave?: string; deel?: string }>;
}) {
  const [{ soort }, { begrip, weergave, deel }] = await Promise.all([params, searchParams]);
  if (!isArtefactSoort(soort)) notFound();
  return <ArtefactPagina key={soort} soort={soort} begrip={begripUitParam(begrip)} weergave={weergaveUitParam(weergave)}
    deel={deel === "samenhang" ? "samenhang" : "lijst"} />;
}
