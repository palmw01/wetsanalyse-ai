/** Een stuk uit een bronconnector in het bronvenster (ADR-013, het bronvenster-plan PR 6). Generiek: wat een stuk is, hoe
 *  de kop eruitziet en welke gegevens erbij horen, komt uit de beschrijving van de connector die graph-qa meegeeft
 *  (`GET /v1/bronnen/{connector}/stukken/{id}`); niets hier kent Kamerstukken. De rekenkern is puur (`bronStuk.test.ts`);
 *  `haalStuk` is de enige aanroep. */
import type { AntwoordBlok } from "@/lib/antwoord";
import { datumTekst } from "@/lib/graaf/knoopinfo";
import type { Herkomst, StandMeldingData } from "@/lib/herkomst";
import { bronHref } from "@/lib/url";

/** Eén passage van een stuk, zoals de leestool haar geeft: de vorm van het blok `extern`. */
export type StukPassage = Extract<AntwoordBlok, { soort: "extern" }>["passages"][number];

export interface StukBeschrijving {
  naam: string; label: string; groep: string; brontype: string; id_prefixen: string[];
  metadata: { sleutel: string; label: string }[];
}

export interface StukDeel {
  status: string;
  volledig?: boolean;
  /** `id`, `label`, `link`, `bron_hash`, `gewijzigd`, `gevalideerd`, en de metadata (`soort`, `datum`, …). */
  stuk?: Record<string, unknown>;
  inhoud?: { kop: string; offset: number }[];
  inhoud_ingekort?: boolean;
  resultaten?: StukPassage[];
  vervolg?: { args?: { offset?: number } };
  reden?: string;
  melding?: string;
}

export interface StukAntwoord { beschrijving: StukBeschrijving; deel: StukDeel }

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/** Streng op de beschrijving; het leesresultaat neemt hij zoals de leestool het geeft (een fout is ook een resultaat). */
export function parseStuk(v: unknown): StukAntwoord | undefined {
  if (!isObject(v) || !isObject(v.connector) || !isObject(v.resultaat)) return undefined;
  const c = v.connector;
  if (typeof c.naam !== "string" || typeof c.label !== "string" || !Array.isArray(c.metadata)) return undefined;
  const deel = v.resultaat as unknown as StukDeel;
  if (typeof deel.status !== "string") return undefined;
  return {
    beschrijving: {
      naam: c.naam, label: c.label, groep: String(c.groep ?? ""), brontype: String(c.brontype ?? ""),
      id_prefixen: Array.isArray(c.id_prefixen) ? c.id_prefixen.map(String) : [],
      metadata: (c.metadata as unknown[]).filter(isObject).map((m) => ({ sleutel: String(m.sleutel), label: String(m.label) })),
    },
    deel: { ...deel, resultaten: Array.isArray(deel.resultaten) ? deel.resultaten : [] },
  };
}

export async function haalStuk(connector: string, id: string, offset = 0): Promise<StukAntwoord> {
  const r = await fetch(`/api/bronnen/${encodeURIComponent(connector)}/${encodeURIComponent(id)}${offset ? `?offset=${offset}` : ""}`,
    { cache: "no-store" });
  if (!r.ok) throw new Error(r.status === 404 ? "Deze bron staat in deze omgeving niet aan." : "De bron is nu niet bereikbaar.");
  const stuk = parseStuk(await r.json());
  if (!stuk) throw new Error("De bron gaf een antwoord dat de werkplek niet kent.");
  return stuk;
}

/** Waar het volgende deel begint, als er meer is. */
export function volgendeOffset(deel: StukDeel): number | undefined {
  const o = deel.vervolg?.args?.offset;
  return deel.volledig === false && typeof o === "number" ? o : undefined;
}

const tekst = (v: unknown): string => (Array.isArray(v) ? v.map(String).join(", ") : typeof v === "string" ? v : v == null ? "" : String(v));

/** De gegevens van het stuk in de volgorde en de woorden van de beschrijving; een datum in gewone woorden. Wat het stuk
 *  niet heeft, blijft weg. */
export function stukGegevens(b: StukBeschrijving, stuk: Record<string, unknown> | undefined): { label: string; waarde: string }[] {
  if (!stuk) return [];
  return b.metadata
    .map((m) => {
      const w = tekst(stuk[m.sleutel]);
      return { label: m.label, waarde: /^\d{4}-\d{2}-\d{2}/.test(w) ? datumTekst(w.slice(0, 10)) : w };
    })
    .filter((g) => g.waarde && g.waarde !== "true" && g.waarde !== "false");
}

/** De herkomst van een stuk voor de kop: het label als titel, de groep · soort · datum eronder, en de officiële vindplaats. */
export function stukHerkomst(b: StukBeschrijving | undefined, stuk: Record<string, unknown> | undefined, terugval: string): Herkomst {
  const datum = tekst(stuk?.datum);
  const plek = [tekst(stuk?.soort), datum ? datumTekst(datum.slice(0, 10)) : ""].filter(Boolean).join(" · ");
  return {
    bepaling: tekst(stuk?.label) || terugval, regeling: b?.groep ?? "", bwb_id: "", plek, plekVoluit: tekst(stuk?.titel) || plek,
    href: bronHref(tekst(stuk?.link)),
  };
}

/** Wat er over de stand van het stuk te zeggen valt: een andere versie dan Lex las, een bewaarde versie bij een storing,
 *  alleen een PDF. */
export function stukMeldingen(deel: StukDeel | undefined, gelezen?: { bron_hash: string }): StandMeldingData[] {
  if (!deel) return [];
  const uit: StandMeldingData[] = [];
  if (deel.reden === "alleen_pdf") {
    uit.push({ soort: "alleen-pdf", tekst: "Dit stuk staat bij de bron alleen als PDF: de tekst is niet te lezen. Open het bij de bron." });
  }
  const hash = tekst(deel.stuk?.bron_hash);
  if (gelezen?.bron_hash && hash && hash !== gelezen.bron_hash) {
    uit.push({ soort: "stuk-gewijzigd", tekst: "Dit stuk is gewijzigd sinds Lex het las: de gemarkeerde passages staan op hun nummer en kunnen verschoven zijn." });
  }
  if (deel.stuk?.gevalideerd === false) {
    uit.push({ soort: "bewaarde-versie", tekst: "De bron was niet te bereiken: dit is de bewaarde versie van het stuk." });
  }
  return uit;
}

/** De verwijzingen uit de voetnoten van wat er geladen is, elk één keer. */
export function stukVerwijzingen(passages: readonly StukPassage[]): { id: string; label: string; link: string }[] {
  const gezien = new Map<string, { id: string; label: string; link: string }>();
  for (const p of passages) for (const v of p.verwijst_naar ?? []) if (!gezien.has(v.id)) gezien.set(v.id, v);
  return [...gezien.values()];
}

/** Hoort dit id bij de connector (een verwijzing in een voetnoot naar een ander stuk van dezelfde bron)? */
export function hoortBij(b: StukBeschrijving, id: string): boolean {
  return b.id_prefixen.some((p) => id.toLowerCase().startsWith(p.toLowerCase()));
}
