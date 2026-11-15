"use client";

import { useCallback, useEffect, useState } from "react";

/** Kopiëren naar het klembord (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md`
 *  §10): één aanroep, één stand en één zin als het niet lukt. Het klembord ontbreekt op een niet-beveiligde origin en kan
 *  geweigerd worden; een klik waar niets van gebeurt leest als een kapotte knop, en bij een eenmalig token denk je dan
 *  dat je het hebt. `app/kopieer.test.ts` bewaakt dat niemand anders `navigator.clipboard` aanroept. */

/** De zin bij een mislukte kopie, in een melding of onder een veld. */
export const KOPIEER_MISLUKT = "Kopiëren lukt niet in deze browser. Selecteer de tekst en kopieer die zelf.";
/** Dezelfde zin, kort genoeg voor de knop zelf. */
export const KOPIEER_MISLUKT_KORT = "Kopiëren lukte niet";

/** `true` als het gelukt is. */
export async function kopieerNaarKlembord(tekst: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(tekst);
    return true;
  } catch {
    return false;
  }
}

export type KopieerStand = "" | "gekopieerd" | "mislukt";

/** De stand van een kopieerknop. Na `duur` ms valt "gekopieerd" terug naar de gewone knop; met `null` blijft hij staan
 *  (een eenmalig token: dan wil je zien dat je hem hebt). */
export function useKopieer(duur: number | null = 1500): { stand: KopieerStand; kopieer: (tekst: string) => Promise<boolean>; wis: () => void } {
  const [stand, setStand] = useState<KopieerStand>("");
  useEffect(() => {
    if (stand !== "gekopieerd" || duur === null) return;
    const id = window.setTimeout(() => setStand(""), duur);
    return () => window.clearTimeout(id);
  }, [stand, duur]);
  const kopieer = useCallback(async (tekst: string) => {
    const gelukt = await kopieerNaarKlembord(tekst);
    setStand(gelukt ? "gekopieerd" : "mislukt");
    return gelukt;
  }, []);
  const wis = useCallback(() => setStand(""), []);
  return { stand, kopieer, wis };
}
