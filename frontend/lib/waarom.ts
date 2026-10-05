import type { LaagGraafcontrole } from "./annotatieNode";
import type { AgentRun, AnnotatieElement, Beslissing, BeurtMeting, ElementTrace } from "./types";
import { verklaar, type Verklaringen } from "./verklaringen";

/** Eén regel in de Waarom-uitklap: een leesbare naam, met de code in de tooltip. */
export interface WaaromRegel { naam: string; code: string; uitleg: string; detail?: string }

/** Waarom een element er staat, als weergavemodel. Alles komt uit het spoor dat de annotatieketen
 *  meegaf (`trace`) en uit de beslissingen van juristen; hier wordt niets afgeleid dat er niet staat. */
export interface WaaromModel {
  /** Geen spoor: een markering van de jurist zelf (of van vóór het spoor). */
  handmatig: boolean;
  /** Wie in de keten besliste: vaste regel, model of specificiteit. */
  besluit?: WaaromRegel;
  /** De laatste inhoudelijke beslissing van een jurist, in gewone taal. */
  jurist?: string;
  bewijs: WaaromRegel[];
  twijfel: WaaromRegel[];
  resolutie: WaaromRegel[];
  validatie: WaaromRegel[];
  subtype?: string;
  gedegradeerd: boolean;
  /** De exacte regel die het model zag; leeg als er geen model aan te pas kwam. */
  vraag: string;
  trace?: ElementTrace;
}

/** Wat een element nodig heeft voor de uitklap; zowel het paneelmodel als het ruwe v2-element passen. */
export type WaaromBron = Pick<AnnotatieElement, "herkomst" | "trace" | "jas_subtype"> & { beslissingen?: Beslissing[]; id?: string };

const JURIST: Partial<Record<Beslissing["type"], string>> = {
  approve: "akkoord bevonden", edit: "aangepast", reject: "verworpen", heropen: "heropend", grens: "andere grens gekozen",
};

/** Bewijs met een regel-id toont de regel; anders de detectiecode. Dezelfde naam twee keer (twee
 *  detectoren die hetzelfde zagen) staat er één keer, met de details samen. */
function bewijsRegels(trace: ElementTrace, v?: Verklaringen): WaaromRegel[] {
  const uit = new Map<string, WaaromRegel>();
  for (const b of trace.kandidaat?.bewijs ?? []) {
    if (b.code === "PRIORITY_APPLIED") continue;  // administratief: zegt niets over de klasse
    const r = b.regel ? verklaar(v, "regels", b.regel) : verklaar(v, "detectie", b.code);
    const bestaand = uit.get(r.code);
    if (bestaand) {
      if (b.detail && !bestaand.detail?.includes(b.detail)) bestaand.detail = [bestaand.detail, b.detail].filter(Boolean).join("; ");
    } else {
      uit.set(r.code, { naam: r.naam, code: r.code, uitleg: r.uitleg, ...(b.detail ? { detail: b.detail } : {}) });
    }
  }
  return [...uit.values()];
}

export function laatsteJuristBeslissing(beslissingen: Beslissing[] = []): string | undefined {
  const b = [...beslissingen].reverse().find((x) => JURIST[x.type]);
  if (!b) return;
  const tijd = b.tijd ? new Date(b.tijd).toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" }) : "";
  return `${JURIST[b.type]} door ${b.actor}${tijd ? ` op ${tijd}` : ""}`;
}

export function waaromVan(el: WaaromBron, v?: Verklaringen): WaaromModel {
  const trace = el.trace && Object.keys(el.trace).length ? el.trace : undefined;
  const jurist = laatsteJuristBeslissing(el.beslissingen);
  if (!trace) return { handmatig: true, jurist, bewijs: [], twijfel: [], resolutie: [], validatie: [], gedegradeerd: false, vraag: "", subtype: el.jas_subtype || undefined };

  const door = trace.beslissing?.door;
  let besluit: WaaromRegel | undefined;
  if (door) {
    const b = verklaar(v, "besluit", door);
    // Bij specificiteit is de reden het id van de voorrangsregel die besliste.
    const regel = door === "specificiteit" && trace.beslissing?.reden ? verklaar(v, "regels", trace.beslissing.reden) : undefined;
    besluit = { naam: b.naam, code: b.code, uitleg: regel ? regel.uitleg || b.uitleg : b.uitleg, ...(regel ? { detail: regel.naam } : {}) };
  }
  return {
    handmatig: false,
    besluit,
    jurist,
    bewijs: bewijsRegels(trace, v),
    twijfel: (trace.twijfel ?? []).map((t) => ({ ...verklaar(v, "twijfel", t.reden), ...(t.detail ? { detail: t.detail } : {}) })),
    resolutie: (trace.resolutie ?? []).map((r) => ({ ...verklaar(v, "resolutie", r.regel), ...(r.motivering ? { detail: r.motivering } : {}) })),
    validatie: (trace.validatie ?? []).map((x) => ({ ...verklaar(v, "validatie", x.code), ...(x.detail ? { detail: x.detail } : {}) })),
    subtype: el.jas_subtype || undefined,
    gedegradeerd: !!trace.kandidaat?.gedegradeerd,
    vraag: trace.vraag ?? "",
    trace,
  };
}

