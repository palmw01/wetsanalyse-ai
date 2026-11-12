import { vraagSuggesties as markeringSuggesties } from "./annotatie";
import type { NodeElement, NodeWeergave } from "./annotatieNode";
import { bronDoel } from "./samenhang";
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
 *    de bronselectie-worker (`BRONSELECTIE_ACTIES`), op de stand die de api bewaart. Ook `bronnen_zoeken` gaat
 *    daarheen: zoeken is een stap van de bronselectie, en ook `bepaling_toevoegen` – zelf een bepaling opzoeken en
 *    toevoegen, met de treffers en hun tekst als kaartje. Zoeken in de graaf hoort bij het gesprek, niet bij een
 *    artefact: daarop lees, bewerk en besluit je. */

export type OnderwerpSoort = "markering" | "deelvraag" | "bron" | "kandidaat" | "begrip" | "werkgebied" | "bepaling" | "stuk";
/** De objecten uit een werkgebied: ze dragen altijd een werkgebied en een id daarin. */
export type ObjectSoort = Exclude<OnderwerpSoort, "markering" | "bepaling" | "stuk">;

/** Een bepaling en een stuk uit een bronconnector (ontdubbelen PR 5): *Vraag Lex* in het bronvenster, op de bronpagina en
 *  de annotatiepagina, ook buiten een werkgebied. graph-qa haalt de tekst zelf met zijn tools (`agent/onderwerp.py`). */
export type BronOnderwerp =
  | { soort: "bepaling"; bron_iri: string; label: string; werkgebied_id?: string;
      /** Er ligt een annotatie op (de laag is aan): andere suggesties. */
      annotatie?: boolean }
  | { soort: "stuk"; connector: string; stuk_id: string; label: string; werkgebied_id?: string };

export type Onderwerp =
  | { soort: "markering"; element: NodeElement; view: NodeWeergave }
  | BronOnderwerp
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
  "bepaling_toevoegen", "regie_bronnen", "regie_annoteren",
] as const;

/** Hoe de suggestie bij een leeg dossierveld het veld noemt; graph-qa herkent het woord (`dossiervelden_in`). De
 *  gebeurtenis hoort sinds 4 nov 2026 bij het dossier (samenstellen en aanvullen), net als de regelingen. */
const VELD_ZIN: Record<DossierVeld, string> = {
  aanleiding: "Vul de aanleiding aan", context: "Vul de context aan", doel: "Vul het doel aan",
  analysevraag: "Vul de analysevraag aan", praktijkvoorbeeld: "Vul het praktijkvoorbeeld aan",
  afbakening: "Vul de afbakening aan", gebeurtenis: "Vul de gebeurtenis aan",
};
const VELD_ACTIE: Partial<Record<DossierVeld, VraagLexActie>> = {};
export type VraagLexActie = (typeof ACTIES)[number];

export interface Suggestie {
  tekst: string;
  actie?: VraagLexActie;
  /** Annoteren van één bepaling: de bestaande annotatieweg (`doel` op `startRun`), geen actie en geen onderwerp. */
  doel?: { bron_iri: string; bwbId: string };
  hergebruik?: "opnieuw";
  /** Niet versturen, maar in het invoerveld zetten: de analist maakt de vraag af. */
  invullen?: true;
  /** Dezelfde handeling als `/commando` in het invoerveld (`lib/commandos.ts`): de naam en een korte hulptekst. Een
   *  commando ís deze suggestie – geen tweede lijst en geen tweede router. */
  commando?: { naam: string; hulp: string };
}

/** Wat er bij een gewone vraag over het onderwerp naar `startRun` gaat. */
export type OnderwerpVerzoek =
  | { modus: "advies"; context: AgentContext }
  | { onderwerp: { soort: ObjectSoort; werkgebied_id: string; id?: string; label?: string } }
  | { onderwerp: { soort: "bepaling"; bron_iri: string; label?: string; werkgebied_id?: string } }
  | { onderwerp: { soort: "stuk"; connector: string; stuk_id: string; label?: string; werkgebied_id?: string } };

