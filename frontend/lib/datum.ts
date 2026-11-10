/** "5 nov 2026, 10:42", in Nederlandse tijd: een moment in een beheerlijst. Leeg blijft leeg, een onleesbare datum ook. */
export function datumTijd(iso: string | null | undefined): string {
  const d = new Date(iso ?? "");
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("nl-NL", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Amsterdam",
  }).replace(" om ", ", ");
}

const MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
  "november", "december"];

/** "2026-10-16" → "16 oktober 2026": een datum uit een bron (de metadata van een Kamerstuk), zonder tijdzone. Iets anders
 *  blijft zoals het is. */
export function datumTekst(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? "");
  if (!m || +m[2] < 1 || +m[2] > 12) return iso ?? "";
  return `${+m[3]} ${MAANDEN[+m[2] - 1]} ${m[1]}`;
}
