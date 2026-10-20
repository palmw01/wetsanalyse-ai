"use client";

import Link from "next/link";
import { createContext, useContext } from "react";

import { SOORT_LABEL, vraagUrl, type ObjectSoort, type Onderwerp } from "@/lib/vraagLex";

type Object_ = Extract<Onderwerp, { soort: ObjectSoort }>;

/** In de werkplek: zet het onderwerp boven het invoerveld (`WerkplekClient`). Daarbuiten is er geen
 *  provider en wordt de knop een link naar een vers gesprek met het onderwerp klaar (`vraagUrl`). */
export const VraagLexContext = createContext<((o: Onderwerp) => void) | null>(null);

const KLASSE = "focus-ring inline-flex min-h-[24px] shrink-0 items-center rounded-full border border-line px-2.5 py-0.5 "
  + "text-xs font-medium text-lint transition-colors hover:border-lint hover:bg-lint/5 coarse:min-h-[44px]";

/** *Vraag Lex* over één object (F3b): één knop voor elke soort, met het object als onderwerp. Een link
 *  buiten de werkplek, zodat de bewaker van niet-bewaarde wijzigingen hem ziet (`useOnbewaardBewaker`). */
export function VraagLexKnop({ onderwerp, className = "" }: { onderwerp: Object_; className?: string }) {
  const kies = useContext(VraagLexContext);
  const naam = `Vraag Lex over ${SOORT_LABEL[onderwerp.soort].toLowerCase()}${onderwerp.label ? `: ${onderwerp.label}` : ""}`;
  if (kies) {
    return (
      <button type="button" data-vraag-lex={onderwerp.soort} aria-label={naam} className={`${KLASSE} ${className}`}
        onClick={() => kies(onderwerp)}>
        Vraag Lex
      </button>
    );
  }
  return (
    <Link href={vraagUrl(onderwerp)} data-vraag-lex={onderwerp.soort} aria-label={naam} className={`${KLASSE} ${className}`}>
      Vraag Lex
    </Link>
  );
}
