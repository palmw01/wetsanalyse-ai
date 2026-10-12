"use client";

/** De koppeling tussen de tekst van een antwoord en de graaf in het paneel. Het overzichtsblok wijst
 *  een knoop aan (hover, focus) en kiest hem (klik); de graaf die openstaat voert het uit.
 *
 *  Twee helften: de graaf zet zijn handelingen in een ref (`GraafKoppeling`), de werkplek geeft via
 *  context een stabiel doorgeefluik aan de thread. Zo hoeft geen `memo`-rij opnieuw te renderen als het
 *  paneel opent of sluit, en weet een klik op het moment zelf of er een graaf is. */
import { createContext, useContext } from "react";

export interface GraafKoppeling {
  /** Een knoop uitlichten, of met `null` niets. */
  wijs: (id: string | null) => void;
  /** Een knoop kiezen en in beeld brengen. `false` = er staat geen graaf open: doe dan het gewone. */
  kies: (id: string) => boolean;
}

const GEEN: GraafKoppeling = { wijs: () => {}, kies: () => false };
export const GraafKoppelingContext = createContext<GraafKoppeling>(GEEN);
export const useGraafKoppeling = () => useContext(GraafKoppelingContext);
