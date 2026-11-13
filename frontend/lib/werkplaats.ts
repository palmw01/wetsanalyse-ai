// De werkplaats (ADR-016 deel B): wat een gebruiker zelf maakt, als concept met versies. De spiegel van de api
// (`/v1/werkplaats/*`, `api/app/werkplaats_store.py`) en van `bronmodel/werkplaats.py`; `werkplaats.test.ts` toetst de
// soorten en de naamvorm tegen de Python-bron. Hier staat ook de ene functie die van de velden van de api een stand
// maakt, zodat de lijst, de pagina van een methode en de editor hetzelfde zeggen.
import type { StatusToon } from "@/components/ui/Lijst";
import type { Soort as CatalogusSoort } from "@/lib/catalogus";

export const WERKPLAATS_SOORTEN = ["skill", "agentprofiel", "mcp"] as const;
export type WerkplaatsSoort = (typeof WERKPLAATS_SOORTEN)[number];

/** Welke soorten de editor nu opent. Het register kent er meer; een profiel volgt met dezelfde editor (B5). */
export const IN_EDITOR: readonly WerkplaatsSoort[] = ["skill"];

export const WERKPLAATS_SOORT_LABEL: Record<WerkplaatsSoort, string> = {
  skill: "Skill", agentprofiel: "Agentprofiel", mcp: "MCP-server",
};

/** De naam van een skill: kleine letters, cijfers en losse koppeltekens (`bronmodel.skill.NAAM`). De api beslist; dit
 *  is alleen om een tikfout te zeggen voordat het formulier weggaat. */
export const SKILL_NAAM = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const MAX_SKILL_NAAM = 64;

export interface Bevinding { code: string; melding: string; bestand: string }

export interface WerkplaatsVersie {
  id: string;
  nummer: number;
  hash: string;
  basis_hash: string;
  toelichting: string;
  geldig: boolean;
  bevindingen: Bevinding[];
  door: string;
  gemaakt: string;
  /** Draait precies deze versie? `null`: de api weet niet wat er draait. */
  actief: boolean | null;
  /** Alleen bij het lezen van één versie. */
  bestanden?: Record<string, string>;
}

export interface WerkplaatsOnderdeel {
  id: string;
  soort: WerkplaatsSoort;
  naam: string;
  eigenaar: string;
  gedeeld: boolean;
  stand: "concept" | "actief" | "ingetrokken";
  /** De drie hieronder zijn `null` als de api niet weet wat er draait (`image_bekend: false`): onbekend, niet "nee". */
  in_image: boolean | null;
  actief_versie: number | null;
  basis_verouderd: boolean | null;
  image_bekend: boolean;
  versies: number;
  laatste: WerkplaatsVersie | null;
  zelfde_naam: number;
  gemaakt: string;
  bijgewerkt: string;
  /** Alleen bij het lezen van één onderdeel. */
  versielijst?: WerkplaatsVersie[];
}

export interface WerkplaatsStand {
  aan: boolean;
  mag_maken: boolean;
  beheerder: boolean;
  image: { bekend: boolean; revisie: string; gemeld_op: string };
  grenzen: { bestanden: number; tekens_per_bestand: number; tekens: number; versies: number; onderdelen: number };
}

/** De werkplaats staat uit: geen knop, geen groep, niets. Ook het antwoord op alles wat niet te lezen is. */
export const UIT: WerkplaatsStand = {
  aan: false, mag_maken: false, beheerder: false, image: { bekend: false, revisie: "", gemeld_op: "" },
  grenzen: { bestanden: 0, tekens_per_bestand: 0, tekens: 0, versies: 0, onderdelen: 0 },
};

const getal = (x: unknown): number => (typeof x === "number" && Number.isFinite(x) ? x : 0);
const tekst = (x: unknown): string => (typeof x === "string" ? x : "");
const jaNeeOnbekend = (x: unknown): boolean | null => (typeof x === "boolean" ? x : null);

