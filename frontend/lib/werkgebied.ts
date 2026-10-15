// Rekenkern van de werkgebiedpagina's (spoor D, levering 1): labels, foutherkenning, de invoer van
// een bepaling en de indeling van de inventaris. Puur, zodat vitest (node-env) het kan toetsen.

import { isApiError } from "./api";
import { ouderVan, type GraafModel } from "./graaf/model";
import { jasVolgorde, klasseLabel } from "./jas";
import type {
  BronBereik,
  BronRol,
  BronselectieInvoer,
  InventarisElement,
  InventarisSelectie,
  WerkgebiedAuditRegel,
  WerkgebiedStatus,
} from "./types";

export const STATUS_LABEL: Record<WerkgebiedStatus, string> = {
  in_voorbereiding: "In voorbereiding",
  actief: "Actief",
  afgerond: "Afgerond",
};

export const ROL_LABEL: Record<BronRol, string> = {
  analyseren: "Analyseren",
  context: "Contextbron",
};

export const ROL_UITLEG: Record<BronRol, string> = {
  analyseren: "De elementen horen bij de werkvoorraad van dit werkgebied.",
  context: "Ondersteunt de analyse, bijvoorbeeld met een definitie; de elementen tellen niet als werkvoorraad.",
};

export const BEREIK_LABEL: Record<BronBereik, string> = {
  onderliggend: "met alles eronder",
  node: "alleen deze bepaling",
};

/** Iemand anders wijzigde het werkgebied tussendoor (412 met `revisie_conflict`). */
export function isRevisieConflict(e: unknown): boolean {
  return isApiError(e) && e.status === 412 && e.data?.fout === "revisie_conflict";
}

/** De bron staat er al, met een andere rol of een ander bereik (409 `al_opgenomen`). */
export function isAlOpgenomen(e: unknown): boolean {
  return isApiError(e) && e.status === 409 && e.data?.fout === "al_opgenomen";
}

export const TABS = [
  { key: "bronnen", label: "Bronnen" },
  { key: "elementen", label: "Elementen" },
  { key: "samenhang", label: "Samenhang" },
  { key: "historie", label: "Historie" },
] as const;
export type WerkgebiedTab = (typeof TABS)[number]["key"];

export function tabUitParam(p: string | undefined): WerkgebiedTab {
  return TABS.some((t) => t.key === p) ? (p as WerkgebiedTab) : "bronnen";
}

const BWB_ID = /^BWB[RV]\d{7}$/;

/** Wat de analist intypt om een bepaling op te nemen, als api-invoer – of een leesbare fout.
 *
 *  Twee wegen: een graaf-IRI (`urn:bwb:…`, zoals de inspector van de graaf hem toont), of regeling +
 *  artikel (+ lid). "artikel 9" en "art. 9" worden "9", "lid 2" wordt "2"; de api verifieert de
 *  bepaling daarna tegen de graaf, dus hier alleen wat zonder graaf te zeggen is. */
export function bronInvoer(velden: {
  regeling: string;
  artikel: string;
  lid: string;
}): { invoer: Omit<BronselectieInvoer, "verwachte_revisie"> } | { fout: string } {
  const regeling = velden.regeling.trim();
  if (regeling.toLowerCase().startsWith("urn:bwb:")) {
    if (velden.artikel.trim() || velden.lid.trim())
      return { fout: "Geef een bron-IRI óf regeling met artikel, niet allebei." };
    return { invoer: { bron_iri: regeling } };
  }
  const bwbId = regeling.toUpperCase();
  if (!BWB_ID.test(bwbId)) return { fout: "Regeling: geef een BWB-id (bijvoorbeeld BWBR0004770) of een bron-IRI." };
  const artikel = velden.artikel.trim().replace(/^(artikel|art\.?)\s*/i, "");
  if (!artikel) return { fout: "Geef het artikelnummer." };
  const lid = velden.lid.trim().replace(/^lid\s*/i, "");
  return { invoer: { bwb_id: bwbId, artikel, ...(lid ? { lid } : {}) } };
}

