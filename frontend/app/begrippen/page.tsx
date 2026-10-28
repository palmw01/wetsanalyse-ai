import { Suspense } from "react";

import { BegrippenOverzichtClient } from "@/components/begrippen/BegrippenOverzichtClient";

export const metadata = { title: "Begrippen · Wetsanalyse" };

export default function BegrippenPagina() {
  // De filters staan in de URL (useSearchParams), en dat vraagt een Suspense-grens bij het prerenderen.
  return (
    <Suspense fallback={null}>
      <BegrippenOverzichtClient />
    </Suspense>
  );
}
