import type { DetailsHTMLAttributes, ReactNode } from "react";

import { ChevronOmlaag } from "@/components/ui/Icoon";

/** Hoe een uitklap eruitziet:
 *  - `kader`: een eigen blok in een paneel (*Historie*, *Dekking*), met een lichte rand;
 *  - `regel`: een kleine grijze regel onder een rij of voorstel (*Waarom stelt Lex dit voor?*);
 *  - `sectie`: een kop van een deel van een lijst (*Al besloten (3)*), in lintblauw;
 *  - `actie`: een woord dat iets openklapt op de plek waar je werkt (*Waarom?* op de reviewkaart), in lintblauw, met
 *    een raakvlak van 44 px op een aanraakscherm. */
export type UitklapVorm = "kader" | "regel" | "sectie" | "actie";

const DETAILS: Record<UitklapVorm, string> = {
  kader: "rounded-kaart border border-line bg-surface/60 px-3 py-2 text-sm",
  regel: "text-xs",
  sectie: "text-sm",
  actie: "text-xs",
};

const SUMMARY: Record<UitklapVorm, string> = {
  kader: "text-xs font-medium text-muted",
  regel: "text-xs text-muted hover:text-ink",
  sectie: "text-sm font-semibold text-lint",
  actie: "min-h-[24px] text-xs text-lint coarse:min-h-[44px]",
};

/** Een ingeklapt blok (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md` §6): een
 *  `<details>` met een chevron die meedraait, nooit het driehoekje van de browser (dat ziet er per platform anders uit,
 *  zie *Symbolen zijn iconen*). De chevron draait op de dichtstbijzijnde `<details>`, dus een uitklap in een uitklap
 *  draait niet mee met de buitenste. `className` is alleen voor de ruimte eromheen; `onToggle`, `open` en `data-`
 *  gaan door naar de `<details>`. `app/uitklap.test.ts` bewaakt dat er geen eigen `<details>` naast komt. */
export function Uitklap({ samenvatting, vorm = "regel", className = "", children, ...rest }: {
  samenvatting: ReactNode;
  vorm?: UitklapVorm;
  className?: string;
  children?: ReactNode;
} & Omit<DetailsHTMLAttributes<HTMLElement>, "className" | "children"> & Record<`data-${string}`, string | number | undefined>) {
  return (
    <details {...rest} className={`${DETAILS[vorm]} ${className}`.trim()}>
      <summary className={`focus-ring ${vorm === "actie" ? "inline-flex" : "flex"} cursor-pointer list-none items-center gap-1.5 rounded [&::-webkit-details-marker]:hidden ${SUMMARY[vorm]}`}>
        <ChevronOmlaag className="shrink-0 -rotate-90 transition-transform [[open]>summary>&]:rotate-0" />
        <span className="min-w-0">{samenvatting}</span>
      </summary>
      {children}
    </details>
  );
}
