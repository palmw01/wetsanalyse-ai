/** De versiekiezer van een artefact (deel 2 van de artefacten, besluit gebruiker 4 nov 2026, naar het voorbeeld van
 *  Claude): de versies zijn de standen direct na elke beurt van Lex (api `artefact_versies`), en daarachter *Nu*, de
 *  stand van nu. Een oudere versie is alleen te lezen. De rekenkern; het component is `components/ui/VersieKiezer`.
 *
 *  Een plek in de kiezer is een index in `[versie 1, …, versie m, Nu]`: `m` (= het aantal versies) is *Nu*. */

/** Waar de kiezer begint bij de versie van een chip: de nieuwste versie opent als *Nu* (live en bewerkbaar – de chip
 *  van de laatste beurt is gewoon het werk), een oudere als die versie. Een id dat er niet (meer) is: *Nu*. */
export function beginPlek(ids: readonly string[], versie: string | undefined): number {
  const i = versie ? ids.indexOf(versie) : -1;
  return i === -1 || i === ids.length - 1 ? ids.length : i;
}

export function isNu(plek: number, aantal: number): boolean {
  return plek >= aantal;
}

/** Wat de kiezer tussen ‹ en › zegt. */
export function plekLabel(plek: number, aantal: number): string {
  return isNu(plek, aantal) ? "Nu" : `Versie ${plek + 1} van ${aantal}`;
}

/** "5 nov, 10:42", in Nederlandse tijd; leeg bij een onleesbare datum. */
export function versieTijd(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("nl-NL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Amsterdam" })
    .replace(" om ", ", ");
}
