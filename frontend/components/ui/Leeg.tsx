import type { ReactNode } from "react";

/** Een lege lijst (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md` §4): "Nog geen
 *  annotaties", "Geen begrip dat hierop past". Op een pagina en in een tab (een overzicht, de elementen) een kader met een
 *  gestippelde rand (`kader`), in een paneel, een menu of een beheerlijst een regel. `klein` is de maat van een paneelrij.
 *  `className` is alleen voor de ruimte eromheen. `app/leeg.test.ts` bewaakt dat er geen eigen lege toestand naast komt. */
export function Leeg({ id, kader = false, klein = false, className = "", children, ...data }: {
  /** Voor `aria-describedby` (de lege commandolijst). */
  id?: string;
  kader?: boolean;
  klein?: boolean;
  className?: string;
  children: ReactNode;
} & Record<`data-${string}`, string | number | undefined>) {
  const maat = klein ? "text-xs" : "text-sm";
  const vorm = kader ? `rounded-kaart border border-dashed border-line px-3 text-center ${klein ? "py-4" : "py-6"}` : "";
  return <p id={id} className={`${vorm} ${maat} text-muted ${className}`.trim()} {...data}>{children}</p>;
}

/** Een veld zonder waarde, midden in een regel of een kaart ("Nog geen definitie."): grijs, niet cursief en niet vet. */
export function LeegWaarde({ children }: { children: ReactNode }) {
  return <span className="font-normal text-muted">{children}</span>;
}
