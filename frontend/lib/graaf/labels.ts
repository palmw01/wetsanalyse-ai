/** Welke knopen een label krijgen: nooit twee over elkaar, en meer detail naarmate je inzoomt.
 *
 *  Sigma's eigen keuze (een raster van vaste cellen, per cel de grootste knopen) kijkt niet naar de
 *  breedte van een label – "Artikel 9 · lid 2" is breder dan een cel en loopt over de buren – en zet
 *  alles met `labelVisibility: "visible"` er ongetoetst bovenop. Daarom kiest de tekenaar per beeld
 *  zelf, met deze pure functies: eerst wat ertoe doet, dan alleen wat nog vrij ligt.
 *
 *  Twee mechanismen, in deze volgorde:
 *  - **Detailniveau** (`magLabel`): uitgezoomd alleen de opbouw (regelingen, hoofdstukken, klassen),
 *    dieper ingezoomd artikelen, leden, en ten slotte onderdelen en markeringen. Gemeten in een
 *    *effectieve* zoom die de grootte van de kaart meeweegt: een kaart van één artikel staat bij zoom 1
 *    al op leesafstand, de hele kennisgraaf niet.
 *  - **Botsingstoets** (`kiesLabels`): gulzig op prioriteit; een label komt alleen als zijn rechthoek
 *    vrij ligt. Wat vorig beeld een label had, wint bij gelijke prioriteit, zodat labels tijdens zoomen
 *    en pannen niet heen en weer springen. */
import { voegToe, type KnoopSoort } from "./model";

/** De rechthoek van een label in schermpixels, met de prioriteit waarmee het om ruimte vraagt. */
export interface LabelKandidaat {
  id: string;
  links: number;
  boven: number;
  breedte: number;
  hoogte: number;
  /** Hoger = eerder. */
  prioriteit: number;
  /** Altijd tekenen (de keuze, wat je aanwijst); neemt wel ruimte in. */
  altijd?: boolean;
}

/** Hoeveel een label dat vorig beeld stond extra weegt: minder dan één soortstap in `labelPrioriteit`,
 *  zodat het alleen gelijken overtroeft. */
const VASTHOUDEN = 5;
const MARGE = 4;
const CEL = 64;

/** De labels die getekend worden. Deterministisch: bij gelijke prioriteit beslist het id. */
export function kiesLabels(kandidaten: readonly LabelKandidaat[], beeld: {
  breedte: number; hoogte: number; vorige?: ReadonlySet<string>;
  /** Wat al ruimte inneemt: de bediening die over de kaart zweeft (zoeken, lagen, beeld). */
  bezet?: readonly Pick<LabelKandidaat, "links" | "boven" | "breedte" | "hoogte">[];
}): Set<string> {
  const { breedte, hoogte, vorige, bezet = [] } = beeld;
  const gewicht = (k: LabelKandidaat) => k.prioriteit + (vorige?.has(k.id) ? VASTHOUDEN : 0);
  // Een label dat de rand raakt, wordt afgekapt: alleen wat helemaal in beeld past (de keuze altijd).
  const volgorde = kandidaten
    .filter((k) => k.altijd ? k.links + k.breedte >= 0 && k.links <= breedte && k.boven + k.hoogte >= 0 && k.boven <= hoogte
      : k.links >= 0 && k.links + k.breedte <= breedte && k.boven >= 0 && k.boven + k.hoogte <= hoogte)
    .sort((a, b) => Number(!!b.altijd) - Number(!!a.altijd) || gewicht(b) - gewicht(a) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  // Een grof raster over het scherm: per cel de rechthoeken die hem raken.
  const raster = new Map<number, LabelKandidaat[]>();
  const cellen = (k: LabelKandidaat) => {
    const uit: number[] = [];
    const [x0, x1] = [Math.floor((k.links - MARGE) / CEL), Math.floor((k.links + k.breedte + MARGE) / CEL)];
    const [y0, y1] = [Math.floor((k.boven - MARGE) / CEL), Math.floor((k.boven + k.hoogte + MARGE) / CEL)];
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) uit.push(x * 100_003 + y);
    return uit;
  };
  const raakt = (a: LabelKandidaat, b: LabelKandidaat) =>
    a.links - MARGE < b.links + b.breedte && b.links - MARGE < a.links + a.breedte
    && a.boven - MARGE < b.boven + b.hoogte && b.boven - MARGE < a.boven + a.hoogte;
  const gekozen = new Set<string>();
  for (const b of bezet) {
    const k = { ...b, id: "", prioriteit: 0 };
    for (const c of cellen(k)) voegToe(raster, c, k);
  }
  for (const k of volgorde) {
    const mijn = cellen(k);
    if (!k.altijd && mijn.some((c) => raster.get(c)?.some((ander) => raakt(k, ander)))) continue;
    gekozen.add(k.id);
    for (const c of mijn) voegToe(raster, c, k);
  }
  return gekozen;
}

/** Hoe ver ingezoomd, gewogen naar de grootte van de kaart: 1 = een kaart van ~1.000 knopen
 *  helemaal in beeld. Kleiner = dichterbij. */
export function effectieveZoom(ratio: number, aantalKnopen: number): number {
  return ratio * Math.sqrt(Math.max(aantalKnopen, 1) / 1000);
}

/** Vanaf welke effectieve zoom een soort een label krijgt (`Infinity` = altijd). */
export const LABEL_VANAF: Record<KnoopSoort, number> = {
  regeling: Infinity, deel: Infinity, klasse: Infinity,
  artikel: 1, lid: 0.5, extern: 0.25, onderdeel: 0.25, markering: 0.25, begrip: Infinity,
};

/** Mag een knoop van deze soort bij deze zoom een label hebben? */
export function magLabel(soort: KnoopSoort, zoom: number): boolean {
  return zoom <= LABEL_VANAF[soort];
}

/** Uitgezoomd zijn de details kleiner, zodat het overzicht rustig blijft; ingezoomd hun volle maat. */
export function detailFactor(soort: KnoopSoort, zoom: number): number {
  return (soort === "onderdeel" || soort === "markering" || soort === "extern") && zoom > LABEL_VANAF[soort] * 2 ? 0.6 : 1;
}

const SOORT_VOLGORDE: Record<KnoopSoort, number> = {
  regeling: 7, deel: 6, klasse: 5, begrip: 5, artikel: 4, lid: 3, onderdeel: 2, extern: 1, markering: 1,
};

/** De prioriteit van een label: eerst het niveau uit de weergave (gekozen of aangewezen 3, nadruk 2,
 *  gewoon 1), dan of het altijd een label hoort te hebben (de keuze met haar buren, de doelen van de
 *  focus), dan de soort. */
export function labelPrioriteit(niveau: number, altijdLabel: boolean, soort: KnoopSoort): number {
  return niveau * 1000 + (altijdLabel ? 500 : 0) + SOORT_VOLGORDE[soort] * 10;
}
