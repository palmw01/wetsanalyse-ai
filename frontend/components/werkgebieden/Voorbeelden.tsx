"use client";

import { StatusLabel, TOON } from "@/components/ui/Lijst";
import { OORDEEL_LABEL, OORDEEL_TOON } from "@/lib/begrippen";
import type { Voorbeeld, VoorbeeldOordeel } from "@/lib/types";

const OORDELEN = Object.keys(OORDEEL_LABEL) as VoorbeeldOordeel[];

/** Het oordeel bij een voorbeeld als gekleurd label met tekst (spoor I3). */
export function OordeelLabel({ oordeel }: { oordeel: VoorbeeldOordeel }) {
  return <StatusLabel toon={OORDEEL_TOON[oordeel]} data-oordeel={oordeel}>{OORDEEL_LABEL[oordeel]}</StatusLabel>;
}

/** De voorbeelden om te lezen: één rij per voorbeeld, het oordeel rechts. */
export function VoorbeeldRijen({ voorbeelden }: { voorbeelden: readonly Voorbeeld[] }) {
  return (
    <ul className="divide-y divide-line" aria-label="Voorbeelden">
      {voorbeelden.map((v, i) => (
        <li key={i} className="flex flex-col gap-1 py-1.5 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
          <span className="min-w-0 whitespace-pre-line [overflow-wrap:anywhere]">{v.tekst}</span>
          <OordeelLabel oordeel={v.oordeel} />
        </li>
      ))}
    </ul>
  );
}

/** Het oordeel kiezen: drie gekleurde keuzepillen in plaats van een uitklaplijst (spoor I3). Echte keuzerondjes
 *  onder de pillen, dus pijltjes en de schermlezer werken zoals bij elke radiogroep. */
export function OordeelKeuze({ waarde, onKies, label, naam }: {
  waarde: VoorbeeldOordeel;
  onKies: (o: VoorbeeldOordeel) => void;
  label: string;
  /** De `name` van de keuzerondjes: uniek per voorbeeld. */
  naam: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1.5">
      {OORDELEN.map((o) => {
        const gekozen = waarde === o;
        return (
          <label key={o}
            className={`relative inline-flex min-h-[24px] cursor-pointer items-center rounded-full border px-2.5 py-0.5 text-xs font-medium coarse:min-h-[44px] has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-lint/40 ${
              gekozen ? TOON[OORDEEL_TOON[o]] : "border-line bg-paper text-muted hover:bg-surface"}`}>
            <input type="radio" name={naam} value={o} checked={gekozen} onChange={() => onKies(o)}
              className="sr-only" />
            {OORDEEL_LABEL[o]}
          </label>
        );
      })}
    </div>
  );
}
