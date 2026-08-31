// Validatie op de agentstroom: de grens waar data van buiten de app binnenkomt.
//
// `verwerkSseStroom` in lib/api.ts las de frames met één grote `as`-cast. De scalairen waren al
// defensief (`?? ""`, `?? 0`, `?? []`), maar de gestructureerde payloads gingen ongecontroleerd de
// UI in: een `element` wordt een annotatiekaart, een `doel` draagt bwbId/artikel. Dat is precies de
// plek waar een typefout uit de agent zich als echte inhoud voordoet.
//
// Drie ontwerpregels, en ze zijn belangrijker dan de controles zelf:
//
//  1. EEN ONGELDIG EVENT SLAAT OVER, HET BEËINDIGT DE RUN NIET. Gooien bij één misvormd frame
//     breekt een lopende beurt af en kost de jurist zijn hele antwoord. Overslaan + een
//     console-regel houdt de rest van de stroom intact.
//  2. `lib/types.ts` BLIJFT DE BRON VAN DE VORM. Dat bestand is met de hand afgeleid van
//     api/app/annotatie_contracts.py; deze controles spiegelen het, ze vervangen het niet. Het
//     retourtype van elke parser is het handgeschreven type, dus loopt het uit elkaar, dan faalt
//     `npm run typecheck`.
//  3. MET DE HAND, NIET MET ZOD. Zod stáát in package.json, maar werd tot nu toe nergens
//     geïmporteerd en zat dus niet in de clientbundel. Hem hier gebruiken kostte gemeten
//     235 KB extra op de werkplek-route (1.220 KB → 1.456 KB) — meer dan al het andere dat deze
//     opschoonronde bespaarde. `zod/mini` helpt niet: dat deelt dezelfde core van 83 KB. Voor acht
//     platte vormen is dit goedkoper, en het leest niet slechter.
//
// Velden die de UI toch al defaultte krijgen hier een standaardwaarde in plaats van een harde eis:
// een agent die een leeg lid meestuurt hoort geen markering te verliezen. Wat écht niet mag
// ontbreken (de klasse en de letterlijke tekst van een markering, het bwbId van een doel) is wél
// verplicht — zonder dat valt er niets brongetrouws te tonen.

import type {
  Aandacht,
  AgentDoel,
  AgentKandidaat,
  AgentRun,
  Alternatief,
  Bron,
  CriticRonde,
  OntbrekendItem,
  RunStart,
  VoorstelElement,
} from "./types";

/** Een parser geeft `undefined` als de vorm niet klopt. Nooit gooien: zie ontwerpregel 1. */
type Parser<T> = (waarde: unknown) => T | undefined;

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

/** Verplichte, niet-lege tekst. Ontbreekt hij, dan is het hele event onbruikbaar. */
const eis = (v: unknown): string | undefined =>
  typeof v === "string" && v.trim() !== "" ? v : undefined;

const tekst = (v: unknown, terugval = ""): string => (typeof v === "string" ? v : terugval);
const getal = (v: unknown, terugval = 0): number =>
  typeof v === "number" && Number.isFinite(v) ? v : terugval;
const vlag = (v: unknown, terugval = false): boolean => (typeof v === "boolean" ? v : terugval);
const optioneel = (v: unknown): string | undefined => (typeof v === "string" ? v : undefined);

const AANDACHT: readonly string[] = ["groen", "geel", "rood"];
const aandachtVan = (v: unknown): Aandacht | undefined =>
  typeof v === "string" && AANDACHT.includes(v) ? (v as Aandacht) : undefined;

/** Elk element moet kloppen; sneuvelt er één, dan is de hele lijst verdacht en gaat hij weg. */
function lijst<T>(parser: Parser<T>): Parser<T[]> {
  return (waarde) => {
    if (!Array.isArray(waarde)) return undefined;
    const uit: T[] = [];
    for (const item of waarde) {
      const ontleed = parser(item);
      if (!ontleed) return undefined;
      uit.push(ontleed);
    }
    return uit;
  };
}

export const parseDoel: Parser<AgentDoel> = (v) => {
  if (!isObject(v)) return undefined;
  const bwbId = eis(v.bwbId);
  if (!bwbId) return undefined;
  const leden = Array.isArray(v.leden_teksten)
    ? v.leden_teksten
        .filter(isObject)
        .map((l) => ({ lid: tekst(l.lid), tekst: tekst(l.tekst) }))
    : undefined;
  return {
    bwbId,
    artikel: tekst(v.artikel),
    lid: tekst(v.lid),
    ...(optioneel(v.nummer) !== undefined ? { nummer: optioneel(v.nummer) } : {}),
    ...(optioneel(v.citeertitel) !== undefined ? { citeertitel: optioneel(v.citeertitel) } : {}),
    ...(leden ? { leden_teksten: leden } : {}),
  };
};

const parseAlternatief: Parser<Alternatief> = (v) =>
  isObject(v) ? { klasse: tekst(v.klasse), motivatie: tekst(v.motivatie) } : undefined;

