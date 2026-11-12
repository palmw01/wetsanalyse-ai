"use client";

import type { Regel } from "@/lib/commandos";
import { MENU_PANEEL, MENU_RIJ } from "@/components/ui/Menu";

/** Het menu bij `/` in het invoerveld (`lib/commandos.ts`). Een listbox volgens het combobox-patroon: de focus blijft in
 *  het veld, dat `aria-activedescendant` naar de actieve regel zet. ↑/↓, Enter, Tab en Escape handelt het veld af
 *  (`WerkplekClient`); hier alleen de regels en de muis of tik. Geen eigen toetsen: `/` is tekst, geen sneltoets. */
export function CommandoMenu({ id, regels, actief, onKies, onActief }: {
  id: string;
  /** `[]`: geen commando – dat zegt het menu, en Enter verstuurt de tekst als vraag. */
  regels: Regel[];
  actief: number;
  onKies: (regel: Regel) => void;
  onActief: (index: number) => void;
}) {
  return (
    <div className={`mb-1 ${MENU_PANEEL}`} data-commandomenu>
      {regels.length ? (
        <ul id={id} role="listbox" aria-label="Commando's" className="max-h-[min(18rem,40dvh)] overflow-y-auto overscroll-contain">
          {regels.map((r, i) => (
            <li key={r.sleutel} id={`${id}-${i}`} role="option" aria-selected={i === actief} aria-disabled={r.uit ? true : undefined}
              data-commando={r.label}
              // `mousedown` met preventDefault: de focus blijft in het veld, zoals bij elke combobox.
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => onActief(i)}
              onClick={() => onKies(r)}
              // Eén regel per commando, zoals het slash-menu van Claude: de naam, dan de hulp die afkapt als hij niet past
              // (voluit in de tooltip en voor een schermlezer). Waarom het nu niet kan, staat apart en kapt nooit af.
              title={r.uit ? `${r.hulp} · ${r.uit}` : r.hulp}
              className={`${MENU_RIJ} cursor-pointer gap-3 ${i === actief ? "bg-surface" : ""} ${r.uit ? "opacity-60" : ""}`}>
              <span className="shrink-0 font-mono text-[13px] text-ink">{r.label}</span>
              <span className="min-w-0 flex-1 truncate text-[13px] text-muted" data-commando-hulp>{r.hulp}</span>
              {r.uit && <span className="shrink-0 text-[13px] text-ink">{r.uit}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p id={id} className="px-2.5 py-1.5 text-[13px] text-muted" data-geen-commando>
          Geen commando – Enter verstuurt je tekst als vraag. Typ <span className="font-mono">/help</span> voor de lijst.
        </p>
      )}
      <p className="sr-only" aria-live="polite">
        {regels.length ? `${regels.length} ${regels.length === 1 ? "commando" : "commando's"}` : "Geen commando"}
      </p>
    </div>
  );
}
