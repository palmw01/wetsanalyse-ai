/** Pure helpers rond het tokenbudget: opmaak en drempels.
 *
 *  Bewust los van de componenten: vitest draait hier node-only en rendert geen React, dus alles wat
 *  te testen valt hoort in `lib/`. De drempel zelf komt van de server mee (`waarschuwing`); de
 *  constante hier is er voor de meterkleur en moet dezelfde waarde houden.
 */

import type { Verbruiksstand } from "./types";

/** Gelijk aan `WAARSCHUWINGSDREMPEL` in de api. */
export const WAARSCHUWINGSDREMPEL = 90;

/** "437.500" – grote getallen leesbaar, zonder eenheid (die zet de aanroeper erbij). */
export function tokens(aantal: number): string {
  return new Intl.NumberFormat("nl-NL").format(Math.max(0, Math.round(aantal)));
}

/** Compact voor krappe plekken: "438k", "1,2 mln". */
export function tokensKort(aantal: number): string {
  const n = Math.max(0, Math.round(aantal));
  if (n >= 1_000_000) return `${new Intl.NumberFormat("nl-NL", { maximumFractionDigits: 1 }).format(n / 1_000_000)} mln`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}k`;
  return String(n);
}

/** "maandag 9 september om 14:00" – de resetdatum zoals hij in beeld komt. */
export function resetdatum(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const datum = d.toLocaleDateString("nl-NL", { weekday: "long", day: "numeric", month: "long" });
  const tijd = d.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });
  return `${datum} om ${tijd}`;
}

/** Hoeveel KALENDERdagen tot de reset; 0 = vandaag nog.
 *
 *  Bewust op kalenderdagen en niet op blokken van 24 uur: een reset vanavond om 23:00 is voor de
 *  lezer "vandaag", ook al is dat over elf uur en zou naar boven afronden er "morgen" van maken.
 */
export function dagenTotReset(iso: string, nu: Date = new Date()): number {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 0;
  const dag = (x: Date) => Date.UTC(x.getFullYear(), x.getMonth(), x.getDate());
  return Math.max(0, Math.round((dag(d) - dag(nu)) / 86_400_000));
}

/** De regel onder de meter: "62% gebruikt · reset over 3 dagen". */
export function verbruikSamenvatting(stand: Verbruiksstand, nu: Date = new Date()): string {
  const dagen = dagenTotReset(stand.reset_op, nu);
  const wanneer = dagen === 0 ? "reset vandaag" : dagen === 1 ? "reset morgen" : `reset over ${dagen} dagen`;
  return `${stand.percentage}% gebruikt · ${wanneer}`;
}

/** Moet de waarschuwingsstrook getoond worden? De server beslist; dit is de leesbare vorm ervan. */
export function toonWaarschuwing(stand: Verbruiksstand | null): boolean {
  return Boolean(stand?.actief && stand.waarschuwing);
}
