// De contenttoets (plan docs/architectuur/plan-contenttoets.md): de spiegel van `packages/bronmodel/bronmodel/contenttoets.py`.
// `contenttoets.test.ts` leest die bron en vergelijkt de oordelen, de criteria en de telling.

import { aantal } from "./aantal";
import type { AntwoordVindplaats } from "./antwoord";
import type { StatusToon } from "@/components/ui/Lijst";

export type Oordeel = "juist" | "mogelijk_onjuist" | "onvolledig" | "niet_in_de_bron";

/** De volgorde van de telling: wat om een wijziging vraagt eerst. */
export const OORDELEN: readonly Oordeel[] = ["mogelijk_onjuist", "onvolledig", "niet_in_de_bron", "juist"];

export const OORDEEL_LABEL: Record<Oordeel, string> = {
  juist: "Juist", mogelijk_onjuist: "Mogelijk onjuist", onvolledig: "Onvolledig", niet_in_de_bron: "Niet in de bron",
};

export const OORDEEL_TELLING: Record<Oordeel, string> = {
  mogelijk_onjuist: "mogelijk onjuist", onvolledig: "onvolledig", niet_in_de_bron: "niet in de bron", juist: "juist",
};

/** De toon van het label: het oordeel draagt de kleur (rood, geel, grijs, groen), zoals in de mockup. */
export const OORDEEL_TOON: Record<Oordeel, StatusToon> = {
  mogelijk_onjuist: "rood", onvolledig: "geel", niet_in_de_bron: "neutraal", juist: "groen",
};

export const CRITERIA: Record<string, string> = {
  J1: "Waarde", J2: "Voorwaarde en uitzondering", J3: "Reikwijdte", J4: "Modaliteit", J5: "Telmoment", J6: "Samenhang",
  J7: "Geldigheid", V1: "Voorwaarde ontbreekt", V2: "Gevolg ontbreekt", V3: "Uitzondering ontbreekt",
};

export const criteriumTekst = (code: string) => (CRITERIA[code] ? `${code} ${CRITERIA[code]}` : "");

export interface ToetsBron { tekst: string; vindplaats: AntwoordVindplaats }

export interface Toetsbevinding {
  nr: number; citaat: string; begin: number; eind: number; oordeel: Oordeel; criterium: string;
  bronnen: ToetsBron[]; toelichting: string; twijfel: string; voorstel: string;
}

export interface ContenttoetsBlok {
  soort: "contenttoets"; door: "lex"; content: string; peildatum: string; getoetst_tegen: string[];
  voor_redacteur: string[]; bevindingen: Toetsbevinding[]; ontbreekt: { tekst: string; bronnen: ToetsBron[] }[];
  niet_getoetst: string[];
}

export function aantallen(b: Pick<ContenttoetsBlok, "bevindingen">): Record<Oordeel, number> {
  const uit: Record<Oordeel, number> = { mogelijk_onjuist: 0, onvolledig: 0, niet_in_de_bron: 0, juist: 0 };
  for (const x of b.bevindingen) uit[x.oordeel] += 1;
  return uit;
}

/** "11 beweringen: 3 mogelijk onjuist, 2 onvolledig, 2 niet in de bron, 4 juist. 1 punt ontbreekt.", zoals
 *  `telling_tekst` in `bronmodel/contenttoets.py`. */
