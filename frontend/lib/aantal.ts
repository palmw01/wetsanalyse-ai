/** Een aantal met het juiste woord: "1 bron", "3 bronnen" (generieke componenten, 15 nov 2026,
 *  `docs/architectuur/plan-generieke-componenten.md` §12). Het woord mag meer zijn dan een zelfstandig naamwoord ("passage
 *  veranderde" / "passages veranderden"). Schrijf `n === 1 ? "1 …" : …` niet zelf (`app/aantal.test.ts`). */
export function aantal(n: number, een: string, meer: string): string {
  return `${n} ${n === 1 ? een : meer}`;
}
