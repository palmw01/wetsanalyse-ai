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
import type { Aandacht, AgentRun, Beslissing, BeslissingType, GesprekSamenvatting } from "./types";

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

/** Eén voorgenomen markering. `voorkomen` telt vanaf 1 binnen het lid en kiest wélke treffer het is. */
interface DemoSpec {
  fragment: string;
  voorkomen?: number;
  klasse: string;
  lid: string;
  aandacht: Aandacht;
  toelichting: string;
  alternatief?: { klasse: string; motivatie: string };
  review_uitleg?: string;
}

const DEMO_SPECS: DemoSpec[] = [
  {
    fragment: "Een belastingaanslag", klasse: "Rechtsobject", lid: "1", aandacht: "groen",
    toelichting: "Het voorwerp waarover de betalingsverplichting loopt.",
  },
  {
    fragment: "is invorderbaar", klasse: "Rechtsbetrekking", lid: "1", aandacht: "geel",
    toelichting: "De juridische toestand die tussen de ontvanger en de belastingschuldige ontstaat.",
    alternatief: {
      klasse: "Rechtsfeit",
      motivatie: "Je kunt het invorderbaar wórden ook lezen als de gebeurtenis die de betalingsplicht opeisbaar maakt.",
    },
    review_uitleg: "Werkwoordsvorm duidt op een rechtsbetrekking, maar het tijdsverloop maakt een rechtsfeit verdedigbaar.",
  },
  {
    fragment: "zes weken na de dagtekening van het aanslagbiljet", klasse: "Tijdsaanduiding", lid: "1",
    aandacht: "groen", toelichting: "Het tijdvak waarna de aanslag invorderbaar is.",
  },
  {
    fragment: "In afwijking van het eerste lid", klasse: "Voorwaarde", lid: "2", aandacht: "geel",
    toelichting: "Bakent af wanneer de hoofdregel van lid 1 niet geldt.",
    alternatief: {
      klasse: "Operator",
      motivatie: "De formulering verbindt twee bepalingen; dat kan ook als logische uitzondering worden gelezen.",
    },
    review_uitleg: "Uitzonderingsformule – Voorwaarde of Operator is hier een echte interpretatiekeuze.",
  },
  {
    fragment: "een navorderingsaanslag", klasse: "Rechtsobject", lid: "2", aandacht: "groen",
    toelichting: "Het voorwerp waarvoor de afwijkende termijn geldt.",
  },
  {
    fragment: "alsmede", klasse: "Operator", lid: "2", aandacht: "groen",
    toelichting: "Logische conjunctie: beide aanslagen vallen onder dezelfde termijn.",
  },
  {
    fragment: "een conserverende navorderingsaanslag", klasse: "Rechtsobject", lid: "2", aandacht: "groen",
    toelichting: "Tweede voorwerp waarvoor de termijn van één maand geldt.",
  },
  {
    // Bewust een misser: het toont hoe een rood oordeel eruitziet en waarom je zelf corrigeert.
    fragment: "invorderbaar", klasse: "Rechtsobject", lid: "2", aandacht: "rood",
    toelichting: "",
    review_uitleg: "Dit is een werkwoordsvorm, geen voorwerp. Hoort vrijwel zeker bij Rechtsbetrekking.",
    alternatief: { klasse: "Rechtsbetrekking", motivatie: "Werkwoord dat de plicht tot betaling uitdrukt." },
  },
  {
    fragment: "één maand na de dagtekening van het aanslagbiljet", klasse: "Tijdsaanduiding", lid: "2",
    aandacht: "groen", toelichting: "Afwijkende termijn voor de (conserverende) navorderingsaanslag.",
  },
  {
    fragment: "een naheffingsaanslag", klasse: "Rechtsobject", lid: "2", aandacht: "groen",
    toelichting: "Het voorwerp waarvoor de kortste termijn geldt.",
  },
  {
    fragment: "veertien dagen na de dagtekening van het aanslagbiljet", klasse: "Tijdsaanduiding", lid: "2",
    aandacht: "groen", toelichting: "Afwijkende termijn voor de naheffingsaanslag.",
  },
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
    beslissingen: [],
    geproduceerd_door: DEMO_RUN,
  };
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
    dekking: {},
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
      denk: "· supervisor koos de definitie-specialist · begrip opgezocht in de graaf · antwoord onderbouwd",
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
      denk:
        "· supervisor koos de annotatie-worker · bepaling opgehaald uit de graaf · " +
        "11 markeringen voorgesteld · 1 modelaanroep · 3 ter keuze · vastgelegd",
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
