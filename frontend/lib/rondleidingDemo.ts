// De voorbeeldscène van de rondleiding: één gesprek en één annotatie, zodat een nieuwe gebruiker de
// werkstroom kan zien zonder eerst 60-90 seconden op een echte annotatiebeurt te wachten.
//
// Vier regels waar deze module zich aan houdt:
//
//  1. **De wettekst is echt.** `DEMO_LEDEN` is de letterlijke tekst van artikel 9, lid 1 van de
//     Invorderingswet 1990, en de graaf draagt de letterlijke tekst van de andere leden van artikel 9, allebei uit de
//     kennisgraaf van acceptatie (die de officiële XML bij `repository.officiele-overheidspublicaties.nl` inleest).
//     In een platform dat om brongetrouwheid draait is een verzonnen wettekst een grotere fout dan een lelijke rondleiding.
//     De markeringen, relaties en impliciete partijen zijn die van de annotatie van dat lid op acceptatie (25 nov 2026),
//     zonder wat de jurist daar verwierp. Twee bewuste afwijkingen: de zes voorstellen van Lex staan nog open (de
//     rondleiding gaat over beoordelen), en de Rechtsbetrekking staat op *Keuze voor jou*, met Rechtsfeit als
//     alternatief, zodat de stap over de badges iets aan te wijzen heeft. Wat de jurist er zelf bij markeerde (de
//     Afleidingsregel, "zes weken" en "invorderbaar") is al beoordeeld, met de relaties en partijen die hij legde.
//  2. **De ankers worden gerekend, niet geteld.** Elk anker komt uit `segmentAnker` over de tekst van
//     zijn eigen lid, in codepoints, net als bij de api. Met de hand ingetypte offsets zouden bij de
//     eerste komma verschuiven en de markeringen laten zweven.
//  3. **Het is de weergave van echt werk.** De demo levert een v2-weergave (`NodeWeergave`) en een
//     opslag (`NodeOpslag`) voor `NodeAnnotatiePaneel` – hetzelfde paneel als een echte annotatie, met dezelfde tabs
//     Tekst, Graaf en Diagram. Het diagram komt uit `rondleidingDemo.diagram.json` (de plaatsing die de api op
//     acceptatie rekende); de graaf is een vaste uitsnede rond artikel 9 (`rondleidingDemo.graaf.json`: de structuur en
//     de verwijzingen) met de markeringen en relaties uit de weergave van nu, zodat hij een beslissing volgt.
//  4. **Niets hiervan raakt de api.** De opslag en de graafbron (`GraafDataBron`) leven in het geheugen van één scène;
//     de handelingen krijgen dezelfde lichamen als de api, maar er gaat geen verzoek de deur uit.

import {
  segmentAnker, type NodeAnker, type NodeDoel, type NodeEindpunt, type NodeElement, type NodeImpliciet, type NodeOpslag,
  type NodeRelatie, type NodeSegment, type NodeWeergave,
} from "./annotatieNode";
import type { DiagramData, DiagramSet, Geplaatst } from "./diagram2c";
import type { GraafDataBron } from "./graaf/databron";
import type { Samenhang, SamenhangKnoop, SamenhangRelatie } from "./samenhang";
import diagramBestand from "./rondleidingDemo.diagram.json";
import graafBestand from "./rondleidingDemo.graaf.json";
import { aantal } from "./aantal";
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

/** Artikel 9, lid 1 van de Invorderingswet 1990 – letterlijk uit de officiële publicatie. Eén lid,
 *  zoals een annotatiebeurt er één annoteert: de keuzekaart legt een artikel met leden per lid voor. */
export const DEMO_LEDEN: { lid: string; tekst: string }[] = [
  { lid: "1", tekst: "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet." },
];

/** Het doel van de voorbeeldannotatie, zoals de chip in de thread hem meegeeft aan het paneel. */
export const DEMO_DOEL: NodeDoel = {
  bron_iri: lidIri("1"),
  type: "Lid",
  label: `${DEMO_LABEL} · Invorderingswet 1990 – artikel 9, lid 1`,
  bwb_id: BWB_ID,
  artikel: "9",
  lid: "1",
  citeertitel: `${DEMO_LABEL} · Invorderingswet 1990`,
  snapshot_id: SNAPSHOT,
};

/** De agent-ronde die de voorbeeldvoorstellen "maakte". Ook een demo hoort een herkomst te dragen. */
const DEMO_RUN: AgentRun = {
  ronde: 1,
  model: "claude-sonnet-4-6",
  provider: "rondleiding",
  agent_versie: "demo",
  stop_reden: "klaar",
  tijd: "2026-01-01T09:00:00Z",
};

