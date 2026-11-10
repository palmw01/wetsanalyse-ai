"use client";

import { useCallback, useEffect, useState } from "react";

import { haalStuk, volgendeOffset, type StukAntwoord, type StukPassage } from "@/lib/bronStuk";

/** Wat er van een stuk geladen is, per sessie bewaard: een tab die terugkomt staat er meteen weer. */
interface Stand { antwoord: StukAntwoord; passages: StukPassage[]; volgende?: number }
const BEWAARD = new Map<string, Stand>();

/** Een stuk uit een bronconnector, per deel (het bronvenster, PR 6). Het eerste deel bij het openen, `meer` voor het
 *  volgende (het `vervolg` van de leestool). `null` = niets te laden. */
export function useStuk(doel: { brontype: string; id: string } | null): {
  stand: Stand | undefined; fout: string | undefined; laadt: boolean; meer: (() => void) | undefined;
} {
  const sleutel = doel ? `${doel.brontype}:${doel.id}` : "";
  const [stand, setStand] = useState<{ sleutel: string; s?: Stand; fout?: string; laadt: boolean }>();
  useEffect(() => {
    if (!doel) return;
    let levend = true;
    haalStuk(doel.brontype, doel.id).then((antwoord) => {
      const s: Stand = { antwoord, passages: antwoord.deel.resultaten ?? [], volgende: volgendeOffset(antwoord.deel) };
      BEWAARD.set(sleutel, s);
      if (levend) setStand({ sleutel, s, laadt: false });
    }, (e: unknown) => levend && setStand({ sleutel, fout: e instanceof Error ? e.message : "De bron is nu niet bereikbaar.", laadt: false }));
    return () => { levend = false; };
    // Alleen opnieuw bij een ander stuk.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sleutel]);
  const huidig = stand?.sleutel === sleutel ? stand.s ?? BEWAARD.get(sleutel) : BEWAARD.get(sleutel);
  const meer = useCallback(() => {
    if (!doel || !huidig || huidig.volgende === undefined) return;
    setStand({ sleutel, s: huidig, laadt: true });
    haalStuk(doel.brontype, doel.id, huidig.volgende).then((a) => {
      const s: Stand = { antwoord: huidig.antwoord, passages: [...huidig.passages, ...(a.deel.resultaten ?? [])], volgende: volgendeOffset(a.deel) };
      BEWAARD.set(sleutel, s);
      setStand({ sleutel, s, laadt: false });
    }, (e: unknown) => setStand({ sleutel, s: huidig, laadt: false, fout: e instanceof Error ? e.message : "Het volgende deel kon niet worden geladen." }));
  }, [doel, huidig, sleutel]);
  return {
    stand: huidig,
    fout: stand?.sleutel === sleutel ? stand.fout : undefined,
    laadt: stand?.sleutel === sleutel ? stand.laadt : false,
    meer: huidig?.volgende !== undefined ? meer : undefined,
  };
}
