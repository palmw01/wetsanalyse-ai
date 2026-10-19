// De voorbeeldscène van de rondleiding: één gesprek en één annotatie, zodat een nieuwe gebruiker de
// werkstroom kan zien zonder eerst 60-90 seconden op een echte annotatiebeurt te wachten.
//
// Vier regels waar deze module zich aan houdt:
//
//  1. **De wettekst is echt.** `DEMO_LEDEN` is de letterlijke tekst van artikel 9, leden 1 en 2 van
//     de Invorderingswet 1990, overgenomen uit de officiële XML bij
//     `repository.officiele-overheidspublicaties.nl/bwb/BWBR0004770/`. In een platform dat om
//     brongetrouwheid draait is een verzonnen wettekst een grotere fout dan een lelijke rondleiding.
//  2. **De ankers worden gerekend, niet geteld.** Elk anker komt uit `segmentAnker` over de tekst van
//     zijn eigen lid, in codepoints, net als bij de api. Met de hand ingetypte offsets zouden bij de
//     eerste komma verschuiven en de markeringen laten zweven.
//  3. **Het is de weergave van echt werk.** De demo levert een v2-weergave (`NodeWeergave`) en een
//     opslag (`NodeOpslag`) voor `NodeAnnotatiePaneel` – hetzelfde paneel als een echte annotatie.
//     Eerst had de demo een eigen documentvorm in een paneel dat verder niemand meer gebruikte; de
//     rondleiding liet zo een werkplek zien die er niet meer was.
//  4. **Niets hiervan raakt de api.** De opslag leeft in het geheugen van één scène; zijn handelingen
//     krijgen dezelfde lichamen als de api, maar er gaat geen verzoek de deur uit.

import {
  segmentAnker, type NodeAnker, type NodeDoel, type NodeElement, type NodeOpslag, type NodeSegment,
  type NodeWeergave,
} from "./annotatieNode";
import type { ThreadItem } from "./threadItem";
import type { Aandacht, AgentRun, Beslissing, BeslissingType, ElementTrace, GesprekSamenvatting } from "./types";

/** De slug van de voorbeeldannotatie. Begint met `demo-` zodat hij nooit met een echte slug botst. */
export const DEMO_SLUG = "demo-rondleiding-iw1990-art9";

/** Het label dat overal meereist. Niemand mag de voorbeeldannotatie voor eigen werk aanzien. */
export const DEMO_LABEL = "VOORBEELD";

const BWB_ID = "BWBR0004770";
/** Een eigen schema (`demo:`), zodat de iri nooit met de graaf (`urn:bwb:`) botst. De vorm `…:lid:<n>`
 *  is wel die van de graaf: `lidUitIri` leest het lidnummer eruit. */
const ARTIKEL_IRI = `demo:${BWB_ID}:artikel:9`;
const SNAPSHOT = "demo-rondleiding";

function lidIri(lid: string): string {
  return `${ARTIKEL_IRI}:lid:${lid}`;
}

/** Artikel 9, leden 1 en 2 van de Invorderingswet 1990 – letterlijk uit de officiële publicatie. */
export const DEMO_LEDEN: { lid: string; tekst: string }[] = [
  { lid: "1", tekst: "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet." },
  {
    lid: "2",
    tekst:
      "In afwijking van het eerste lid is een navorderingsaanslag, alsmede een conserverende " +
      "navorderingsaanslag invorderbaar één maand na de dagtekening van het aanslagbiljet en een " +
      "naheffingsaanslag invorderbaar veertien dagen na de dagtekening van het aanslagbiljet.",
  },
];

/** Het doel van de voorbeeldannotatie, zoals de chip in de thread hem meegeeft aan het paneel. */
export const DEMO_DOEL: NodeDoel = {
  bron_iri: ARTIKEL_IRI,
  type: "Artikel",
  label: `${DEMO_LABEL} · Invorderingswet 1990 – artikel 9`,
  bwb_id: BWB_ID,
  artikel: "9",
  citeertitel: `${DEMO_LABEL} · Invorderingswet 1990`,
  snapshot_id: SNAPSHOT,
};