/** Eén markering van de voorbeeldannotatie. `voorkomen` telt vanaf 1 binnen het lid en kiest wélke treffer het is.
 *
 *  Een voorstel van Lex (`door` gezet) staat open; de aandacht volgt de keten van nu: geen badge is een gewoon voorstel,
 *  geel ("Keuze voor jou") is twijfel die de reviewer niet besliste. Rood zet de keten niet, dus de demo ook niet. Het
 *  spoor gebruikt de codes uit `tools/graph-qa/agent/jas_pipeline/verklaringen.yaml`, zodat *Waarom?* er net zo uitziet
 *  als bij echt werk. Zonder `door` is het een markering van de jurist zelf: beoordeeld, zonder spoor van de keten. */
interface DemoSpec {
  /** Het id van het element op acceptatie; de demo zet er `demo-` voor. */
  acc: string;
  fragment: string;
  voorkomen?: number;
  klasse: string;
  jas_subtype?: string;
  lid: string;
  aandacht: Aandacht | null;
  toelichting: string;
  /** Wie besliste: een vaste regel of het model. Leeg: de jurist markeerde dit zelf. */
  door?: "regel" | "model";
  /** Het bewijs van de detectoren: [detector, code]. */
  bewijs?: [string, string][];
  alternatieven?: { klasse: string; motivatie: string }[];
  review_uitleg?: string;
  twijfel?: string;
  resolutie?: string;
}

