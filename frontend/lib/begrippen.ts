// Rekenkern van de begrippenwerkplek (spoor D, levering 2): labels, het vergelijken van inhoud, de
// volgorde van passages en de herkenning van de fouten die de api geeft. Puur, voor vitest.

import { isApiError } from "./api";
import type {
  Actualiteit,
  BegripInhoud,
  BegripRevisie,
  DefinitieHerkomst,
  KoppelBeoordeling,
  KoppelRol,
  Koppeling,
  VoorbeeldOordeel,
} from "./types";

export const LEGE_INHOUD: BegripInhoud = {
  naam: "",
  alternatieve_termen: [],
  context: "",
  begripstype: "",
  jas_klasse: "",
  jas_subtype: "",
  geldigheid: "",
  definitie: "",
  definitie_herkomst: null,
  uitleg: "",
  onderbouwing: "",
  voorbeelden: [],
  eigenschappen: {},
  open_vragen: [],
};

/** Vult een inhoud van de api aan tot een volledige: een ouder begrip kan velden missen. */
export function volledigeInhoud(inhoud: Partial<BegripInhoud>): BegripInhoud {
  return { ...LEGE_INHOUD, ...inhoud };
}

/** Wat de api bij opslaan als lijst bewaart: lege regels vallen weg, de rest wordt getrimd. Zo is
 *  "een lege regel toegevoegd" geen wijziging. */
export function genormaliseerd(i: BegripInhoud): BegripInhoud {
  const lijst = (xs: string[]) => xs.map((x) => x.trim()).filter(Boolean);
  return {
    ...i,
    naam: i.naam.trim(),
    alternatieve_termen: lijst(i.alternatieve_termen),
    open_vragen: lijst(i.open_vragen),
    voorbeelden: i.voorbeelden.filter((v) => v.tekst.trim()),
    eigenschappen: Object.fromEntries(Object.entries(i.eigenschappen).filter(([k]) => k.trim())),
  };
}

/** Wijkt `nieuw` inhoudelijk af van `oud`? Bepaalt of *Opslaan* aan staat – en dus of er een
 *  revisie komt. Sleutelvolgorde telt niet mee. */
export function inhoudGewijzigd(oud: BegripInhoud, nieuw: BegripInhoud): boolean {
  return gewijzigdeVelden(oud, nieuw).length > 0;
}

export function gewijzigdeVelden(oud: BegripInhoud, nieuw: BegripInhoud): (keyof BegripInhoud)[] {
  const a = genormaliseerd(volledigeInhoud(oud));
  const b = genormaliseerd(volledigeInhoud(nieuw));
  return (Object.keys(LEGE_INHOUD) as (keyof BegripInhoud)[]).filter(
    (k) => stabiel(a[k]) !== stabiel(b[k]),
  );
}

function stabiel(v: unknown): string {
  if (v && typeof v === "object" && !Array.isArray(v)) {
    return JSON.stringify(Object.fromEntries(Object.entries(v).sort(([x], [y]) => x.localeCompare(y))));
  }
  return JSON.stringify(v ?? null);
}

export const HERKOMST_LABEL: Record<DefinitieHerkomst, string> = {
  letterlijk: "Letterlijk uit de bron",
  samengesteld: "Samengesteld uit bronpassages",
  // Ook een definitie die Lex formuleerde en de analist overnam (fase C); de onderbouwing zegt wie.
  geformuleerd: "Geformuleerd (door de analist of door Lex)",
};

export const OORDEEL_LABEL: Record<VoorbeeldOordeel, string> = {
  wel: "valt eronder",
  niet: "valt er niet onder",
  onzeker: "onzeker",
};

export const KOPPELROL_LABEL: Record<KoppelRol, string> = {
  duiding: "Duidt dit begrip aan",
  definitie: "Ondersteunt de definitie",
  context: "Context",
};

export const BEOORDELING_LABEL: Record<KoppelBeoordeling, string> = {
  open: "nog niet beoordeeld",
  akkoord: "akkoord",
  afgewezen: "afgewezen",
};

/** De stand van een passage nu. Alleen wat niet actueel is, vraagt aandacht. */
export const ACTUALITEIT_LABEL: Record<Actualiteit, string> = {
  actueel: "actueel",
  gewijzigd: "annotatie gewijzigd sinds koppelen",
  verworpen: "annotatie verworpen",
  verdwenen: "annotatie bestaat niet meer",
};

const ROL_VOLGORDE: Record<KoppelRol, number> = { duiding: 0, definitie: 1, context: 2 };

/** Passages: eerst wat het begrip aanduidt, dan wat de definitie draagt, dan context; daarbinnen op
 *  vindplaats (natuurlijk: lid 2 vóór lid 10) en tekst. */
