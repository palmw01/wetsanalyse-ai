/** Markeerbanen: overlappende markeringen zo tonen dat ze allemaal te zien zijn (optie B uit
 *  `docs/architectuur/voorstel-markeringen-en-diagrammen.md`, besluit gebruiker 18 nov 2026).
 *
 *  Een markering die geen andere omvat, krijgt het **vlak** in haar JAS-kleur. Een markering die andere omvat (meestal een
 *  rechtsbetrekking, voorwaarde of afleidingsregel over een hele zin) krijgt een **baan**: een streep onder de tekst, op een
 *  vaste hoogte over haar hele lengte.
 *
 *  De tweeling van `api/app/markeerbanen.py` (het rapport); beide toetsen tegen `markeerbanen.vectoren.json`. De regels
 *  staan daar. De functie kent geen tekst en geen eenheid: offsets zijn gehele getallen in de eenheid van de aanroeper. */

export interface MarkeerSpan { sleutel: string; start: number; eind: number }

export interface BaanStuk {
  start: number;
  eind: number;
  /** De sleutel van de markering met het vlak, of geen. */
  vlak: string | null;
  /** De markeringen met een baan over dit stuk, op baan oplopend. */
  banen: { sleutel: string; baan: number }[];
  /** De markeringen die aan het eind van dit stuk eindigen, in de volgorde van de invoer. */
  eindigt: string[];
}

export interface Banen {
  stukken: BaanStuk[];
  /** Hoeveel banen er nodig zijn (0 als alles een vlak heeft). */
  aantal: number;
}

interface Norm { i: number; k: string; s: number; e: number }

const raakt = (a: { s: number; e: number }, b: { s: number; e: number }) => a.s < b.e && b.s < a.e;
const orde = (a: Norm, b: Norm) => (a.e - a.s) - (b.e - b.s) || a.s - b.s || a.i - b.i;

export function markeerbanen(lengte: number, spans: readonly MarkeerSpan[]): Banen {
  const norm: Norm[] = spans
    .map((x, i) => ({ i, k: x.sleutel, s: Math.max(0, x.start), e: Math.min(lengte, x.eind) }))
    .filter((x) => x.e > x.s);

  const omvat = new Set(norm.filter((x) => norm.some((y) =>
    y.i !== x.i && x.s <= y.s && y.e <= x.e && (x.e - x.s) > (y.e - y.s))).map((x) => x.i));

  const vlak: Norm[] = [];
  const rest: Norm[] = [];
  for (const x of norm.filter((x) => !omvat.has(x.i)).sort(orde)) {
    (vlak.some((v) => raakt(x, v)) ? rest : vlak).push(x);
  }
  rest.push(...norm.filter((x) => omvat.has(x.i)));

  const baanVan = new Map<number, number>();
  const bezet: { s: number; e: number }[][] = [];
  for (const x of [...rest].sort(orde)) {
    let j = bezet.findIndex((lijst) => !lijst.some((r) => raakt(x, r)));
    if (j < 0) { bezet.push([]); j = bezet.length - 1; }
    bezet[j].push({ s: x.s, e: x.e });
    baanVan.set(x.i, j);
  }

  const vlakIds = new Set(vlak.map((v) => v.i));
  const grenzen = [...new Set([0, lengte, ...norm.flatMap((x) => [x.s, x.e])])].sort((a, b) => a - b);
  const stukken: BaanStuk[] = [];
  for (let n = 0; n < grenzen.length - 1; n++) {
    const [a, b] = [grenzen[n], grenzen[n + 1]];
    const dekking = norm.filter((x) => x.s <= a && x.e >= b);
    const v = dekking.find((x) => vlakIds.has(x.i));
    const banen = dekking.filter((x) => baanVan.has(x.i))
      .sort((p, q) => baanVan.get(p.i)! - baanVan.get(q.i)! || p.i - q.i)
      .map((x) => ({ sleutel: x.k, baan: baanVan.get(x.i)! }));
    const eindigt: string[] = [];
    for (const x of norm) if (x.e === b && x.s < b && !eindigt.includes(x.k)) eindigt.push(x.k);
    stukken.push({ start: a, eind: b, vlak: v ? v.k : null, banen, eindigt });
  }
  return { stukken, aantal: bezet.length };
}

/** De maat van een baan in de werkplek: een streep van 3 px, elke volgende 4 px lager, de eerste 3 px onder de letters (onder de rand van een vlak). */
export const BAAN_DIKTE = 3;
export const BAAN_STAP = 4;
export const BAAN_BEGIN = 3;

/** De stijl van een stuk tekst met banen: de strepen als achtergrond in de opvulling eronder. `aantal` is het aantal banen
 *  van de hele alinea, zodat een baan op elke regel op dezelfde hoogte ligt. Een gedimde baan (niet de gekozen markering)
 *  krijgt een doorzichtige kleur. */
export function baanStijl(banen: readonly { kleur: string; baan: number; gedimd?: boolean }[], aantal: number) {
  const onder = BAAN_BEGIN + aantal * BAAN_STAP;
  return {
    paddingBottom: `${onder}px`,
    backgroundImage: banen.map((b) => {
      const kleur = b.gedimd ? `${b.kleur}59` : b.kleur;
      return `linear-gradient(${kleur}, ${kleur})`;
    }).join(", "),
    backgroundSize: banen.map(() => `100% ${BAAN_DIKTE}px`).join(", "),
    backgroundPosition: banen.map((b) => `0 calc(100% - ${onder - BAAN_BEGIN - b.baan * BAAN_STAP - BAAN_DIKTE}px)`).join(", "),
    backgroundRepeat: "no-repeat",
  };
}

/** De regelhoogte van een alinea met `aantal` banen: de gewone hoogte plus de ruimte voor de strepen. */
export function regelhoogte(basisEm: number, aantal: number): string | undefined {
  return aantal ? `calc(${basisEm}em + ${BAAN_BEGIN + aantal * BAAN_STAP}px)` : undefined;
}