// De markeringen van de annotatie op acceptatie, in de volgorde van de tekst: eerst de zes voorstellen van Lex, dan de
// drie van de jurist. De toelichtingen zijn die van de keten; de bewijscodes die van haar spoor.
const DEMO_SPECS: DemoSpec[] = [
  {
    acc: "473c19a14797",
    fragment: "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.",
    klasse: "Rechtsbetrekking", lid: "1", aandacht: "geel", door: "model",
    bewijs: [["norm", "NORMATIVE_PREDICATE"], ["norm", "LEGAL_EFFECT_PREDICATE"]],
    toelichting:
      "Een rechtsbetrekking is een relatie tussen twee rechtssubjecten waarbij het ene subject een recht heeft en het " +
      "andere een daarmee corresponderende plicht. Hier: de ontvanger mag de belastingaanslag invorderen bij de " +
      "belastingschuldige – Normatief gezegde (“invorderbaar”).",
    alternatieven: [{
      klasse: "Rechtsfeit",
      motivatie: "aangedragen door Rechtsgevolg in de norm (“invorderbaar”) – het verstrijken van de termijn als rechtsfeit",
    }],
    review_uitleg:
      "Je kunt de zin lezen als de bevoegdheid van de ontvanger om de aanslag in te vorderen (Rechtsbetrekking) of als " +
      "het tijdsverloop dat de aanslag invorderbaar maakt (Rechtsfeit). Beide lezingen zijn verdedigbaar; de keuze is aan jou.",
    twijfel: "DETECTOR_CONFLICT", resolutie: "R-CONFLICT-HUMAN",
  },
  {
    acc: "223ac94d9c58", fragment: "Een belastingaanslag", klasse: "Rechtsobject", lid: "1", aandacht: null, door: "model",
    bewijs: [["naamwoordgroep", "THING_NP"]],
    toelichting:
      "Een rechtsobject is het voorwerp van een rechtsbetrekking en/of rechtsfeit. Hier: “Een belastingaanslag” – " +
      "Document of rechtshandeling als ding (“belastingaanslag”).",
    alternatieven: [{
      klasse: "Variabele en variabelewaarde",
      motivatie: "aangedragen door Document of rechtshandeling als ding (“belastingaanslag”) – bedrag of toeslag als voorwerp",
    }],
  },
  {
    acc: "055a7e165515", fragment: "zes weken na de dagtekening van het aanslagbiljet", klasse: "Tijdsaanduiding",
    jas_subtype: "verbijzondert parameter", lid: "1", aandacht: null, door: "model",
    bewijs: [["tijd", "TEMPORAL_DURATION"], ["nominalisatie", "NOMINALIZED_ACTION"]],
    toelichting:
      "Een tijdsaanduiding is een omschrijving van een tijdstip of tijdvak. Hier: “zes weken na de dagtekening van het " +
      "aanslagbiljet” – Termijn (“zes weken”).",
    alternatieven: [{
      klasse: "Rechtsfeit",
      motivatie: "aangedragen door Handeling als zelfstandig naamwoord (“dagtekening”) – tijdsverloop of een startgebeurtenis in een termijn",
    }],
  },
  {
    acc: "a362df5f5bef", fragment: "na", klasse: "Operator", lid: "1", aandacht: null, door: "model",
    bewijs: [["operator", "DURATION_OFFSET"]],
    toelichting:
      "Een operator is een woord, een combinatie van woorden of een teken dat een rekenkundige bewerking, een " +
      "samengestelde voorwaarde, een gelijkstelling of een vergelijking van twee waarden of berekeningen uitdrukt. " +
      "Hier: “na” – Duur vanaf een moment (“na”).",
  },
  {
    acc: "d46ea984bf1d", fragment: "de dagtekening van het aanslagbiljet", klasse: "Tijdsaanduiding",
    jas_subtype: "verbijzondert variabele", lid: "1", aandacht: null, door: "model",
    bewijs: [["tijd", "TEMPORAL_VALUE"]],
    toelichting:
      "Een tijdsaanduiding is een omschrijving van een tijdstip of tijdvak. Hier: “de dagtekening van het " +
      "aanslagbiljet” – Tijdstip als waarde.",
  },
  {
    acc: "1c3866246a40", fragment: "het aanslagbiljet", klasse: "Rechtsobject", lid: "1", aandacht: null, door: "model",
    bewijs: [["naamwoordgroep", "THING_NP"]],
    toelichting:
      "Een rechtsobject is het voorwerp van een rechtsbetrekking en/of rechtsfeit. Hier: “het aanslagbiljet” – " +
      "Document of rechtshandeling als ding (“aanslagbiljet”).",
    alternatieven: [{
      klasse: "Variabele en variabelewaarde",
      motivatie: "aangedragen door Document of rechtshandeling als ding (“aanslagbiljet”) – bedrag of toeslag als voorwerp",
    }],
  },
  {
    acc: "8263fa226caa491988a08721285d4106", fragment: "invorderbaar zes weken na de dagtekening van het aanslagbiljet",
    klasse: "Afleidingsregel", lid: "1", aandacht: null,
    toelichting:
      "Leidt af wanneer een belastingaanslag invorderbaar is: zes weken (parameter) na de dagtekening van het " +
      "aanslagbiljet (tijdsaanduiding).",
  },
  {
    acc: "379bc7e16ded465b895586eedddb2e3f", fragment: "zes weken", klasse: "Tijdsaanduiding",
    jas_subtype: "verbijzondert parameter", lid: "1", aandacht: null,
    toelichting: "Een termijn (tijdvak) die voor iedere aanslag zonder termijnen gelijk is: een tijdsaanduiding die een parameter verbijzondert.",
  },
  {
    acc: "5bdea17d31534e0994a895a1376b2f49", fragment: "invorderbaar", klasse: "Variabele en variabelewaarde",
    jas_subtype: "variabele", lid: "1", aandacht: null,
    toelichting: "Of een belastingaanslag invorderbaar is: de uitvoer van de afleidingsregel, met een waarde per aanslag (ja of nee op een datum).",
  },
];

/** Het id van een element, partij of relatie in de demo: het id van acceptatie met `demo-` ervoor. */
export const demoId = (acc: string) => `demo-${acc}`;

/** De twee partijen die de tekst niet noemt, zoals de jurist ze op acceptatie vastlegde (ADR-011). */
const DEMO_IMPLICIET: Omit<NodeImpliciet, "laag_id">[] = [
  {
    id: demoId("I45f83f76a2ea4913"), klasse: "Rechtssubject", label: "de belastingschuldige", herkomst: "mens",
    vindplaats: "Invorderingswet 1990, art. 2 lid 1 onderdeel k",
    toelichting: "Lid 1 noemt niet tegen wie wordt ingevorderd: degene te wiens naam de belastingaanslag is gesteld (art. 2 lid 1 onderdeel k), de plichthebbende van deze rechtsbetrekking.",
  },
  {
    id: demoId("Ibdcdf4fb8ac14c7d"), klasse: "Rechtssubject", label: "de ontvanger", herkomst: "mens",
    vindplaats: "Invorderingswet 1990, art. 2 lid 1 onderdeel i",
    toelichting: "Lid 1 noemt niet wie invordert. Invorderbaar betekent dat de ontvanger de aanslag mag invorderen: de rechthebbende van deze rechtsbetrekking.",
  },
];

