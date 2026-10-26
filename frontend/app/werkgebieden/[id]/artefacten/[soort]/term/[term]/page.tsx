import { notFound } from "next/navigation";

import { BegripTermPagina } from "@/components/werkgebieden/BegripTerm";

/** De voorstellen van Lex voor één term in het begrippenkader (spoor H4). */
export default async function Pagina({ params }: { params: Promise<{ soort: string; term: string }> }) {
  const { soort, term } = await params;
  if (soort !== "begrippen") notFound();
  return <BegripTermPagina sleutel={decodeURIComponent(term)} />;
}
