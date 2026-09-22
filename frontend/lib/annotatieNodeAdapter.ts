// Van een bronnode-weergave (contract 2) naar de vorm waar het vertrouwde annotatiepaneel
// (`ArtefactInhoud`) mee werkt – en terug.
//
// Waarom een vertaling en geen tweede paneel: het artefact draagt maanden aan afwegingen over
// highlights, reviewkaarten, sneltoetsen en de selectiepopover. Een eigen v2-paneel liet dat
// allemaal vallen (#473) en zag er daarna uit als een formulier. Eén inhoud, twee databronnen.
//
// Twee coördinatenstelsels, en die mogen nergens door elkaar lopen:
//  • v2 rekent per bronnode in Unicode-codepoints binnen de kale nodetekst (zonder nummer);
//  • het paneel rekent in UTF-16-posities in één samengestelde bron (`bronVan(regelsVan(info))`),
//    mét het "1. "-voorvoegsel van een lid en een "a. " voor elk onderdeel.
// Alles wat van het ene naar het andere gaat, loopt via `SegmentPlek.begin`.

import { bronVan, regelsVan } from "./annotatie";
import { segmentAnker, type NodeAnker, type NodeElement, type NodeSegment, type NodeWeergave } from "./annotatieNode";
import { maakAnker, snapSelectie, vindPositie } from "./selectie";
import type {
  Anker, AnnotatieDocument, AnnotatieElement, BeslissingInvoer, GraafArtikel, Lifecycle,
} from "./types";

/** Waar de eigen tekst van één bronnode in de samengestelde bron begint (UTF-16). */
export interface SegmentPlek {
  segment: NodeSegment;
  begin: number;
  /** Het lid waar deze node onder valt, "" als er geen is. */
  lid: string;
}

export interface NodeBron {
  info: GraafArtikel;
  plekken: SegmentPlek[];
  /** Exact `bronVan(regelsVan(info))` – de tekst waar het paneel zijn posities in uitdrukt. */
  bron: string;
}

/** Het lidnummer uit een bron-IRI (`…:lid:2:onderdeel:a` → "2"), of "". */
export function lidUitIri(iri: string): string {
  return /:lid:([^:]+)/.exec(iri)?.[1] ?? "";
}

/** "a" → "a. ", "1°" → "1°. ", "b." blijft "b. ". Het paneel herkent een onderdeel aan dat nummer
 *  (`lib/wetstructuur.ts`) en zet het dan ingesprongen met een hangend nummer. */
function nummerVoorvoegsel(nummer: string): string {
  const n = nummer.trim();
  if (!n) return "";
  return `${n.endsWith(".") ? n : `${n}.`} `;
}

/** UTF-16-lengte van de eerste `codepoints` tekens. */
function utf16Van(tekst: string, codepoints: number): number {
  return Array.from(tekst).slice(0, codepoints).join("").length;
}

/** Bouw de artikelvorm uit de segmenten van een weergave.
 *
 *  Eén regel per lid, met de onderdelen eronder op een eigen regel – zo zag de wettekst er in het
 *  paneel altijd uit, en zo herkent `blokkenVan` de nesting. Een lid zonder eigen tekst (alleen
 *  onderdelen) staat niet tussen de segmenten; dan houdt het lid toch zijn kopregel, zodat je ziet
 *  waar de onderdelen bij horen. */
