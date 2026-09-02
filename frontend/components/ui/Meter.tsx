/** Een voortgangs-/verbruiksbalk.
 *
 *  Geëxtraheerd uit `ReviewQueue`, die hem als eerste had; het tokenbudget is de tweede gebruiker en
 *  twee losse balken zouden vroeg of laat uit elkaar lopen. Wat er bij het extraheren is bijgekomen:
 *  een verplicht `label` (de oorspronkelijke `role="progressbar"` had geen toegankelijke naam) en de
 *  drempelkleuren.
 */

export type MeterToon = "voortgang" | "verbruik";

/** Vanaf hier kleurt een verbruiksmeter oranje. Gelijk aan `WAARSCHUWINGSDREMPEL` in de api —
 *  de balk moet niet op een ander moment verkleuren dan waarop de melding verschijnt. */
export const METER_WAARSCHUWING = 90;

function vulkleur(percentage: number, toon: MeterToon, afgerond: boolean): string {
  if (toon === "voortgang") return afgerond ? "bg-succes" : "bg-lint";
  if (percentage >= 100) return "bg-fout";
  if (percentage >= METER_WAARSCHUWING) return "bg-waarschuwing";
  return "bg-lint";
}

export function Meter({
  percentage,
  label,
  toon = "voortgang",
  afgerond = false,
  dun = false,
  className = "",
}: {
  /** 0–100. Wordt geklemd, zodat een overschrijding de balk niet buiten zijn baan duwt. */
  percentage: number;
  /** Toegankelijke naam, bv. "Tokenverbruik" of "Voortgang review". */
  label: string;
  /** `verbruik` kleurt mee met de drempels; `voortgang` blijft lintblauw (groen als afgerond). */
  toon?: MeterToon;
  afgerond?: boolean;
  /** Dunner, voor een plek waar de balk bijzaak is (de sidebar). */
  dun?: boolean;
  className?: string;
}) {
  const perc = Math.max(0, Math.min(100, Math.round(percentage)));
  return (
    <div
      className={`${dun ? "h-1" : "h-1.5"} overflow-hidden rounded-full bg-line/60 ${className}`}
      role="progressbar"
      aria-label={label}
      aria-valuenow={perc}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={`h-full rounded-full transition-all ${vulkleur(perc, toon, afgerond)}`}
        style={{ width: `${perc}%` }}
      />
    </div>
  );
}
