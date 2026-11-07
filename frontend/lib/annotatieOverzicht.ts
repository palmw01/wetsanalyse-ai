// Sorteren, filteren en groeperen voor het annotatie-overzicht.
//
// Bewust een eigen module zonder React: vitest draait node-env zonder DOM (`vitest.config.ts`), dus
// alleen pure helpers zijn te testen – dezelfde reden waarom `lib/selectie.ts` los staat van het
// documentpaneel. Het component eromheen doet alleen nog weergave.

import type { DocumentSamenvatting } from "./types";

export type Weergave = "te-beoordelen" | "af-te-ronden" | "afgerond" | "alles";

/** De weergaven volgen de weg van een annotatie: eerst beoordelen, dan afronden. "Te doen" heette de eerste vroeger,
 *  maar afronden is ook nog te doen. De eerste drie sluiten elkaar uit; *Alles* telt ook een laag zonder markeringen. */
export const WEERGAVEN: { waarde: Weergave; label: string }[] = [
  { waarde: "te-beoordelen", label: "Te beoordelen" },
  { waarde: "af-te-ronden", label: "Af te ronden" },
  { waarde: "afgerond", label: "Afgerond" },
  { waarde: "alles", label: "Alles" },
];

export function weergaveUitParam(param: string | null | undefined): Weergave {
  return WEERGAVEN.find((w) => w.waarde === param)?.waarde ?? "te-beoordelen";
}

/** De vindplaats zoals hij in beeld komt: `art. 9 lid 2`, of `bepaling 25.1` bij een beleidsregel.
 *  Werkt op zowel een samenvatting als een volledig document – beide dragen artikel en lid.
 *
 *  Het `soort` komt uit de bronboom van de api en wordt niet uit het nummer geraden: een
 *  heel getal als "25" is bij de Invorderingswet een artikel en bij de Leidraad een divisie. Zonder
 *  soort blijft het "art.", wat het bij de zes wet-achtige regelingen ook is. */
export function vindplaatsLabel(d: { artikel: string; lid: string; soort?: string; label?: string }): string {
  if (d.soort === "Divisie") return `bepaling ${d.artikel}${d.lid ? `, ${d.lid}` : ""}`;
  const basis = `art. ${d.artikel}${d.lid ? ` lid ${d.lid}` : ""}`;
  // Het label van een onderdeel is alleen "Onderdeel c.": zonder artikel en lid zegt dat niets.
  return d.soort === "Onderdeel" && d.label ? `${basis}, ${d.label.replace(/\.$/, "").toLowerCase()}` : basis;
}

/** De naam waaronder een annotatie in beeld komt, met dezelfde terugval als de server hanteert:
 *  citeertitel → werkgebied → bwbId. */
export function naamVan(d: { citeertitel?: string; werkgebied?: string; bwbId: string }): string {
  return d.citeertitel || d.werkgebied || d.bwbId;
}

/** Staan hier nog markeringen te beoordelen? Alleen documenten die de jurist niet heeft afgerond tellen mee —
 *  afronden is een expliciete handeling, dus een afgerond document met open elementen is een
 *  bewuste keuze en geen restpost. */
export function isTeBeoordelen(d: DocumentSamenvatting): boolean {
  return d.status === "in_review" && d.te_beoordelen > 0;
}

/** Alles is beoordeeld, maar de jurist heeft de annotatie nog niet afgerond. Dat blijft een eigen stap: `in_review`
 *  gaat niet vanzelf over, dus de status in de api verandert niet – dit is alleen hoe de stand in beeld komt.
 *
 *  Bij nul actuele markeringen is er niets beoordeeld, dus ook niets klaar: dat is een lege laag, of een laag waarvan
 *  alleen historie over is omdat de wettekst veranderde. */
export function isKlaarOmAfTeRonden(
  d: Pick<DocumentSamenvatting, "status" | "aantal_elementen" | "te_beoordelen">,
): boolean {
  return d.status === "in_review" && d.aantal_elementen > 0 && d.te_beoordelen === 0;
}