export const SOORT_LABEL: Record<OnderwerpSoort, string> = {
  markering: "Markering", deelvraag: "Deelvraag", bron: "Bron", kandidaat: "Kandidaat", begrip: "Begrip",
  werkgebied: "Werkgebied", bepaling: "Bepaling", stuk: "Stuk",
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
type Bepaling = Extract<Onderwerp, { soort: "bepaling" }>;
type Stuk = Extract<Onderwerp, { soort: "stuk" }>;

/** "dit onderdeel", "dit lid", "dit artikel" of "deze bepaling": uit de vorm van de bronnode. */
function ditDeel(iri: string): string {
  if (/:o:[^:]+$/.test(iri)) return "dit onderdeel";
  if (/:lid:[^:]+$/.test(iri)) return "dit lid";
  if (/:artikel:[^:]+$/.test(iri)) return "dit artikel";
  return "deze bepaling";
}

const BEPALING: Module<Bepaling> = {
  chip: (o) => o.label || SOORT_LABEL.bepaling,
  suggesties: (o) => {
    const deel = ditDeel(o.bron_iri);
    const doel = { bron_iri: o.bron_iri, bwbId: bronDoel(o.bron_iri)?.bwb_id ?? "" };
    return o.annotatie ? [
      { tekst: `Annoteer ${deel} opnieuw`, doel, hergebruik: "opnieuw", commando: { naam: "annoteer", hulp: `Annoteer ${deel} opnieuw` } },
      { tekst: "Welke markeringen vragen nog aandacht?" },
      { tekst: `Wat betekent ${deel}?` },
      { tekst: `Naar welke bepalingen verwijst ${deel}?` },
    ] : [
      { tekst: `Annoteer ${deel}`, doel, commando: { naam: "annoteer", hulp: `Annoteer ${deel}` } },
      { tekst: `Wat betekent ${deel}?` },
      { tekst: `Naar welke bepalingen verwijst ${deel}?` },
    ];
  },
  verzoek: (o) => ({ onderwerp: { soort: "bepaling", bron_iri: o.bron_iri, ...(o.label ? { label: o.label.slice(0, 300) } : {}),
    ...(o.werkgebied_id ? { werkgebied_id: o.werkgebied_id } : {}) } }),
  over: (o) => `bepaling ${o.label || o.bron_iri}`,
};

const STUK: Module<Stuk> = {
  chip: (o) => o.label || SOORT_LABEL.stuk,
  suggesties: () => [
    { tekst: "Vat dit stuk samen" },
    { tekst: "Wat zegt dit stuk over de wet?" },
    { tekst: "Welke bepalingen noemt dit stuk?" },
  ],
  verzoek: (o) => ({ onderwerp: { soort: "stuk", connector: o.connector, stuk_id: o.stuk_id,
    ...(o.label ? { label: o.label.slice(0, 300) } : {}), ...(o.werkgebied_id ? { werkgebied_id: o.werkgebied_id } : {}) } }),
  over: (o) => `stuk ${o.label || o.stuk_id}`,
};

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
    { tekst: "Vul het dossier aan", actie: "dossier_aanvullen", commando: { naam: "dossier", hulp: "Vul de lege velden van het dossier aan" } },
    // Een vraagkaart van het aanvullen (spoor I7): graph-qa leest het veld `thema` uit de tekst.
    { tekst: "Kies een thema", actie: "dossier_aanvullen", commando: { naam: "thema", hulp: "Kies het thema van het werkgebied" } },
    { tekst: "Stel deelvragen voor", actie: "deelvragen_voorstellen", commando: { naam: "deelvragen", hulp: "Lex stelt deelvragen voor bij de analysevraag" } },
    // De bronselectie per deelvraag (spoor J): beginnen, of verder waar je was – ook in een ander gesprek. Er is
    // geen losse zoekknop meer: de bronselectie zoekt zelf.
    { tekst: "Bepaal de bronnen per deelvraag", actie: "bronselectie", commando: { naam: "bronnen", hulp: "De bronselectie per deelvraag: beginnen of verder waar je was" } },
    // Zelf een bepaling toevoegen: Lex zoekt haar op en toont de tekst (geen zoekvenster op het artefact).
    { tekst: "Noem een bepaling", actie: "bepaling_toevoegen", commando: { naam: "bepaling", hulp: "Noem zelf een bepaling; Lex zet haar als voorstel in het paneel" } },
    { tekst: "Annoteer de bepalingen van de deelvragen", actie: "deelvragen_annoteren", commando: { naam: "annoteer-deelvragen", hulp: "Annoteer alleen de bronnen onder de deelvragen (eerst een bevestiging)" } },
    { tekst: "Annoteer wat nog niet geannoteerd is", actie: "werkgebied_annoteren", commando: { naam: "annoteer", hulp: "Annoteer de nieuwe bepalingen van het werkgebied (eerst een bevestiging)" } },
    { tekst: "Stel begrippen voor", actie: "begrippen_voorstellen", commando: { naam: "begrippen", hulp: "Lex stelt begrippen voor uit de annotaties" } },
    { tekst: "Denk mee over de begrippen", actie: "begrippen_meedenken", commando: { naam: "meedenken", hulp: "Lex denkt mee over twijfelparen en definities (eerst een bevestiging)" } },
    // Generieke begrippen (ADR-006): een vraag, geen actie; Lex zoekt ze zelf en koppelen doe je op het artefact.
    { tekst: "Welke generieke begrippen passen bij dit werkgebied?" },
    // De dekking als controle achteraf: hebben de deelvragen een bron en een geaccordeerd begrip?
    { tekst: "Hoe staat de dekking ervoor?", actie: "dekking", commando: { naam: "dekking", hulp: "Hebben de deelvragen een bron en een geaccordeerd begrip?" } },
  ],
  deelvraag: [
    // Eerst de vraag zelf, dan haar bronnen.
    { tekst: "Formuleer scherper", actie: "deelvraag_herformuleren", commando: { naam: "scherper", hulp: "Lex stelt een scherpere formulering voor" } },
    { tekst: "Splits deze deelvraag", actie: "deelvraag_splitsen", commando: { naam: "splits", hulp: "Lex stelt voor de deelvraag te splitsen" } },
    { tekst: "Bepaal de bronnen bij deze deelvraag", actie: "bronselectie", commando: { naam: "bronnen", hulp: "De bronselectie bij deze deelvraag" } },
    { tekst: "Noem een bepaling", actie: "bepaling_toevoegen", commando: { naam: "bepaling", hulp: "Noem zelf een bepaling; Lex zet haar als voorstel in het paneel" } },
    { tekst: "Annoteer de bepalingen hierbij", actie: "deelvragen_annoteren", commando: { naam: "annoteer", hulp: "Annoteer de bronnen onder deze deelvraag (eerst een bevestiging)" } },
    { tekst: "Is deze deelvraag gedekt?", actie: "dekking", commando: { naam: "dekking", hulp: "Heeft deze deelvraag een bron en een geaccordeerd begrip?" } },
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
    { tekst: "Werk het begrip volledig uit", actie: "begrip_uitwerken", commando: { naam: "uitwerken", hulp: "Brondefinitie, scherpere definitie en voorbeelden, elk als voorstel" } },
    { tekst: "Zoek de brondefinitie", actie: "brondefinitie", commando: { naam: "brondefinitie", hulp: "Zoek de definitie in de wet, zonder model" } },
    { tekst: "Schrijf de uitleg in B1", actie: "uitleg", commando: { naam: "uitleg", hulp: "Een uitleg in eenvoudige taal, als voorstel" } },
    { tekst: "Geef voorbeelden", actie: "voorbeelden", commando: { naam: "voorbeelden", hulp: "Voorbeelden die er wel en niet onder vallen" } },
    { tekst: "Stel relaties voor", actie: "relaties", commando: { naam: "relaties", hulp: "Relaties met andere begrippen, als voorstel" } },
    { tekst: "Wat is het betekenisverschil met ", invullen: true, commando: { naam: "verschil", hulp: "Zet de vraag klaar; jij noemt het andere begrip" } },
  ],
};

