import { Suspense } from "react";

import { RegelsOverzichtClient } from "@/components/regels/RegelsOverzichtClient";

export const metadata = { title: "Afleidingsregels · Wetsanalyse" };

export default function AfleidingsregelsPagina() {
  // De filters staan in de URL (useSearchParams), en dat vraagt een Suspense-grens bij het prerenderen.
  return (
    <Suspense fallback={null}>
      <RegelsOverzichtClient />
    </Suspense>
  );
}
