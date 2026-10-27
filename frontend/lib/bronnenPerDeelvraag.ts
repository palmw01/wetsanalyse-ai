// Hulpjes voor de bronnen per deelvraag (spoor K/L, `components/werkgebieden/BronnenBijDeelvraag`): een label als
// bepaling en regeling, en de andere deelvragen waar een bron bij hoort. De groepering zelf komt uit de
// bronselectie van de api (`lib/bronselectie.ts`).
//
// Pure functies, zodat vitest ze zonder DOM toetst (lib/bronnenPerDeelvraag.test.ts).

/** Begint een stuk label met een plek in een regeling ("Artikel 9", "Hoofdstuk V", "art. 3.1")? */
const PLEK = /^(artikel|art\.|lid|onderdeel|hoofdstuk|afdeling|paragraaf|subparagraaf|titeldeel|titel\s+\d|divisie|bepaling|bijlage|boek|deel\s+\d)/i;

/** Een label als bepaling en regeling, voor een rij zoals in de mock-up: de bepaling als titel, de regeling
 *  eronder. Twee vormen komen voor: van Lex "Artikel 9, lid 1 – Invorderingswet 1990" (regeling achteraan) en van
 *  de api "Invorderingswet 1990 – Artikel 9, Lid 1" (regeling vooraan, soms met een opschrift erachter). */
export function bepalingEnRegeling(label: string): { bepaling: string; regeling: string } {
  const delen = label.split(" – ").map((d) => d.trim()).filter(Boolean);
  if (delen.length < 2) return { bepaling: label, regeling: "" };
  if (PLEK.test(delen[0])) return { bepaling: delen.slice(0, -1).join(" – "), regeling: delen[delen.length - 1] };
  if (PLEK.test(delen[1])) return { bepaling: delen.slice(1).join(" – "), regeling: delen[0] };
  return { bepaling: label, regeling: "" };
}

/** "ook bij deelvraag 2", "ook bij deelvragen 2 en 3"; leeg als de bron alleen hier hoort. */
export function ookBijZin(ook: readonly number[]): string {
  if (!ook.length) return "";
  if (ook.length === 1) return `ook bij deelvraag ${ook[0]}`;
  return `ook bij deelvragen ${ook.slice(0, -1).join(", ")} en ${ook[ook.length - 1]}`;
}
