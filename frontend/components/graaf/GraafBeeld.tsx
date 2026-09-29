"use client";

import { Min, Passend, Plus } from "@/components/ui/Icoon";

const KNOP = "focus-ring flex h-9 w-9 items-center justify-center text-muted transition-colors hover:bg-surface hover:text-lint coarse:h-11 coarse:w-11";

/** Het beeld sturen, rechtsonder in het canvas: zoals de zoomknoppen van een kaart. */
export function GraafBeeld({ onPasIn, onZoom }: { onPasIn: () => void; onZoom: (factor: number) => void }) {
  return <div role="group" aria-label="Beeld" className="pointer-events-auto flex flex-col divide-y divide-line overflow-hidden rounded-kaart border border-line bg-paper/95 shadow-kaart">
    <button type="button" className={KNOP} onClick={onPasIn} aria-label="Alles in beeld" title="Alles in beeld"><Passend /></button>
    <button type="button" className={KNOP} onClick={() => onZoom(0.7)} aria-label="Inzoomen" title="Inzoomen"><Plus /></button>
    <button type="button" className={KNOP} onClick={() => onZoom(1.4)} aria-label="Uitzoomen" title="Uitzoomen"><Min /></button>
  </div>;
}
