import { Suspense } from "react";

import { WerkgebiedenClient } from "@/components/werkgebieden/WerkgebiedenClient";

export const metadata = { title: "Werkgebieden · Wetsanalyse" };

export default function WerkgebiedenPagina() {
  // Het statusfilter staat in de URL (useSearchParams), en dat vraagt een Suspense-grens bij het prerenderen.
  return (
    <Suspense fallback={null}>
      <WerkgebiedenClient />
    </Suspense>
  );
}