/** De agent-ronde die de voorbeeldvoorstellen "maakte". Ook een demo hoort een herkomst te dragen. */
const DEMO_RUN: AgentRun = {
  ronde: 1,
  model: "voorbeeld",
  provider: "rondleiding",
  agent_versie: "demo",
  stop_reden: "klaar",
  tijd: "2026-01-01T09:00:00Z",
};

/** Eén voorgenomen markering. `voorkomen` telt vanaf 1 binnen het lid en kiest wélke treffer het is.
 *
 *  De aandacht volgt de keten van nu: geen badge is een gewoon voorstel, geel ("Keuze voor jou") is
 *  twijfel die de reviewer niet besliste, groen ("Bevestigd door review") een twijfelgeval dat hij
 *  wél besliste. Rood zet de keten niet, dus de demo ook niet. Het spoor (`door`, `spoor`) gebruikt
 *  de codes uit `tools/graph-qa/agent/jas_pipeline/verklaringen.yaml`, zodat *Waarom?* er net zo
 *  uitziet als bij echt werk. */
interface DemoSpec {
  fragment: string;
  voorkomen?: number;
  klasse: string;
  lid: string;
  aandacht: Aandacht | null;
  toelichting: string;
  /** Wie besliste: een vaste regel, het model, of niemand (`terugval`: de jurist kiest). */
  door: "regel" | "model" | "terugval";
  /** Het bewijs van de detectoren: [detector, code]. */
  bewijs: [string, string][];
  alternatief?: { klasse: string; motivatie: string };
  review_uitleg?: string;
  twijfel?: string;
  resolutie?: string;
  /** Een kortere grens die de keten ook overwoog, als tekst binnen het fragment ("Andere grens"). */
  grens?: string;
}

const DEMO_SPECS: DemoSpec[] = [
  {
    fragment: "Een belastingaanslag", klasse: "Rechtsobject", lid: "1", aandacht: null, door: "regel",
    bewijs: [["naamwoordgroep", "THING_NP"]],
    toelichting: "Het voorwerp waarover de betalingsverplichting loopt.",
  },
  {
    fragment: "is invorderbaar", klasse: "Rechtsbetrekking", lid: "1", aandacht: "geel", door: "model",
    bewijs: [["gevolg", "LEGAL_EFFECT_PREDICATE"]],
    toelichting: "De juridische toestand die tussen de ontvanger en de belastingschuldige ontstaat.",
    alternatief: {
      klasse: "Rechtsfeit",
      motivatie: "Je kunt het invorderbaar wórden ook lezen als de gebeurtenis die de betalingsplicht opeisbaar maakt.",
    },
    review_uitleg: "Werkwoordsvorm duidt op een rechtsbetrekking, maar het tijdsverloop maakt een rechtsfeit verdedigbaar.",
    twijfel: "DETECTOR_CONFLICT", resolutie: "R-CONFLICT-HUMAN",
  },
  {
    fragment: "zes weken na de dagtekening van het aanslagbiljet", klasse: "Tijdsaanduiding", lid: "1",
    aandacht: null, door: "regel", bewijs: [["tijd", "TEMPORAL_DURATION"]], grens: "zes weken",
    toelichting: "Het tijdvak waarna de aanslag invorderbaar is.",
  },
  {
    fragment: "In afwijking van het eerste lid", klasse: "Voorwaarde", lid: "2", aandacht: "groen", door: "model",
    bewijs: [["voorwaarde", "CONDITIONAL_FORMULA"]],
    toelichting: "Bakent af wanneer de hoofdregel van lid 1 niet geldt.",
    alternatief: {
      klasse: "Operator",
      motivatie: "De formulering verbindt twee bepalingen; dat kan ook als logische uitzondering worden gelezen.",
    },
    review_uitleg: "Een vaste voorwaardeformule: de afwijking begrenst wanneer de termijn van lid 1 geldt.",
    twijfel: "DETECTOR_CONFLICT", resolutie: "R-CONFLICT-CHANGE",
  },
  {
    fragment: "een navorderingsaanslag", klasse: "Rechtsobject", lid: "2", aandacht: null, door: "regel",
    bewijs: [["naamwoordgroep", "THING_NP"]],
    toelichting: "Het voorwerp waarvoor de afwijkende termijn geldt.",
  },
  {
    fragment: "alsmede", klasse: "Operator", lid: "2", aandacht: null, door: "regel",
    bewijs: [["logisch", "LOGICAL"]],
    toelichting: "Logische conjunctie: beide aanslagen vallen onder dezelfde termijn.",
  },
  {
    fragment: "een conserverende navorderingsaanslag", klasse: "Rechtsobject", lid: "2", aandacht: null,
    door: "regel", bewijs: [["naamwoordgroep", "THING_NP"]],
    toelichting: "Tweede voorwerp waarvoor de termijn van één maand geldt.",
  },
  {
    // Bewust een misser: het model gaf geen keuze, en de klasse die er voorlopig staat klopt niet. Zo
    // ziet de gebruiker waarom "Keuze voor jou" serieus genomen moet worden.
    fragment: "invorderbaar", klasse: "Rechtsobject", lid: "2", aandacht: "geel", door: "terugval",
    bewijs: [["gevolg", "LEGAL_EFFECT_PREDICATE"]],
    toelichting: "",
    review_uitleg: "Dit is een werkwoordsvorm, geen voorwerp. Hoort vrijwel zeker bij Rechtsbetrekking.",
    alternatief: { klasse: "Rechtsbetrekking", motivatie: "Werkwoord dat de plicht tot betaling uitdrukt." },
    twijfel: "CLASSIFIER_ABSTAIN", resolutie: "R-ABSTAIN-HUMAN",
  },
  {
    fragment: "één maand na de dagtekening van het aanslagbiljet", klasse: "Tijdsaanduiding", lid: "2",
    aandacht: null, door: "regel", bewijs: [["tijd", "TEMPORAL_DURATION"]],
    toelichting: "Afwijkende termijn voor de (conserverende) navorderingsaanslag.",
  },
  {
    fragment: "een naheffingsaanslag", klasse: "Rechtsobject", lid: "2", aandacht: null, door: "regel",
    bewijs: [["naamwoordgroep", "THING_NP"]],
    toelichting: "Het voorwerp waarvoor de kortste termijn geldt.",
  },
  {
    fragment: "veertien dagen na de dagtekening van het aanslagbiljet", klasse: "Tijdsaanduiding", lid: "2",
    aandacht: null, door: "regel", bewijs: [["tijd", "TEMPORAL_DURATION"]],
    toelichting: "Afwijkende termijn voor de naheffingsaanslag.",
  },
];

