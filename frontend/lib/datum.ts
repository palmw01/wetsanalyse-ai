/** "5 nov 2026, 10:42", in Nederlandse tijd: een moment in een beheerlijst. Leeg blijft leeg, een onleesbare datum ook. */
export function datumTijd(iso: string | null | undefined): string {
  const d = new Date(iso ?? "");
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("nl-NL", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Amsterdam",
  }).replace(" om ", ", ");
}
