// Rekenkern van de strook "Voorstellen van Lex" (spoor D, levering 3a): volgorde, wat een overname
// wordt, en de woorden waarmee de werkplek de uitkomst van de keten noemt. Puur, voor vitest.

import type { Betekenisgroep, GroepBesluit, Passage, TwijfelVraag } from "./types";

/** Groen: de wet legt het verband zelf (een definitie, "bedoeld in"). Geel: er is ook iets dat
 *  ertegen pleit; de jurist beslist. Kleur draagt het nooit alleen. */
export const AANDACHT_LABEL: Record<"groen" | "geel", string> = {
  groen: "door de wet onderbouwd",
  geel: "vraagt een oordeel",
};

export const BESLUIT_LABEL: Record<GroepBesluit, string> = {
  open: "open",
  overgenomen: "overgenomen",
  gekoppeld: "gekoppeld aan een begrip",
  afgewezen: "afgewezen",
  geparkeerd: "geparkeerd",
};

/** De relaties van de keten in gewone woorden: "X geldt als Y". */
export const HYPOTHESE_LABEL: Record<string, string> = {
  zelfde_betekenis: "betekent hetzelfde als",
  kwalificatie: "geldt als",
  inclusie: "omvat ook",
  uitsluiting: "omvat niet",
  hierarchie: "is een soort",
};

const OPEN = (g: Betekenisgroep) => g.besluit === "open" || g.besluit === "geparkeerd";

/** Wat nog een besluit vraagt eerst (open, dan geparkeerd), daarbinnen geel vóór groen en meer leden
 *  eerst; besloten groepen achteraan. Stabiel op naam. */
export function sorteerGroepen(groepen: readonly Betekenisgroep[]): Betekenisgroep[] {
  const rang = (g: Betekenisgroep) => (g.besluit === "open" ? 0 : g.besluit === "geparkeerd" ? 1 : 2);
  return [...groepen].sort(
    (a, b) =>
      rang(a) - rang(b) ||
      (a.aandacht === b.aandacht ? 0 : a.aandacht === "geel" ? -1 : 1) ||
      b.leden.length - a.leden.length ||
      a.voorstel.naam.localeCompare(b.voorstel.naam, "nl"),
  );
}

export const isBeslisbaar = OPEN;

/** De overname voor de api: één of meer groepen, met de gekozen leden. Zijn alle leden gekozen, dan
 *  hoeven ze niet mee (de api neemt dan de hele groep); is het een deel, dan is het splitsen. */
export function overnameVoor(
  groepen: readonly Betekenisgroep[],
  gekozen: ReadonlySet<string>,
  naam: string,
  metDefinitie: boolean,
): { groep_ids: string[]; naam: string; element_ids?: string[]; met_definitie: boolean } {
  const alle = groepen.flatMap((g) => g.leden.map((l) => l.element_id));
  const leden = alle.filter((e) => gekozen.has(e));
  return {
    groep_ids: groepen.map((g) => g.id),
    naam: naam.trim(),
    ...(leden.length === alle.length ? {} : { element_ids: leden }),
    met_definitie: metDefinitie,
  };
}

/** De letterlijke definitie die mee kan bij een overname: alleen als er precies één is (bij
 *  combineren kiest de analist zelf, zo doet de api het ook). */
export function enigeDefinitie(groepen: readonly Betekenisgroep[]): { tekst: string; vindplaats: string } | null {
  const defs = new Map<string, string>();
  for (const g of groepen)
    if (g.voorstel.definitie) defs.set(g.voorstel.definitie, g.voorstel.definitie_vindplaats ?? "");
  if (defs.size !== 1) return null;
  const [[tekst, vindplaats]] = [...defs];
  return { tekst, vindplaats };
}

/** De groepen waar beide passages van een twijfelvraag in staan en die nog open zijn – die zet
 *  "samen" klaar om te combineren. */
export function groepenVanVraag(vraag: TwijfelVraag, groepen: readonly Betekenisgroep[]): string[] {
  const in_ = (e: string) => groepen.find((g) => OPEN(g) && g.leden.some((l) => l.element_id === e))?.id;
  const ids = [in_(vraag.van), in_(vraag.naar)].filter((x): x is string => !!x);
  return [...new Set(ids)];
}

/** Een passage in één regel: "“tekst” (vindplaats)". Ontbreekt hij, dan het id – liever zichtbaar
 *  onbekend dan stil weg. */
export function passageTekst(e: string, passages: Record<string, Passage>, groepen: readonly Betekenisgroep[] = []): string {
  const p = passages[e] ?? groepen.flatMap((g) => g.leden).find((l) => l.element_id === e);
  return p ? `“${p.tekst}”${p.vindplaats ? ` (${p.vindplaats})` : ""}` : e;
}

/** Een statusregel van graph-qa ("Lex · Groeperen: …") zonder de actor, voor de voortgangslijst. */
export function voortgangsregel(bericht: string): string {
  return bericht.replace(/^Lex\s*·\s*/, "");
}

/** "Samen" bij een twijfelvraag wordt één begrip: beide passages, plus de leden van een open groep
 *  waar een van de twee in zit. De naam: die van zo'n groep, anders de tekst van de eerste passage. */
export function samenOvername(
  vraag: TwijfelVraag,
  groepen: readonly Betekenisgroep[],
  passages: Record<string, Passage>,
): { groep_ids: string[]; naam: string; element_ids: string[]; met_definitie: boolean } {
  const ids = groepenVanVraag(vraag, groepen);
  const gekozen = groepen.filter((g) => ids.includes(g.id));
  const leden = [...new Set([...gekozen.flatMap((g) => g.leden.map((l) => l.element_id)), vraag.van, vraag.naar])];
  const tekst = passages[vraag.van]?.tekst ?? groepen.flatMap((g) => g.leden).find((l) => l.element_id === vraag.van)?.tekst ?? "";
  const naam = gekozen[0]?.voorstel.naam ?? tekst.replace(/^(de|het|een|die|deze|dat|dit)\s+/i, "").toLowerCase();
  return { groep_ids: ids, naam, element_ids: leden, met_definitie: true };
}
