/** De rekenkern van de markeerlaag op de wettekst (ontdubbelen PR 4): waar de markeringen staan, in banen (optie B), en
 *  hoe een stuk tekst geknipt wordt. Puur, getest in `markeerlaag.test.ts`; de weergave is `WettekstBlok` met `laag`. */
import { markeerbanen, type Banen } from "@/lib/markeerbanen";
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
  /** De markering met het vlak op dit stuk (optie B: een markering die geen andere omvat). */
  klasse?: string;
  id?: string;
  herkomst?: string;
  /** De markeringen die andere omvatten en over dit stuk lopen, als baan eronder (`lib/markeerbanen.ts`). */
  banen?: { id: string; klasse: string; baan: number; herkomst?: string }[];
  /** Opmaak van dit stuk wettekst: het onderdeelnummer of de gedefinieerde term. */
  nadruk?: "nummer" | "term";
  /** Dit stuk valt in een zinsdeel waar geen detector iets vond (de dekkingsmeting). */
  ongedekt?: { start: number; eind: number };
}

/** Een markering op haar plek in de bron. */
export interface Plek { start: number; eind: number; klasse: string; id?: string; herkomst?: string }

/** Waar staat een markering in de bron? `null` als ze er niet (meer) letterlijk staat.
 *
 *  De positie komt uit `vindPositie`: eerst het anker (exacte offsets), dan de omringende tekst, dan het eerste voorkomen.
 *  Dat houdt twee identieke fragmenten in één artikel uit elkaar – zonder anker zou de tweede "De ontvanger" op de eerste
 *  landen. Eén plek waar dat wordt uitgerekend, voor de gekozen markering (`markeringVan`) en voor de laag (`laagVan`). */
function plekVan(bron: string, el: Markeerbaar): Plek | null {
  const fragment = el.tekst.trim();
  const start = fragment ? vindPositie(bron, fragment, el.anker, []) : -1;
  if (start < 0) return null;
  return { start, eind: start + fragment.length, klasse: el.klasse, id: el.id, herkomst: el.herkomst };
}

/** Waar staat de gekozen markering in de bron? `null` als er geen is of hij zweeft. */
export function markeringVan(bron: string, elementen: Markeerbaar[], actiefId?: string): Plek | null {
  const el = actiefId ? elementen.find((e) => e.id === actiefId) : undefined;
  return el ? plekVan(bron, el) : null;
}

/** Alle markeringen van de bron in banen (optie B, besluit gebruiker 18 nov 2026): een markering die niets omvat krijgt
 *  het vlak, een die andere omvat een baan eronder. Vroeger toonde de tekst alleen de gekozen markering, omdat een korte
 *  markering in een lange wegviel; met de banen staat alles er, en licht de gekozen op. Een markering die niet in de tekst
 *  te vinden is, staat er niet in (ze staat wel in de reviewlijst). */
export interface Laag { plekken: Map<string, Plek>; banen: Banen }

export function laagVan(bron: string, elementen: Markeerbaar[]): Laag {
  const plekken = new Map<string, Plek>();
  elementen.forEach((el, i) => {
    const p = plekVan(bron, el);
    if (p) plekken.set(el.id ?? `#${i}`, p);
  });
  const spans = [...plekken].map(([sleutel, p]) => ({ sleutel, start: p.start, eind: p.eind }))
    .sort((p, q) => p.start - q.start || p.eind - q.eind || (p.sleutel < q.sleutel ? -1 : p.sleutel > q.sleutel ? 1 : 0));
  return { plekken, banen: markeerbanen(bron.length, spans) };
}

/** Hoeveel banen de stukken van een blok nodig hebben. */
export function banenInBlok(segmenten: readonly Segment[]): number {
  return Math.max(0, ...segmenten.flatMap((s) => (s.banen ?? []).map((b) => b.baan + 1)));
}

