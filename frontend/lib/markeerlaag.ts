/** De rekenkern van de markeerlaag op de wettekst (ontdubbelen PR 4): welke ene markering oplicht en hoe een stuk tekst
 *  geknipt wordt. Puur, getest in `markeerlaag.test.ts`; de weergave is `WettekstBlok` met `laag`. */
import { vindPositie } from "@/lib/selectie";
import type { Anker } from "@/lib/types";

/** Minimaal element voor highlighting: klasse + letterlijk fragment (+ optioneel id/anker/herkomst). */
export interface Markeerbaar {
  id?: string;
  klasse: string;
  tekst: string;
  herkomst?: string;
  anker?: Anker | null;
}

export interface Segment {
  tekst: string;
  klasse?: string;
  id?: string;
  herkomst?: string;
  /** Opmaak van dit stuk wettekst: het onderdeelnummer of de gedefinieerde term. */
  nadruk?: "nummer" | "term";
  /** Dit stuk valt in een zinsdeel waar geen detector iets vond (de dekkingsmeting). */
  ongedekt?: { start: number; eind: number };
}

/** Knip `bron` in segmenten, met hoogstens ÉÉN gemarkeerd: de geselecteerde.
 *
 *  Alles tegelijk kleuren was onleesbaar én onvolledig. Twee markeringen kunnen niet op dezelfde
 *  tekst liggen, dus een markering die binnen een langere valt – een Rechtsobject in een zin die als
 *  geheel een Afleidingsregel is – verdween gewoon uit beeld. Nu is de reviewlijst de ingang en laat
 *  de tekst zien wáár het gekozen element staat; zonder selectie blijft de tekst schoon.
 *
 *  De positie komt uit `vindPositie`: eerst het anker (exacte offsets), dan de omringende tekst, dan
 *  het eerste voorkomen. Dat houdt twee identieke fragmenten in één artikel uit elkaar – zonder
 *  anker zou de tweede "De ontvanger" op de eerste landen.
 */
export function segmenteer(bron: string, elementen: Markeerbaar[], actiefId?: string): Segment[] {
  const m = markeringVan(bron, elementen, actiefId);
  if (!m) return [{ tekst: bron }];
  return [
    ...(m.start > 0 ? [{ tekst: bron.slice(0, m.start) }] : []),
    { tekst: bron.slice(m.start, m.eind), klasse: m.klasse, id: m.id, herkomst: m.herkomst },
    ...(m.eind < bron.length ? [{ tekst: bron.slice(m.eind) }] : []),
  ];
}

/** Waar staat de geselecteerde markering in de bron? `null` als er geen is of hij zweeft.
 *
 *  Eén plek waar dat wordt uitgerekend, want de tekst wordt op twee manieren opgebouwd: als hele
 *  bron (`segmenteer`, waar de bestaande tests aan hangen) en per blok (`segmentenVanBlok`). Zouden
 *  die elk hun eigen `vindPositie` doen, dan kunnen ze op een ander voorkomen uitkomen. */
export function markeringVan(
  bron: string,
  elementen: Markeerbaar[],
  actiefId?: string,
): { start: number; eind: number; klasse: string; id?: string; herkomst?: string } | null {
  const el = actiefId ? elementen.find((e) => e.id === actiefId) : undefined;
  const fragment = el?.tekst.trim() ?? "";
  const start = fragment ? vindPositie(bron, fragment, el?.anker, []) : -1;
  if (!el || start < 0) return null;
  return { start, eind: start + fragment.length, klasse: el.klasse, id: el.id, herkomst: el.herkomst };
}

/** De segmenten van één blok: de tekst van dit blok, geknipt op alles wat er anders uitziet.
 *
 *  ÉÉN BRON VAN TEKST. De weergave mag nummer en term niet zelf opnieuw samenstellen naast deze
 *  segmenten — dan staat de tekst dubbel in de DOM én lopen de offsets mis, want `offsetVanGrens`
 *  telt de tekstknopen binnen het blok op. Die fout is niet te zien in de losse tests van
 *  `blokkenVan` en deze functie; alleen hun combinatie breekt. Vandaar de test die
 *  eist dat de segmenten samen exact `blok.regel` vormen.
 *
 *  Geknipt wordt op twee soorten grenzen tegelijk: de markering (waar de jurist naar kijkt) en de
 *  opmaak (nummer, term). Een `<mark>` kan bovendien niet over twee blokken heen — die zijn aparte
 *  elementen — dus een markering die van de aanhef doorloopt tot in een onderdeel wordt hier per
 *  blok afgekapt, met dezelfde klasse en hetzelfde id; `box-decoration-clone` laat ze doorlopen.
 */
export function segmentenVanBlok(
  blok: { offset: number; regel: string; nummerEind: number; termStart: number; termEind: number },
  markering: { start: number; eind: number; klasse: string; id?: string; herkomst?: string } | null,
  ongedekt: { start: number; eind: number }[] = [],
): Segment[] {
  const n = blok.regel.length;
  const eindeBlok = blok.offset + n;
  const raakt = markering && markering.eind > blok.offset && markering.start < eindeBlok;
  const mVan = raakt ? Math.max(markering!.start - blok.offset, 0) : -1;
  const mTot = raakt ? Math.min(markering!.eind - blok.offset, n) : -1;
  // De ongedekte zinsdelen die dit blok raken, in blokcoördinaten; ook die knippen de tekst.
  const gaten = ongedekt
    .filter((o) => o.eind > blok.offset && o.start < eindeBlok)
    .map((o) => ({ van: Math.max(o.start - blok.offset, 0), tot: Math.min(o.eind - blok.offset, n), deel: o }));

  const grenzen = [0, n, blok.nummerEind, blok.termStart, blok.termEind, mVan, mTot, ...gaten.flatMap((g) => [g.van, g.tot])]
    .filter((g) => g >= 0 && g <= n)
    .sort((a, b) => a - b);

  const uit: Segment[] = [];
  for (let i = 0; i < grenzen.length - 1; i++) {
    const [van, tot] = [grenzen[i], grenzen[i + 1]];
    if (van === tot) continue;   // dubbele grenzen (nummer eindigt waar de term begint)
    const seg: Segment = { tekst: blok.regel.slice(van, tot) };
    if (blok.nummerEind > 0 && tot <= blok.nummerEind) seg.nadruk = "nummer";
    else if (blok.termStart >= 0 && van >= blok.termStart && tot <= blok.termEind) seg.nadruk = "term";
    if (raakt && van >= mVan && tot <= mTot) {
      seg.klasse = markering!.klasse;
      seg.id = markering!.id;
      seg.herkomst = markering!.herkomst;
    } else {
      // De markering gaat voor: wat de jurist bekijkt, kleurt; een onderstreping eronder zou alleen storen.
      const gat = gaten.find((g) => van >= g.van && tot <= g.tot);
      if (gat) seg.ongedekt = { start: gat.deel.start, eind: gat.deel.eind };
    }
    uit.push(seg);
  }
  return uit.length ? uit : [{ tekst: blok.regel }];
}
