"use client";

import { useEffect, useState } from "react";

import { haalPlaatsen } from "@/lib/annotatieNode";
import type { Plaats } from "@/lib/bronPlaats";

/** De plek van deze bepalingen in hun regeling, één verzoek per (gewijzigde) set. Een hint: faalt het, of
 *  loopt het nog, dan is het `null` en groepeert de boom op wat de IRI zelf zegt. De vorige plekken blijven
 *  staan tot de nieuwe er zijn, zodat de boom niet verspringt. */
export function usePlaatsen(iris: readonly string[]): ReadonlyMap<string, Plaats> | null {
  const sleutel = [...new Set(iris)].sort().join("|");
  const [plaatsen, setPlaatsen] = useState<ReadonlyMap<string, Plaats> | null>(null);
  useEffect(() => {
    if (!sleutel) return;
    let levend = true;
    haalPlaatsen(sleutel.split("|"))
      .then((p) => { if (levend) setPlaatsen(new Map(p.map((x) => [x.bron_iri, x]))); })
      .catch(() => {});
    return () => { levend = false; };
  }, [sleutel]);
  return sleutel ? plaatsen : null;
}
