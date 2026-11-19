"use client";

import { useCallback, useEffect, useState } from "react";

import { foutTekst, haalRegel, haalRegelKeten, lijstRegels } from "@/lib/api";
import type { Regel, RegelKeten } from "@/lib/regels";
import { isRevisieConflict } from "@/lib/werkgebied";

export type RegelMelding = { type: "bevestiging" | "waarschuwing"; tekst: string } | null;

/** Eén afleidingsregel, zoals de pagina en het paneel hem delen (de vorm van `useBegrip`). Alle mutaties lopen via
 *  `muteer`, met de revisie in beeld: een 412 laadt de nieuwste stand en zegt dat, de handeling wordt niet stil
 *  opnieuw uitgevoerd. Een opname (een oude versie) laadt niets en muteert niets. */
export function useRegel({ werkgebiedId, regelId, opname }: { werkgebiedId: string; regelId: string; opname?: Regel }) {
  const [regel, setRegel] = useState<Regel | null>(opname ?? null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<RegelMelding>(null);
  const [bezig, setBezig] = useState(false);
  const [lading, setLading] = useState(0);

  useEffect(() => {
    if (opname) return;
    let levend = true;
    haalRegel(werkgebiedId, regelId)
      .then((r) => { if (levend) { setRegel(r); setFout(null); } })
      .catch((e) => levend && setFout(foutTekst(e, "De afleidingsregel kon niet worden geladen.")));
    return () => { levend = false; };
  }, [werkgebiedId, regelId, opname, lading]);

  const laad = useCallback(() => setLading((n) => n + 1), []);

  const muteer = useCallback(async (actie: (revisie: number) => Promise<Regel>, gelukt?: string): Promise<boolean> => {
    if (!regel || opname) return false;
    setMelding(null);
    setBezig(true);
    try {
      setRegel(await actie(regel.revisie));
      if (gelukt) setMelding({ type: "bevestiging", tekst: gelukt });
      return true;
    } catch (e) {
      if (isRevisieConflict(e)) {
        laad();
        setMelding({ type: "waarschuwing", tekst: "Iemand anders wijzigde deze regel net. De nieuwste stand staat nu in beeld; kijk of je besluit nog nodig is." });
      } else setMelding({ type: "waarschuwing", tekst: foutTekst(e) });
      return false;
    } finally {
      setBezig(false);
    }
  }, [regel, opname, laad]);

  return { regel, fout, melding, bezig, laad, muteer, alleenLezen: !!opname };
}

export type RegelStand = ReturnType<typeof useRegel>;

/** De regels van een werkgebied met hun keten (`regels/hierarchie`). Beide laden los: zonder keten staat de lijst er in
 *  de volgorde van aanmaken. */
export function useRegelKeten(werkgebiedId: string, opname?: { regels: Regel[]; keten: RegelKeten | null }) {
  const [regels, setRegels] = useState<Regel[] | null>(opname?.regels ?? null);
  const [keten, setKeten] = useState<RegelKeten | null>(opname?.keten ?? null);
  const [fout, setFout] = useState<string | null>(null);
  const [lading, setLading] = useState(0);

  useEffect(() => {
    if (opname) return;
    let levend = true;
    lijstRegels(werkgebiedId).then((r) => { if (levend) { setRegels(r); setFout(null); } })
      .catch((e) => levend && setFout(foutTekst(e, "De afleidingsregels konden niet worden geladen.")));
    haalRegelKeten(werkgebiedId).then((k) => levend && setKeten(k)).catch(() => levend && setKeten(null));
    return () => { levend = false; };
  }, [werkgebiedId, opname, lading]);

  return { regels, keten, fout, laad: useCallback(() => setLading((n) => n + 1), []) };
}
