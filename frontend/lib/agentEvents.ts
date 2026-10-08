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
//     de api-contracten; deze controles spiegelen het, ze vervangen het niet. Het
//     retourtype van elke parser is het handgeschreven type, dus loopt het uit elkaar, dan faalt
//     `npm run typecheck`.
//  3. MET DE HAND, NIET MET ZOD. Zod stáát in package.json, maar wordt nergens in de
//     clientcode geïmporteerd en zit dus niet in de clientbundel. Hem hier gebruiken kost gemeten
//     235 KB extra op de werkplek-route (1.220 KB → 1.456 KB). `zod/mini` helpt niet: dat deelt dezelfde core van 83 KB. Voor acht
//     platte vormen is dit goedkoper, en het leest niet slechter.
//
// Velden die de UI toch al defaultte krijgen hier een standaardwaarde in plaats van een harde eis:
// een agent die een leeg lid meestuurt hoort geen markering te verliezen. Wat écht niet mag
// ontbreken (de klasse en de letterlijke tekst van een markering, het bwbId van een doel) is wél
// verplicht — zonder dat valt er niets brongetrouws te tonen.

import type {
  Aandacht,
  AgentDoel,
  AgentHergebruik,
  AgentKandidaat,
  AgentKeuze,
  AgentRun,
  KandidaatStand,
  Alternatief,
  Bron,
  Overzicht,
  OverzichtBepaling,
  OverzichtDeel,
  OverzichtRegeling,
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
    ...(typeof v.bron_iri === "string" ? { bron_iri: v.bron_iri } : {}),
    ...(typeof v.snapshot_id === "string" ? { snapshot_id: v.snapshot_id } : {}),
    ...(typeof v.label === "string" ? { label: v.label } : {}),
    artikel: tekst(v.artikel),
    lid: tekst(v.lid),
    ...(optioneel(v.nummer) !== undefined ? { nummer: optioneel(v.nummer) } : {}),
    ...(optioneel(v.citeertitel) !== undefined ? { citeertitel: optioneel(v.citeertitel) } : {}),
    ...(leden ? { leden_teksten: leden } : {}),
  };
};

const parseAlternatief: Parser<Alternatief> = (v) =>
  isObject(v) ? { klasse: tekst(v.klasse), motivatie: tekst(v.motivatie) } : undefined;

export const parseElement: Parser<VoorstelElement> = (v) => {
  if (!isObject(v)) return undefined;
  // Zonder letterlijke tekst is er niets brongetrouws te markeren. Zonder klasse alleen als het een
  // vraag is: een terugval draagt geen klasse maar wel de klassen waaruit de jurist kiest.
  const klasse = tekst(v.klasse);
  const inhoud = eis(v.tekst);
  const alternatieven =
    v.alternatieven === undefined ? [] : lijst(parseAlternatief)(v.alternatieven);
  if (!inhoud || !alternatieven || (!klasse && !alternatieven.length)) return undefined;
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
    ...(optioneel(v.review_uitleg) !== undefined ? { review_uitleg: optioneel(v.review_uitleg) } : {}),
  };
};

export const parseRun: Parser<AgentRun> = (v) =>
  isObject(v)
    ? {
        ronde: getal(v.ronde),
        model: tekst(v.model),
        provider: tekst(v.provider),
        agent_versie: tekst(v.agent_versie),
        stop_reden: tekst(v.stop_reden),
        tijd: tekst(v.tijd),
      }
    : undefined;

export const parseBronnen = lijst<Bron>((v) =>
  isObject(v) ? { label: tekst(v.label), uri: tekst(v.uri) } : undefined,
);

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
    ...(eis(v.bron_iri) ? { bron_iri: eis(v.bron_iri) } : {}),
    ...(optioneel(v.nummer) !== undefined ? { nummer: optioneel(v.nummer) } : {}),
    ...(optioneel(v.soort) !== undefined ? { soort: optioneel(v.soort) } : {}),
    ...(optioneel(v.label) !== undefined ? { label: optioneel(v.label) } : {}),
    ...(parseStand(v.stand) ? { stand: parseStand(v.stand) } : {}),
    ...(v.gekozen === true ? { gekozen: true } : {}),
  };
});

const STANDEN: readonly string[] = ["nieuw", "te_beoordelen", "beoordeeld", "afgerond"];

/** De stand van een onderdeel. Een onbekende status is geen stand: liever geen badge dan een
 *  verkeerde. */
export const parseStand: Parser<KandidaatStand> = (v) =>
  isObject(v) && typeof v.status === "string" && STANDEN.includes(v.status)
    ? { status: v.status as KandidaatStand["status"], voorstellen: getal(v.voorstellen),
        te_beoordelen: getal(v.te_beoordelen) }
    : undefined;

/** Wat voor keuze de kandidaten vormen. Ontbreekt of onbekend → `undefined`: dan is het de
 *  bestaande onderwerpkeuze, en dat is het veilige gedrag. */
export const parseKeuze: Parser<AgentKeuze> = (v) =>
  isObject(v) && (v.soort === "onderdeel" || v.soort === "bepaling")
    ? { soort: v.soort, ouder: tekst(v.ouder), alles: vlag(v.alles) }
    : undefined;

