"use client";

import { useEffect, useState } from "react";

import { haalNodeWeergave, type NodeElement, type NodeWeergave } from "@/lib/annotatieNode";
import { foutTekst } from "@/lib/api";
import { actueleElementen, maakWeergaveCache } from "@/lib/bronWeergave";

/** De weergaven per bepaling voor deze sessie (het bronvenster, PR 2): één bron voor elke plek die wettekst toont. Wat
 *  bewaard is, staat er meteen – een tab die terugkomt, een paneel dat opnieuw opent – en de lezing ernaast houdt de
 *  markeringen bij. Alleen hier (en in de annotatieopslag van `lib/annotatieNode.ts`) wordt `haalNodeWeergave`
 *  aangeroepen (`app/wettekst.test.ts`). */
const WEERGAVEN = maakWeergaveCache((iri: string) => haalNodeWeergave({ bron_iri: iri }));

/** De weergave van één bepaling, vers van de server (gedeeld met een lezing die al loopt). */
export function haalBepalingWeergave(iri: string): Promise<NodeWeergave> {
  return WEERGAVEN.haal(iri);
}

/** Na een wijziging aan de annotatie: de bewaarde lezing telt niet meer. */
export function vergeetBepalingWeergave(iri?: string): void {
  WEERGAVEN.vergeet(iri);
}

export interface BepalingStand {
  view: NodeWeergave | undefined;
  /** De markeringen die in de lopende tekst staan (`actueleElementen`). */
  actueel: NodeElement[];
  fout: string | undefined;
}

/** De wettekst van een bepaling met haar markeringen. `null` = niets te laden. */
export function useBepaling(iri: string | null | undefined, foutZin = "De bepaling kon niet worden geladen."): BepalingStand {
  const [stand, setStand] = useState<{ iri: string; view?: NodeWeergave; fout?: string }>();
  useEffect(() => {
    if (!iri) return;
    let levend = true;
    WEERGAVEN.haal(iri).then((view) => levend && setStand({ iri, view }),
      (e) => levend && setStand((s) => s?.iri === iri && s.view ? s : { iri, fout: foutTekst(e, foutZin) }));
    return () => { levend = false; };
  }, [iri, foutZin]);
  if (!iri) return { view: undefined, actueel: [], fout: undefined };
  const view = stand?.iri === iri ? stand.view ?? WEERGAVEN.bewaard(iri) : WEERGAVEN.bewaard(iri);
  const fout = stand?.iri === iri && !view ? stand.fout : undefined;
  return { view, actueel: actueleElementen(view), fout };
}