/** Tolerant: een antwoord dat geen stand is (een lege body, een fout, een oudere api) is "uit". */
export function parseStand(x: unknown): WerkplaatsStand {
  const s = x as Record<string, unknown> | null;
  if (!s || s.aan !== true) return UIT;
  const image = (s.image ?? {}) as Record<string, unknown>;
  const g = (s.grenzen ?? {}) as Record<string, unknown>;
  return {
    aan: true, mag_maken: s.mag_maken === true, beheerder: s.beheerder === true,
    image: { bekend: image.bekend === true, revisie: tekst(image.revisie), gemeld_op: tekst(image.gemeld_op) },
    grenzen: { bestanden: getal(g.bestanden), tekens_per_bestand: getal(g.tekens_per_bestand), tekens: getal(g.tekens),
      versies: getal(g.versies), onderdelen: getal(g.onderdelen) },
  };
}

function parseBevindingen(x: unknown): Bevinding[] {
  return Array.isArray(x) ? x.filter((b) => b && typeof b.code === "string")
    .map((b) => ({ code: b.code, melding: tekst(b.melding), bestand: tekst(b.bestand) })) : [];
}

export function parseVersie(x: unknown): WerkplaatsVersie | null {
  const v = x as Record<string, unknown> | null;
  if (!v || typeof v.nummer !== "number" || typeof v.hash !== "string") return null;
  const bestanden = v.bestanden && typeof v.bestanden === "object"
    ? Object.fromEntries(Object.entries(v.bestanden as Record<string, unknown>).filter(([, t]) => typeof t === "string")) as Record<string, string>
    : undefined;
  return {
    id: tekst(v.id), nummer: v.nummer, hash: v.hash, basis_hash: tekst(v.basis_hash), toelichting: tekst(v.toelichting),
    geldig: v.geldig === true, bevindingen: parseBevindingen(v.bevindingen), door: tekst(v.door), gemaakt: tekst(v.gemaakt),
    actief: jaNeeOnbekend(v.actief), ...(bestanden ? { bestanden } : {}),
  };
}

/** Streng: een rij zonder id, met een onbekende soort of stand valt weg, zodat de pagina nooit half tekent. */
export function parseOnderdeel(x: unknown): WerkplaatsOnderdeel | null {
  const o = x as Record<string, unknown> | null;
  if (!o || typeof o.id !== "string" || !o.id || typeof o.naam !== "string"
    || !(WERKPLAATS_SOORTEN as readonly string[]).includes(tekst(o.soort))
    || !["concept", "actief", "ingetrokken"].includes(tekst(o.stand))) return null;
  const bekend = o.image_bekend === true;
  const lijst = Array.isArray(o.versielijst)
    ? o.versielijst.map(parseVersie).filter((v): v is WerkplaatsVersie => v !== null) : undefined;
  return {
    id: o.id, soort: o.soort as WerkplaatsSoort, naam: o.naam, eigenaar: tekst(o.eigenaar), gedeeld: o.gedeeld === true,
    stand: o.stand as WerkplaatsOnderdeel["stand"],
    in_image: bekend ? jaNeeOnbekend(o.in_image) : null,
    actief_versie: bekend && typeof o.actief_versie === "number" ? o.actief_versie : null,
    basis_verouderd: bekend ? jaNeeOnbekend(o.basis_verouderd) : null,
    image_bekend: bekend, versies: getal(o.versies), laatste: parseVersie(o.laatste), zelfde_naam: getal(o.zelfde_naam),
    gemaakt: tekst(o.gemaakt), bijgewerkt: tekst(o.bijgewerkt), ...(lijst ? { versielijst: lijst } : {}),
  };
}

export function parseOnderdelen(x: unknown): WerkplaatsOnderdeel[] {
  return Array.isArray(x) ? x.map(parseOnderdeel).filter((o): o is WerkplaatsOnderdeel => o !== null) : [];
}

export interface StandLabel { tekst: string; toon: StatusToon; uitleg: string }

/** De stand van een concept in woorden. Eén functie voor de lijst, de pagina van een methode en de editor.
 *
 *  "Nog onbekend" is geen "draait niet": zolang de api niet weet wat er draait, zegt het label dat, en niets anders. */