/** De segmenten van één blok: de tekst van dit blok, geknipt op alles wat er anders uitziet.
 *
 *  ÉÉN BRON VAN TEKST. De weergave mag nummer en term niet zelf opnieuw samenstellen naast deze
 *  segmenten — dan staat de tekst dubbel in de DOM én lopen de offsets mis, want `offsetVanGrens`
 *  telt de tekstknopen binnen het blok op. Die fout is niet te zien in de losse tests van
 *  `blokkenVan` en deze functie; alleen hun combinatie breekt. Vandaar de test die
 *  eist dat de segmenten samen exact `blok.regel` vormen.
 *
 *  Geknipt wordt op drie soorten grenzen tegelijk: de stukken van de laag (vlak en banen), de opmaak (nummer, term) en
 *  de ongedekte zinsdelen. Een `<mark>` kan niet over twee blokken heen – die zijn aparte elementen – dus een markering
 *  die van de aanhef doorloopt tot in een onderdeel wordt hier per blok afgekapt, met dezelfde klasse en hetzelfde id;
 *  `box-decoration-clone` laat ze doorlopen.
 */
export function segmentenVanBlok(
  blok: { offset: number; regel: string; nummerEind: number; termStart: number; termEind: number },
  laag: Laag | null,
  ongedekt: { start: number; eind: number }[] = [],
): Segment[] {
  const n = blok.regel.length;
  const eindeBlok = blok.offset + n;
  const stukken = (laag?.banen.stukken ?? []).filter((s) => s.eind > blok.offset && s.start < eindeBlok);
  // De ongedekte zinsdelen die dit blok raken, in blokcoördinaten; ook die knippen de tekst.
  const gaten = ongedekt
    .filter((o) => o.eind > blok.offset && o.start < eindeBlok)
    .map((o) => ({ van: Math.max(o.start - blok.offset, 0), tot: Math.min(o.eind - blok.offset, n), deel: o }));

  const grenzen = [0, n, blok.nummerEind, blok.termStart, blok.termEind,
    ...stukken.flatMap((s) => [s.start - blok.offset, s.eind - blok.offset]), ...gaten.flatMap((g) => [g.van, g.tot])]
    .filter((g) => g >= 0 && g <= n)
    .sort((a, b) => a - b);

  const uit: Segment[] = [];
  for (let i = 0; i < grenzen.length - 1; i++) {
    const [van, tot] = [grenzen[i], grenzen[i + 1]];
    if (van === tot) continue;   // dubbele grenzen (nummer eindigt waar de term begint)
    const seg: Segment = { tekst: blok.regel.slice(van, tot) };
    if (blok.nummerEind > 0 && tot <= blok.nummerEind) seg.nadruk = "nummer";
    else if (blok.termStart >= 0 && van >= blok.termStart && tot <= blok.termEind) seg.nadruk = "term";
    const stuk = stukken.find((s) => s.start <= blok.offset + van && s.eind >= blok.offset + tot);
    const vlak = stuk?.vlak ? laag!.plekken.get(stuk.vlak) : undefined;
    if (vlak) {
      seg.klasse = vlak.klasse;
      seg.id = vlak.id;
      seg.herkomst = vlak.herkomst;
    }
    if (stuk?.banen.length) {
      seg.banen = stuk.banen.map((b) => {
        const p = laag!.plekken.get(b.sleutel)!;
        return { id: p.id ?? b.sleutel, klasse: p.klasse, baan: b.baan, ...(p.herkomst ? { herkomst: p.herkomst } : {}) };
      });
    }
    if (!vlak && !seg.banen) {
      // De markering gaat voor: wat gemarkeerd is, kleurt; een onderstreping eronder zou alleen storen.
      const gat = gaten.find((g) => van >= g.van && tot <= g.tot);
      if (gat) seg.ongedekt = { start: gat.deel.start, eind: gat.deel.eind };
    }
    uit.push(seg);
  }
  return uit.length ? uit : [{ tekst: blok.regel }];
}