/** De relaties van de annotatie op acceptatie, zonder de verworpen: [id, type, leesvorm, van, naar, volgorde, herkomst]. */
const DEMO_RELATIES: [string, string, string, string, string, number | null, "mens" | "agent"][] = [
  ["R229274641127d160", "rechthebbende", "is rechthebbende van", "Ibdcdf4fb8ac14c7d", "473c19a14797", null, "mens"],
  ["Rd052f8bcab4452c5", "plichthebbende", "is plichthebbende van", "I45f83f76a2ea4913", "473c19a14797", null, "mens"],
  ["Rc7b1492915b923d0", "voorwerp", "heeft als voorwerp", "473c19a14797", "223ac94d9c58", null, "mens"],
  ["R63f1304f3b4238f9", "tijd", "heeft als tijdsaanduiding", "473c19a14797", "055a7e165515", null, "agent"],
  ["R815ac01935b74cef", "invoer", "is invoer van", "d46ea984bf1d", "8263fa226caa491988a08721285d4106", 1, "mens"],
  ["R389f61c92831a82c", "invoer", "is invoer van", "379bc7e16ded465b895586eedddb2e3f", "8263fa226caa491988a08721285d4106", 2, "mens"],
  ["Rf05b7f561d2b5f6f", "operator_in", "is operator in", "a362df5f5bef", "8263fa226caa491988a08721285d4106", null, "mens"],
  ["Rad2633e896a8ac99", "uitvoer", "levert op", "8263fa226caa491988a08721285d4106", "5bdea17d31534e0994a895a1376b2f49", null, "mens"],
  ["R59d127e85b1ae045", "kenmerk", "is kenmerk van", "5bdea17d31534e0994a895a1376b2f49", "223ac94d9c58", null, "mens"],
];

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

/** Het herkomstspoor van een voorstel van Lex, in de vorm van de keten. */
function spoorVan(spec: DemoSpec): ElementTrace | undefined {
  if (!spec.door) return undefined;
  return {
    pijplijn: "hybrid_v1",
    kandidaat: {
      label: spec.fragment,
      mogelijke_klassen: [spec.klasse, ...(spec.alternatieven ?? []).map((a) => a.klasse)],
      bewijs: (spec.bewijs ?? []).map(([detector, code]) => ({ detector, code })),
    },
    beslissing: { status: "voorgesteld", klasse: spec.klasse, door: spec.door },
    ...(spec.twijfel ? { twijfel: [{
      reden: spec.twijfel, huidig: spec.klasse, alternatieven: (spec.alternatieven ?? []).map((a) => a.klasse),
    }] } : {}),
    ...(spec.resolutie ? { resolutie: [{ regel: spec.resolutie }] } : {}),
  };
}

function elementVan(spec: DemoSpec, segment: NodeSegment): NodeElement {
  const start = positieVan(segment.tekst, spec.fragment, spec.voorkomen ?? 1);
  // Een fragment dat niet in de tekst staat, hoort ook in de demo niet stilzwijgend te verdwijnen:
  // zonder anker toont de reviewlijst hem als zwevende markering, precies zoals bij echt werk.
  const ankers: NodeAnker[] = start === -1 ? [] : [segmentAnker(segment, start, start + spec.fragment.length)];
  const vanLex = Boolean(spec.door);
  return {
    id: demoId(spec.acc),
    eigenaar_iri: segment.bron_iri,
    laag_id: laagId(spec.lid),
    klasse: spec.klasse,
    ...(spec.jas_subtype ? { jas_subtype: spec.jas_subtype } : {}),
    tekst: spec.fragment,
    toelichting: spec.toelichting,
    ankers,
    lifecycle: vanLex ? "voorgesteld" : "human_approved",
    herkomst: vanLex ? "agent" : "mens",
    alternatieven: spec.alternatieven ?? [],
    aandacht: spec.aandacht,
    review_uitleg: spec.review_uitleg,
    trace: spoorVan(spec),
    beslissingen: vanLex ? [] : [{ type: "markering", actor: "voorbeeld", tijd: DEMO_RUN.tijd, comment: "", wijziging: { klasse: spec.klasse } }],
    geproduceerd_door: vanLex ? DEMO_RUN : null,
  };
}

/** De dekking zoals de keten haar mat: alle dimensies gedraaid, en – zoals op acceptatie – geen zinsdeel
 *  zonder treffer. */
function demoDekking(segmenten: NodeSegment[]) {
  const structureel = Object.fromEntries(segmenten.map((segment) => [segment.bron_iri, {
    dimensies: Object.fromEntries(DIMENSIES.map((d) => [d, "uitgevoerd" as const])),
    ongedekt: [] as { tekst: string; start: number; eind: number }[],
  }]));
  return { voltooid: true, structureel };
}

