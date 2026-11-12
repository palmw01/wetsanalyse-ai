/** De tabs van het paneel naast het gesprek (het bronvenster, PR 3b). Puur, getest in `paneelTabs.test.ts`.
 *
 *  Het paneel toont één inhoud tegelijk – die staat in de werkplek in zijn eigen slots (een context, een annotatie, een
 *  werkgebied-artefact), met de bewaker en de één-paneel-regel ongewijzigd. Dit is de lijst ernaast: wat er nog meer open
 *  stond, zodat je wisselt zonder het opnieuw te zoeken, per gesprek bewaard. Een inactieve tab is een beschrijving, geen
 *  gemount paneel; terugkomen laadt hem in de slots, en de wettekst staat er meteen (`lib/useBron.ts`).
 *
 *  Leestabs (een bepaling, een element, de bronnen, een overzicht) kunnen er meer zijn. Een bepaling is één tab, of je
 *  haar leest of annoteert (ontdubbelen PR 2, besluit gebruiker 10 nov 2026): de annotatie is een laag op de tab van
 *  die bepaling, met dezelfde sleutel, dus *Beoordelen* zet hem in dezelfde tab aan en er kunnen meer bepalingen tegelijk
 *  in beoordeling openstaan. Het artefact van een werkgebied heeft één tab: bewerken doe je in één tegelijk. */
import type { ContextDoel } from "@/components/werkplek/ContextPaneel";
import type { GraafOpties } from "@/components/graaf/useGraafStand";
import type { NodeDoel } from "@/lib/annotatieNode";
import { artefactKop, type WerkgebiedArtefact } from "@/lib/artefact";
import { herkomstVan } from "@/lib/herkomst";

export type PaneelInhoud =
  | { soort: "context"; ctx: ContextDoel }
  | { soort: "annotatie"; doel: NodeDoel; tab: "tekst" | "graaf"; extra: NodeDoel[]; graaf: GraafOpties; reeks?: string }
  | { soort: "artefact"; artefact: WerkgebiedArtefact };

export interface PaneelTab {
  sleutel: string;
  inhoud: PaneelInhoud;
  /** Waar hij geopend werd ("een antwoord", "Bronnen"): alleen in de tooltip. */
  vanuit?: string;
}

export interface TabStand { tabs: PaneelTab[]; actief?: string }

/** Hoeveel tabs er open kunnen staan; daarboven valt de oudste af die niet actief is. */
export const MAX_TABS = 8;

/** De sleutel van de tab van een bepaling: dezelfde voor lezen en annoteren. */
export const bepalingSleutel = (bronIri: string) => `bron:${bronIri}`;

export function contextSleutelVan(c: ContextDoel): string {
  return c.soort === "bron" ? bepalingSleutel(c.bron_iri)
    : c.soort === "element" ? `element:${c.element_id}`
    : c.soort === "overzicht" ? `overzicht:${c.overzicht.gevraagd}`
    : c.soort === "stuk" ? `stuk:${c.id}`
    // De bepalingen van een antwoord: dezelfde lijst is dezelfde tab, dus een tweede klik opent geen tweede.
    : c.soort === "bepalingen" ? `bepalingen:${c.bepalingen.map((v) => v.iri).join("|")}`
    // De contextweergave: één tab, voor de meter en voor `/context`.
    : c.soort === "contextopbouw" ? "contextopbouw"
    : `bibliotheek:${c.werkgebied_id}`;
}

export function sleutelVan(i: PaneelInhoud): string {
  return i.soort === "context" ? contextSleutelVan(i.ctx) : i.soort === "annotatie" ? bepalingSleutel(i.doel.bron_iri) : i.soort;
}

/** Opent of werkt bij: dezelfde sleutel vervangt de inhoud op haar plek (een andere versie, een ander lid van de reeks),
 *  een nieuwe komt achteraan en wordt actief. */
export function openTab(stand: TabStand, inhoud: PaneelInhoud, vanuit?: string, max = MAX_TABS): TabStand {
  const sleutel = sleutelVan(inhoud);
  const bestaand = stand.tabs.find((t) => t.sleutel === sleutel);
  let tabs = bestaand
    ? stand.tabs.map((t) => (t.sleutel === sleutel ? { ...t, inhoud, vanuit: vanuit ?? t.vanuit } : t))
    : [...stand.tabs, { sleutel, inhoud, vanuit }];
  while (tabs.length > max) {
    const weg = tabs.findIndex((t) => t.sleutel !== sleutel);
    tabs = tabs.filter((_, i) => i !== weg);
  }
  return { tabs, actief: sleutel };
}

/** Sluit een tab. Was hij actief, dan wordt de buur actief (de volgende, anders de vorige); `buur` is wat de werkplek
 *  moet laden. */
export function sluitTab(stand: TabStand, sleutel: string): TabStand & { buur?: PaneelTab } {
  const i = stand.tabs.findIndex((t) => t.sleutel === sleutel);
  if (i < 0) return stand;
  const tabs = stand.tabs.filter((t) => t.sleutel !== sleutel);
  if (stand.actief !== sleutel) return { tabs, actief: stand.actief };
  const buur = tabs[i] ?? tabs[i - 1];
  return { tabs, actief: buur?.sleutel, buur };
}

