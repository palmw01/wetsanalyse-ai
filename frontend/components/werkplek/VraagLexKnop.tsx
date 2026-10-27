"use client";

import Link from "next/link";
import { createContext, useContext } from "react";

import { KNOP_XS, knopKlasse } from "@/components/ui/Button";
import { SOORT_LABEL, vraagUrl, type ObjectSoort, type Onderwerp } from "@/lib/vraagLex";

type Object_ = Extract<Onderwerp, { soort: ObjectSoort }>;

/** In de werkplek: zet het onderwerp boven het invoerveld (`WerkplekClient`). Daarbuiten is er geen
 *  provider en wordt de knop een link naar een vers gesprek met het onderwerp klaar (`vraagUrl`). */
export const VraagLexContext = createContext<((o: Onderwerp) => void) | null>(null);

const KLASSE = `${KNOP_XS} border-line text-lint hover:border-lint hover:bg-lint/5`;

/** *Vraag Lex* over één object (F3b): één knop voor elke soort, met het object als onderwerp. Een link
 *  buiten de werkplek, zodat de bewaker van niet-bewaarde wijzigingen hem ziet (`useOnbewaardBewaker`). */
/** De ene knop op een detailpagina (spoor G2, de mock-up): primair, met de tekst *Bespreek met Lex*. */
const PRIMAIR = knopKlasse("primary", "sm");

export function VraagLexKnop({ onderwerp, naam: eigenNaam, tekst: eigenTekst, primair = false, alleenInGesprek = false, className = "" }: {
  onderwerp: Object_;
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
  const naam = eigenNaam ?? `Vraag Lex over ${SOORT_LABEL[onderwerp.soort].toLowerCase()}${onderwerp.label ? `: ${onderwerp.label}` : ""}`;
  if (kies) {
    return (
      <button type="button" data-vraag-lex={onderwerp.veld ? "veld" : onderwerp.soort} data-vraag-veld={onderwerp.veld} aria-label={naam} className={klasse}
        onClick={() => kies(onderwerp)}>
        {tekst}
      </button>
    );
  }
  return (
    <Link href={vraagUrl(onderwerp)} data-vraag-lex={onderwerp.veld ? "veld" : onderwerp.soort} data-vraag-veld={onderwerp.veld} aria-label={naam} className={klasse}>
      {tekst}
    </Link>
  );
}
