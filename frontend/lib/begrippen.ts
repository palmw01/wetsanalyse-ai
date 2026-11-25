// Rekenkern van de begrippenwerkplek (spoor D, levering 2): labels, de inhoud aanvullen en de
// volgorde van passages. Puur, voor vitest.

import { aantal } from "./aantal";
import type {
  Actualiteit,
  Begrip,
  BegripInhoud,
  BegripKlasse,
  BegripRevisie,
  BegripSamenvatting,
  DefinitieHerkomst,
  KoppelBeoordeling,
  KoppelRol,
  KoppelStand,
  Koppeling,
  VoorbeeldOordeel,
  WaardeSoort,
  Waardebereik,
} from "./types";

export const LEGE_INHOUD: BegripInhoud = {
  naam: "",
  alternatieve_termen: [],
  context: "",
  definitie: "",
  definitie_herkomst: null,
  uitleg: "",
  voorbeelden: [],
};

/** Vult een inhoud van de api aan tot een volledige: een ouder begrip kan velden missen. Alleen de velden
 *  van het slanke model (spoor I1) blijven over. */
export function volledigeInhoud(inhoud: Partial<BegripInhoud>): BegripInhoud {
  const uit = { ...LEGE_INHOUD } as Record<string, unknown>;
  for (const k of [...Object.keys(LEGE_INHOUD), "definitie_door"]) {
    if (k in inhoud) uit[k] = (inhoud as Record<string, unknown>)[k];
  }
  const i = uit as unknown as BegripInhoud;
  return { ...i, voorbeelden: (i.voorbeelden ?? []).map((v) => ({ tekst: v.tekst, oordeel: v.oordeel })) };
}

export const HERKOMST_LABEL: Record<DefinitieHerkomst, string> = {
  letterlijk: "Letterlijk uit de bron",
  samengesteld: "Samengesteld uit bronpassages",
  geformuleerd: "Geformuleerd",
};

/** Wat voor definitie dit is, in de woorden van de begripskaart (spoor G5). Een analysebegrip is niet
 *  automatisch een wettelijke definitie: alleen een letterlijk overgenomen brondefinitie is dat; een
 *  samengestelde of geformuleerde definitie is een analyse-uitkomst. Zonder definitie: nog niets. */
export function definitieAard(inhoud: { definitie?: string; definitie_herkomst?: DefinitieHerkomst | "" | null }):
  { soort: "brondefinitie" | "analysebegrip" | "geen"; titel: string; uitleg: string } {
  if (!inhoud.definitie?.trim()) return { soort: "geen", titel: "Nog geen definitie", uitleg: "De betekenis is nog niet vastgelegd." };
  if (inhoud.definitie_herkomst === "letterlijk")
    return { soort: "brondefinitie", titel: "Brondefinitie",
      uitleg: "Letterlijk uit de wettekst overgenomen; de bronpassage is de wettelijke definitie." };
  return { soort: "analysebegrip", titel: "Analysebegrip",
    uitleg: inhoud.definitie_herkomst === "samengesteld"
      ? "Samengesteld uit bronpassages. Dit is een analyse-uitkomst, geen wettelijke definitie."
      : "Geformuleerd in de analyse. Dit is een analyse-uitkomst, geen wettelijke definitie." };
}

export const OORDEEL_LABEL: Record<VoorbeeldOordeel, string> = {
  wel: "valt eronder",
  niet: "valt er niet onder",
  onzeker: "twijfel",
};

/** De kleur van een oordeel (spoor I3): groen valt eronder, rood niet, oker twijfel. Kleur draagt het oordeel
 *  nooit alleen: het label staat er altijd bij. */
export const OORDEEL_TOON: Record<VoorbeeldOordeel, "groen" | "rood" | "geel"> = {
  wel: "groen",
  niet: "rood",
  onzeker: "geel",
};

