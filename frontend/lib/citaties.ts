// Citatie-chips: een vindplaats die Lex in gewone taal noemt ("artikel 9, tweede lid") koppelen aan
// een bron van de beurt, zodat de vermelding zelf een bronkaart opent.
//
// Bewust in de werkplek en niet in de prompt: Lex schrijft vindplaatsen al zo (prompts.py, de
// schrijfrichtlijn), en zo werkt het ook voor gesprekken die al bewaard zijn. Alleen een
// éénduidige koppeling wordt een chip – liever een vermelding zonder kaart dan een kaart bij de
// verkeerde bepaling. De tekst zelf verandert niet: de chip wikkelt de vermelding in, zoals
// `markeerPassages` een afgekeurd citaat.

import type { HastKnoop } from "./markering";
import type { NodeDoel } from "./annotatieNode";
import { bronDoel, iriSegment, vindplaatsVan } from "./samenhang";
import type { Bron } from "./types";

const RANG = ["eerste", "tweede", "derde", "vierde", "vijfde", "zesde", "zevende", "achtste", "negende", "tiende",
  "elfde", "twaalfde", "dertiende", "veertiende", "vijftiende", "zestiende", "zeventiende", "achttiende",
  "negentiende", "twintigste"];

// "artikel 9", "art. 9a", "artikel 3.1", "artikel 4:94a" (Awb), "artikel 31bis", met optioneel "lid 2",
// ", lid 2", ", tweede lid" of " tweede lid". Het nummer loopt door tot er geen letter of cijfer meer
// volgt: anders werd "artikel 4:94a" artikel 4 en "artikel 31bis" artikel 31 – een chip naar de
// verkeerde bepaling, juist in een antwoord over meerdere regelingen. Daarachter optioneel "onderdeel m"
// of "aanhef en onderdeel m", met de nummers en de woorden-die-geen-nummer-zijn van de importer
// (`_NR` en `_GEEN_NUMMER` in tools/bwb-import/app/references.py): "onderdeel is" is geen onderdeel.
const VERMELDING = new RegExp(
  String.raw`\b(?:artikel|art\.)\s+(\d+[a-z]*(?:[.:]\d+[a-z]*)*)(?![a-z0-9])` +
  String.raw`(?:,?\s+(?:lid\s+(\d+[a-z]?)|(${RANG.join("|")})\s+lid))?` +
  String.raw`(?:,?\s+(?:aanhef\s+en\s+)?onderdeel\s+(?!(?:de|en|of|in|op|te|is|na|om|al|er|ze)\b)([a-z]{1,2}|\d+[a-z]?)°?(?![a-z0-9]))?`,
  "gi",
);

// Wat achter een vermelding een regeling noemt: "van de Awb", "uit het Besluit …", of meteen "Awb". Een
// naam begint met een hoofdletter; "van deze wet" noemt niets. Tot het eerste leesteken dat een zin knipt.
const REGELING_ACHTER = /^,?\s+(?:(?:van|uit)\s+(?:de\s+|het\s+)?)?(?=\p{Lu})([^,;:()?!\n]*)/u;
const MAX_NAAMWOORDEN = 8;

export interface Vermelding {
  start: number;
  eind: number;
  artikel: string;
  lid?: string;
  onderdeel?: string;
  /** De woorden van de regeling die achter de vermelding staat (`woorden`), als die er een noemt. */
  regeling?: string[];
}

/** Een naam als vergelijkbare woorden: kleine letters, zonder leestekens en zonder jaartal. Dezelfde regel
 *  voor citeertitel en afkorting, zodat "Iw", "IW" en "Iw 1990" hetzelfde zijn. */
function woorden(naam: string): string[] {
  return naam.toLowerCase().split(/\s+/).map((w) => w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, ""))
    .filter((w) => w && !/^\d{4}$/.test(w));
}

/** Noemt de tekst deze bron? De namen komen uit de graaf (`Bron.regeling`, `Bron.afkortingen`), dus er is
 *  geen eigen afkortingenlijst. Is de naam van de bron onbekend, dan past hij niet: liever geen kaart. */
function noemtBron(genoemd: readonly string[], bron: Bron): boolean {
  return [bron.regeling, ...(bron.afkortingen ?? [])].some((naam) => {
    const naamwoorden = woorden(naam ?? "");
    return naamwoorden.length > 0 && naamwoorden.every((w, i) => w === genoemd[i]);
  });
}

export function vindVermeldingen(tekst: string): Vermelding[] {
  const uit: Vermelding[] = [];
  for (const m of tekst.matchAll(VERMELDING)) {
    const lid = m[2] ?? (m[3] ? String(RANG.indexOf(m[3].toLowerCase()) + 1) : undefined);
    const eind = m.index! + m[0].length;
    const regeling = REGELING_ACHTER.exec(tekst.slice(eind))?.[1];
    uit.push({ start: m.index!, eind, artikel: m[1].toLowerCase(), ...(lid ? { lid } : {}),
      ...(m[4] ? { onderdeel: m[4].toLowerCase() } : {}),
      ...(regeling ? { regeling: woorden(regeling).slice(0, MAX_NAAMWOORDEN) } : {}) });
  }
  return uit;
}

