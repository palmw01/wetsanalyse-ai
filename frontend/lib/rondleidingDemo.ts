// De voorbeeldscène van de rondleiding: één gesprek en één annotatie, zodat een nieuwe gebruiker de
// werkstroom kan zien zonder eerst 60-90 seconden op een echte annotatiebeurt te wachten.
//
// Drie regels waar deze module zich aan houdt:
//
//  1. **De wettekst is echt.** `DEMO_ARTIKEL` is de letterlijke tekst van artikel 9, leden 1 en 2 van
//     de Invorderingswet 1990, overgenomen uit de officiële XML bij
//     `repository.officiele-overheidspublicaties.nl/bwb/BWBR0004770/`. In een platform dat om
//     brongetrouwheid draait is een verzonnen wettekst een grotere fout dan een lelijke rondleiding.
//  2. **De ankers worden gerekend, niet geteld.** De offsets komen uit `maakAnker` over dezelfde
//     brontekst die het documentpaneel opbouwt (`regelsVan` → `bronVan`). Met de hand ingetypte
//     offsets zouden bij de eerste komma verschuiven en de markeringen laten zweven.
//  3. **Niets hiervan raakt de api.** De demo leeft in het geheugen van één mount; de mutaties
//     hieronder zijn pure functies op een document, geen verzoeken.

import { bronVan, regelsVan } from "./annotatie";
import { maakAnker } from "./selectie";
import type { ThreadItem } from "./threadItem";
import type {
  Aandacht, AnnotatieDocument, AnnotatieElement, AgentRun, Anker, BeslissingInvoer,
  GesprekSamenvatting, GraafArtikel, Lifecycle,
} from "./types";

/** De slug van het voorbeelddocument. Begint met `demo-` zodat hij nooit met een echte slug botst. */
export const DEMO_SLUG = "demo-rondleiding-iw1990-art9";

/** Het label dat overal meereist. Niemand mag de voorbeeldannotatie voor eigen werk aanzien. */
export const DEMO_LABEL = "VOORBEELD";

/** Artikel 9, leden 1 en 2 van de Invorderingswet 1990 – letterlijk uit de officiële publicatie. */
export const DEMO_ARTIKEL: GraafArtikel = {
  bwbId: "BWBR0004770",
  artikel: "9",
  citeertitel: "Invorderingswet 1990",
  opschrift: "Invorderingswet 1990 – artikel 9",
  leden_teksten: [
    { lid: "1", tekst: "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet." },
    {
      lid: "2",
      tekst:
        "In afwijking van het eerste lid is een navorderingsaanslag, alsmede een conserverende " +
        "navorderingsaanslag invorderbaar één maand na de dagtekening van het aanslagbiljet en een " +
        "naheffingsaanslag invorderbaar veertien dagen na de dagtekening van het aanslagbiljet.",
    },
  ],
};

/** De agent-ronde die de voorbeeldvoorstellen "maakte". Ook een demo hoort een herkomst te dragen. */
const DEMO_RUN: AgentRun = {
  ronde: 1,
  model: "voorbeeld",
  provider: "rondleiding",
  agent_versie: "demo",
  critic_rondes: 1,
  stop_reden: "klaar",
  tijd: "2026-01-01T09:00:00Z",
};

/** Eén voorgenomen markering. `voorkomen` telt vanaf 1 en kiest wélke treffer in de brontekst het is
 *  – "invorderbaar" staat er drie keer, en het maakt uit welke je bedoelt. */