/** Wat de keten in lid 2 niet zag: het tweede "invorderbaar" (vóór "veertien dagen"). Het paneel
 *  onderstreept het gestippeld, en één klik erop markeert het – de stap "Zelf markeren". */
const DEMO_ONGEDEKT = { lid: "2", fragment: "invorderbaar", voorkomen: 2 };

/** De twaalf detectiedimensies van de keten (`jas_pipeline/dekking.py`). */
const DIMENSIES = [
  "actor", "object", "normatieve relatie", "handeling/gebeurtenis", "voorwaarde", "berekening/afleiding",
  "waarde", "operator", "tijd", "plaats", "delegatie", "definitie",
];

/** De segmenten van de weergave: één per lid, met de letterlijke tekst. */
function demoSegmenten(): NodeSegment[] {
  return DEMO_LEDEN.map(({ lid, tekst }, i) => ({
    bron_iri: lidIri(lid), parent_iri: ARTIKEL_IRI, type: "Lid", nummer: lid, label: `Lid ${lid}`,
    tekst, bron_hash: `demo-lid-${lid}`, volgorde: i + 1,
  }));
}

/** Positie (UTF-16) van de `n`-de treffer van `fragment`; -1 als hij er niet is. */
function positieVan(tekst: string, fragment: string, voorkomen: number): number {
  let i = -1;
  for (let n = 0; n < voorkomen; n++) {
    i = tekst.indexOf(fragment, i + 1);
    if (i === -1) return -1;
  }
  return i;
}

function laagId(lid: string): string {
  return `demo-laag-${lid}`;
}

/** Het herkomstspoor van een demo-element, in de vorm van de keten. Posities in codepoints binnen
 *  het lid, net als de ankers. */
