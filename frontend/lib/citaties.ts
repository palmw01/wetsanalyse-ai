// Citatie-chips: een vindplaats die Lex in gewone taal noemt ("artikel 9, tweede lid") koppelen aan
// een bron van de beurt, zodat de vermelding zelf een bronkaart opent.
//
// Bewust in de werkplek en niet in de prompt: Lex schrijft vindplaatsen al zo (prompts.py, de
// schrijfrichtlijn), en zo werkt het ook voor gesprekken die al bewaard zijn. Alleen een
// éénduidige koppeling wordt een chip – liever een vermelding zonder kaart dan een kaart bij de
// verkeerde bepaling. De tekst zelf verandert niet: de chip wikkelt de vermelding in, zoals
// `markeerPassages` een afgekeurd citaat.

import type { HastKnoop } from "./markering";
import { bronDoel, vindplaatsVan } from "./samenhang";
import type { Bron } from "./types";

const RANG = ["eerste", "tweede", "derde", "vierde", "vijfde", "zesde", "zevende", "achtste", "negende", "tiende",
  "elfde", "twaalfde", "dertiende", "veertiende", "vijftiende", "zestiende", "zeventiende", "achttiende",
  "negentiende", "twintigste"];

// "artikel 9", "art. 9a", "artikel 3.1", "artikel 4:94a" (Awb), "artikel 31bis", met optioneel "lid 2",
// ", lid 2", ", tweede lid" of " tweede lid". Het nummer loopt door tot er geen letter of cijfer meer
// volgt: anders werd "artikel 4:94a" artikel 4 en "artikel 31bis" artikel 31 – een chip naar de
// verkeerde bepaling, juist in een antwoord over meerdere regelingen.
const VERMELDING = new RegExp(
  String.raw`\b(?:artikel|art\.)\s+(\d+[a-z]*(?:[.:]\d+[a-z]*)*)(?![a-z0-9])` +
  String.raw`(?:,?\s+(?:lid\s+(\d+[a-z]?)|(${RANG.join("|")})\s+lid))?`,
  "gi",
);

export interface Vermelding { start: number; eind: number; artikel: string; lid?: string }

export function vindVermeldingen(tekst: string): Vermelding[] {
  const uit: Vermelding[] = [];
  for (const m of tekst.matchAll(VERMELDING)) {
    const lid = m[2] ?? (m[3] ? String(RANG.indexOf(m[3].toLowerCase()) + 1) : undefined);
    uit.push({ start: m.index!, eind: m.index! + m[0].length, artikel: m[1].toLowerCase(), ...(lid ? { lid } : {}) });
  }
  return uit;
}

/** De index van de bron bij deze vermelding, of -1. Met een lid: de bron van dat lid. Zonder lid:
 *  de bron van het hele artikel, en anders de enige bron onder dat artikel. Meer dan één kandidaat
 *  levert niets op. */
export function koppelBron(v: Vermelding, bronnen: readonly Bron[]): number {
  const doelen = bronnen.map((b) => bronDoel(b.uri));
  const zelfdeArtikel = doelen.map((d, i) => ({ d, i })).filter(({ d }) => d?.artikel?.toLowerCase() === v.artikel);
  const uniekeBron = (lijst: { d: ReturnType<typeof bronDoel>; i: number }[]) => {
    const iris = new Set(lijst.map(({ d }) => d!.bron_iri));
    return iris.size === 1 ? lijst[0].i : -1;
  };
  if (v.lid) return uniekeBron(zelfdeArtikel.filter(({ d }) => d!.lid?.toLowerCase() === v.lid));
  const heel = zelfdeArtikel.filter(({ d }) => !d!.lid);
  return heel.length ? uniekeBron(heel) : uniekeBron(zelfdeArtikel);
}

/** Rehype-plugin: wikkel elke te koppelen vermelding in een `cite` met `data-bron`. Code en
 *  bestaande `cite`/`mark`/`a` blijven ongemoeid. */
export function markeerCitaties(bronnen: readonly Bron[]) {
  return () => (boom: HastKnoop) => {
    const loop = (knoop: HastKnoop): void => {
      if (!knoop.children?.length || ["code", "pre", "a", "cite", "mark"].includes(knoop.tagName ?? "")) return;
      const nieuw: HastKnoop[] = [];
      for (const kind of knoop.children) {
        if (kind.type !== "text" || !kind.value) {
          loop(kind);
          nieuw.push(kind);
          continue;
        }
        let pos = 0;
        for (const v of vindVermeldingen(kind.value)) {
          const index = koppelBron(v, bronnen);
          if (index < 0) continue;
          if (v.start > pos) nieuw.push({ type: "text", value: kind.value.slice(pos, v.start) });
          nieuw.push({ type: "element", tagName: "cite", properties: { dataBron: String(index) },
            children: [{ type: "text", value: kind.value.slice(v.start, v.eind) }] });
          pos = v.eind;
        }
        nieuw.push(pos === 0 ? kind : { type: "text", value: kind.value.slice(pos) });
      }
      knoop.children = nieuw.filter((k) => k.type !== "text" || k.value);
    };
    loop(boom);
  };
}

/** Het leesbare label van een bron, in plaats van de rauwe IRI. */
export function bronLabel(b: Bron): string {
  return vindplaatsVan(b.bron_iri || b.uri)?.label || b.label;
}
