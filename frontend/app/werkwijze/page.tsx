import { Suspense } from "react";

import { WerkwijzeClient } from "@/components/werkwijze/WerkwijzeClient";

export const metadata = { title: "Werkwijze van Lex · Wetsanalyse" };

export default function WerkwijzePagina() {
  // De filters staan in de URL (useSearchParams), en dat vraagt een Suspense-grens bij het prerenderen.
  return (
    <Suspense fallback={null}>
      <WerkwijzeClient />
    </Suspense>
  );
}