/** Een vermelding gekoppeld aan een bron: de bron zelf en de bepaling die de vermelding aanwijst. */
export interface Koppeling { index: number; doel: NodeDoel }

const zelfdePad = (a: readonly [string, string][], b: readonly [string, string][]) =>
  a.every(([k, w], i) => b[i]?.[0] === k && b[i][1].toLowerCase() === w);

/** De bepaling bij deze vermelding, of niets. De vermelding kiest alleen uit de bronnen van de beurt, in
 *  deze volgorde: de bron die precies de vermelding is, dan de diepste bron erboven (een artikelbron bij
 *  "artikel 9, eerste lid": dan is het doel dat lid, onder die bron), dan de enige bron eronder. Een
 *  bepaling waar geen bron boven of onder hangt, komt er dus niet bij. Of een verdiept lid echt bestaat,
 *  ziet de frontend niet (hij kent de boom niet): een lid dat Lex verkeerd noemt, meldt de api als fout.
 *
 *  Noemt de tekst een regeling, dan tellen alleen de bronnen van die regeling: artikelnummers komen in
 *  elke wet terug. Blijven er bronnen uit twee regelingen over, of meerdere bepalingen op hetzelfde
 *  niveau, dan levert het niets op: liever geen kaart dan de verkeerde. */
export function koppelVermelding(v: Vermelding, bronnen: readonly Bron[]): Koppeling | undefined {
  const genoemd: [string, string][] = [
    ...(v.lid ? [["lid", v.lid] as [string, string]] : []),
    ...(v.onderdeel ? [["o", v.onderdeel] as [string, string]] : []),
  ];
  const plekken = bronnen.flatMap((b, index) => {
    const doel = bronDoel(b.uri), vp = vindplaatsVan(b.uri);
    if (!doel || !vp || doel.artikel?.toLowerCase() !== v.artikel) return [];
    if (v.regeling && !noemtBron(v.regeling, b)) return [];
    const onder = vp.pad.slice(vp.pad.findIndex(([k]) => k === "artikel") + 1);
    const gelijk = onder.length === genoemd.length && zelfdePad(genoemd, onder);
    const ouder = onder.length < genoemd.length && zelfdePad(onder.map(([k, w]) => [k, w.toLowerCase()]), genoemd);
    const kind = onder.length > genoemd.length && zelfdePad(genoemd, onder);
    return gelijk || ouder || kind ? [{ index, doel, vp, diepte: onder.length, gelijk, ouder }] : [];
  });
  if (new Set(plekken.map((p) => p.vp.bwb_id)).size !== 1) return undefined;
  const uniek = (lijst: typeof plekken) => new Set(lijst.map((p) => p.vp.bron_iri)).size === 1 ? lijst[0] : undefined;
  const gelijk = plekken.filter((p) => p.gelijk);
  if (gelijk.length) { const p = uniek(gelijk); return p && { index: p.index, doel: p.doel }; }
  const ouders = plekken.filter((p) => p.ouder);
  if (ouders.length) {
    const p = uniek(ouders.filter((o) => o.diepte === Math.max(...ouders.map((x) => x.diepte))));
    const dieper = p && bronDoel(p.vp.bron_iri + genoemd.slice(p.diepte).map(([k, w]) => `:${k}:${iriSegment(w)}`).join(""));
    return p && dieper && { index: p.index, doel: dieper };
  }
  const p = uniek(plekken);
  return p && { index: p.index, doel: p.doel };
}

/** De index van de bron bij deze vermelding, of -1 (`koppelVermelding`). */
export function koppelBron(v: Vermelding, bronnen: readonly Bron[]): number {
  return koppelVermelding(v, bronnen)?.index ?? -1;
}

/** Rehype-plugin: wikkel elke te koppelen vermelding in een `cite` met `data-bron`, en met `data-doel`
 *  als de vermelding dieper wijst dan de bron. Code en bestaande `cite`/`mark`/`a` blijven ongemoeid. */
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
          const koppeling = koppelVermelding(v, bronnen);
          if (!koppeling) continue;
          const { index, doel } = koppeling;
          const dieper = doel.bron_iri !== bronDoel(bronnen[index].uri)?.bron_iri;
          if (v.start > pos) nieuw.push({ type: "text", value: kind.value.slice(pos, v.start) });
          nieuw.push({ type: "element", tagName: "cite", properties: { dataBron: String(index), ...(dieper ? { dataDoel: doel.bron_iri } : {}) },
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