/** Een bron-IRI uit de graaf. Een overzicht zonder geldige IRI kan niet naar zijn bron wijzen: dan
 *  is die rij onbruikbaar en het hele overzicht verdacht (zie `lijst`). */
const bronIri = (v: unknown): string | undefined =>
  typeof v === "string" && /^urn:bwb:BWB[RV]\d+(?::[A-Za-z0-9._~%-]+)*$/.test(v) ? v : undefined;

const parseDeelVerwijzing: Parser<{ iri: string; label: string }> = (v) => {
  if (!isObject(v)) return undefined;
  const iri = bronIri(v.iri);
  return iri ? { iri, label: tekst(v.label) } : undefined;
};

const parseOverzichtBepaling: Parser<OverzichtBepaling> = (v) => {
  if (!isObject(v)) return undefined;
  const iri = bronIri(v.iri);
  if (!iri) return undefined;
  const inDeel = v.in_deel === undefined ? undefined : parseDeelVerwijzing(v.in_deel);
  return { iri, nummer: tekst(v.nummer), label: tekst(v.label),
    ...(optioneel(v.jci) ? { jci: tekst(v.jci) } : {}), ...(inDeel ? { in_deel: inDeel } : {}) };
};

const parseOverzichtDeel: Parser<OverzichtDeel> = (v) => {
  if (!isObject(v)) return undefined;
  const iri = bronIri(v.iri);
  const bepalingen = lijst(parseOverzichtBepaling)(v.bepalingen ?? []);
  const subdelen = lijst(parseDeelVerwijzing)(v.subdelen ?? []);
  if (!iri || !bepalingen || !subdelen) return undefined;
  return { iri, soort: tekst(v.soort), label: tekst(v.label), jci: tekst(v.jci), bepalingen, subdelen };
};

const parseOverzichtRegeling: Parser<OverzichtRegeling> = (v) => {
  if (!isObject(v)) return undefined;
  const bwb = eis(v.bwb_id);
  const delen = lijst(parseOverzichtDeel)(v.delen ?? []);
  const ook = lijst(parseOverzichtBepaling)(v.ook_genoemd ?? []);
  if (!bwb || !delen || !ook) return undefined;
  return { bwb_id: bwb, citeertitel: tekst(v.citeertitel, bwb), soort: tekst(v.soort), delen, ook_genoemd: ook };
};

/** Het overzicht van een onderwerp (`overzicht`-event of `Bericht.overzicht`). Klopt één regeling
 *  niet, dan geen overzicht: een blok met gaten zou zich als volledig voordoen. */
export const parseOverzicht: Parser<Overzicht> = (v) => {
  if (!isObject(v)) return undefined;
  const regelingen = lijst(parseOverzichtRegeling)(v.regelingen);
  if (!regelingen) return undefined;
  const definities = Array.isArray(v.definities)
    ? v.definities.filter(isObject).flatMap((d) => {
        const iri = bronIri(d.iri);
        return iri ? [{ iri, begrip: tekst(d.begrip), label: tekst(d.label), tekst: tekst(d.tekst), jci: tekst(d.jci),
                        bwb_id: tekst(d.bwb_id), citeertitel: tekst(d.citeertitel) }] : [];
      })
    : [];
  const trefwoorden = Array.isArray(v.trefwoorden)
    ? v.trefwoorden.filter(isObject).map((t) => ({
        trefwoord: tekst(t.trefwoord),
        regelingen: Array.isArray(t.regelingen)
          ? t.regelingen.filter(isObject).map((r) => ({ bwb_id: tekst(r.bwb_id), citeertitel: tekst(r.citeertitel) }))
          : [],
      }))
    : [];
  const gevraagd = tekst(v.gevraagd, tekst(v.onderwerp));
  return {
    gevraagd,
    onderwerp_opbouw: tekst(v.onderwerp_opbouw, gevraagd),
    onderwerp_tekst: tekst(v.onderwerp_tekst, gevraagd),
    scope: Array.isArray(v.scope) ? v.scope.filter((x): x is string => typeof x === "string") : [],
    volledig: vlag(v.volledig, true),
    definities, trefwoorden, regelingen,
  };
};

/** Lex hergebruikte (een deel van) de gedeelde laag. De leden komen als `{lid, hash, iri}` binnen;
 *  voor de werkplek telt alleen welk lid. Zonder slug is het event onbruikbaar: dan is er niets om
 *  naar te wijzen. */
export const parseHergebruik: Parser<AgentHergebruik> = (v) => {
  if (!isObject(v)) return undefined;
  const slug = eis(v.slug);
  if (!slug) return undefined;
  const leden = Array.isArray(v.leden)
    ? v.leden.map((l) => (isObject(l) ? tekst(l.lid) : tekst(l)))
    : [];
  const t = isObject(v.telling) ? v.telling : {};
  return {
    slug,
    leden,
    volledig: vlag(v.volledig),
    bijgewerkt: tekst(v.bijgewerkt),
    telling: {
      markeringen: getal(t.markeringen),
      beoordeeld: getal(t.beoordeeld),
      afgewezen: getal(t.afgewezen),
      te_beoordelen: getal(t.te_beoordelen),
    },
  };
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
