"use client";

// De stand van elk deelgesprek in de sidebar (ADR-016 §A5): loopt, wacht op antwoord, klaar, afgesloten, mislukt. Hij
// staat bij de delegatie, en die hoort bij het oudergesprek: één verzoek per ouder (`haalDelegaties`, gedeeld met de
// blokken in het gesprek), opnieuw als de lijst verandert of een delegatie afloopt (`vergeetDelegaties`).

import { useEffect, useMemo, useState } from "react";

import { haalDelegaties, luisterNaarDelegaties } from "@/lib/api";
import { standenPerDeelgesprek, standVanDeelgesprek, type TaakStand } from "@/lib/delegatie";
import type { GesprekSamenvatting } from "@/lib/types";

/** Hoeveel oudergesprekken de sidebar hooguit naloopt: de nieuwste; een ouder deelgesprek mist dan alleen zijn stand. */
export const MAX_OUDERS = 10;

/** De oudergesprekken waarvan de sidebar deelgesprekken toont, nieuwste eerst, ontdubbeld. */
export function oudersVan(gesprekken: readonly GesprekSamenvatting[]): string[] {
  const uit: string[] = [];
  for (const g of gesprekken) {
    if (g.ouder_id && g.delegatie_id && !uit.includes(g.ouder_id)) uit.push(g.ouder_id);
    if (uit.length >= MAX_OUDERS) break;
  }
  return uit;
}

export function useDelegatieStanden(gesprekken: readonly GesprekSamenvatting[]): Record<string, TaakStand> {
  const ouders = useMemo(() => oudersVan(gesprekken), [gesprekken]);
  const sleutel = ouders.join(",");
  const [standen, setStanden] = useState<Record<string, TaakStand>>({});
  const [versie, setVersie] = useState(0);
  useEffect(() => luisterNaarDelegaties(() => setVersie((v) => v + 1)), []);
  useEffect(() => {
    if (!sleutel) return;
    let weg = false;
    void Promise.all(sleutel.split(",").map((id) => haalDelegaties(id))).then((lijsten) => {
      if (weg) return;
      const delegaties = lijsten.flat();
      const perGesprek = standenPerDeelgesprek(delegaties);
      const uit: Record<string, TaakStand> = {};
      for (const g of gesprekken) {
        const s = g.ouder_id ? standVanDeelgesprek(g, perGesprek, delegaties) : undefined;
        if (s) uit[g.id] = s;
      }
      setStanden(uit);
    });
    return () => { weg = true; };
  }, [sleutel, versie, gesprekken]);
  return sleutel ? standen : {};
}
