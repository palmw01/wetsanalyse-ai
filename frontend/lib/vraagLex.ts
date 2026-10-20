import { vraagSuggesties as markeringSuggesties } from "./annotatie";
import type { NodeElement, NodeWeergave } from "./annotatieNode";
import type { AgentContext } from "./types";

/** Eén *Vraag Lex* vanuit elk object (spoor F, F3b).
 *
 *  Vanuit een markering, deelvraag, bronselectie, kandidaat, begrip of het werkgebied leidt dezelfde knop
 *  naar het gesprek: een chip boven het invoerveld zegt waar de vraag over gaat, met suggesties die bij
 *  dat object passen. Per soort één module (`MODULES`) met de chip, de suggesties en wat er naar de agent
 *  gaat (`verzoek`).
 *
 *  - **markering** blijft de adviesvraag: `modus: "advies"` met de context, byte-gelijk aan wat de
 *    werkplek al stuurde (`vraagLex.test.ts` bewaakt het). graph-qa routeert die hard naar de duiding.
 *  - **de rest** stuurt alleen soort en id's (`onderwerp`); graph-qa haalt het object bij de api
 *    (`agent/onderwerp.py`) en zet het als context naast de vraag. Context, geen filter.
 *  - **Een suggestie met een `actie`** is een vaste handeling: graph-qa routeert hem zonder model
 *    (`models.ACTIE_MODUS`). Wat duur is vraagt daar eerst een bevestiging, zoals altijd. */

export type OnderwerpSoort = "markering" | "deelvraag" | "bron" | "kandidaat" | "begrip" | "werkgebied";
export type ObjectSoort = Exclude<OnderwerpSoort, "markering">;

export type Onderwerp =
  | { soort: "markering"; element: NodeElement; view: NodeWeergave }
  | { soort: ObjectSoort; werkgebied_id: string; id: string; label: string };

/** De acties die graph-qa kent (`agent/models.py`, `ACTIE_MODUS`); `vraagLex.test.ts` leest die bron. */
export const ACTIES = ["werkgebied_annoteren", "bronnen_zoeken", "begrippen_voorstellen", "begrippen_meedenken"] as const;
export type VraagLexActie = (typeof ACTIES)[number];

export interface Suggestie {
  tekst: string;
  actie?: VraagLexActie;
}

/** Wat er bij een gewone vraag over het onderwerp naar `startRun` gaat. */
export type OnderwerpVerzoek =
  | { modus: "advies"; context: AgentContext }
  | { onderwerp: { soort: ObjectSoort; werkgebied_id: string; id?: string; label?: string } };

export const SOORT_LABEL: Record<OnderwerpSoort, string> = {
  markering: "Markering", deelvraag: "Deelvraag", bron: "Bron", kandidaat: "Kandidaat", begrip: "Begrip",
  werkgebied: "Werkgebied",
};

interface Module<O> {
  /** De tekst in de chip: zonder aanhalingstekens, die zet de chip zelf waar het een citaat is. */
  chip: (o: O) => string;
  suggesties: (o: O) => Suggestie[];
  verzoek: (o: O) => OnderwerpVerzoek;
  /** Waar de vraag over ging, in het bewaarde bericht ("Bij <dit>: <vraag>"). */
  over: (o: O) => string;
}

type Markering = Extract<Onderwerp, { soort: "markering" }>;
type Object_ = Extract<Onderwerp, { soort: ObjectSoort }>;

const MARKERING: Module<Markering> = {
  chip: (o) => o.element.tekst,
  suggesties: (o) => markeringSuggesties(o.element).map((tekst) => ({ tekst })),
  verzoek: ({ element, view }) => ({
    modus: "advies", context: {
      bron_iri: element.eigenaar_iri, snapshot_id: view.snapshot_id,
      bwbId: view.doel.bwb_id, artikel: view.doel.artikel, lid: view.doel.lid,
      element_id: element.id, klasse: element.klasse, fragment: element.tekst,
      corpus: view.segmenten.map((s) => s.tekst).join("\n\n"),
    },
  }),
  over: ({ element, view }) => `${view.doel.label}: ${element.tekst}`,
};

