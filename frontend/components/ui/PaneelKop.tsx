import Link from "next/link";

import { knopKlasse } from "@/components/ui/Button";

/** Het kruisje rechtsboven in elk paneel en venster: één icoon, één lijndikte, één plek. */
export function SluitKnop({ onSluit, className = "" }: { onSluit: () => void; className?: string }) {
  return (
    <button type="button" onClick={onSluit} aria-label="Sluiten"
      // `-mr-1` haalt de optische ruimte van het icoon weg, zodat het kruisje uitlijnt met de kantlijn.
      className={`focus-ring -mr-1 shrink-0 rounded-full p-1.5 text-muted transition-colors hover:bg-surface hover:text-ink ${className}`}>
      <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
        <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
      </svg>
    </button>
  );
}

/** De kop van een paneel naast het gesprek (spoor I4): soort en titel, één regel met *Open volledige pagina* en
 *  *Vraag Lex* als pillen, en het kruisje rechtsboven – voor het artefact-, het werkgebied- en het contextpaneel.
 *  Extra handelingen (status, exporteren, verwijderen) staan op een eigen regel rechts, onder het kruisje, zodat
 *  dat niet meewandelt als de ruimte krap wordt. */
export function PaneelKop({ soort, titel, pagina, lex, acties, onSluit }: {
  soort: string;
  titel: string;
  /** Waar *Open volledige pagina* heen gaat; zonder geen knop (de rondleiding). */
  pagina?: string;
  /** De *Vraag Lex*-knop van het object, als die er is. */
  lex?: React.ReactNode;
  acties?: React.ReactNode;
  onSluit?: () => void;
}) {
  return (
    <div data-paneel-kop className="flex shrink-0 flex-col gap-2 border-b border-line px-5 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-muted">{soort}</p>
          <h2 className="truncate font-display text-base font-semibold text-lint">{titel}</h2>
        </div>
        {onSluit && <SluitKnop onSluit={onSluit} />}
      </div>
      {(pagina || lex) && (
        <div className="flex flex-wrap items-center gap-2">
          {pagina && <Link href={pagina} className={`focus-ring ${knopKlasse("secondary", "xs")}`}>Open volledige pagina</Link>}
          {lex}
        </div>
      )}
      {acties && <div data-tour="artefact-acties" className="flex flex-wrap items-center justify-end gap-2">{acties}</div>}
    </div>
  );
}
