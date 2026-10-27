import { vraagSuggesties as markeringSuggesties } from "./annotatie";
import type { NodeElement, NodeWeergave } from "./annotatieNode";
import type { AgentContext } from "./types";
import type { DossierVeld } from "./werkgebied";

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
 *  - **Een suggestie met een `actie`** is een vaste handeling: graph-qa kiest er zonder model een agent
 *    en een taak bij (`models.ACTIE_TAAK`). Wat duur is vraagt daar eerst een bevestiging, zoals altijd.
 *  - **Een suggestie zonder actie** is een vraag die je zo ook had kunnen typen: ze gaat met het onderwerp
 *    langs de supervisor. Met `invullen` komt ze in het invoerveld in plaats van verstuurd te worden –
 *    voor een vraag die de analist zelf moet afmaken ("Wat is het betekenisverschil met …").
 *  - **Het dossier aanvullen** (`dossier_aanvullen`) is geen taak van een agent maar de vraagkaarten van de
 *    intake (graph-qa `INTAKE_ACTIES`); welk veld leest graph-qa uit de tekst ("Vul het praktijkvoorbeeld
 *    aan"). *Vraag Lex* bij een leeg veld zet dat veld op het werkgebied (`veld`), en de suggestie noemt het.
 *  - **De bronselectie** (`bronselectie`, spoor J) is evenmin een taak van een agent: graph-qa routeert hem naar
 *    de bronselectie-worker (`BRONSELECTIE_ACTIES`), op de stand die de api bewaart. */

export type OnderwerpSoort = "markering" | "deelvraag" | "bron" | "kandidaat" | "begrip" | "werkgebied";
export type ObjectSoort = Exclude<OnderwerpSoort, "markering">;

export type Onderwerp =
  | { soort: "markering"; element: NodeElement; view: NodeWeergave }
  | { soort: ObjectSoort; werkgebied_id: string; id: string; label: string;
      /** Het lege veld waarvoor de analist *Vraag Lex* koos: een dossierveld bij het werkgebied, de uitleg
       *  bij een begrip (spoor I2). */
      veld?: DossierVeld | BegripVeld };

/** De velden van een begrip waarvoor *Vraag Lex* bij een leeg veld een eigen suggestie heeft. */
export type BegripVeld = "uitleg";

/** De acties die graph-qa kent (`agent/models.py`, `Actie`: een taak van een agent uit `ACTIE_TAAK`, of het
 *  dossier aanvullen); `vraagLex.test.ts` leest die bron. */
export const ACTIES = [
  "werkgebied_annoteren", "deelvragen_annoteren", "deelvragen_voorstellen", "deelvraag_herformuleren", "deelvraag_splitsen",
  "bronnen_zoeken", "dekking", "begrippen_voorstellen", "begrippen_meedenken", "brondefinitie", "scherper",
  "uitleg", "voorbeelden", "betekenisverschil", "begrip_uitwerken", "relaties", "dossier_aanvullen", "bronselectie",
] as const;

/** Hoe de suggestie bij een leeg dossierveld het veld noemt; graph-qa herkent het woord (`dossiervelden_in`). */
const VELD_ZIN: Record<DossierVeld, string> = {
  aanleiding: "Vul de aanleiding aan", context: "Vul de context aan", doel: "Vul het doel aan",
  analysevraag: "Vul de analysevraag aan", praktijkvoorbeeld: "Vul het praktijkvoorbeeld aan",
  afbakening: "Vul de afbakening aan",
};
export type VraagLexActie = (typeof ACTIES)[number];

export interface Suggestie {
  tekst: string;
  actie?: VraagLexActie;
  /** Niet versturen, maar in het invoerveld zetten: de analist maakt de vraag af. */
  invullen?: true;
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

/** Per soort wat Lex met het object kan (F3d), in de volgorde van de methode. Een actie is een taak van een
 *  agent (de deelvragen-, begrippen- of annotatie-agent); een bron of kandidaat heeft alleen vragen, die
 *  de antwoord-worker met het object als context beantwoordt. In de werkplek staan de suggesties van het
 *  werkgebied ook zonder chip boven het invoerveld (`werkgebiedSuggesties`). */
const SUGGESTIES: Record<ObjectSoort, Suggestie[]> = {
  werkgebied: [
    { tekst: "Vul het dossier aan", actie: "dossier_aanvullen" },
    // Een vraagkaart van het aanvullen (spoor I7): graph-qa leest het veld `thema` uit de tekst.
    { tekst: "Kies een thema", actie: "dossier_aanvullen" },
    { tekst: "Stel deelvragen voor", actie: "deelvragen_voorstellen" },
    // De bronselectie per deelvraag (spoor J): beginnen of verder waar je was, ook in een ander gesprek.
    { tekst: "Verder met de bronselectie", actie: "bronselectie" },
    { tekst: "Zoek bepalingen bij alle deelvragen", actie: "bronnen_zoeken" },
    { tekst: "Hoe staat de dekking ervoor?", actie: "dekking" },
    { tekst: "Annoteer wat nog niet geannoteerd is", actie: "werkgebied_annoteren" },
    { tekst: "Annoteer de bepalingen van de deelvragen", actie: "deelvragen_annoteren" },
    { tekst: "Stel begrippen voor", actie: "begrippen_voorstellen" },
    { tekst: "Denk mee over de begrippen", actie: "begrippen_meedenken" },
  ],
  deelvraag: [
    { tekst: "Bepaal de bronnen bij deze deelvraag", actie: "bronselectie" },
    { tekst: "Zoek bepalingen hierbij", actie: "bronnen_zoeken" },
    { tekst: "Annoteer de bepalingen hierbij", actie: "deelvragen_annoteren" },
    { tekst: "Is deze deelvraag gedekt?", actie: "dekking" },
    { tekst: "Formuleer scherper", actie: "deelvraag_herformuleren" },
    { tekst: "Splits deze deelvraag", actie: "deelvraag_splitsen" },
  ],
  bron: [
    { tekst: "Waarom hoort deze bepaling bij het werkgebied?" },
    { tekst: "Naar welke bepalingen verwijst deze bepaling?" },
    { tekst: "Bij welke deelvraag hoort deze bepaling?" },
  ],
  kandidaat: [
    { tekst: "Waarom stel je deze bepaling voor?" },
    { tekst: "Naar welke bepalingen verwijst deze bepaling?" },
    { tekst: "Bij welke deelvraag hoort deze bepaling?" },
  ],
  begrip: [
    { tekst: "Werk het begrip volledig uit", actie: "begrip_uitwerken" },
    { tekst: "Zoek de brondefinitie", actie: "brondefinitie" },
    { tekst: "Schrijf de uitleg in B1", actie: "uitleg" },
    { tekst: "Geef voorbeelden", actie: "voorbeelden" },
    { tekst: "Stel relaties voor", actie: "relaties" },
    { tekst: "Wat is het betekenisverschil met ", invullen: true },
  ],
};

export const MODULES: { markering: Module<Markering> } & Record<ObjectSoort, Module<Object_>> = {
  markering: MARKERING,
  deelvraag: objectModule(() => SUGGESTIES.deelvraag),
  bron: objectModule(() => SUGGESTIES.bron),
  kandidaat: objectModule(() => SUGGESTIES.kandidaat),
  // Bij een leeg veld (`veld`) eerst de suggestie die precies dat veld aanvult.
  begrip: objectModule((o) => o.veld === "uitleg"
    ? [...SUGGESTIES.begrip.filter((s) => s.actie === "uitleg"), ...SUGGESTIES.begrip.filter((s) => s.actie !== "uitleg")]
    : SUGGESTIES.begrip),
  werkgebied: objectModule((o) => o.veld && o.veld in VELD_ZIN
    ? [{ tekst: VELD_ZIN[o.veld as DossierVeld], actie: "dossier_aanvullen" }, ...SUGGESTIES.werkgebied]
    : SUGGESTIES.werkgebied),
};

/** De suggesties van het werkgebied, voor de werkplek in een werkgebied zonder ander onderwerp. */
export const werkgebiedSuggesties = (): Suggestie[] => SUGGESTIES.werkgebied;

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
  if ((o.soort === "werkgebied" || o.soort === "begrip") && o.veld) qs.set("vraag_veld", o.veld);
  return `/workbench?${qs}`;
}

const VELDEN = new Set<string>(Object.keys(VELD_ZIN));

/** Het onderwerp uit de URL van de werkplek, of `null` als het er niet (geldig) staat. */
export function onderwerpUitUrl(zoek: { get(naam: string): string | null }): Object_ | null {
  const [soort, id] = (zoek.get("vraag") ?? "").split(":");
  const werkgebied = zoek.get("werkgebied") ?? "";
  if (!SOORTEN.includes(soort as ObjectSoort) || !ID.test(id ?? "") || !ID.test(werkgebied)) return null;
  const veld = zoek.get("vraag_veld") ?? "";
  return {
    soort: soort as ObjectSoort, werkgebied_id: werkgebied, id: soort === "werkgebied" ? "" : id,
    label: (zoek.get("vraag_label") ?? "").slice(0, 200),
    ...(soort === "werkgebied" && VELDEN.has(veld) ? { veld: veld as DossierVeld } : {}),
    ...(soort === "begrip" && veld === "uitleg" ? { veld: "uitleg" as const } : {}),
  };
}