export interface SelectieGroep {
  selectie: InventarisSelectie;
  elementen: InventarisElement[];
}

/** Elk element één keer, onder de eerste selectie (in de volgorde van het werkgebied) die het
 *  dekt. Overlappende selecties tellen het element dus niet dubbel – zelfde regel als de api. */
export function groepeerPerSelectie(
  selecties: InventarisSelectie[],
  elementen: InventarisElement[],
): SelectieGroep[] {
  const volgorde = new Map(selecties.map((s, i) => [s.id, i]));
  const groepen = selecties.map((selectie) => ({ selectie, elementen: [] as InventarisElement[] }));
  for (const el of elementen) {
    const eerste = [...el.selecties].sort(
      (a, b) => (volgorde.get(a) ?? Infinity) - (volgorde.get(b) ?? Infinity),
    )[0];
    const i = eerste === undefined ? undefined : volgorde.get(eerste);
    if (i !== undefined) groepen[i].elementen.push(el);
  }
  return groepen;
}

export interface ElementFilter {
  rol: BronRol | "alle";
  klasse: string | "alle";
  term: string;
}

export function filterElementen(elementen: InventarisElement[], f: ElementFilter): InventarisElement[] {
  const term = f.term.trim().toLowerCase();
  return elementen.filter(
    (e) =>
      (f.rol === "alle" || e.rol === f.rol) &&
      (f.klasse === "alle" || klasseLabel(e.klasse) === f.klasse) &&
      (!term || e.tekst.toLowerCase().includes(term) || (e.toelichting ?? "").toLowerCase().includes(term)),
  );
}

/** Aantal elementen per klasse, in de canonieke JAS-volgorde. */
export function klasseTelling(elementen: InventarisElement[]): { klasse: string; aantal: number }[] {
  const n = new Map<string, number>();
  for (const e of elementen) n.set(klasseLabel(e.klasse), (n.get(klasseLabel(e.klasse)) ?? 0) + 1);
  return [...n.entries()]
    .map(([klasse, aantal]) => ({ klasse, aantal }))
    .sort((a, b) => jasVolgorde(a.klasse) - jasVolgorde(b.klasse) || a.klasse.localeCompare(b.klasse));
}

/** Door een jurist beoordeeld. Een voorstel van Lex of een hergebruikt element is dat (nog) niet:
 *  het mag als input dienen, maar met zichtbaar voorbehoud. */
export function isBeoordeeld(e: InventarisElement): boolean {
  return e.lifecycle === "human_approved" || e.lifecycle === "edited" || e.lifecycle === "published";
}

/** De voortgang over de werkvoorraad: alleen elementen met rol `analyseren`. Zegt niets over
 *  juridische dekking – alleen hoeveel er nog een oordeel van een jurist vraagt. */
export function voortgang(elementen: InventarisElement[]): { totaal: number; beoordeeld: number } {
  const werk = elementen.filter((e) => e.rol === "analyseren");
  return {
    totaal: werk.length,
    beoordeeld: werk.filter(isBeoordeeld).length,
  };
}

const VELD_LABEL: Record<string, string> = {
  naam: "naam",
  analysevraag: "analysevraag",
  afbakening: "afbakening",
  peildatum: "peildatum",
  status: "status",
  rol: "rol",
  reden: "reden",
};

/** Eén regel uit de audit als zin. `labels` vertaalt een bron-IRI naar wat de analist kent. */
export function auditZin(regel: WerkgebiedAuditRegel, labels: Map<string, string>): string {
  const d = regel.detail ?? {};
  const bron = typeof d.bron_iri === "string" ? (labels.get(d.bron_iri) ?? d.bron_iri) : "een bron";
  const velden = Array.isArray(d.velden) ? (d.velden as string[]).map((v) => VELD_LABEL[v] ?? v) : [];
  switch (regel.actie) {
    case "aangemaakt":
      return "Werkgebied aangemaakt";
    case "gewijzigd":
      return velden.length ? `Gewijzigd: ${velden.join(", ")}` : "Opgeslagen zonder wijziging";
    case "gearchiveerd":
      return "Gearchiveerd";
    case "bron-toegevoegd":
      return `${bron} opgenomen als ${ROL_LABEL[d.rol as BronRol]?.toLowerCase() ?? "bron"}`;
    case "bron-gewijzigd":
      return velden.length ? `Bronselectie gewijzigd: ${velden.join(", ")}` : "Bronselectie opgeslagen";
    case "bron-verwijderd":
      return `${bron} uit het werkgebied gehaald`;
    default:
      return regel.actie;
  }
}

