// Eén manier van bewerken (4 nov 2026, naar het voorbeeld van Claude: een bericht ter plekke aanpassen). De tekst
// wordt op dezelfde plek een invoerveld, met daaronder rechts *Annuleren* · *Opslaan*. Escape annuleert,
// Ctrl/⌘+Enter slaat op, en Enter in een veld van één regel ook. Pure regels, zodat ze zonder DOM te testen zijn
// (lib/bewerken.test.ts); `components/ui/Bewerkbaar.tsx` draagt de vorm.

export type BewerkToets = "annuleren" | "opslaan" | null;

/** Wat een toets in een bewerkveld doet. `regel`: een veld van één regel (Enter slaat op); in een tekstvak is Enter
 *  een nieuwe regel en slaat alleen Ctrl/⌘+Enter op. Tijdens het samenstellen van een teken (IME) doet een toets
 *  niets. */
export function bewerkToets(e: { key: string; ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean; isComposing?: boolean },
  regel: boolean): BewerkToets {
  if (e.isComposing) return null;
  if (e.key === "Escape") return "annuleren";
  if (e.key !== "Enter") return null;
  if (e.ctrlKey || e.metaKey) return "opslaan";
  return regel && !e.shiftKey ? "opslaan" : null;
}

/** Is er iets veranderd? Witruimte aan de randen telt niet; sleutelvolgorde ook niet. */
export function isGewijzigd<T>(begin: T, nu: T): boolean {
  const norm = (v: unknown): unknown => typeof v === "string" ? v.trim()
    : Array.isArray(v) ? v.map(norm)
    : v && typeof v === "object" ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b)).map(([k, x]) => [k, norm(x)]))
    : v;
  return JSON.stringify(norm(begin)) !== JSON.stringify(norm(nu));
}
