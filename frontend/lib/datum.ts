/** De datums en tijden van Lex (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md` §8):
 *  alles in Nederlandse tijd, in een paar vaste vormen. Formatteer nergens anders zelf (`app/datum.test.ts`). Leeg blijft
 *  leeg, een onleesbare datum ook. */
const TIJDZONE = "Europe/Amsterdam";

function moment(iso: string | null | undefined): Date | null {
  const d = new Date(iso ?? "");
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "5 nov 2026, 10:42": een moment in een lijst (historie, revisies, beslissingen, tokens). */
export function datumTijd(iso: string | null | undefined): string {
  const d = moment(iso);
  if (!d) return "";
  return d.toLocaleString("nl-NL", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: TIJDZONE,
  }).replace(" om ", ", ");
}

/** "5 nov 2026": de dag waarop iets gebeurde (gewijzigd, verwijderd, beoordeeld). */
export function datumKort(iso: string | null | undefined): string {
  const d = moment(iso);
  return d ? d.toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric", timeZone: TIJDZONE }) : "";
}

/** "5 november 2026": een datum in lopende tekst (een bericht, een aanvraag). */
export function datumLang(iso: string | null | undefined): string {
  const d = moment(iso);
  return d ? d.toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric", timeZone: TIJDZONE }) : "";
}

/** "5 nov, 10:42": een moment van dit jaar, waar het jaar niets toevoegt (een versie, een run). */
export function momentKort(iso: string | null | undefined): string {
  const d = moment(iso);
  if (!d) return "";
  return d.toLocaleString("nl-NL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: TIJDZONE })
    .replace(" om ", ", ");
}

/** "10:42": alleen de tijd (een beslissing van vandaag). */
export function tijd(iso: string | null | undefined): string {
  const d = moment(iso);
  return d ? d.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit", timeZone: TIJDZONE }) : "";
}

/** Vandaag "10:42", anders "5 nov": de gesprekkenlijst. */
export function tijdOfDag(iso: string | null | undefined, nu: Date = new Date()): string {
  const d = moment(iso);
  if (!d) return "";
  const dag = (x: Date) => x.toLocaleDateString("nl-NL", { timeZone: TIJDZONE });
  return dag(d) === dag(nu) ? tijd(iso) : d.toLocaleDateString("nl-NL", { day: "numeric", month: "short", timeZone: TIJDZONE });
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