export function nodeBronVan(view: NodeWeergave): NodeBron {
  const segmenten = [...view.segmenten].sort((a, b) => a.volgorde - b.volgorde);
  const groepen: { lid: string; tekst: string; delen: { segment: NodeSegment; binnen: number }[] }[] = [];
  for (const s of segmenten) {
    const lid = s.type === "Lid" ? (s.nummer?.trim() || lidUitIri(s.bron_iri)) : lidUitIri(s.bron_iri);
    const huidig = groepen.at(-1);
    const onderdeel = s.type === "Onderdeel";
    if (!onderdeel || !huidig || huidig.lid !== lid) {
      // Een onderdeel dat een groep opent heeft een lid zonder eigen tekst boven zich (dan een lege
      // kopregel voor het lidnummer) of geen lid (dan meteen het onderdeel).
      const kop = onderdeel ? (lid ? "\n" : "") + nummerVoorvoegsel(s.nummer ?? "") : "";
      groepen.push({ lid, tekst: kop + s.tekst, delen: [{ segment: s, binnen: kop.length }] });
    } else {
      const kop = "\n" + nummerVoorvoegsel(s.nummer ?? "");
      huidig.delen.push({ segment: s, binnen: huidig.tekst.length + kop.length });
      huidig.tekst += kop + s.tekst;
    }
  }

  const info: GraafArtikel = {
    bwbId: view.doel.bwb_id ?? "",
    artikel: view.doel.artikel ?? "",
    citeertitel: view.doel.citeertitel ?? "",
    opschrift: view.doel.label ?? "",
    leden_teksten: groepen.map((g) => ({ lid: g.lid, tekst: g.tekst })),
    soort: view.doel.type === "Divisie" ? "Divisie" : "Artikel",
  };

  // Dezelfde rekensom als `regelsVan` + `bronVan`: "<lid>. " ervoor, "\n\n" ertussen. De test houdt
  // beide kanten gelijk; loopt dit uiteen, dan landt elke markering naast zijn tekst.
  const plekken: SegmentPlek[] = [];
  let pos = 0;
  for (const g of groepen) {
    if (!g.tekst.trim()) continue; // `regelsVan` slaat lege regels over, dus hier ook
    const voorvoegsel = g.lid ? g.lid.length + 2 : 0;
    for (const d of g.delen) plekken.push({ segment: d.segment, begin: pos + voorvoegsel + d.binnen, lid: g.lid });
    pos += voorvoegsel + g.tekst.length + 2;
  }
  return { info, plekken, bron: bronVan(regelsVan(info)) };
}

/** Het bereik van een element in de samengestelde bron, of `null` als een anker hier niet (meer)
 *  op de tekst past – dan is het element historie of hoort het bij een andere bronstand. */
function bereikVan(nb: NodeBron, ankers: NodeAnker[]): { start: number; eind: number; lid: string } | null {
  let start = -1, eind = -1, lid = "";
  for (const a of ankers) {
    const p = nb.plekken.find((x) => x.segment.bron_iri === a.bron_iri && x.segment.bron_hash === a.bron_hash);
    if (!p) return null;
    const s = p.begin + utf16Van(p.segment.tekst, a.start);
    const e = p.begin + utf16Van(p.segment.tekst, a.eind);
    if (start < 0) { start = s; lid = p.lid; }
    eind = e;
  }
  return start < 0 || eind <= start ? null : { start, eind, lid };
}

/** Een v2-element als paneel-element.
 *
 *  Een element met meerdere ankers (over onderdelen heen) wordt één doorlopende markering van het
 *  eerste tot het laatste anker, precies zoals een markering over onderdelen er in het paneel al
 *  uitzag. De tekst is dan het stuk bron dat ertussen staat, inclusief het onderdeelnummer; de
 *  letterlijke ankers blijven ongewijzigd in de api staan. */
export function elementVanNode(el: NodeElement, nb: NodeBron): AnnotatieElement {
  const bereik = el.verouderd ? null : bereikVan(nb, el.ankers);
  const run = el.geproduceerd_door ?? null;
  return {
    id: el.id,
    klasse: el.klasse,
    tekst: bereik ? nb.bron.slice(bereik.start, bereik.eind) : el.tekst,
    lid: bereik?.lid ?? lidUitIri(el.eigenaar_iri),
    toelichting: el.toelichting ?? "",
    vindplaats: "",
    herkomst: el.herkomst,
    gewijzigd_door: el.gewijzigd_door ?? "",
    lifecycle: el.lifecycle as Lifecycle,
    alternatieven: el.alternatieven ?? [],
    aandacht: (el.aandacht as AnnotatieElement["aandacht"]) ?? null,
    critic: el.critic,
    critic_rondes: el.critic_rondes ?? [],
    critic_suggestie: el.critic_suggestie ?? null,
    anker: bereik ? maakAnker(nb.bron, bereik.start, bereik.eind, bereik.lid) : null,
    diff: {},
    beslissingen: el.beslissingen ?? [],
    geproduceerd_door: run,
    verouderd: !!el.verouderd,
  };
}

