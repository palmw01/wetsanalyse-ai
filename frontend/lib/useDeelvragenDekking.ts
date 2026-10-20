"use client";

import { useEffect, useState } from "react";

import { haalDeelvragenDekking } from "@/lib/api";
import { isDeelvragenDekking } from "@/lib/deelvragen";
import type { DeelvragenDekking } from "@/lib/types";

/** De stand per deelvraag, opnieuw bij elke revisie: een nieuwe koppeling of een geaccordeerd begrip
 *  verandert haar. Een hint: faalt ze, of zijn er geen actieve deelvragen, dan is het `null` en staan de
 *  deelvragen er zonder stand. De stand van een vorige revisie blijft staan tot de nieuwe er is, zodat
 *  de labels niet knipperen. */
export function useDeelvragenDekking(id: string, revisie: number, actief: number): DeelvragenDekking | null {
  const [dekking, setDekking] = useState<DeelvragenDekking | null>(null);
  useEffect(() => {
    if (!actief) return;
    let levend = true;
    haalDeelvragenDekking(id)
      .then((d) => { if (levend) setDekking(isDeelvragenDekking(d) ? d : null); })
      .catch(() => { if (levend) setDekking(null); });
    return () => { levend = false; };
  }, [id, revisie, actief]);
  return actief ? dekking : null;
}