/** De relaties en partijen met hun eindpunten zoals de weergave ze beschrijft (`beschrijf` in de api). */
function demoRelaties(elementen: NodeElement[], impliciet: NodeImpliciet[]): NodeRelatie[] {
  const eind = (acc: string): NodeEindpunt => {
    const id = demoId(acc);
    const el = elementen.find((e) => e.id === id);
    if (el) return { soort: "element", id, bestaat: true, klasse: el.klasse, tekst: el.tekst, laag_id: el.laag_id, actueel: true };
    const p = impliciet.find((x) => x.id === id);
    return { soort: "impliciet", id, bestaat: Boolean(p), klasse: p?.klasse, tekst: p?.label, laag_id: p?.laag_id, actueel: true };
  };
  return DEMO_RELATIES.map(([id, type, leesvorm, van, naar, volgorde, herkomst]) => ({
    // Wat de jurist legde is vastgesteld; wat Lex voorstelde staat open, net als zijn markeringen.
    id: demoId(id), type, leesvorm, volgorde, lifecycle: herkomst === "mens" ? "human_approved" : "voorgesteld", herkomst, laag_id: laagId("1"),
    veranderd: false, van: eind(van), naar: eind(naar),
  }));
}

/** De weergave van de voorbeeldannotatie, vers opgebouwd. Elke start krijgt een schone lei. */
export function maakDemoWeergave(): NodeWeergave {
  const segmenten = demoSegmenten();
  const segmentVan = (lid: string) => segmenten.find((s) => s.nummer === lid)!;
  const elementen = DEMO_SPECS.map((spec) => elementVan(spec, segmentVan(spec.lid)));
  const impliciet = DEMO_IMPLICIET.map((p) => ({ ...p, laag_id: laagId("1") }));
  return {
    schema_versie: 2,
    doel: { ...DEMO_DOEL },
    snapshot_id: SNAPSHOT,
    segmenten,
    lagen: DEMO_LEDEN.map(({ lid }) => ({ id: laagId(lid), bron_iri: lidIri(lid), revisie: 1, status: "in_review" })),
    elementen,
    verwijzingen: [],
    dekking: demoDekking(segmenten),
    relaties: demoRelaties(elementen, impliciet),
    impliciet,
  };
}

// --- het diagram en de graaf (in het geheugen, in de vorm van de api) ----------------------

interface DiagramBestand {
  diagrammen: (Omit<DiagramData, "plaatsing"> & {
    plaatsing: { breedte: number; hoogte: number; knopen: (Omit<Geplaatst, "knoop"> & { id: string })[] };
  })[];
}

/** De diagrammen van de bepaling zoals de api ze op acceptatie plaatste, met de stand van de weergave van nu: een
 *  beslissing kleurt de knoop mee, net als bij echt werk. Opnieuw plaatsen rekent de api; dat doet de demo niet. */
export function demoDiagrammen(view: NodeWeergave): DiagramSet {
  const bestand = diagramBestand as unknown as DiagramBestand;
  const lifecycleVan = (k: { id: string; soort: string; lifecycle: string }) =>
    k.soort === "element" ? view.elementen.find((e) => e.id === k.id)?.lifecycle ?? k.lifecycle : k.lifecycle;
  return {
    bron_iri: view.doel.bron_iri,
    diagrammen: bestand.diagrammen.map((d) => {
      const knopen = d.diagram.knopen.map((k) => {
        const knoop = { ...k, id: demoId(k.id) };
        return { ...knoop, lifecycle: lifecycleVan(knoop) };
      });
      const knoopVan = (id: string) => knopen.find((k) => k.id === demoId(id))!;
      return {
        diagram: {
          ...d.diagram, centraal: demoId(d.diagram.centraal), knopen,
          lijnen: d.diagram.lijnen.map((l) => {
            const r = view.relaties?.find((x) => x.van.id === demoId(l.van) && x.naar.id === demoId(l.naar) && x.type === l.code);
            return { ...l, van: demoId(l.van), naar: demoId(l.naar), lifecycle: r?.lifecycle ?? l.lifecycle };
          }),
        },
        plaatsing: { ...d.plaatsing, knopen: d.plaatsing.knopen.map(({ id, ...g }) => ({ ...g, knoop: knoopVan(id) })) },
        lijnen: d.lijnen.map((l) => ({ ...l, relatie_id: demoId(l.relatie_id), van: demoId(l.van), naar: demoId(l.naar),
          lifecycle: view.relaties?.find((r) => r.id === demoId(l.relatie_id))?.lifecycle ?? l.lifecycle })),
        ontbreekt_rollen: d.ontbreekt_rollen,
      };
    }),
  };
}