function spoorVan(spec: DemoSpec, segment: NodeSegment, start: number): ElementTrace {
  const cp = (utf16: number) => Array.from(segment.tekst.slice(0, utf16)).length;
  const grens = spec.grens && start >= 0 ? segment.tekst.indexOf(spec.grens, start) : -1;
  const kandidaat = {
    label: spec.fragment,
    mogelijke_klassen: [spec.klasse, ...(spec.alternatief ? [spec.alternatief.klasse] : [])],
    bewijs: spec.bewijs.map(([detector, code]) => ({ detector, code })),
    ...(grens >= 0 && start >= 0 ? {
      span: { bron_iri: segment.bron_iri },
      spanopties: [
        { soort: "volledig", start: cp(start), eind: cp(start + spec.fragment.length) },
        { soort: "kern", start: cp(grens), eind: cp(grens + spec.grens!.length) },
      ],
    } : {}),
  };
  return {
    pijplijn: "hybrid_v1",
    kandidaat,
    beslissing: { status: "voorgesteld", klasse: spec.klasse, door: spec.door },
    ...(spec.twijfel ? { twijfel: [{
      reden: spec.twijfel, huidig: spec.klasse, alternatieven: spec.alternatief ? [spec.alternatief.klasse] : [],
    }] } : {}),
    ...(spec.resolutie ? { resolutie: [{ regel: spec.resolutie }] } : {}),
  };
}

function elementVan(spec: DemoSpec, index: number, segment: NodeSegment): NodeElement {
  const start = positieVan(segment.tekst, spec.fragment, spec.voorkomen ?? 1);
  // Een fragment dat niet in de tekst staat, hoort ook in de demo niet stilzwijgend te verdwijnen:
  // zonder anker toont de reviewlijst hem als zwevende markering, precies zoals bij echt werk.
  const ankers: NodeAnker[] = start === -1 ? [] : [segmentAnker(segment, start, start + spec.fragment.length)];
  return {
    id: `demo-el-${index + 1}`,
    eigenaar_iri: segment.bron_iri,
    laag_id: laagId(spec.lid),
    klasse: spec.klasse,
    tekst: spec.fragment,
    toelichting: spec.toelichting,
    ankers,
    lifecycle: "voorgesteld",
    herkomst: "agent",
    alternatieven: spec.alternatief ? [spec.alternatief] : [],
    aandacht: spec.aandacht,
    review_uitleg: spec.review_uitleg,
    trace: spoorVan(spec, segment, start),
    beslissingen: [],
    geproduceerd_door: DEMO_RUN,
  };
}

/** De dekking zoals de keten haar meet: alle dimensies gedraaid, en in lid 2 één zinsdeel zonder
 *  treffer. */
function demoDekking(segmenten: NodeSegment[]) {
  const structureel = Object.fromEntries(segmenten.map((segment) => {
    const ongedekt = [];
    if (segment.nummer === DEMO_ONGEDEKT.lid) {
      const start = positieVan(segment.tekst, DEMO_ONGEDEKT.fragment, DEMO_ONGEDEKT.voorkomen);
      const a = segmentAnker(segment, start, start + DEMO_ONGEDEKT.fragment.length);
      ongedekt.push({ tekst: a.tekst, start: a.start, eind: a.eind });
    }
    return [segment.bron_iri, {
      dimensies: Object.fromEntries(DIMENSIES.map((d) => [d, "uitgevoerd" as const])),
      ongedekt,
    }];
  }));
  return { voltooid: true, structureel };
}

/** De weergave van de voorbeeldannotatie, vers opgebouwd. Elke start krijgt een schone lei. */
export function maakDemoWeergave(): NodeWeergave {
  const segmenten = demoSegmenten();
  const segmentVan = (lid: string) => segmenten.find((s) => s.nummer === lid)!;
  return {
    schema_versie: 2,
    doel: { ...DEMO_DOEL },
    snapshot_id: SNAPSHOT,
    segmenten,
    lagen: DEMO_LEDEN.map(({ lid }) => ({ id: laagId(lid), bron_iri: lidIri(lid), revisie: 1, status: "in_review" })),
    elementen: DEMO_SPECS.map((spec, i) => elementVan(spec, i, segmentVan(spec.lid))),
    verwijzingen: [],
    dekking: demoDekking(segmenten),
  };
}