export function tellingTekst(b: Pick<ContenttoetsBlok, "bevindingen" | "ontbreekt">): string {
  const n = aantallen(b);
  const totaal = OORDELEN.reduce((s, o) => s + n[o], 0);
  const delen = OORDELEN.filter((o) => n[o]).map((o) => `${n[o]} ${OORDEEL_TELLING[o]}`);
  let zin = `${aantal(totaal, "bewering", "beweringen")}${delen.length ? `: ${delen.join(", ")}.` : "."}`;
  const ontbreekt = b.ontbreekt.length;
  if (ontbreekt) zin += ` ${aantal(ontbreekt, "punt ontbreekt", "punten ontbreken")}.`;
  return zin;
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isBron = (v: unknown) => isObject(v) && typeof v.tekst === "string" && isObject(v.vindplaats) &&
  typeof v.vindplaats.iri === "string" && typeof v.vindplaats.label === "string";

/** Streng, zoals elk blok: een bevinding met een gat (geen oordeel, een plek buiten de content) maakt het blok ongeldig. */
export function isContenttoets(b: Record<string, unknown>): boolean {
  if (typeof b.content !== "string" || !Array.isArray(b.bevindingen)) return false;
  const lengte = [...b.content].length;
  return b.bevindingen.every((x) => isObject(x) && typeof x.citaat === "string" && OORDELEN.includes(x.oordeel as Oordeel) &&
    typeof x.begin === "number" && typeof x.eind === "number" && x.begin >= 0 && x.eind <= lengte && x.begin <= x.eind &&
    Array.isArray(x.bronnen) && x.bronnen.every(isBron)) &&
    (b.ontbreekt == null || (Array.isArray(b.ontbreekt) && b.ontbreekt.every((o) => isObject(o) && typeof o.tekst === "string")));
}

/** Een stuk van de content in het zijpaneel: gewone tekst, of de tekst van één bevinding (`nr`). */
export interface ContentDeel { tekst: string; nr?: number; oordeel?: Oordeel }

/** De content in stukken, met de bevindingen als markering (fase 2 van het plan, het zijpaneel). `begin` en `eind` zijn
 *  Unicode-codepoints, zoals in `bronmodel` (`[...tekst]`, niet `tekst.slice`: een emoji of een samengesteld teken telt
 *  anders mee). Overlappen twee bevindingen, dan krijgt de eerste de tekst en de tweede alleen het deel erna; een
 *  bevinding zonder eigen tekst (eind = begin, of helemaal overlapt) staat in de lijst, niet in de content. */
export function contentDelen(b: Pick<ContenttoetsBlok, "content" | "bevindingen">): ContentDeel[] {
  const tekens = [...b.content];
  const marks = [...b.bevindingen].filter((x) => x.eind > x.begin).sort((x, y) => x.begin - y.begin || x.nr - y.nr);
  const uit: ContentDeel[] = [];
  let plek = 0;
  for (const m of marks) {
    const begin = Math.max(m.begin, plek);
    const eind = Math.min(m.eind, tekens.length);
    if (eind <= begin) continue;
    if (begin > plek) uit.push({ tekst: tekens.slice(plek, begin).join("") });
    uit.push({ tekst: tekens.slice(begin, eind).join(""), nr: m.nr, oordeel: m.oordeel });
    plek = eind;
  }
  if (plek < tekens.length) uit.push({ tekst: tekens.slice(plek).join("") });
  return uit;
}

/** De sleutel van de tab van een toets: dezelfde toets is dezelfde tab, een nieuwe toets van dezelfde tekst ook (hij
 *  vervangt de vorige op haar plek). Een korte hash van de content en de peildatum; geen inhoud in de sleutel. */
export function toetsSleutel(b: Pick<ContenttoetsBlok, "content" | "peildatum">): string {
  let h = 5381;
  for (const c of `${b.peildatum}\n${b.content}`) h = ((h * 33) ^ c.codePointAt(0)!) >>> 0;
  return h.toString(36);
}

// ── Het oordeel van de mens (C7) ────────────────────────────────────────────────────────────────────────────────────
// De spiegel van TOETSOORDELEN en VOORSTELBESLUITEN in `bronmodel/contenttoets.py` (drift: `contenttoets.test.ts`).

export type ToetsOordeel = "eens" | "oneens";
export type VoorstelBesluit = "overgenomen" | "aangepast" | "afgewezen";

export const TOETSOORDELEN: readonly ToetsOordeel[] = ["eens", "oneens"];
export const VOORSTELBESLUITEN: readonly VoorstelBesluit[] = ["overgenomen", "aangepast", "afgewezen"];
export const TOETSOORDEEL_LABEL: Record<ToetsOordeel, string> = { eens: "Eens", oneens: "Oneens" };
export const VOORSTELBESLUIT_LABEL: Record<VoorstelBesluit, string> = {
  overgenomen: "Overgenomen", aangepast: "Aangepast", afgewezen: "Afgewezen",
};

export interface ToetsbesluitInvoer { oordeel?: ToetsOordeel | null; voorstel?: VoorstelBesluit | null; tekst?: string; reden?: string }
export interface Toetsbesluit { nr: number; oordeel: ToetsOordeel | null; voorstel: VoorstelBesluit | null; tekst: string; reden: string; door: string; op: string }

/** Waar de besluiten van een toets staan: het bericht dat de run schreef, in dit gesprek. */
export interface ToetsBericht { gesprek_id: string; run_id: string }

/** Hoeveel bevindingen beoordeeld zijn: een oordeel, of bij een voorstel ook een besluit daarover. */
export function beoordeeld(b: Pick<ContenttoetsBlok, "bevindingen">, besluiten: readonly Toetsbesluit[]): number {
  const per = new Map(besluiten.map((x) => [x.nr, x]));
  return b.bevindingen.filter((x) => {
    const d = per.get(x.nr);
    return !!d?.oordeel && (!x.voorstel || !!d.voorstel);
  }).length;
}

/** De tekst die in de content komt: het aangepaste voorstel, anders het overgenomen voorstel, anders niets. */
export function nieuweTekst(b: Toetsbevinding, d?: Toetsbesluit): string {
  return d?.voorstel === "aangepast" ? d.tekst : d?.voorstel === "overgenomen" ? b.voorstel : "";
}

/** Het rapport als Markdown, om te kopiëren of te bewaren: lijsten, geen tabel, zodat het overal heel blijft. Met de
 *  besluiten van de redacteur erbij; een bevinding zonder besluit zegt dat. */
export function toetsMarkdown(b: ContenttoetsBlok, besluiten: readonly Toetsbesluit[] = []): string {
  const per = new Map(besluiten.map((x) => [x.nr, x]));
  const tegen = b.getoetst_tegen.length ? b.getoetst_tegen.join(", ") : "de wet- en regelgeving in de graaf";
  const r: string[] = ["# Contenttoets", "", `Getoetst tegen ${tegen}${b.peildatum ? `, geldend op ${b.peildatum}` : ""}.`,
    tellingTekst(b), `Beoordeeld: ${beoordeeld(b, besluiten)} van ${b.bevindingen.length}.`, ""];
  if (b.voor_redacteur.length) r.push("## Voor de redacteur", "", ...b.voor_redacteur.map((x) => `- ${x}`), "");
  r.push("## Per bewering", "");
  for (const x of b.bevindingen) {
    const d = per.get(x.nr);
    r.push(`### [${x.nr}] ${OORDEEL_LABEL[x.oordeel]}${x.criterium ? ` – ${criteriumTekst(x.criterium)}` : ""}`, "",
      `- De tekst: “${x.citaat}”`);
    for (const bron of x.bronnen) r.push(`- De bron (${bron.vindplaats.label}${bron.vindplaats.regeling ? `, ${bron.vindplaats.regeling}` : ""}): “${bron.tekst}”`);
    if (x.toelichting) r.push(`- Toelichting van Lex: ${x.toelichting}`);
    if (x.twijfel) r.push(`- Twijfel of aanname: ${x.twijfel}`);
    if (x.voorstel) r.push(`- ${x.oordeel === "niet_in_de_bron" ? "Vraag" : "Voorstel"} van Lex: ${x.voorstel}`);
    if (!d) r.push("- Besluit: nog niet beoordeeld");
    else {
      const delen = [d.oordeel ? `${TOETSOORDEEL_LABEL[d.oordeel].toLowerCase()} met Lex` : "",
        d.voorstel ? `voorstel ${VOORSTELBESLUIT_LABEL[d.voorstel].toLowerCase()}` : ""].filter(Boolean);
      r.push(`- Besluit: ${delen.join(", ") || "geen"} (${d.door})`);
      if (d.voorstel === "aangepast") r.push(`- Nieuwe tekst: ${d.tekst}`);
      if (d.reden) r.push(`- Reden: ${d.reden}`);
    }
    r.push("");
  }
  if (b.ontbreekt.length) {
    r.push("## Ontbreekt", "");
    for (const o of b.ontbreekt) {
      r.push(`- ${o.tekst}`);
      for (const bron of o.bronnen) r.push(`  - ${bron.vindplaats.label}: “${bron.tekst}”`);
    }
    r.push("");
  }
  if (b.niet_getoetst.length) r.push("## Niet getoetst", "", ...b.niet_getoetst.map((x) => `- ${x}`), "");
  r.push("Lex stelt voor; de redacteur en de jurist beoordelen. Dit rapport is geen juridisch advies.");
  return r.join("\n");
}

export function parseToetsbesluiten(v: unknown): Toetsbesluit[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is Toetsbesluit => isObject(x) && typeof x.nr === "number" &&
    (x.oordeel == null || TOETSOORDELEN.includes(x.oordeel as ToetsOordeel)) &&
    (x.voorstel == null || VOORSTELBESLUITEN.includes(x.voorstel as VoorstelBesluit)))
    .map((x) => ({ ...x, oordeel: x.oordeel ?? null, voorstel: x.voorstel ?? null, tekst: x.tekst ?? "", reden: x.reden ?? "" }));
}