/** Hoort dit document bij de weergave? */
export function inWeergave(d: DocumentSamenvatting, weergave: Weergave): boolean {
  if (weergave === "te-beoordelen") return isTeBeoordelen(d);
  if (weergave === "af-te-ronden") return isKlaarOmAfTeRonden(d);
  if (weergave === "afgerond") return d.status !== "in_review";
  return true;
}

const UITLEG: Record<Weergave, string> = {
  "te-beoordelen": "Bepalingen met markeringen die je nog moet beoordelen, rood eerst.",
  "af-te-ronden": "Alle markeringen zijn beoordeeld; alleen het afronden ontbreekt. Dat doe je in de annotatie zelf.",
  afgerond: "Bepalingen waarvan een jurist de annotatie heeft afgerond, per regeling.",
  alles: "Alle bepalingen met een annotatie, per regeling.",
};

/** De zin onder de weergaveknoppen. De aantallen tellen bepalingen, want één annotatie hoort bij één artikel, lid of
 *  onderdeel – niet bij één markering. */
export function uitlegWeergave(weergave: Weergave): string {
  return `${UITLEG[weergave]} De aantallen tellen bepalingen, niet markeringen.`;
}

/** De lege staat van een weergave. Alleen voor als er wel annotaties zijn, maar geen in deze weergave. */
export function legeWeergave(weergave: Weergave): string {
  if (weergave === "te-beoordelen") return "Niets meer te beoordelen.";
  if (weergave === "af-te-ronden") return "Niets af te ronden.";
  if (weergave === "afgerond") return "Nog niets afgerond.";
  return "Geen annotatie die hierop past.";
}

function aandacht(d: DocumentSamenvatting, niveau: string): number {
  return d.per_aandacht?.[niveau] ?? 0;
}

function tijd(d: DocumentSamenvatting): number {
  const t = d.updated ? Date.parse(d.updated) : NaN;
  return Number.isNaN(t) ? 0 : t;
}

/** Werkvoorraad-volgorde: rood eerst, dan geel, dan wat het langst stil ligt.
 *
 *  Niet op "meeste te beoordelen": een document met dertig open elementen zonder aandachtssignaal
 *  is routinewerk, terwijl één rood element een echte vraag is. Het aandachtssignaal weegt dus
 *  zwaarder dan de omvang. */
export function sorteerTeBeoordelen(docs: DocumentSamenvatting[]): DocumentSamenvatting[] {
  return [...docs].sort(
    (a, b) =>
      aandacht(b, "rood") - aandacht(a, "rood") ||
      aandacht(b, "geel") - aandacht(a, "geel") ||
      tijd(a) - tijd(b),
  );
}

/** Alles-volgorde binnen een regeling: op artikel (numeriek, want '10' hoort ná '2'), dan lid, dan het
 *  onderdeel – dat alleen in het label staat. */
function sorteerBinnenRegeling(docs: DocumentSamenvatting[]): DocumentSamenvatting[] {
  return [...docs].sort(
    (a, b) => vergelijkNummer(a.artikel, b.artikel) || vergelijkNummer(a.lid, b.lid)
      || (a.label ?? "").localeCompare(b.label ?? "", "nl", { numeric: true }),
  );
}

/** Sorteersleutel per punt-gescheiden segment: [[25],[1],[1]] voor "25.1.1".
 *
 * Alleen het eerste cijferblok lezen gaf voor een beleidsregel overal dezelfde sleutel: alle
 * bepalingen "25.x.y" van de Leidraad sorteerden als 25 en stonden daarmee in willekeurige
 * volgorde in de werkvoorraad. Per segment komt 25.2 vóór 25.10 en valt 73.3a tussen 73.3 en 73.4. */
