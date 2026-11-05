"use client";

import { Sectie } from "@/components/ui/Lijst";
import { Kaart } from "@/components/ui/Pagina";

export type BegripWeergaveVorm = "pagina" | "paneel";

/** Een blok van een begrip: op de pagina een kaart, naast het gesprek een sectie zonder rand (daar staat al een paneel
 *  omheen). */
export function BegripBlok({ weergave, titel, telling, toelichting, acties, children, ...rest }: {
  weergave: BegripWeergaveVorm;
  titel: string;
  telling?: number;
  toelichting?: React.ReactNode;
  acties?: React.ReactNode;
  children: React.ReactNode;
} & Omit<React.HTMLAttributes<HTMLElement>, "title">) {
  return weergave === "pagina"
    ? <Kaart titel={titel} telling={telling} toelichting={toelichting} acties={acties} {...rest}>{children}</Kaart>
    : <Sectie titel={titel} telling={telling} toelichting={toelichting} acties={acties} niveau={3} {...rest}>{children}</Sectie>;
}