const parseCriticRonde: Parser<CriticRonde> = (v) => {
  if (!isObject(v)) return undefined;
  return {
    ronde: getal(v.ronde),
    aandacht: aandachtVan(v.aandacht) ?? null,
    motivatie: tekst(v.motivatie),
    actie: tekst(v.actie),
    ...(typeof v.toegepast === "boolean" ? { toegepast: v.toegepast } : {}),
    voorstel_klasse: tekst(v.voorstel_klasse),
    voorstel_tekst: tekst(v.voorstel_tekst),
    tijd: tekst(v.tijd),
  };
};

export const parseElement: Parser<VoorstelElement> = (v) => {
  if (!isObject(v)) return undefined;
  // Zonder klasse of letterlijke tekst is er niets brongetrouws te markeren.
  const klasse = eis(v.klasse);
  const inhoud = eis(v.tekst);
  if (!klasse || !inhoud) return undefined;
  const alternatieven =
    v.alternatieven === undefined ? [] : lijst(parseAlternatief)(v.alternatieven);
  if (!alternatieven) return undefined;
  const rondes = v.critic_rondes === undefined ? undefined : lijst(parseCriticRonde)(v.critic_rondes);
  if (v.critic_rondes !== undefined && !rondes) return undefined;
  const aandacht = aandachtVan(v.aandacht);
  return {
    ...(optioneel(v.id) !== undefined ? { id: optioneel(v.id) } : {}),
    klasse,
    tekst: inhoud,
    lid: tekst(v.lid),
    toelichting: tekst(v.toelichting),
    vindplaats: tekst(v.vindplaats),
    alternatieven,
    grounded: vlag(v.grounded),
    ...(aandacht ? { aandacht } : {}),
    ...(optioneel(v.critic) !== undefined ? { critic: optioneel(v.critic) } : {}),
    ...(rondes ? { critic_rondes: rondes } : {}),
  };
};

export const parseRun: Parser<AgentRun> = (v) =>
  isObject(v)
    ? {
        ronde: getal(v.ronde),
        model: tekst(v.model),
        provider: tekst(v.provider),
        agent_versie: tekst(v.agent_versie),
        critic_rondes: getal(v.critic_rondes),
        stop_reden: tekst(v.stop_reden),
        tijd: tekst(v.tijd),
      }
    : undefined;

export const parseBronnen = lijst<Bron>((v) =>
  isObject(v) ? { label: tekst(v.label), uri: tekst(v.uri) } : undefined,
);

export const parseOntbrekend = lijst<OntbrekendItem>((v) => {
  if (!isObject(v)) return undefined;
  const klasse = eis(v.klasse);
  if (!klasse) return undefined;
  return {
    klasse,
    reden: tekst(v.reden),
    ...(optioneel(v.tekst) !== undefined ? { tekst: optioneel(v.tekst) } : {}),
  };
});

export const parseKandidaten = lijst<AgentKandidaat>((v) => {
  if (!isObject(v)) return undefined;
  const bwbId = eis(v.bwbId);
  if (!bwbId) return undefined;
  return {
    bwbId,
    artikel: tekst(v.artikel),
    ...(optioneel(v.lid) !== undefined ? { lid: optioneel(v.lid) } : {}),
    ...(optioneel(v.citeertitel) !== undefined ? { citeertitel: optioneel(v.citeertitel) } : {}),
    ...(optioneel(v.fragment) !== undefined ? { fragment: optioneel(v.fragment) } : {}),
  };
});

export const parseSuggestie: Parser<{ element_id: string; aandacht: string; motivatie: string }> = (
  v,
) => {
  if (!isObject(v)) return undefined;
  const elementId = eis(v.element_id);
  if (!elementId) return undefined;
  return { element_id: elementId, aandacht: tekst(v.aandacht), motivatie: tekst(v.motivatie) };
};

const STATUS: readonly string[] = ["loopt", "klaar", "gestopt", "mislukt"];

export const parseRunStart: Parser<RunStart> = (v) => {
  if (!isObject(v)) return undefined;
  // De run_id stuurt alles wat erna komt: aanhaken, stoppen, idempotent wegschrijven.
  const runId = eis(v.run_id);
  if (!runId || typeof v.status !== "string" || !STATUS.includes(v.status)) return undefined;
  return {
    run_id: runId,
    conversation_id: tekst(v.conversation_id),
    vraag: tekst(v.vraag),
    status: v.status as RunStart["status"],
    volgende_seq: getal(v.volgende_seq),
    weggevallen: getal(v.weggevallen),
  };
};

/** Draai een payload door zijn parser. Faalt hij, dan `undefined` — de aanroeper slaat het over. */
export function geldig<T>(parser: Parser<T>, waarde: unknown, wat: string): T | undefined {
  const uitkomst = parser(waarde);
  if (uitkomst === undefined) {
    // Geen inhoud meeloggen: een agent-payload kan wettekst dragen en die hoort niet in de console.
    console.warn(`Agent-event "${wat}" overgeslagen: vorm klopt niet.`);
  }
  return uitkomst;
}