interface DemoSpec {
  fragment: string;
  voorkomen?: number;
  klasse: string;
  lid: string;
  aandacht: Aandacht;
  toelichting: string;
  alternatief?: { klasse: string; motivatie: string };
  critic?: string;
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
    critic: "Werkwoordsvorm duidt op een rechtsbetrekking, maar het tijdsverloop maakt een rechtsfeit verdedigbaar.",
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
    critic: "Uitzonderingsformule – Voorwaarde of Operator is hier een echte interpretatiekeuze.",
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
    fragment: "invorderbaar", voorkomen: 2, klasse: "Rechtsobject", lid: "2", aandacht: "rood",
    toelichting: "",
    critic: "Dit is een werkwoordsvorm, geen voorwerp. Hoort vrijwel zeker bij Rechtsbetrekking.",
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

/** De brontekst waar het documentpaneel en de ankers over praten. */
export function demoBron(): string {
  return bronVan(regelsVan(DEMO_ARTIKEL));
}

/** Positie van de `n`-de treffer van `fragment`; -1 als hij er niet is. */
function positieVan(bron: string, fragment: string, voorkomen: number): number {
  let i = -1;
  for (let n = 0; n < voorkomen; n++) {
    i = bron.indexOf(fragment, i + 1);
    if (i === -1) return -1;
  }
  return i;
}

function elementVan(spec: DemoSpec, index: number, bron: string): AnnotatieElement {
  const start = positieVan(bron, spec.fragment, spec.voorkomen ?? 1);
  // Een fragment dat niet in de tekst staat, hoort ook in de demo niet stilzwijgend te verdwijnen:
  // zonder anker toont de reviewlijst hem als zwevende markering, precies zoals bij echt werk.
  const anker: Anker | null =
    start === -1 ? null : maakAnker(bron, start, start + spec.fragment.length, spec.lid);
  return {
    id: `demo-el-${index + 1}`,
    klasse: spec.klasse,
    tekst: spec.fragment,
    lid: spec.lid,
    toelichting: spec.toelichting,
    vindplaats: `lid ${spec.lid}`,
    herkomst: "agent",
    gewijzigd_door: "",
    lifecycle: "critic_checked" as Lifecycle,
    alternatieven: spec.alternatief ? [spec.alternatief] : [],
    aandacht: spec.aandacht,
    critic: spec.critic,
    critic_rondes: [],
    critic_suggestie: null,
    anker,
    diff: {},
    beslissingen: [],
    geproduceerd_door: DEMO_RUN,
  };
}

/** Het voorbeelddocument, vers opgebouwd. Elke start van de rondleiding krijgt een schone lei. */
export function maakDemoDocument(): AnnotatieDocument {
  const bron = demoBron();
  return {
    slug: DEMO_SLUG,
    user_id: "demo",
    client_id: "demo",
    citeertitel: `${DEMO_LABEL} · ${DEMO_ARTIKEL.citeertitel}`,
    werkgebied: "rondleiding",
    bwbId: DEMO_ARTIKEL.bwbId,
    artikel: DEMO_ARTIKEL.artikel,
    lid: "",
    status: "in_review",
    elementen: DEMO_SPECS.map((spec, i) => elementVan(spec, i, bron)),
    runs: [DEMO_RUN],
    created: DEMO_RUN.tijd,
    updated: DEMO_RUN.tijd,
  };
}

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
      titel: `${DEMO_LABEL} · Invorderingswet 1990 – artikel 9`,
      denk:
        "· supervisor koos de annotatie-worker · bepaling opgehaald uit de graaf · " +
        "11 markeringen voorgesteld · Critic las mee (1 ronde) · vastgelegd",
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
  docs: Record<string, AnnotatieDocument>;
  infos: Record<string, GraafArtikel>;
  /** De sidebar draait tijdens de rondleiding op deze lijst in plaats van op die uit de api. */
  gesprekken: GesprekSamenvatting[];
}

export function maakDemoScene(): DemoScene {
  return {
    items: maakDemoItems(),
    docs: { [DEMO_SLUG]: maakDemoDocument() },
    infos: { [DEMO_SLUG]: DEMO_ARTIKEL },
    gesprekken: maakDemoGesprekken(),
  };
}

// --- mutaties binnen de demo (pure functies, geen api) ---------------------------------------

/** Welke lifecycle hoort bij een beslissing? Dezelfde uitkomsten als de api, zonder het auditspoor —
 *  dat hoort bij echt werk en wordt in de rondleiding alleen benoemd, niet nagebouwd. */
function lifecycleNa(type: BeslissingInvoer["type"], huidig: Lifecycle): Lifecycle {
  if (type === "approve") return "human_approved";
  if (type === "reject") return "rejected";
  if (type === "edit") return "edited";
  if (type === "heropen") return "critic_checked";
  return huidig;
}

export function pasDemoBeslissingToe(
  doc: AnnotatieDocument,
  elementId: string,
  req: BeslissingInvoer,
): AnnotatieDocument {
  return {
    ...doc,
    elementen: doc.elementen.map((el) => {
      if (el.id !== elementId) return el;
      const wijziging = (req.wijziging ?? {}) as Partial<AnnotatieElement>;
      return {
        ...el,
        ...(req.type === "edit" ? wijziging : {}),
        lifecycle: lifecycleNa(req.type, el.lifecycle),
        gewijzigd_door: req.type === "edit" ? "mens" : el.gewijzigd_door,
      };
    }),
  };
}

export function voegDemoElementToe(
  doc: AnnotatieDocument,
  invoer: { klasse: string; tekst: string; lid: string; toelichting: string; anker: Anker },
): { doc: AnnotatieDocument; id: string } {
  const id = `demo-eigen-${doc.elementen.length + 1}`;
  const nieuw: AnnotatieElement = {
    id,
    klasse: invoer.klasse,
    tekst: invoer.tekst,
    lid: invoer.lid,
    toelichting: invoer.toelichting,
    vindplaats: invoer.lid ? `lid ${invoer.lid}` : "",
    herkomst: "mens",
    gewijzigd_door: "",
    lifecycle: "human_approved",
    alternatieven: [],
    aandacht: null,
    critic_rondes: [],
    critic_suggestie: null,
    anker: invoer.anker,
    diff: {},
    beslissingen: [],
    geproduceerd_door: null,
  };
  return { doc: { ...doc, elementen: [...doc.elementen, nieuw] }, id };
}

export function wisDemoElement(doc: AnnotatieDocument, elementId: string): AnnotatieDocument {
  return { ...doc, elementen: doc.elementen.filter((el) => el.id !== elementId) };
}

export function zetDemoStatus(doc: AnnotatieDocument, status: AnnotatieDocument["status"]): AnnotatieDocument {
  return { ...doc, status };
}
