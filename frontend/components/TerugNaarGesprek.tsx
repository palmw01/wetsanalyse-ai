"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { ChevronOmlaag } from "@/components/ui/Icoon";
import { gesprekHref, vanuitGesprek } from "@/lib/terugNaarGesprek";

/** *Terug naar het gesprek* op een volle pagina die je vanuit het zijpaneel opende (`?vanuit=<gesprek>`, zie
 *  `lib/terugNaarGesprek.ts`). Eén strook voor elke pagina, in de root-layout: de pagina's hebben elk hun eigen schil,
 *  dus een knop per schil zou per soort verschillen. Hij zweeft onderaan in het midden, boven de inhoud, en terug in de
 *  werkplek opent het paneel weer met dezelfde tab. */
export function TerugNaarGesprek() {
  const gesprek = vanuitGesprek(usePathname(), useSearchParams());
  if (!gesprek) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center px-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
      <Link href={gesprekHref(gesprek)} data-terug-naar-gesprek
        className="focus-ring pointer-events-auto inline-flex min-h-[36px] items-center gap-1.5 rounded-knop border border-line bg-paper px-3.5 py-1.5 text-sm font-medium text-lint shadow-kaart transition-colors hover:bg-surface coarse:min-h-[44px]">
        <ChevronOmlaag className="rotate-90" /> Terug naar het gesprek
      </Link>
    </div>
  );
}