// --- de opslag (in het geheugen, met de lichamen van de api) --------------------------------

/** Welke lifecycle hoort bij een beslissing? Dezelfde uitkomsten als de api. */
function lifecycleNa(type: BeslissingType, huidig: string): string {
  if (type === "approve") return "human_approved";
  if (type === "reject") return "rejected";
  if (type === "edit" || type === "grens") return "edited";
  if (type === "heropen") return "voorgesteld";
  return huidig;
}

interface BeslissingLichaam {
  type: BeslissingType;
  comment?: string;
  review_reason?: Beslissing["review_reason"];
  wijziging?: { klasse?: string; toelichting?: string; tekst?: string; ankers?: NodeAnker[]; optie?: number };
}

/** Een beslissing op de weergave, zoals de api hem zou verwerken. Pure functie. */
export function pasDemoBeslissingToe(view: NodeWeergave, elementId: string, body: BeslissingLichaam): NodeWeergave {
  const el = view.elementen.find((e) => e.id === elementId);
  if (!el) return view;
  const w = body.wijziging ?? {};
  let wijziging: Partial<NodeElement> = {};
  if (body.type === "edit") {
    wijziging = {
      ...(w.klasse ? { klasse: w.klasse } : {}),
      ...(w.toelichting != null ? { toelichting: w.toelichting } : {}),
      ...(w.ankers?.length ? { ankers: w.ankers, tekst: w.tekst ?? el.tekst } : {}),
      gewijzigd_door: "mens",
    };
  } else if (body.type === "grens" && typeof w.optie === "number") {
    // Het anker van een grenskeuze rekent de api uit de bron; hier hetzelfde, uit de spanoptie.
    const kandidaat = el.trace?.kandidaat as
      | { spanopties?: { start: number; eind: number }[]; span?: { bron_iri?: string } }
      | undefined;
    const optie = kandidaat?.spanopties?.[w.optie];
    const segment = view.segmenten.find((s) => s.bron_iri === (kandidaat?.span?.bron_iri ?? el.eigenaar_iri));
    if (optie && segment) {
      const tekst = Array.from(segment.tekst).slice(optie.start, optie.eind).join("");
      wijziging = {
        ankers: [{ bron_iri: segment.bron_iri, start: optie.start, eind: optie.eind, tekst, bron_hash: segment.bron_hash }],
        tekst,
      };
    }
  }
  const beslissing: Beslissing = {
    type: body.type, actor: "voorbeeld", tijd: new Date().toISOString(),
    review_reason: body.review_reason ?? null, comment: body.comment ?? "", wijziging: { ...w },
  };
  return metRevisie({
    ...view,
    elementen: view.elementen.map((e) => e.id !== elementId ? e : {
      ...e, ...wijziging, lifecycle: lifecycleNa(body.type, e.lifecycle),
      beslissingen: [...(e.beslissingen ?? []), beslissing],
    }),
  }, el.eigenaar_iri);
}

/** Een eigen markering van de jurist: meteen goedgekeurd, net als bij de api. */
export function voegDemoElementToe(
  view: NodeWeergave,
  invoer: { klasse: string; toelichting: string; tekst: string; ankers: NodeAnker[] },
): { view: NodeWeergave; id: string } {
  const eigenaar = invoer.ankers[0]?.bron_iri ?? view.doel.bron_iri;
  const id = `demo-eigen-${view.elementen.length + 1}`;
  const nieuw: NodeElement = {
    id, eigenaar_iri: eigenaar, laag_id: view.lagen.find((l) => l.bron_iri === eigenaar)?.id ?? laagId("eigen"),
    klasse: invoer.klasse, tekst: invoer.tekst, toelichting: invoer.toelichting, ankers: invoer.ankers,
    lifecycle: "human_approved", herkomst: "mens", alternatieven: [], aandacht: null, beslissingen: [],
    geproduceerd_door: null,
  };
  return { view: metRevisie({ ...view, elementen: [...view.elementen, nieuw] }, eigenaar), id };
}

