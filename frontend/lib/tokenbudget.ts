/** Pure helpers rond het tokenbudget: opmaak en drempels.
 *
 *  Bewust los van de componenten: vitest draait hier node-only en rendert geen React, dus alles wat
 *  te testen valt hoort in `lib/`. De drempel zelf komt van de server mee (`waarschuwing`); de
 *  constante hier is er voor de meterkleur en moet dezelfde waarde houden.
 */

import type { Verbruiksstand, VerbruikRegel } from "./types";

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

/** "maandag 9 september om 14:00" – de resetdatum zoals hij in beeld komt.
 *
 *  Met `tijdzone` (die van het budgetbeleid) in die zone; zonder in die van de browser. */
export function resetdatum(iso: string, tijdzone?: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const zone = tijdzone ? { timeZone: tijdzone } : {};
  const datum = d.toLocaleDateString("nl-NL", { weekday: "long", day: "numeric", month: "long", ...zone });
  const tijd = d.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit", ...zone });
  return `${datum} om ${tijd}`;
}

/** De weekdagen in de volgorde van de api (`datetime.weekday()`: 0 = maandag). */
export const WEEKDAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"] as const;

/** Hoe vaak het budget weer vol is. `dagen` is een ander aantal dagen dat via de api is gezet: het scherm laat het
 *  staan, maar biedt het niet als nieuwe keuze aan. */
export type PeriodeSoort = "dag" | "week" | "maand" | "dagen";

/** Het deel van het beleid dat de periode bepaalt. */
export interface Periode {
  periode_dagen: number;
  periode_maanden?: number;
}

export function periodeSoort(p: Periode): PeriodeSoort {
  if ((p.periode_maanden ?? 0) > 0) return "maand";
  if (p.periode_dagen === 1) return "dag";
  if (p.periode_dagen === 7) return "week";
  return "dagen";
}

/** "Per week", "Per maand", "Per 3 maanden", "Per 30 dagen". */
export function periodeLabel(p: Periode): string {
  const maanden = p.periode_maanden ?? 0;
  if (maanden > 1) return `Per ${maanden} maanden`;
  if (maanden === 1) return "Per maand";
  if (p.periode_dagen === 1) return "Per dag";
  if (p.periode_dagen === 7) return "Per week";
  return `Per ${p.periode_dagen} dagen`;
}

/** Wat de wandklok in `tijdzone` aanwijst op dit moment: datum, dag van de maand, weekdag (0 = maandag) en "HH:MM". */
export function wandklok(iso: string | Date, tijdzone: string): { datum: string; dag: number; weekdag: number; tijd: string } {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const delen = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: tijdzone, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(d).map((p) => [p.type, p.value]),
  );
  const datum = `${delen.year}-${delen.month}-${delen.day}`;
  // De weekdag volgt uit de kalenderdatum zelf, niet uit de tijdzone van de machine.
  const weekdag = (new Date(`${datum}T00:00:00Z`).getUTCDay() + 6) % 7;
  return { datum, dag: Number(delen.day), weekdag, tijd: `${delen.hour}:${delen.minute}` };
}

/** Een kalenderdatum ("2026-11-25") plus of min een aantal dagen, zonder tijdzone. */
function plusDagen(datum: string, dagen: number): string {
  const d = new Date(`${datum}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + dagen);
  return d.toISOString().slice(0, 10);
}

// De ankers hieronder zijn allemaal de VORIGE keer dat het gekozen moment er was, en nooit de volgende: een anker in
// de toekomst laat tot dat moment niets meetellen (`venster_start` in de api). Het resultaat is wandkloktijd zonder
// tijdzone ("2026-11-23T00:00:00"); de api leest dat in de tijdzone van het beleid, dus zomertijd speelt hier niet.

/** Het anker voor "elke dag om `tijd`". */
export function ankerVoorDag(tijd: string, tijdzone: string, nu: Date = new Date()): string {
  const hier = wandklok(nu, tijdzone);
  return `${hier.tijd < tijd ? plusDagen(hier.datum, -1) : hier.datum}T${tijd}:00`;
}

/** Het anker voor "elke `weekdag` om `tijd`". */
export function ankerVoorWeekdag(weekdag: number, tijd: string, tijdzone: string, nu: Date = new Date()): string {
  const hier = wandklok(nu, tijdzone);
  let terug = (hier.weekdag - weekdag + 7) % 7;
  if (terug === 0 && hier.tijd < tijd) terug = 7;
  return `${plusDagen(hier.datum, -terug)}T${tijd}:00`;
}

/** Het anker voor "elke maand op de `dag`e om `tijd`". Het scherm biedt 1–28 aan, zodat elke maand die dag heeft. */
export function ankerVoorMaanddag(dag: number, tijd: string, tijdzone: string, nu: Date = new Date()): string {
  const hier = wandklok(nu, tijdzone);
  let [jaar, maand] = hier.datum.split("-").map(Number);
  if (hier.dag < dag || (hier.dag === dag && hier.tijd < tijd)) {
    maand -= 1;
    if (maand === 0) { maand = 12; jaar -= 1; }
  }
  const twee = (n: number) => String(n).padStart(2, "0");
  return `${jaar}-${twee(maand)}-${twee(dag)}T${tijd}:00`;
}

/** Het anker voor een gekozen datum en tijd, als wandkloktijd zonder tijdzone. */
export function ankerVoorDatum(datum: string, tijd: string): string {
  return `${datum}T${tijd}:00`;
}

/** "Eén gebruiker zit" / "3 gebruikers zitten" in het nieuwe venster boven zijn budget. */
export function bovenBudgetMelding(userids: string[]): string {
  if (userids.length === 0) return "";
  const wie = userids.length === 1 ? "Eén gebruiker zit" : `${userids.length} gebruikers zitten`;
  return `${wie} in het nieuwe venster boven ${userids.length === 1 ? "zijn" : "hun"} budget: ${userids.join(", ")}.`;
}

/** "Analist" – een rol als begin van een regel. */
export function rolLabel(rol: string): string {
  return rol.charAt(0).toUpperCase() + rol.slice(1);
}

/** "Budget van de rol analist: 300.000 tokens" – welke waarde geldt, en waar die vandaan komt. */
export function budgetHerkomst(regel: Pick<VerbruikRegel, "budget" | "rol">): string {
  return `Budget van de rol ${regel.rol}: ${tokens(regel.budget)} tokens`;
}

/** "Gereset op maandag 9 september om 14:00 door wpalm"; leeg als dit venster niemand resette. */
export function resetRegel(regel: Pick<VerbruikRegel, "gereset_op" | "gereset_door">): string {
  if (!regel.gereset_op) return "";
  return `Gereset op ${resetdatum(regel.gereset_op)}${regel.gereset_door ? ` door ${regel.gereset_door}` : ""}`;
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

