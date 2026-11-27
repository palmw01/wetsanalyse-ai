"use client";

import { useState } from "react";

/** De ene versleepbare scheiding tussen twee vlakken (een verticale lijn): het zijpaneel naast het gesprek, en tekst en
 *  lijst naast elkaar (`TekstEnLijst`). Slepen met de muis of de vinger, de pijltjes als hij de focus heeft (WCAG
 *  2.1.1), en dubbelklik zet de standaard terug. Wat een stap of een positie betekent, beslist de eigenaar (`onSleep`,
 *  `onLos`, `onToets`); dit component kent alleen het gebaar. */
export function Scheiding({ label, waarde, min, max, onSleep, onLos, onToets, onStandaard, className = "", ...data }: {
  /** De voorleesnaam ("Breedte van het paneel"). */
  label: string;
  /** De huidige waarde, met de grenzen, voor een schermlezer (`aria-valuenow`). */
  waarde: number;
  min: number;
  max: number;
  /** Tijdens het slepen, met de x-positie van de wijzer. */
  onSleep: (clientX: number) => void;
  /** Bij loslaten: dan bewaart de eigenaar. */
  onLos: (clientX: number) => void;
  /** Een toets met de focus erop; `true` als de eigenaar hem gebruikte (dan gaat hij niet door). */
  onToets: (toets: string) => boolean;
  onStandaard: () => void;
  /** Plaatsing en maat; de kleur en de cursor zijn van dit component. */
  className?: string;
  [data: `data-${string}`]: string | boolean | undefined;
}) {
  const [sleept, setSleept] = useState(false);

  function begin(e: React.PointerEvent<HTMLDivElement>) {
    if (e.button !== 0) return;
    e.preventDefault();
    const doel = e.currentTarget;
    doel.setPointerCapture(e.pointerId);
    setSleept(true);
    const beweeg = (ev: PointerEvent) => onSleep(ev.clientX);
    const los = (ev: PointerEvent) => {
      doel.removeEventListener("pointermove", beweeg);
      doel.removeEventListener("pointerup", los);
      doel.removeEventListener("pointercancel", los);
      setSleept(false);
      onLos(ev.clientX);
    };
    doel.addEventListener("pointermove", beweeg);
    doel.addEventListener("pointerup", los);
    doel.addEventListener("pointercancel", los);
  }

  return (
    // Een focusbare separator met aria-valuenow is een ARIA-splitter (WAI-ARIA window splitter): interactief, dus tabIndex.
    <div role="separator" aria-orientation="vertical" aria-label={label} tabIndex={0} /* NOSONAR: ARIA-splitter */
      aria-valuemin={min} aria-valuemax={max} aria-valuenow={Math.round(waarde)} {...data}
      onPointerDown={begin} onDoubleClick={onStandaard}
      onKeyDown={(e) => { if (onToets(e.key)) e.preventDefault(); }}
      className={`focus-ring cursor-col-resize touch-none rounded-sm hover:bg-lint/20 ${sleept ? "bg-lint/30" : ""} ${className}`} />
  );
}