export function wisDemoElement(view: NodeWeergave, elementId: string): NodeWeergave {
  const el = view.elementen.find((e) => e.id === elementId);
  if (!el) return view;
  return metRevisie({ ...view, elementen: view.elementen.filter((e) => e.id !== elementId) }, el.eigenaar_iri);
}

export function zetDemoStatus(view: NodeWeergave, laag: string, status: string): NodeWeergave {
  return { ...view, lagen: view.lagen.map((l) => l.id === laag ? { ...l, status, revisie: l.revisie + 1 } : l) };
}

/** Elke wijziging aan een laag verhoogt zijn revisie, zoals bij de api. */
function metRevisie(view: NodeWeergave, iri: string): NodeWeergave {
  return { ...view, lagen: view.lagen.map((l) => l.bron_iri === iri ? { ...l, revisie: l.revisie + 1 } : l) };
}

/** De opslag van de voorbeeldannotatie. Eén per scène: wat je beslist, blijft staan tot de
 *  rondleiding stopt. */
export function maakDemoOpslag(): NodeOpslag {
  let view = maakDemoWeergave();
  return {
    levend: false,
    weergave: async () => structuredClone(view),
    async beslis(id, body) {
      view = pasDemoBeslissingToe(view, id, body as unknown as BeslissingLichaam);
      return {};
    },
    async markeer(body) {
      const { element } = body as {
        element: { klasse: string; toelichting: string; tekst: string; ankers: NodeAnker[] };
      };
      const uit = voegDemoElementToe(view, element);
      view = uit.view;
      return { element: { id: uit.id } };
    },
    async wis(id) {
      view = wisDemoElement(view, id);
      return {};
    },
    async status(laag, body) {
      view = zetDemoStatus(view, laag, body.status);
      return {};
    },
    async verwijder() {
      view = { ...view, elementen: [], lagen: [], verwijderd: { op: new Date().toISOString() } };
      return {};
    },
    // Een voorbeeld levert geen bestand: het keuzepaneel sluit, zoals bij elke export.
    async exporteer() {},
  };
}

// --- de thread en de sidebar ----------------------------------------------------------------

/** Wat Lex onder de annotatie zegt. Elke zin volgt uit `DEMO_SPECS`, zoals bij graph-qa. */
export const DEMO_SAMENVATTING =
  "Ik heb artikel 9 van de Invorderingswet 1990 geanalyseerd en elf JAS-elementen gevonden. " +
  "De markeringen zijn vooral Rechtsobject en Tijdsaanduiding. " +
  "Twee voorstellen hebben een plausibel alternatief en verdienen daarom extra aandacht. " +
  "Acht voorstellen volgen rechtstreeks uit vaste regels, twee koos het model.";

