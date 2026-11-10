"use client";

import Link from "next/link";
import { createContext, useContext } from "react";

import { KNOP_XS, knopKlasse } from "@/components/ui/Button";
import { SOORT_LABEL, chipTekst, vraagUrl, type Onderwerp } from "@/lib/vraagLex";

/** In de werkplek: zet het onderwerp boven het invoerveld (`WerkplekClient`). Daarbuiten is er geen
 *  provider en wordt de knop een link naar een vers gesprek met het onderwerp klaar (`vraagUrl`). */
export const VraagLexContext = createContext<((o: Onderwerp) => void) | null>(null);

const KLASSE = `${KNOP_XS} border-line text-lint hover:border-lint hover:bg-lint/5`;

/** *Vraag Lex* over één object (F3b; ontdubbelen PR 5): **de** knop voor elke soort – een object uit een werkgebied, een
 *  bepaling, een stuk uit een bronconnector, een markering – met het object als onderwerp. In de werkplek zet hij het
 *  onderwerp boven het invoerveld met de suggesties van zijn soort (`lib/vraagLex.ts`); daarbuiten is hij een link naar
 *  een vers gesprek (`vraagUrl`), zodat de bewaker van niet-bewaarde wijzigingen hem ziet. Een markering heeft buiten de
 *  werkplek geen weg: dan geen knop. Geen andere plek tekent een *Vraag Lex* (`app/vraagLex.test.ts`). */
/** De ene knop op een detailpagina (spoor G2, de mock-up): primair, met de tekst *Bespreek met Lex*. Een hoofdknop, dus
 *  op een telefoon over de volle breedte, ook buiten de `PaginaKop` (7 nov 2026; op de tab Bronnen stond hij smal). */
const PRIMAIR = `${knopKlasse("primary", "sm")} w-full sm:w-auto`;

export function VraagLexKnop({ onderwerp, naam: eigenNaam, tekst: eigenTekst, primair = false, alleenInGesprek = false, className = "" }: {
  onderwerp: Onderwerp;
  /** De toegankelijke naam, als de standaard ("Vraag Lex over …") niet zegt waar de knop voor is. */
  naam?: string;
  /** De zichtbare tekst, als de knop een handeling is en geen vraag (*Ga verder met deelvraag 2*, spoor K). */
  tekst?: string;
  /** *Bespreek met Lex* in de kop van een detailpagina, in plaats van de kleine *Vraag Lex*. */
  primair?: boolean;
  /** Alleen naast het gesprek, waar de knop het object klaarzet in hetzelfde gesprek. Op een pagina staat
   *  per object één *Bespreek met Lex* in de kop, niet een knop in elke rij (spoor G2, besluit 26 okt 2026). */
  alleenInGesprek?: boolean;
  className?: string;
}) {
  const tekst = eigenTekst ?? (primair ? "Bespreek met Lex" : "Vraag Lex");
  const klasse = `${primair ? PRIMAIR : KLASSE} ${className}`;
  const kies = useContext(VraagLexContext);
  if (alleenInGesprek && !kies) return null;
  // Een knop bij een leeg dossierveld heet anders dan *Vraag Lex* over het werkgebied zelf (in de kop).
  const label = onderwerp.soort === "markering" ? chipTekst(onderwerp) : onderwerp.label;
  const naam = eigenNaam ?? `Vraag Lex over ${SOORT_LABEL[onderwerp.soort].toLowerCase()}${label ? `: ${label}` : ""}`;
  const veld = "veld" in onderwerp ? onderwerp.veld : undefined;
  const data = { "data-vraag-lex": veld ? "veld" : onderwerp.soort, "data-vraag-veld": veld };
  if (kies) {
    return (
      <button type="button" {...data} aria-label={naam} className={klasse} onClick={() => kies(onderwerp)}>
        {tekst}
      </button>
    );
  }
  const href = vraagUrl(onderwerp);
  if (!href) return null;
  return <Link href={href} {...data} aria-label={naam} className={klasse}>{tekst}</Link>;
}