export const KOPPELROL_LABEL: Record<KoppelRol, string> = {
  duiding: "Duidt dit begrip aan",
  afgeleid: "Afleidingsregel die dit begrip afleidt",
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

const ROL_VOLGORDE: Record<KoppelRol, number> = { duiding: 0, afgeleid: 1, definitie: 2, context: 3 };

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

// Een revisie van vóór spoor I1 kan nog andere velden noemen; die verschijnen zoals de api ze noemt.
const VELD: Record<string, string> = {
  naam: "naam",
  alternatieve_termen: "alternatieve termen",
  context: "toelichting",
  definitie: "definitie",
  definitie_herkomst: "herkomst van de definitie",
  definitie_door: "voorgesteld door",
  uitleg: "uitleg",
  voorbeelden: "voorbeelden",
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

/** De kaart met de stand na een besluit erover. `null`: de stand noemt iets dat de kaart niet heeft (een nieuwe passage,
 *  een nieuwe bewijsstand), en dan hoort de kaart opnieuw opgehaald te worden. */
export function metKoppelstand(begrip: Begrip, stand: KoppelStand): Begrip | null {
  const oud = new Map(begrip.koppelingen.map((k) => [k.id, k]));
  if (stand.koppelingen.some((k) => !oud.has(k.id) || (oud.get(k.id)?.bevestigingen?.length ?? 0) !== k.bevestigingen)) return null;
  return { ...begrip, ...stand, koppelingen: stand.koppelingen.map(({ bevestigingen: _, ...k }) => ({ ...oud.get(k.id)!, ...k })) };
}

/** Eén revisie als zin, voor de historie op de kaart. */
export function revisieZin(r: Pick<BegripRevisie, "actie" | "detail">): string {
  const d = r.detail ?? {};
  if (r.actie === "begrip-gewijzigd") {
    const velden = Array.isArray(d.velden) ? (d.velden as string[]).map((v) => VELD[v] ?? v) : [];
    return velden.length ? `Gewijzigd: ${velden.join(", ")}` : "Gewijzigd";
  }
  if (r.actie === "begrip-gekoppeld" || r.actie === "begrip-aangemaakt") {
    const n = Array.isArray(d.element_ids) ? d.element_ids.length : 0;
    const basis = ACTIE[r.actie];
    return n ? `${basis} (${aantal(n, "passage", "passages")})` : basis;
  }
  if (r.actie === "voorstel-overgenomen") {
    // Lex naast de kaart (fase E): het voorstel, en of de analist het aanpaste.
    const veld = typeof d.veld === "string" ? (VELD[d.veld] ?? d.veld).toLowerCase() : "";
    return `${d.aangepast ? "Aangepast overgenomen" : "Overgenomen"} van Lex${veld ? `: ${veld}` : ""}`;
  }
  const koppelingen = Array.isArray(d.koppelingen) ? d.koppelingen.length : 0;
  if (r.actie === "koppeling-gewijzigd" && typeof d.beoordeling === "string") {
    const uitkomst = BEOORDELING_LABEL[d.beoordeling as KoppelBeoordeling] ?? d.beoordeling;
    return koppelingen ? `${koppelingen === 1 ? "Passage" : `${koppelingen} passages`} beoordeeld: ${uitkomst}` : `Passage beoordeeld: ${uitkomst}`;
  }
  if (r.actie === "koppeling-bevestigd" && koppelingen > 1) return `${koppelingen} veranderde passages bevestigd`;
  if (r.actie === "begrip-geaccordeerd" && typeof d.reden === "string" && d.reden) return `Geaccordeerd: ${d.reden}`;
  return ACTIE[r.actie] ?? r.actie;
}

/** Een lijst als tekst met één item per regel, en terug. */
export const regels = (xs: readonly string[]) => xs.join("\n");
export const uitRegels = (tekst: string) => tekst.split("\n");

export const EXPORT_FORMATEN = [
  { formaat: "csv" as const, label: "CSV", uitleg: "één rij per passage, met vindplaats en bron" },
  { formaat: "json" as const, label: "JSON", uitleg: "alle begrippen met hun koppelingen en bewijsstand" },
  { formaat: "ttl" as const, label: "Turtle (NL-SBB)", uitleg: "de geaccordeerde begrippen als begrippenkader, met conformiteit per begrip" },
  { formaat: "ttl-alle" as const, label: "Turtle, alle begrippen", uitleg: "ook concepten en vervangen begrippen, met hun status" },
];

export type BegripStatusFilter = "alle" | BegripSamenvatting["status"];

/** De begrippen van het kader bij een zoekterm en status. De zoekterm kijkt naar naam, alternatieve termen en definitie. */
export function filterBegrippen<T extends Pick<BegripSamenvatting, "status" | "inhoud">>(
  begrippen: readonly T[], { term, status }: { term: string; status: BegripStatusFilter }): T[] {
  const t = term.trim().toLowerCase();
  return begrippen.filter((b) => (status === "alle" || b.status === status) && (!t
    || [b.inhoud.naam, ...(b.inhoud.alternatieve_termen ?? []), b.inhoud.definitie ?? ""].some((x) => x.toLowerCase().includes(t))));
}


// --- Klasse, waardebereik en eigenaar (V2, V4) -----------------------------------------------------------------------

export const WAARDE_SOORT_LABEL: Record<WaardeSoort, string> = {
  ja_nee: "ja of nee", datum: "datum", bedrag: "bedrag", aantal: "aantal", duur: "duur", tekst: "tekst",
  opsomming: "een van een vaste lijst",
};

/** Het waardebereik in één regel: "bedrag in euro, 0 decimalen, vanaf 0" of "een van: april, mei". */
export function waardebereikZin(w: Waardebereik | null | undefined): string {
  if (!w) return "";
  const delen: string[] = [WAARDE_SOORT_LABEL[w.soort] ?? w.soort];
  if (w.eenheid) delen[0] += ` in ${w.eenheid}`;
  if (w.decimalen != null) delen.push(aantal(w.decimalen, "decimaal", "decimalen"));
  if (w.minimum && w.maximum) delen.push(`van ${w.minimum} tot en met ${w.maximum}`);
  else if (w.minimum) delen.push(`vanaf ${w.minimum}`);
  else if (w.maximum) delen.push(`tot en met ${w.maximum}`);
  let zin = delen.join(", ");
  if (w.soort === "opsomming" && w.waarden?.length) zin = `een van: ${w.waarden.join(", ")}`;
  return w.toelichting ? `${zin} (${w.toelichting})` : zin;
}

/** Wat de kaart over de klasse zegt: de klasse en waar ze vandaan komt. */
export function klasseZin(k: BegripKlasse | undefined): { klasse: string; herkomst: string } {
  if (!k || !k.klasse) return { klasse: "", herkomst: "" };
  if (k.gekozen && k.gekozen !== k.afgeleid) {
    return { klasse: k.gekozen, herkomst: k.afgeleid ? `gekozen; de passages zeggen ${k.afgeleid}` : "gekozen" };
  }
  const n = Object.values(k.uit_passages).reduce((s, x) => s + x, 0);
  return { klasse: k.klasse, herkomst: n ? `uit ${aantal(n, "passage", "passages")}` : "" };
}

/** De geldigheid van een begrip in één zin (B8), met de datum zoals de werkplek hem schrijft; leeg zonder datum. */
export function geldigheidZin(i: { geldig_vanaf?: string; geldig_tot?: string }): string {
  const d = (x: string) => x.split("-").reverse().join("-");
  const van = i.geldig_vanaf ? d(i.geldig_vanaf) : "", tot = i.geldig_tot ? d(i.geldig_tot) : "";
  if (van && tot) return `van ${van} tot en met ${tot}`;
  if (van) return `vanaf ${van}`;
  return tot ? `tot en met ${tot}` : "";
}

/** Het waardebereik uit de velden van het formulier; zonder soort geen waardebereik. Een opsomming leest één waarde
 *  per regel. */
export function waardebereikUit(v: { soort: string; eenheid: string; decimalen: string; minimum: string; maximum: string;
  waarden: string; toelichting: string }): Waardebereik | null {
  if (!v.soort) return null;
  const soort = v.soort as WaardeSoort;
  const decimalen = v.decimalen.trim() === "" ? null : Number(v.decimalen);
  return {
    soort, eenheid: v.eenheid.trim(), decimalen: Number.isFinite(decimalen) ? decimalen : null,
    minimum: v.minimum.trim(), maximum: v.maximum.trim(), toelichting: v.toelichting.trim(),
    waarden: soort === "opsomming" ? uitRegels(v.waarden).map((x) => x.trim()).filter(Boolean) : [],
  };
}
