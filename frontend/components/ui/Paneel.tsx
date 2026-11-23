"use client";

import { createContext, useContext, type ReactNode } from "react";

import { IcoonKnop } from "@/components/ui/Button";
import { HANDELINGEN, type Handeling, type PaneelPlek } from "@/lib/paneelBediening";

/** Wat een paneel over zijn plek weet (besluit gebruiker 23 nov 2026): één context in plaats van losse contexten per
 *  onderwerp. De werkplek en het zijpaneel vullen hem; een paneel leest hem met `usePaneel()` en zegt zelf alleen wat het
 *  is. Zonder provider staat het paneel op een `pagina`: geen bediening van een paneel. */
export interface PaneelOmgeving {
  plek: PaneelPlek;
  /** Groot of klein zetten (het zijpaneel of de sheet); weg waar dat niet kan. */
  zetVergroot?: (v: boolean) => void;
  inklappen?: () => void;
  uitklappen?: () => void;
  /** Sluit wat er open is (de actieve tab); de enige ✕. */
  sluiten?: () => void;
  /** Een inhoud die Escape zelf laag voor laag afpelt (de graaf) claimt hem, zodat het paneel hem niet eerst wegvangt. */
  claimEscape?: (ja: boolean) => void;
  /** Het gesprek waarin het paneel openstaat: *Openen als pagina* neemt het mee (`?vanuit=`). */
  gesprekId?: string | null;
  /** De tabrij op een telefoon, boven de kop van de sheet (alleen bij twee of meer open items). */
  tabs?: ReactNode;
}

const PAGINA: PaneelOmgeving = { plek: "pagina" };
export const PaneelContext = createContext<PaneelOmgeving>(PAGINA);

export function usePaneel(): PaneelOmgeving {
  return useContext(PaneelContext);
}

/** De enige knop voor een handeling van het paneel: label, titel en icoon uit `HANDELINGEN`. */
export function PaneelKnop({ handeling, onClick, size = "sm" }: { handeling: Handeling; onClick?: () => void; size?: "xs" | "sm" }) {
  const h = HANDELINGEN[handeling];
  return (
    <IcoonKnop size={size} aria-label={h.label} title={h.titel} onClick={onClick} data-paneel-knop={handeling}>
      <svg width={16} height={16} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round"
        strokeLinejoin="round" aria-hidden><path d={h.icoon} /></svg>
    </IcoonKnop>
  );
}

/** Wat een knop doet op deze plek; `undefined` als de omgeving het niet kan (dan geen knop). */
export function actieVan(handeling: Handeling, p: PaneelOmgeving): (() => void) | undefined {
  switch (handeling) {
    case "vergroten": return p.zetVergroot && (() => p.zetVergroot!(true));
    case "verkleinen": return p.zetVergroot && (() => p.zetVergroot!(false));
    case "inklappen": return p.inklappen;
    case "uitklappen": return p.uitklappen;
    case "sluiten": return p.sluiten;
  }
}