/** De link naar de bronnode-annotatie van een element. Via `URLSearchParams`, want een IRI bevat
 *  `:` en `#`. */
export function annotatieHref(bronIri: string): string {
  return `/annotaties/node?${new URLSearchParams({ bron_iri: bronIri })}`;
}

// --- Samenhang: verwijzingen naar bepalingen buiten het werkgebied ---------

/** Wat de selecties dekken in het geladen model: de bronnode zelf, en bij `onderliggend` alles wat
 *  zij via `bevat` bevat. */
export function scopeInModel(g: GraafModel, selecties: { bron_iri: string; bereik: BronBereik }[]): Set<string> {
  const scope = new Set<string>();
  for (const s of selecties) {
    if (!g.hasNode(s.bron_iri)) continue;
    const stapel = [s.bron_iri];
    while (stapel.length) {
      const id = stapel.pop()!;
      if (scope.has(id)) continue;
      scope.add(id);
      if (s.bereik === "node") continue;
      g.forEachOutEdge(id, (_, a, __, doel) => { if (a.soort === "bevat") stapel.push(doel); });
    }
  }
  return scope;
}

export interface Suggestie {
  /** De bron-IRI van de bepaling waarnaar verwezen wordt. */
  id: string;
  naam: string;
  /** De citeertitel als de regeling geladen is, anders het BWB-id. */
  regeling: string;
  /** In de graaf, dus op te nemen. Een niet-geïmporteerde bepaling blijft een open punt. */
  beschikbaar: boolean;
  /** Vanuit welke bepalingen in het werkgebied er verwezen wordt (namen, uniek, gesorteerd). */
  vanuit: string[];
}

const opNummer = (a: string, b: string) => a.localeCompare(b, "nl", { numeric: true });

/** De bepalingen waarnaar het werkgebied verwijst maar die er niet in staan – een suggestie, geen
 *  automatische uitbreiding. Een verwijzing naar iets wat de selectie zelf omvat (het eigen hoofdstuk)
 *  telt niet. Meest genoemd eerst, dan op naam. */
export function verwijzingSuggesties(g: GraafModel, selecties: { bron_iri: string; bereik: BronBereik }[]): Suggestie[] {
  const scope = scopeInModel(g, selecties);
  const omvattend = new Set<string>();
  for (const s of selecties) {
    for (let o = g.hasNode(s.bron_iri) ? ouderVan(g, s.bron_iri) : undefined; o; o = ouderVan(g, o)) omvattend.add(o);
  }
  const regelingNaam = new Map<string, string>();
  g.forEachNode((_, a) => { if (a.soort === "regeling" && a.bwb_id) regelingNaam.set(a.bwb_id, a.naam); });

  const per = new Map<string, Set<string>>();
  g.forEachEdge((_, a, bron, doel) => {
    if (a.soort !== "verwijst_naar" || !scope.has(bron) || scope.has(doel) || omvattend.has(doel)) return;
    if (!per.has(doel)) per.set(doel, new Set());
    per.get(doel)!.add(g.getNodeAttribute(bron, "naam"));
  });
  return [...per.entries()]
    .map(([id, vanuit]) => {
      const k = g.getNodeAttributes(id);
      return {
        id, naam: k.naam, regeling: regelingNaam.get(k.bwb_id) ?? k.bwb_id,
        beschikbaar: k.soort !== "extern" && !!k.bwb_id, vanuit: [...vanuit].sort(opNummer),
      };
    })
    .sort((a, b) => b.vanuit.length - a.vanuit.length || opNummer(a.naam, b.naam));
}