/** Waar de uitsnede stopt: wat de graaf daarbuiten vraagt, zegt dat in gewone woorden. */
const BUITEN_UITSNEDE = "In het voorbeeld staat alleen artikel 9 van de Invorderingswet 1990 in de graaf.";

/** De samenhang van artikel 9 zoals de api hem levert: de vaste uitsnede (structuur en verwijzingen) met de markeringen,
 *  klassen, partijen en relaties uit de weergave van nu. */
export function demoSamenhang(view: NodeWeergave): Samenhang {
  const vast = graafBestand as unknown as { knopen: SamenhangKnoop[]; relaties: SamenhangRelatie[] };
  const leeg = { tekst: "", klasse: "", lifecycle: "", element_id: "", bwb_id: BWB_ID, artikel: "", lid: "", rand: false };
  // Het label reist mee tot in de graaf: ook daar mag niemand het voorbeeld voor echt werk aanzien.
  const structuur = vast.knopen.map((k) => (k.soort === "regeling" ? { ...k, label: `${DEMO_LABEL} · ${k.label}` } : k));
  const elementen = view.elementen.filter((e) => !e.verouderd);
  const markeringen: SamenhangKnoop[] = elementen.map((e) => ({
    ...leeg, id: `element:${e.id}`, soort: "markering", label: e.tekst, tekst: e.tekst, klasse: e.klasse,
    lifecycle: e.lifecycle, element_id: e.id, artikel: "9", lid: "1", herkomst: e.herkomst, aandacht: e.aandacht ?? "",
    subtype: e.jas_subtype ?? "", beslist_door: e.trace?.beslissing?.door ?? "",
  }));
  const klassen: SamenhangKnoop[] = [...new Set(elementen.map((e) => e.klasse))].map((k) => ({
    ...leeg, bwb_id: "", id: `klasse:${k}`, soort: "klasse", label: k, klasse: k,
  }));
  const partijen: SamenhangKnoop[] = (view.impliciet ?? []).map((p) => ({
    ...leeg, bwb_id: "", id: `impliciet:${p.id}`, soort: "impliciet", label: p.label, klasse: p.klasse,
  }));
  const eindVan = (e: NodeEindpunt) => `${e.soort === "impliciet" ? "impliciet" : "element"}:${e.id}`;
  const relatie = (bron: string, doel: string, soort: SamenhangRelatie["soort"], groep: SamenhangRelatie["groep"], anker = "") =>
    ({ bron, doel, soort, groep, anker_tekst: anker });
  return {
    schema_versie: 1, doel: { ...view.doel }, snapshot_id: view.snapshot_id, artikel_iri: ARTIKEL_IRI,
    knopen: [...structuur, ...markeringen, ...klassen, ...partijen],
    relaties: [
      ...vast.relaties,
      ...elementen.flatMap((e) => [
        relatie(`element:${e.id}`, e.eigenaar_iri, "markeert", "annotaties"),
        relatie(`element:${e.id}`, `klasse:${e.klasse}`, "heeft_klasse", "annotaties"),
      ]),
      ...(view.relaties ?? []).filter((r) => r.lifecycle !== "rejected")
        .map((r) => ({ ...relatie(eindVan(r.van), eindVan(r.naar), "jas_relatie", "relaties", r.leesvorm),
          type: r.type, leesvorm: r.leesvorm, lifecycle: r.lifecycle, veranderd: r.veranderd, volgorde: r.volgorde ?? null })),
    ],
    verwijzingen_beschikbaar: true, afgekapt: false,
  };
}

/** De tekst van een bepaling uit de uitsnede, voor de inspector: lid 1 uit de weergave (met de markeringen), een ander
 *  lid of onderdeel met zijn letterlijke tekst, het artikel met zijn leden. */