/** Waarom een alternatieve klasse op tafel ligt. De keten geeft elk alternatief dezelfde vaste
 *  motivatie mee; de twijfel in het spoor zegt het preciezer, dus die gaat voor. */
export function redenVoorAlternatief(el: WaaromBron, klasse: string, motivatie: string, v?: Verklaringen): string {
  const t = el.trace?.twijfel?.find((x) => x.alternatieven?.includes(klasse));
  if (!t) return motivatie;
  const r = verklaar(v, "twijfel", t.reden);
  return r.uitleg ? `${r.naam}: ${r.uitleg}` : r.naam;
}

/** De laatste agent-ronde onder deze elementen (een document kan er meer dragen: hergebruik, een
 *  aanvulling). Op tijd, want de volgorde van de elementen zegt daar niets over. */
export function laatsteRun(elementen: Pick<AnnotatieElement, "geproduceerd_door">[]): AgentRun | undefined {
  let laatste: AgentRun | undefined;
  for (const e of elementen) {
    const r = e.geproduceerd_door;
    if (r && (!laatste || (r.tijd ?? "") > (laatste.tijd ?? ""))) laatste = r;
  }
  return laatste;
}

function seconden(ms: number): string {
  return `${(ms / 1000).toLocaleString("nl-NL", { maximumFractionDigits: 1, minimumFractionDigits: ms < 10000 ? 1 : 0 })} s`;
}

/** Eén regel over de beurt: wat er uitkwam, wat zonder zinsontleding ging en hoe lang het duurde.
 *  Leeg zonder meting – dan is er niets te melden en hoort er ook geen regel te staan. */
export function beurtSamenvatting(meting?: BeurtMeting): string {
  const fasen = meting?.fasen ?? [];
  if (!fasen.length) return "";
  const resultaat = fasen.find((f) => f.fase === "Resultaat")?.samenvatting;
  const gedegradeerd = meting?.gedegradeerd?.length ?? 0;
  const duur = fasen.reduce((s, f) => s + (f.ms || 0), 0);
  return [
    resultaat,
    gedegradeerd ? `${gedegradeerd} ${gedegradeerd === 1 ? "bronnode" : "bronnodes"} zonder zinsontleding` : "",
    duur ? seconden(duur) : "",
  ].filter(Boolean).join(" · ");
}

/** De graafcontrole van een laag in gewone taal. Alleen een echte afwijking vraagt aandacht; een
 *  achterstand haalt de api zelf in, en een onbereikbare graaf is geen oordeel over de annotatie. */
export function graafStatusTekst(gc: LaagGraafcontrole): { tekst: string; ernst: "goed" | "neutraal" | "aandacht" } {
  const shacl = gc.shacl && gc.shacl.beschikbaar && !gc.shacl.conform ? gc.shacl.aantal : 0;
  switch (gc.status) {
    case "in_orde": return { tekst: "De graaf klopt met de database (revisie " + gc.revisie + ").", ernst: "goed" };
    case "achterstand": return { tekst: "Nog niet in de graaf bijgewerkt; de api haalt dat zelf in.", ernst: "neutraal" };
    case "onbeschikbaar": return { tekst: "De kennisgraaf is nu niet bereikbaar – geen oordeel.", ernst: "neutraal" };
    case "uit": return { tekst: "Deze omgeving projecteert niet naar de kennisgraaf.", ernst: "neutraal" };
    default: {
      const delen = [gc.afwijkingen.length ? `${gc.afwijkingen.length} ${gc.afwijkingen.length === 1 ? "afwijking" : "afwijkingen"}` : "",
        shacl ? `${shacl} SHACL-${shacl === 1 ? "bevinding" : "bevindingen"}` : ""].filter(Boolean);
      return { tekst: `De graaf wijkt af van de database: ${delen.join(", ") || "zie de beheercontrole"}.`, ernst: "aandacht" };
    }
  }
}