function objectModule(suggesties: (o: Object_) => Suggestie[] = () => []): Module<Object_> {
  return {
    chip: (o) => o.label || SOORT_LABEL[o.soort],
    suggesties,
    verzoek: (o) => ({
      onderwerp: { soort: o.soort, werkgebied_id: o.werkgebied_id, ...(o.id ? { id: o.id } : {}),
        ...(o.label ? { label: o.label.slice(0, 300) } : {}) },
    }),
    over: (o) => `${SOORT_LABEL[o.soort].toLowerCase()} ${o.label || o.id}`.trim(),
  };
}

/** De handelingen op het werkgebied die er al waren, als suggestie met een actie. De suggesties van de
 *  andere soorten komen met de agents (F3d); tot dan typ je de vraag zelf. */
const WERKGEBIED_SUGGESTIES: Suggestie[] = [
  { tekst: "Zoek bepalingen die bij dit werkgebied horen", actie: "bronnen_zoeken" },
  { tekst: "Stel begrippen voor", actie: "begrippen_voorstellen" },
  { tekst: "Denk mee over de begrippen", actie: "begrippen_meedenken" },
  { tekst: "Annoteer wat nog niet geannoteerd is", actie: "werkgebied_annoteren" },
];

export const MODULES: { markering: Module<Markering> } & Record<ObjectSoort, Module<Object_>> = {
  markering: MARKERING,
  deelvraag: objectModule(),
  bron: objectModule(),
  kandidaat: objectModule(),
  begrip: objectModule(),
  werkgebied: objectModule(() => WERKGEBIED_SUGGESTIES),
};

function module(o: Onderwerp): Module<Onderwerp> {
  return MODULES[o.soort] as Module<Onderwerp>;
}

export const chipTekst = (o: Onderwerp) => module(o).chip(o);
export const suggestiesVan = (o: Onderwerp) => module(o).suggesties(o);
export const verzoekVan = (o: Onderwerp) => module(o).verzoek(o);
export const overVan = (o: Onderwerp) => module(o).over(o);

/** Een klik op een suggestie met een actie: geen context en geen doel, wel het onderwerp – graph-qa haalt
 *  het werkgebied daaruit als de werkplek er nog niet in staat. */
export function actieVerzoek(o: Object_, actie: VraagLexActie) {
  return { actie, ...(verzoekVan(o) as Extract<OnderwerpVerzoek, { onderwerp: unknown }>) };
}

// --- Buiten de werkplek: naar het gesprek met het onderwerp klaar ---------------------------------------

const SOORTEN: ObjectSoort[] = ["deelvraag", "bron", "kandidaat", "begrip", "werkgebied"];
const ID = /^[A-Za-z0-9-]{1,64}$/;

/** `/workbench?werkgebied=<id>&vraag=<soort>:<id>&vraag_label=<label>`: een vers gesprek in het
 *  werkgebied, met de chip al gezet. Een markering heeft hier geen weg: daarvoor is het paneel. */
export function vraagUrl(o: Object_): string {
  const qs = new URLSearchParams({ werkgebied: o.werkgebied_id, vraag: `${o.soort}:${o.id || o.werkgebied_id}` });
  if (o.label) qs.set("vraag_label", o.label.slice(0, 200));
  return `/workbench?${qs}`;
}

/** Het onderwerp uit de URL van de werkplek, of `null` als het er niet (geldig) staat. */
export function onderwerpUitUrl(zoek: { get(naam: string): string | null }): Object_ | null {
  const [soort, id] = (zoek.get("vraag") ?? "").split(":");
  const werkgebied = zoek.get("werkgebied") ?? "";
  if (!SOORTEN.includes(soort as ObjectSoort) || !ID.test(id ?? "") || !ID.test(werkgebied)) return null;
  return {
    soort: soort as ObjectSoort, werkgebied_id: werkgebied, id: soort === "werkgebied" ? "" : id,
    label: (zoek.get("vraag_label") ?? "").slice(0, 200),
  };
}