export const MODULES: { markering: Module<Markering>; bepaling: Module<Bepaling>; stuk: Module<Stuk> }
  & Record<ObjectSoort, Module<Object_>> = {
  markering: MARKERING,
  bepaling: BEPALING,
  stuk: STUK,
  deelvraag: objectModule(() => SUGGESTIES.deelvraag),
  bron: objectModule(() => SUGGESTIES.bron),
  kandidaat: objectModule(() => SUGGESTIES.kandidaat),
  // Bij een leeg veld (`veld`) eerst de suggestie die precies dat veld aanvult.
  begrip: objectModule((o) => o.veld === "uitleg"
    ? [...SUGGESTIES.begrip.filter((s) => s.actie === "uitleg"), ...SUGGESTIES.begrip.filter((s) => s.actie !== "uitleg")]
    : SUGGESTIES.begrip),
  werkgebied: objectModule((o) => o.veld && o.veld in VELD_ZIN
    ? [{ tekst: VELD_ZIN[o.veld as DossierVeld], actie: VELD_ACTIE[o.veld as DossierVeld] ?? "dossier_aanvullen" },
      ...SUGGESTIES.werkgebied]
    : SUGGESTIES.werkgebied),
};

/** De suggesties van het werkgebied, voor de werkplek in een werkgebied zonder ander onderwerp. */
export const werkgebiedSuggesties = (): Suggestie[] => SUGGESTIES.werkgebied;

/** Een object uit een werkgebied (geen markering, bepaling of stuk): alleen dat kent een actie. */
export function isObjectOnderwerp(o: Onderwerp | undefined): o is Object_ {
  return !!o && o.soort !== "markering" && o.soort !== "bepaling" && o.soort !== "stuk";
}

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

