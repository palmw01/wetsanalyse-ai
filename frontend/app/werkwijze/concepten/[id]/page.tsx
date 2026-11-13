import { Suspense } from "react";

import { ConceptPagina } from "@/components/werkwijze/ConceptPagina";

export const metadata = { title: "Concept · Werkwijze van Lex · Wetsanalyse" };

export default async function ConceptRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // Het gekozen bestand staat in de URL (useSearchParams), en dat vraagt een Suspense-grens bij het prerenderen.
  return (
    <Suspense fallback={null}>
      <ConceptPagina id={decodeURIComponent(id)} />
    </Suspense>
  );
}