export function sorteerKoppelingen(ks: readonly Koppeling[]): Koppeling[] {
  return [...ks].sort(
    (a, b) =>
      ROL_VOLGORDE[a.rol] - ROL_VOLGORDE[b.rol] ||
      a.bewijs.vindplaats.localeCompare(b.bewijs.vindplaats, "nl", { numeric: true }) ||
      a.bewijs.tekst.localeCompare(b.bewijs.tekst, "nl"),
  );
}

/** Een id uit de URL, of niets. */
export function begripUitParam(p: string | undefined): string | undefined {
  return p && /^[A-Za-z0-9-]{1,64}$/.test(p) ? p : undefined;
}

/** Het element duidt al een ander begrip aan (409 `al_primair`). */
export function isAlPrimair(e: unknown): boolean {
  return isApiError(e) && e.status === 409 && e.data?.fout === "al_primair";
}

/** Accorderen geweigerd door de poort (409 `poort`); de redenen staan in `data.redenen`. */
export function isPoortFout(e: unknown): boolean {
  return isApiError(e) && e.status === 409 && e.data?.fout === "poort";
}

const VELD: Record<keyof BegripInhoud, string> = {
  naam: "naam",
  alternatieve_termen: "alternatieve termen",
  context: "context",
  begripstype: "begripstype",
  jas_klasse: "JAS-duiding",
  jas_subtype: "subtype",
  geldigheid: "geldigheid",
  definitie: "definitie",
  definitie_herkomst: "herkomst van de definitie",
  definitie_door: "voorgesteld door",
  uitleg: "uitleg",
  onderbouwing: "onderbouwing",
  voorbeelden: "voorbeelden",
  eigenschappen: "eigenschappen",
  open_vragen: "open vragen",
};

const ACTIE: Record<string, string> = {
  "begrip-aangemaakt": "Aangemaakt",
  "begrip-gekoppeld": "Passages gekoppeld",
  "koppeling-gewijzigd": "Koppeling gewijzigd",
  "koppeling-verwijderd": "Passage losgemaakt",
  "begrip-geaccordeerd": "Geaccordeerd",
  "begrip-heropend": "Heropend",
  "begrip-verwijderd": "Verwijderd",
  "koppeling-herkoppeld": "Passage herkoppeld aan haar opvolger",
  "koppeling-bevestigd": "Veranderde passage bevestigd",
  "begrip-vervangen": "Vervangen door een opvolger",
  "begrip-gecombineerd": "Gecombineerd met een ander begrip",
  "begrip-hersteld": "Teruggezet: de opvolger is verwijderd",
  "begrip-opgevolgd": "Opvolger gemaakt (nieuwe betekenis)",
};

/** Eén revisie als zin, voor de historie op de kaart. */
export function revisieZin(r: Pick<BegripRevisie, "actie" | "detail">): string {
  const d = r.detail ?? {};
  if (r.actie === "begrip-gewijzigd") {
    const velden = Array.isArray(d.velden) ? (d.velden as (keyof BegripInhoud)[]).map((v) => VELD[v] ?? v) : [];
    return velden.length ? `Gewijzigd: ${velden.join(", ")}` : "Gewijzigd";
  }
  if (r.actie === "begrip-gekoppeld" || r.actie === "begrip-aangemaakt") {
    const n = Array.isArray(d.element_ids) ? d.element_ids.length : 0;
    const basis = ACTIE[r.actie];
    return n ? `${basis} (${n === 1 ? "1 passage" : `${n} passages`})` : basis;
  }
  if (r.actie === "voorstel-overgenomen") {
    // Lex naast de kaart (fase E): het voorstel, en of de analist het aanpaste.
    const veld = typeof d.veld === "string" ? (VELD[d.veld as keyof BegripInhoud] ?? d.veld).toLowerCase() : "";
    return `${d.aangepast ? "Aangepast overgenomen" : "Overgenomen"} van Lex${veld ? `: ${veld}` : ""}`;
  }
  if (r.actie === "koppeling-gewijzigd" && typeof d.beoordeling === "string") {
    return `Passage beoordeeld: ${BEOORDELING_LABEL[d.beoordeling as KoppelBeoordeling] ?? d.beoordeling}`;
  }
  return ACTIE[r.actie] ?? r.actie;
}

/** Eigenschappen worden als rijen bewerkt: een sleutel hernoemen in een object kan niet zonder de
 *  volgorde kwijt te raken. */
export function naarRijen(eigenschappen: Record<string, string>): [string, string][] {
  return Object.entries(eigenschappen);
}

/** Terug naar een object; rijen zonder sleutel vallen weg, bij een dubbele sleutel wint de laatste. */
export function uitRijen(rijen: readonly [string, string][]): Record<string, string> {
  return Object.fromEntries(rijen.map(([k, v]) => [k.trim(), v] as const).filter(([k]) => k));
}

/** Een lijst als tekst met één item per regel, en terug. */
export const regels = (xs: readonly string[]) => xs.join("\n");
export const uitRegels = (tekst: string) => tekst.split("\n");
