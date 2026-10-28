"use client";

import { useEffect, useState } from "react";

import { haalKandidaten, haalWerkvoorraad, lijstBegrippen, lijstGesprekken } from "@/lib/api";
import type { BegripSamenvatting, BronKandidaat, GesprekSamenvatting, Werkgebied } from "@/lib/types";
import { isWerkvoorraad, type Werkvoorraad } from "@/lib/werkgebiedPaden";

export interface WerkgebiedStand {
  /** De eigen gesprekken in dit werkgebied (gesprekken zijn per gebruiker). */
  gesprekken: GesprekSamenvatting[] | null;
  begrippen: BegripSamenvatting[] | null;
  kandidaten: BronKandidaat[] | null;
  /** Vraagt de graaf; komt later binnen, en kan ontbreken. */
  werkvoorraad: Werkvoorraad | null;
}

/** Wat de overzichtsteksten van een werkgebied nodig hebben, naast het werkgebied zelf (spoor G2). Elk
 *  onderdeel laadt los en faalt stil: een teller of kaart zonder data toont geen getal in plaats van een
 *  verzonnen nul. Opnieuw bij elke revisie; de werkvoorraad alleen als de bronnen veranderen. */
export function useWerkgebiedStand(wg: Werkgebied, delen: { werkvoorraad?: boolean } = {}): WerkgebiedStand {
  const [gesprekken, setGesprekken] = useState<GesprekSamenvatting[] | null>(null);
  const [begrippen, setBegrippen] = useState<BegripSamenvatting[] | null>(null);
  const [kandidaten, setKandidaten] = useState<BronKandidaat[] | null>(null);
  const [werkvoorraad, setWerkvoorraad] = useState<Werkvoorraad | null>(null);
  const bronnen = wg.bronnen.map((b) => `${b.id}:${b.rol}`).join("|");

  useEffect(() => {
    let levend = true;
    lijstGesprekken({ werkgebiedId: wg.id, gearchiveerd: false })
      .then((g) => levend && setGesprekken(g)).catch(() => levend && setGesprekken(null));
    lijstBegrippen(wg.id).then((b) => levend && setBegrippen(b.begrippen)).catch(() => levend && setBegrippen(null));
    haalKandidaten(wg.id).then((k) => levend && setKandidaten(k.kandidaten)).catch(() => levend && setKandidaten(null));
    return () => { levend = false; };
  }, [wg.id, wg.revisie]);

  const metWerkvoorraad = delen.werkvoorraad ?? true;
  useEffect(() => {
    if (!metWerkvoorraad || !bronnen) return;
    let levend = true;
    haalWerkvoorraad(wg.id)
      .then((w) => levend && setWerkvoorraad(isWerkvoorraad(w) ? w : null))
      .catch(() => levend && setWerkvoorraad(null));
    return () => { levend = false; };
  }, [wg.id, bronnen, metWerkvoorraad]);

  return { gesprekken, begrippen, kandidaten, werkvoorraad: bronnen ? werkvoorraad : null };
}