/** De weergave als paneel-document. Eén bepaling kan meerdere lagen dragen (een per bronnode met
 *  eigen markeringen); afgerond is hij pas als ze dat allemaal zijn. */
export function documentVanNode(view: NodeWeergave, nb: NodeBron): AnnotatieDocument {
  const afgerond = view.lagen.length > 0 && view.lagen.every((l) => l.status === "geaccordeerd");
  return {
    slug: view.doel.bron_iri,
    user_id: "",
    client_id: "",
    citeertitel: nb.info.citeertitel,
    werkgebied: "",
    bwbId: nb.info.bwbId,
    artikel: nb.info.artikel,
    lid: view.doel.lid ?? "",
    status: afgerond ? "geaccordeerd" : "in_review",
    elementen: view.elementen.map((e) => elementVanNode(e, nb)),
    runs: [],
    // Gedeelde laag: het paneel toont dan geen verwijderknop voor het geheel.
    laag_sleutel: view.doel.bron_iri,
  };
}

/** Een selectie in de samengestelde bron als v2-ankers: één per geraakte bronnode, in bronvolgorde.
 *  Nummers en regeleindes tussen de nodes vallen erbuiten – die staan niet in de wettekst zelf. */
export function nodeAnkersUitSelectie(nb: NodeBron, start: number, eind: number): NodeAnker[] {
  const ankers: NodeAnker[] = [];
  for (const p of nb.plekken) {
    const s = Math.max(start, p.begin) - p.begin;
    const e = Math.min(eind, p.begin + p.segment.tekst.length) - p.begin;
    if (e <= s) continue;
    const bijgesneden = snapSelectie(p.segment.tekst, s, e);
    if (bijgesneden.eind <= bijgesneden.start) continue;
    ankers.push(segmentAnker(p.segment, bijgesneden.start, bijgesneden.eind));
  }
  return ankers;
}

/** De elementtekst die de api bij een set ankers verwacht: de fragmenten met één spatie ertussen. */
export function tekstVanAnkers(ankers: NodeAnker[]): string {
  return ankers.map((a) => a.tekst).join(" ");
}

/** Een beslissing uit het paneel als v2-beslissing.
 *
 *  Het paneel stuurt bij een fragmentcorrectie een anker in zijn eigen coördinaten mee; dat wordt
 *  hier een set bronnode-ankers. "Fragment overnemen" van de Critic stuurt alleen tekst: die zoeken
 *  we op dezelfde manier als de weergave, dicht bij de huidige plek van het element. */
export function beslissingNaarNode(
  req: BeslissingInvoer, nb: NodeBron, huidig?: AnnotatieElement,
): { type: BeslissingInvoer["type"]; comment?: string; review_reason?: string | null; wijziging?: Record<string, unknown> } {
  const uit: ReturnType<typeof beslissingNaarNode> = { type: req.type };
  if (req.comment) uit.comment = req.comment;
  if (req.review_reason) uit.review_reason = req.review_reason;
  const w = req.wijziging;
  if (!w) return uit;
  const wijziging: Record<string, unknown> = {};
  if (w.klasse) wijziging.klasse = w.klasse;
  if (w.toelichting != null) wijziging.toelichting = w.toelichting;
  if (w.tekst) {
    const bereik = w.anker ? { start: w.anker.start, eind: w.anker.eind } : zoekFragment(nb, w.tekst, huidig?.anker);
    if (!bereik) throw new Error("Dit fragment staat niet letterlijk in de wettekst van deze bepaling.");
    const ankers = nodeAnkersUitSelectie(nb, bereik.start, bereik.eind);
    if (!ankers.length) throw new Error("Dit fragment valt buiten de wettekst van deze bepaling.");
    wijziging.ankers = ankers;
    wijziging.tekst = tekstVanAnkers(ankers);
  }
  return { ...uit, wijziging };
}

function zoekFragment(nb: NodeBron, tekst: string, anker?: Anker | null): { start: number; eind: number } | null {
  const fragment = tekst.trim();
  const start = vindPositie(nb.bron, fragment, anker, []);
  return start < 0 ? null : { start, eind: start + fragment.length };
}
