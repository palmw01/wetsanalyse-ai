"use client";

import { useEffect, useState } from "react";

import { haalBronselectie } from "@/lib/api";
import type { BronselectieOverzicht } from "@/lib/bronselectie";

/** Het overzicht van de bronselectie (spoor J), opnieuw bij elke revisie: daaruit komt de stand per deelvraag in
 *  de rijen (spoor K). Een hint: faalt het, of zijn er geen actieve deelvragen, dan is het `null` en staan de
 *  deelvragen er zonder stand. Het overzicht van een vorige revisie blijft staan tot het nieuwe er is, zodat de
 *  labels niet knipperen. */
export function useBronselectieStand(id: string, revisie: number, actief: number): BronselectieOverzicht | null {
  const [overzicht, setOverzicht] = useState<BronselectieOverzicht | null>(null);
  useEffect(() => {
    if (!actief) return;
    let levend = true;
    haalBronselectie(id)
      .then((o) => { if (levend) setOverzicht(o); })
      .catch(() => { if (levend) setOverzicht(null); });
    return () => { levend = false; };
  }, [id, revisie, actief]);
  return actief ? overzicht : null;
}