/** Het korte label op de tab en het volle in de tooltip. */
export function tabLabel(t: PaneelTab): { kort: string; vol: string } {
  const i = t.inhoud;
  let kort: string, vol: string;
  if (i.soort === "context") {
    const c = i.ctx;
    if (c.soort === "bron") {
      const h = herkomstVan({ iri: c.bron_iri, label: c.titel });
      kort = h.bepaling;
      vol = c.titel || h.bepaling;
    } else if (c.soort === "element") { kort = "Element"; vol = c.titel || "JAS-element"; }
    else if (c.soort === "bibliotheek") { kort = "Bronnen"; vol = "Bronnen van dit werkgebied"; }
    else if (c.soort === "stuk") { kort = c.titel || c.id; vol = c.titel || c.id; }
    else if (c.soort === "contextopbouw") { kort = "Context"; vol = "Context van deze beurt"; }
    else if (c.soort === "bepalingen") { kort = c.titel || "Bepalingen"; vol = `Bepalingen in dit antwoord: ${c.titel}`; }
    else { kort = c.titel || "Overzicht"; vol = `Overzicht: ${c.titel}`; }
  } else if (i.soort === "annotatie") {
    const h = herkomstVan({ iri: i.doel.bron_iri, label: i.doel.label, regeling: i.doel.citeertitel });
    // Dezelfde tab als bij lezen: de bepaling zelf. De tooltip zegt dat ze in beoordeling openstaat.
    kort = h.bepaling;
    vol = `${h.regeling ? `${h.bepaling}, ${h.regeling}` : h.bepaling} · annotatie`;
  } else {
    const k = artefactKop(i.artefact);
    kort = k.titel;
    vol = k.soort ? `${k.soort}: ${k.titel}` : k.titel;
  }
  return { kort, vol: t.vanuit ? `${vol} · geopend vanuit ${t.vanuit}` : vol };
}

// ── Bewaren per gesprek ──────────────────────────────────────────────────────────────────────────────────────────────

export const opslagSleutel = (gesprekId: string | null | undefined) => `lex.paneel.tabs.${gesprekId || "nieuw"}`;

/** Wat er bewaard wordt: de beschrijvingen, zonder de kennisgraaf die een graaf meekreeg (groot, en na een beurt niet meer
 *  actueel). Geen tekst: die komt bij het openen van de server. */
export function bewaarVorm(stand: TabStand): TabStand {
  return {
    actief: stand.actief,
    tabs: stand.tabs.map((t) => {
      const i = t.inhoud;
      if (i.soort === "annotatie") return { ...t, inhoud: { ...i, graaf: zonderKennisgraaf(i.graaf) } };
      if (i.soort === "context" && i.ctx.soort === "bron" && i.ctx.samenhang) {
        return { ...t, inhoud: { ...i, ctx: { ...i.ctx, samenhang: { ...i.ctx.samenhang, graaf: zonderKennisgraaf(i.ctx.samenhang.graaf) } } } };
      }
      return t;
    }),
  };
}

/** Wat een graaf meekrijgt, zonder de kennisgraaf zelf (groot, en na een beurt niet meer actueel): het bereik, de
 *  ketting, de nadruk en het werkgebied. */
export function zonderKennisgraaf(g: GraafOpties): GraafOpties {
  if (!g.kennisgraaf) return g;
  const { kennisgraaf: _weg, ...rest } = g;
  void _weg;
  return rest;
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

function geldigeInhoud(v: unknown): v is PaneelInhoud {
  if (!isObject(v)) return false;
  if (v.soort === "context") {
    const c = v.ctx;
    if (!isObject(c) || typeof c.soort !== "string") return false;
    if (c.soort === "bron") return typeof c.bron_iri === "string";
    if (c.soort === "element") return typeof c.element_id === "string";
    if (c.soort === "bibliotheek") return typeof c.werkgebied_id === "string";
    if (c.soort === "stuk") return typeof c.brontype === "string" && typeof c.id === "string";
    if (c.soort === "bepalingen") return Array.isArray(c.bepalingen) && c.bepalingen.length > 0
      && c.bepalingen.every((v) => isObject(v) && typeof v.iri === "string" && typeof v.label === "string");
    return c.soort === "overzicht" && isObject(c.overzicht) && typeof (c.overzicht as Record<string, unknown>).gevraagd === "string";
  }
  if (v.soort === "annotatie") {
    return isObject(v.doel) && typeof v.doel.bron_iri === "string" && (v.tab === "tekst" || v.tab === "graaf")
      && Array.isArray(v.extra) && isObject(v.graaf);
  }
  return v.soort === "artefact" && isObject(v.artefact) && typeof v.artefact.soort === "string"
    && typeof v.artefact.werkgebied_id === "string";
}

/** Een bewaarde stand, streng: een tab die niet klopt (een oudere vorm) valt weg, nooit een half paneel. */
export function leesBewaard(ruw: unknown): TabStand | undefined {
  if (!isObject(ruw) || !Array.isArray(ruw.tabs)) return undefined;
  const tabs = ruw.tabs
    .filter((t): t is PaneelTab => isObject(t) && geldigeInhoud(t.inhoud))
    .map((t) => ({ sleutel: sleutelVan(t.inhoud), inhoud: t.inhoud, vanuit: typeof t.vanuit === "string" ? t.vanuit : undefined }))
    .slice(-MAX_TABS);
  if (!tabs.length) return undefined;
  const actief = tabs.some((t) => t.sleutel === ruw.actief) ? (ruw.actief as string) : undefined;
  return { tabs, actief };
}