function demoBepaling(view: NodeWeergave, iri: string): NodeWeergave {
  if (view.segmenten.some((s) => s.bron_iri === iri)) return view;
  const vast = graafBestand as unknown as { knopen: SamenhangKnoop[]; relaties: SamenhangRelatie[] };
  const kinderen = (id: string) => vast.relaties.filter((r) => r.soort === "bevat" && r.bron === id).map((r) => r.doel);
  const iris = vast.knopen.some((k) => k.id === iri && k.tekst) ? [iri] : kinderen(iri);
  const segmenten: NodeSegment[] = iris.flatMap((id, i) => {
    if (id === lidIri("1")) return view.segmenten;
    const k = vast.knopen.find((x) => x.id === id && x.tekst && !x.rand);
    return k ? [{ bron_iri: k.id, type: k.soort === "onderdeel" ? "Onderdeel" : "Lid", nummer: k.lid, label: k.label,
      tekst: k.tekst, bron_hash: `demo-${k.id}`, volgorde: i + 1 }] : [];
  });
  if (!segmenten.length) throw new Error(BUITEN_UITSNEDE);
  return { ...view, doel: { ...view.doel, bron_iri: iri }, segmenten,
    elementen: view.elementen.filter((e) => segmenten.some((s) => s.bron_iri === e.eigenaar_iri)) };
}

/** De graafbron van de demo: alles uit de weergave van nu en de vaste uitsnede, niets van de api. */
export function demoGraafBron(huidig: () => NodeWeergave): GraafDataBron {
  const binnen = (doel: { bron_iri: string }) => doel.bron_iri.startsWith(ARTIKEL_IRI);
  const samenhang = async (doel: { bron_iri: string }) => {
    if (!binnen(doel)) throw new Error(BUITEN_UITSNEDE);
    return demoSamenhang(huidig());
  };
  return {
    samenhang,
    async samenhangen(doelen) {
      return {
        resultaten: doelen.some(binnen) ? [demoSamenhang(huidig())] : [],
        fouten: doelen.filter((d) => !binnen(d)).map((d) => ({ bron_iri: d.bron_iri, reden: BUITEN_UITSNEDE })),
      };
    },
    keten: async (doelen) => samenhang(doelen[0] ?? { bron_iri: "" }),
    async kennisgraaf() {
      const s = demoSamenhang(huidig());
      return { schema_versie: 1, versie: "demo-rondleiding", knopen: s.knopen, relaties: s.relaties,
        regelingen: [{ bwb_id: BWB_ID, citeertitel: `${DEMO_LABEL} · Invorderingswet 1990`, toestand: "2026-10-01" }] };
    },
    // Wat de BWB-graaf verder over een knoop weet (geldigheid, herkomst, triples) zit niet in de uitsnede.
    knoopInfo: async (iri) => ({ schema_versie: 1, bron_iri: iri, beschikbaar: false, groepen: [], ruw: [], verwijzingen: [] }),
    bepaling: async (iri) => demoBepaling(huidig(), iri),
    async element(id) {
      const el = huidig().elementen.find((e) => e.id === id);
      if (!el) throw new Error(BUITEN_UITSNEDE);
      return el;
    },
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
  wijziging?: { klasse?: string; jas_subtype?: string; toelichting?: string; tekst?: string; ankers?: NodeAnker[]; optie?: number };
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
      ...(w.jas_subtype != null ? { jas_subtype: w.jas_subtype } : {}),
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
    lifecycle: "human_approved", herkomst: "mens", alternatieven: [], aandacht: null, geproduceerd_door: null,
    beslissingen: [{ type: "markering", actor: "voorbeeld", tijd: new Date().toISOString(), comment: "", wijziging: { klasse: invoer.klasse } }],
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
    async beslisLaag(_laag, body) {
      for (const b of body.besluiten) view = pasDemoBeslissingToe(view, b.element_id, b as unknown as BeslissingLichaam);
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
      view = { ...view, elementen: [], lagen: [], relaties: [], impliciet: [], verwijderd: { op: new Date().toISOString() } };
      return {};
    },
    // Een voorbeeld levert geen bestand: het keuzepaneel sluit, zoals bij elke export.
    async exporteer() {},
    // Het diagram en de graaf komen uit hetzelfde geheugen, met de stand van nu.
    diagrammen: async () => demoDiagrammen(view),
    graaf: demoGraafBron(() => view),
  };
}

// --- de thread en de sidebar ----------------------------------------------------------------

/** Wat Lex onder de annotatie zegt. Elke zin volgt uit `DEMO_SPECS`, zoals bij graph-qa. */
/** Wat Lex onder de annotatie zegt, uit dezelfde weergave als het paneel en de graaf: de tellingen kloppen dus altijd
 *  met de reviewlijst ("3/9 beoordeeld") en de graaf ("9 markeringen"). De opbouw volgt graph-qa
 *  (`agent/nodes/annotatie_samenvatting.py`): het aantal, de klassen die het vaakst voorkomen, de twijfel, wie koos. */