/** De twee beurten die in de thread staan: een vraag met bronnen, en de annotatie met zijn tijdlijn. */
function maakDemoItems(): ThreadItem[] {
  return [
    { id: "demo-1", type: "user", tekst: "Wat betekent het begrip 'belastingschuldige'?" },
    {
      id: "demo-2",
      type: "antwoord",
      // Let op de spelling: "te wiens **name**". De wet zegt "te wiens naam" (artikel 2, eerste lid,
      // onderdeel k). Dat is geen typfout maar de misser die het blok hieronder aanwijst – herstel
      // je hem, dan meldt de rondleiding een citaatfout die er niet meer is, en faalt er niets dat
      // je erop wijst.
      tekst:
        "De Invorderingswet 1990 verstaat onder **belastingschuldige** degene te wiens name de " +
        "belastingaanslag is gesteld (artikel 2, eerste lid, onderdeel k). Het begrip bepaalt wie de " +
        "ontvanger kan aanspreken voor de betaling.\n\n" +
        `_(${DEMO_LABEL}: dit antwoord hoort bij de rondleiding.)_`,
      denk: [
        "· Supervisor · een vraag naar een begrip: de definitie-specialist (0,6 s)",
        "· Graaf · begripsbepaling opgehaald uit artikel 2 van de Invorderingswet 1990 (0,4 s)",
        "· Controle · 1 citaat niet letterlijk in de opgehaalde tekst (0,1 s)",
      ].join("\n"),
      bronnen: [
        { label: "Invorderingswet 1990, artikel 2", uri: "jci1.3:c:BWBR0004770&artikel=2" },
        { label: "Invorderingswet 1990, artikel 9", uri: "jci1.3:c:BWBR0004770&artikel=9" },
      ],
      // Bewust `ongegrond`: het blok zwijgt bij een geslaagde toets, en dan valt er in de rondleiding
      // niets aan te wijzen. Zo ziet de gebruiker meteen wát het blok doet als er iets aan de hand is.
      grounding: {
        niveau: "ongegrond",
        grounded: false,
        cited: 2,
        unsupported: [],
        niet_letterlijk: ["degene te wiens name de belastingaanslag is gesteld"],
      },
    },
    { id: "demo-3", type: "user", tekst: "Annoteer artikel 9 van de Invorderingswet 1990" },
    {
      id: "demo-4",
      type: "annotatie",
      slug: DEMO_SLUG,
      titel: DEMO_DOEL.label,
      annotatie_doel: DEMO_DOEL,
      // Zoals graph-qa haar uit de voorstellen opbouwt (`agent/nodes/annotatie_samenvatting.py`); de
      // test houdt de telling gelijk met `DEMO_SPECS`.
      tekst: DEMO_SAMENVATTING,
      // De fasen van de annotatieketen, in de vorm van `agent/narratie.py`: één regel per stap.
      denk: [
        `· Bron · artikel 9 van de Invorderingswet 1990 (${DEMO_LEDEN.reduce((n, l) => n + l.tekst.length, 0)} tekens)`,
        "· Taalanalyse · nl_core_news_md, 2 zin(nen) (0,6 s)",
        "· Detectie · 15 kandidaten uit 9 detectoren (0,2 s)",
        "· Besluit · 8 op vaste regels, 3 naar het model (0,0 s)",
        "· Classificatie · 3 kandidaten in 1 modelaanroep(en) (3,8 s)",
        "· Review · 3 twijfelgeval(len), 3 naar de reviewer (4,6 s)",
        "· Resultaat · 11 voorgesteld, 2 ter keuze aan de jurist (0,1 s)",
        "· Klaar · 11 elementen ter beoordeling",
      ].join("\n"),
    },
  ];
}

/** De gesprekkenlijst die de sidebar tijdens de rondleiding toont.
 *
 *  Die lijst komt normaal uit de api, en bij een nieuwe gebruiker is hij dus leeg – precies de
 *  gebruiker die de rondleiding krijgt. De stap "Je werk terugvinden" wees dan naar een lege kolom
 *  terwijl de tekst zegt dat je gesprekken er staan. De rondleiding hoort niet af te hangen van wat
 *  er toevallig in het account staat, net zomin als de thread dat doet. */
function maakDemoGesprekken(): GesprekSamenvatting[] {
  // Vaste tijdstippen, aflopend: een demo die "3 minuten geleden" zegt omdat hij nu gestart wordt,
  // suggereert werk dat de gebruiker nooit gedaan heeft.
  return [
    { id: "demo-gesprek-1", titel: `${DEMO_LABEL} – Invorderingswet 1990, artikel 9`,
      aantal_berichten: 4, updated: "2026-03-17T10:12:00Z" },
    { id: "demo-gesprek-2", titel: `${DEMO_LABEL} – Wat betekent 'belastingschuldige'?`,
      aantal_berichten: 2, updated: "2026-03-16T15:40:00Z" },
    { id: "demo-gesprek-3", titel: `${DEMO_LABEL} – Termijnen bij uitstel van betaling`,
      aantal_berichten: 6, updated: "2026-03-14T09:05:00Z" },
  ];
}

/** Alles wat de werkplek nodig heeft om de voorbeeldscène te tonen. */
export interface DemoScene {
  items: ThreadItem[];
  /** Waar het annotatiepaneel in de demo zijn weergave vandaan haalt en zijn handelingen heen stuurt. */
  opslag: NodeOpslag;
  /** De sidebar draait tijdens de rondleiding op deze lijst in plaats van op die uit de api. */
  gesprekken: GesprekSamenvatting[];
}

export function maakDemoScene(): DemoScene {
  return { items: maakDemoItems(), opslag: maakDemoOpslag(), gesprekken: maakDemoGesprekken() };
}