export function standLabel(o: Pick<WerkplaatsOnderdeel, "stand" | "image_bekend" | "basis_verouderd" | "actief_versie" | "laatste">): StandLabel {
  if (o.stand === "ingetrokken") return { tekst: "Ingetrokken", toon: "neutraal", uitleg: "Dit concept is ingetrokken. De versies blijven te lezen." };
  if (!o.image_bekend) return { tekst: "Concept · nog onbekend wat er draait", toon: "neutraal",
    uitleg: "Lex heeft nog niet gemeld welke versie er draait. Of dit concept daarvan afwijkt, is nu niet te zeggen." };
  if (o.stand === "actief") return { tekst: "Draait nu", toon: "groen", uitleg: "De laatste versie van dit concept is de versie die Lex gebruikt." };
  if (o.basis_verouderd) return { tekst: "Concept · loopt achter", toon: "geel",
    uitleg: "Er draait intussen een andere versie dan waar dit concept op voortbouwt." };
  return { tekst: "Concept", toon: "lint", uitleg: o.actief_versie
    ? `Versie ${o.actief_versie} draait; de laatste versie nog niet.` : "Dit concept draait niet; het is alleen hier te lezen en te bewerken." };
}

/** Het label van de laatste versie: geldig, of hoeveel bevindingen poort 1 gaf. */
export function geldigLabel(v: Pick<WerkplaatsVersie, "geldig" | "bevindingen"> | null): StandLabel | null {
  if (!v) return null;
  if (v.geldig) return { tekst: "Geldig", toon: "groen", uitleg: "De laatste versie haalt de controle." };
  const n = v.bevindingen.length;
  return { tekst: n === 1 ? "1 bevinding" : `${n} bevindingen`, toon: "geel",
    uitleg: "De laatste versie haalt de controle niet. Ze is bewaard, maar kan zo niet verder." };
}

export function conceptPad(id: string): string {
  return `/werkwijze/concepten/${encodeURIComponent(id)}`;
}

/** Welke soort in de werkplaats hoort bij een onderdeel van de catalogus; `null` als het daar niet te bewerken is. */
export function werkplaatsSoortVan(soort: CatalogusSoort): WerkplaatsSoort | null {
  const s: WerkplaatsSoort | null = soort === "methode" ? "skill" : soort === "agentprofiel" ? "agentprofiel" : null;
  return s && IN_EDITOR.includes(s) ? s : null;
}

/** Het eigen, niet-ingetrokken concept van deze soort en naam, als het er is: één per eigenaar. */
export function eigenConcept(lijst: WerkplaatsOnderdeel[], soort: WerkplaatsSoort, naam: string, userid: string | undefined): WerkplaatsOnderdeel | null {
  return lijst.find((o) => o.soort === soort && o.naam === naam && o.eigenaar === userid && o.stand !== "ingetrokken") ?? null;
}

/** De concepten voor het overzicht: wat de editor opent, de eigen eerst, ingetrokken onderaan, dan op naam. */
export function voorOverzicht(lijst: WerkplaatsOnderdeel[], userid: string | undefined): WerkplaatsOnderdeel[] {
  const rang = (o: WerkplaatsOnderdeel) => (o.stand === "ingetrokken" ? 2 : o.eigenaar === userid ? 0 : 1);
  return lijst.filter((o) => IN_EDITOR.includes(o.soort))
    .sort((a, b) => rang(a) - rang(b) || a.naam.localeCompare(b.naam, "nl") || a.id.localeCompare(b.id));
}

/** Wat er fout is aan een naam, of leeg. */
export function naamFout(naam: string): string {
  if (!naam) return "";
  if (naam.length > MAX_SKILL_NAAM) return `Hoogstens ${MAX_SKILL_NAAM} tekens.`;
  return SKILL_NAAM.test(naam) ? "" : "Alleen kleine letters, cijfers en losse koppeltekens, bijvoorbeeld jrm-scenario.";
}

/** De bestanden van een versie in een vaste volgorde: het hoofdbestand, de bestanden in de wortel, dan per map. */
export function bestandsvolgorde(paden: string[]): string[] {
  const rang = (p: string) => (p === "SKILL.md" ? 0 : p.includes("/") ? 2 : 1);
  return [...paden].sort((a, b) => rang(a) - rang(b) || a.localeCompare(b, "nl"));
}