function sleutel(waarde: string): [number, string][] {
  const tekst = (waarde ?? "").trim();
  if (!tekst) return [[Number.MAX_SAFE_INTEGER, ""]];
  const delen = tekst.split(".");
  const uit: [number, string][] = [];
  for (const deel of delen) {
    const m = /^(\d*)([a-z]*)$/i.exec(deel);
    if (!m || !deel) return [[Number.MAX_SAFE_INTEGER, tekst]];
    uit.push([m[1] ? Number(m[1]) : Number.MAX_SAFE_INTEGER, m[2].toLowerCase()]);
  }
  return uit;
}

function vergelijkNummer(a: string, b: string): number {
  const x = sleutel(a);
  const y = sleutel(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const [xn, xs] = x[i] ?? [-1, ""];
    const [yn, ys] = y[i] ?? [-1, ""];
    if (xn !== yn) return xn - yn;
    if (xs !== ys) return xs < ys ? -1 : 1;
  }
  return 0;
}

export interface Regeling {
  naam: string;
  bwbId: string;
  documenten: DocumentSamenvatting[];
}

/** Groeperen op regeling: juristen denken in wetten, niet in losse documenten op datum.
 *  De groepen staan op naam; binnen een groep telt de artikelvolgorde. */
export function groepeerPerRegeling(docs: DocumentSamenvatting[]): Regeling[] {
  const perId = new Map<string, Regeling>();
  for (const d of docs) {
    const bestaand = perId.get(d.bwbId);
    if (bestaand) bestaand.documenten.push(d);
    else perId.set(d.bwbId, { naam: d.citeertitel || d.bwbId, bwbId: d.bwbId, documenten: [d] });
  }
  return [...perId.values()]
    .map((r) => ({ ...r, documenten: sorteerBinnenRegeling(r.documenten) }))
    .sort((a, b) => a.naam.localeCompare(b.naam, "nl"));
}

/** Zoeken op wat de jurist ziet: regelingnaam, bwbId, artikel/lid/onderdeel en werkgebied. Woord voor woord,
 *  zodat "zorgverzekering 43" werkt zonder dat de volgorde uitmaakt. Het woord "artikel" hoort erbij: wie dat typt,
 *  ziet op de kaart "art." staan. Een kort woord (een nummer, de letter van een onderdeel) moet heel kloppen: anders
 *  vindt "artikel 9" elk artikel van de Invorderingswet 1990. */
export function zoek(docs: DocumentSamenvatting[], term: string): DocumentSamenvatting[] {
  const woorden = term.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (woorden.length === 0) return docs;
  return docs.filter((d) => {
    const hooiberg = [
      d.citeertitel, d.werkgebied, d.bwbId, `artikel ${d.artikel}`, d.lid, vindplaatsLabel(d),
    ]
      .join(" ")
      .toLowerCase();
    const heleWoorden = hooiberg.split(/[^\p{L}\p{N}]+/u);
    return woorden.every((w) => (w.length <= 2 ? heleWoorden.includes(w) : hooiberg.includes(w)));
  });
}

/** De JAS-kleurstrip: welk aandeel heeft elke klasse in dit document?
 *
 *  Terug in canonieke tabelvolgorde, zodat dezelfde verdeling er altijd hetzelfde uitziet en twee
 *  documenten naast elkaar te vergelijken zijn. */
export function kleurstrip(
  perKlasse: Record<string, number>,
  volgorde: readonly string[],
): { klasse: string; aantal: number }[] {
  const bekend = volgorde
    .filter((k) => (perKlasse?.[k] ?? 0) > 0)
    .map((k) => ({ klasse: k, aantal: perKlasse[k] }));
  // Klassen die niet in de canonieke lijst staan (oude data, drift) achteraan in plaats van weg:
  // een strip die stilzwijgend elementen weglaat liegt over de verdeling.
  const rest = Object.entries(perKlasse ?? {})
    .filter(([k, n]) => n > 0 && !volgorde.includes(k))
    .map(([klasse, aantal]) => ({ klasse, aantal }));
  return [...bekend, ...rest];
}