const BRON_IRI = /^urn:bwb:[A-Za-z0-9:._-]{1,200}$/;
const CONNECTOR = /^[a-z_]{1,40}$/;
const STUK_ID = /^[A-Za-z0-9:._-]{1,120}$/;

/** `/workbench?werkgebied=<id>&vraag=<soort>:<id>&vraag_label=<label>`: een vers gesprek in het
 *  werkgebied, met de chip al gezet. Een bepaling heet daar `vraag=bepaling&vraag_bron=<urn:bwb:…>`, een stuk
 *  `vraag=stuk&vraag_connector=…&vraag_stuk=…`, met het werkgebied alleen als ze erin staan. Een markering heeft hier
 *  geen weg: daarvoor is het paneel (`null`). */
export function vraagUrl(o: Onderwerp): string | null {
  if (o.soort === "markering") return null;
  if (o.soort === "bepaling" || o.soort === "stuk") {
    const qs = new URLSearchParams(o.werkgebied_id ? { werkgebied: o.werkgebied_id } : {});
    qs.set("vraag", o.soort);
    if (o.soort === "bepaling") qs.set("vraag_bron", o.bron_iri);
    else { qs.set("vraag_connector", o.connector); qs.set("vraag_stuk", o.stuk_id); }
    if (o.label) qs.set("vraag_label", o.label.slice(0, 200));
    return `/workbench?${qs}`;
  }
  const qs = new URLSearchParams({ werkgebied: o.werkgebied_id, vraag: `${o.soort}:${o.id || o.werkgebied_id}` });
  if (o.label) qs.set("vraag_label", o.label.slice(0, 200));
  if ((o.soort === "werkgebied" || o.soort === "begrip") && o.veld) qs.set("vraag_veld", o.veld);
  return `/workbench?${qs}`;
}

const VELDEN = new Set<string>(Object.keys(VELD_ZIN));

/** Het onderwerp uit de URL van de werkplek, of `null` als het er niet (geldig) staat. */
export function onderwerpUitUrl(zoek: { get(naam: string): string | null }): Exclude<Onderwerp, Markering> | null {
  const vraag = zoek.get("vraag") ?? "";
  const werkgebied = zoek.get("werkgebied") ?? "";
  const label = (zoek.get("vraag_label") ?? "").slice(0, 200);
  const wg = werkgebied && ID.test(werkgebied) ? { werkgebied_id: werkgebied } : {};
  if (vraag === "bepaling") {
    const bron = zoek.get("vraag_bron") ?? "";
    return BRON_IRI.test(bron) ? { soort: "bepaling", bron_iri: bron, label, ...wg } : null;
  }
  if (vraag === "stuk") {
    const connector = zoek.get("vraag_connector") ?? "", stuk = zoek.get("vraag_stuk") ?? "";
    return CONNECTOR.test(connector) && STUK_ID.test(stuk) ? { soort: "stuk", connector, stuk_id: stuk, label, ...wg } : null;
  }
  const [soort, id] = vraag.split(":");
  if (!SOORTEN.includes(soort as ObjectSoort) || !ID.test(id ?? "") || !ID.test(werkgebied)) return null;
  const veld = zoek.get("vraag_veld") ?? "";
  return {
    soort: soort as ObjectSoort, werkgebied_id: werkgebied, id: soort === "werkgebied" ? "" : id,
    label: (zoek.get("vraag_label") ?? "").slice(0, 200),
    ...(soort === "werkgebied" && VELDEN.has(veld) ? { veld: veld as DossierVeld } : {}),
    ...(soort === "begrip" && veld === "uitleg" ? { veld: "uitleg" as const } : {}),
  };
}


// --- Lex gaat zelf verder ---------------------------------------------------------------------------

/** Een vervolgstap die Lex na een beurt zelf aankondigt (`opgeslagen.vervolg`, graph-qa `beurt.py`): na *Werkgebied
 *  aanmaken* de bronselectie per deelvraag. De werkplek stuurt hem als een klik op de suggestie met die actie, één
 *  keer en alleen live; na herladen start er niets vanzelf. */
export interface Vervolg { actie: "bronselectie"; werkgebied_id: string }

export const VERVOLG_TEKST: Record<Vervolg["actie"], string> = {
  bronselectie: "Bepaal de bronnen per deelvraag",
};

export function parseVervolg(ruw: unknown): Vervolg | undefined {
  const r = (ruw ?? {}) as Record<string, unknown>;
  return r.actie === "bronselectie" && typeof r.werkgebied_id === "string" && /^[A-Za-z0-9-]{1,64}$/.test(r.werkgebied_id)
    ? { actie: "bronselectie", werkgebied_id: r.werkgebied_id } : undefined;
}