export function demoSamenvatting(view: NodeWeergave): string {
  const els = view.elementen.filter((e) => !e.verouderd);
  const vanLex = els.filter((e) => e.herkomst === "agent");
  const telling = new Map<string, number>();
  for (const e of els) telling.set(e.klasse, (telling.get(e.klasse) ?? 0) + 1);
  const top = [...telling.entries()].sort((x, y) => y[1] - x[1]).slice(0, 2).filter(([, n]) => n >= 2).map(([k]) => k);
  const keuze = vanLex.filter((e) => e.aandacht === "geel").length;
  return [
    `Ik heb artikel 9 lid 1 van de Invorderingswet 1990 geanalyseerd. De annotatie telt ${aantal(els.length, "JAS-element", "JAS-elementen")}: ` +
      `${aantal(vanLex.length, "voorstel", "voorstellen")} van mij en ` +
      `${aantal(els.length - vanLex.length, "markering", "markeringen")} die de jurist al vastlegde.`,
    top.length ? `De markeringen zijn vooral ${top.join(" en ")}.` : "",
    keuze ? `Extra aandacht: ${aantal(keuze, "voorstel", "voorstellen")} met een plausibel alternatief.` : "",
    vanLex.every((e) => e.trace?.beslissing?.door === "model") ? "Alle voorstellen koos het model." : "",
  ].filter(Boolean).join(" ");
}

export const DEMO_SAMENVATTING = demoSamenvatting(maakDemoWeergave());

/** De twee beurten die in de thread staan: een vraag met bronnen, en de annotatie met zijn tijdlijn. */
function maakDemoItems(): ThreadItem[] {
  // De tijdlijn telt uit dezelfde weergave als de samenvatting, het paneel en de graaf.
  const lex = maakDemoWeergave().elementen.filter((e) => e.herkomst === "agent");
  return [
    { id: "demo-1", type: "user", tekst: "Wat betekent het begrip 'belastingschuldige'?" },
    {
      id: "demo-2",
      type: "antwoord",
      // Het citaat is letterlijk artikel 2, eerste lid, onderdeel k (de kennisgraaf van acceptatie, 25 nov 2026), dus de
      // toets slaagt en het blok Brongetrouwheid zwijgt, zoals bij elk goed antwoord.
      tekst:
        "De Invorderingswet 1990 verstaat onder **belastingschuldige** degene te wiens naam de " +
        "belastingaanslag is gesteld (artikel 2, eerste lid, onderdeel k). Het begrip bepaalt wie de " +
        "ontvanger kan aanspreken voor de betaling.\n\n" +
        `_(${DEMO_LABEL}: dit antwoord hoort bij de rondleiding.)_`,
      denk: [
        "· Lex · zoekt de definitie op (0,6 s)",
        "· Graaf · begripsbepaling opgehaald uit artikel 2 van de Invorderingswet 1990 (0,4 s)",
        "· Controle · 1 citaat letterlijk in de opgehaalde tekst (0,1 s)",
      ].join("\n"),
      bronnen: [
        { label: "Invorderingswet 1990, artikel 2", uri: "jci1.3:c:BWBR0004770&artikel=2" },
      ],
      grounding: { niveau: "gegrond", grounded: true, cited: 1, unsupported: [], niet_letterlijk: [] },
    },
    { id: "demo-3", type: "user", tekst: "Annoteer artikel 9 lid 1 van de Invorderingswet 1990" },
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
        `· Bron · artikel 9 lid 1 van de Invorderingswet 1990 (${DEMO_LEDEN.reduce((n, l) => n + l.tekst.length, 0)} tekens)`,
        "· Taalanalyse · nl_core_news_md, 1 zin(nen) (0,4 s)",
        `· Detectie · ${lex.length} kandidaten uit 18 detectoren (0,1 s)`,
        `· Besluit · 0 op vaste regels, ${lex.length} naar het model (0,0 s)`,
        `· Classificatie · ${lex.length} kandidaten in 4 modelaanroep(en) (3,2 s)`,
        "· Review · 1 twijfelgeval(len), 1 naar de reviewer (2,9 s)",
        `· Resultaat · ${lex.length} voorgesteld, ${lex.filter((e) => e.aandacht === "geel").length} ter keuze aan de jurist (0,1 s)`,
        "· Relaties · 1 relatie(s) voorgesteld (0,0 s)",
        `· Klaar · ${lex.length} elementen ter beoordeling`,
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
    { id: "demo-gesprek-1", titel: `${DEMO_LABEL} – Invorderingswet 1990, artikel 9 lid 1`,
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
