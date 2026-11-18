"use client";

import { useEffect, useRef } from "react";

/** Hoe lang na een verversing een volgende terugkomst niets doet. */
export const TERUGKOMST_MS = 15_000;

/** Of een terugkomst nu moet verversen: het venster is zichtbaar en de vorige verversing is lang genoeg
 *  geleden. Los, zodat het zonder DOM te toetsen is. */
export function moetNuVerversen(zichtbaar: boolean, nu: number, laatst: number, wachtMs = TERUGKOMST_MS): boolean {
  return zichtbaar && nu - laatst >= wachtMs;
}

/** Roept `ververs` aan als de gebruiker terugkomt in dit venster: het venster krijgt de focus of wordt weer
 *  zichtbaar, of de pagina komt terug uit de cache van de browser (`pageshow` met `persisted`).
 *
 *  Waarom: een app op het beginscherm van een iPhone (en een tab die lang in de achtergrond stond) wordt bij
 *  terugkeer niet herladen. Een laag die zijn data één keer laadt, zoals het werkgebied met zijn tellers,
 *  toont dan dagen later nog de stand van toen (melding gebruiker 18 nov 2026: "0 begrippen" op de iPhone,
 *  9 op de pc). Hoogstens eens per `TERUGKOMST_MS`, en geen timer: zonder handeling geen verzoek. */
export function useBijTerugkomst(ververs: () => void, actief = true): void {
  const ref = useRef(ververs);
  useEffect(() => {
    ref.current = ververs;
  });
  useEffect(() => {
    if (!actief) return;
    let laatst = Date.now();
    const terug = (e?: Event) => {
      const uitCache = e?.type === "pageshow" && (e as PageTransitionEvent).persisted;
      if (!uitCache && !moetNuVerversen(document.visibilityState !== "hidden", Date.now(), laatst)) return;
      laatst = Date.now();
      ref.current();
    };
    window.addEventListener("focus", terug);
    window.addEventListener("pageshow", terug);
    document.addEventListener("visibilitychange", terug);
    return () => {
      window.removeEventListener("focus", terug);
      window.removeEventListener("pageshow", terug);
      document.removeEventListener("visibilitychange", terug);
    };
  }, [actief]);
}
