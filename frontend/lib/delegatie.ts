// Wat de subagents van een beurt doen (ADR-016 §A5, en de regie van ADR-012): één stand, live uit de stroom en na
// herladen uit de api.
//
// graph-qa stuurt twee events (`agent/subagent.py`, `agent/regie/regisseur.py`):
//  - `regie` met `fase: start` (het plan: per taak titel en profiel; `hervat` als een subagent verdergaat na een
//    antwoord) en `fase: eind` (de uitkomst, de tellingen en bij een subagent de kinderen);
//  - `regie_taak` per kind, bij de start (het deelgesprek, het profiel, het gekozen model) en het eind (de uitkomst,
//    het model waarop hij echt draaide, en wat het rapport zei).
// Na herladen staat de stand bij de delegatie (`/v1/delegaties`); het bericht noemt alleen haar id
// (`Bericht.delegaties`). Zo staat er na herladen de stand van nu: een vraag die de jurist later beantwoordde, staat
// niet meer als open.
//
// Zuiver, zodat vitest het zonder DOM toetst; een ongeldig event laat de stand staan (ontwerpregel 1 van
// `agentEvents.ts`).

import type { Delegatie } from "./types";

/** De stand van één kind. `gepland` is nog niet begonnen; `overgeslagen` kwam niet aan bod (gestopt, het plafond). */
export type TaakStand =
  | "gepland" | "loopt" | "vraag" | "klaar" | "afgesloten" | "niet_gelukt" | "gestopt" | "budget_op" | "mislukt"
  | "overgeslagen";

export interface DelegatieTaak {
  titel: string;
  /** Het profiel van de subagent (`algemeen`, `definitie`, `duiding`); leeg bij een kind van de regie. */
  profiel: string;
  gesprek_id?: string;
  stand: TaakStand;
  /** Het model waarop het kind echt draaide (de laatste aanroep), anders het gekozen model. */
  model?: string;
  /** De afbakening die het kind zelf koos, en de periode (`[van, tot]`), als het rapport ze noemt. */
  afbakening?: string[];
  periode?: number[];
  /** Hoeveel vragen van dit kind Lex zelf uit het dossier beantwoordde (`zelf_beantwoord` op de kindregel). */
  zelfBeantwoord?: number;
}

export interface DelegatieVoortgang {
  regie_id: string;
  soort: "subagent" | "regie";
  /** Een subagent die verdergaat na een antwoord van de jurist (§A4). */
  hervat: boolean;
  /** Het eind-event kwam (live), of de delegatie staat in een eindstand of wacht (api). */
  afgerond: boolean;
  /** De stand van de delegatie zelf: `loopt`, `wacht`, `klaar`, `gestopt` of `mislukt`. */
  status: Delegatie["status"];
  taken: DelegatieTaak[];
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const tekst = (v: unknown): string => (typeof v === "string" ? v : "");
const teksten = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);
const getallen = (v: unknown): number[] =>
  Array.isArray(v) ? v.filter((x): x is number => typeof x === "number" && Number.isFinite(x)).slice(0, 2) : [];

const STANDEN: readonly string[] = ["gepland", "loopt", "vraag", "klaar", "afgesloten", "niet_gelukt", "gestopt",
  "budget_op", "mislukt", "overgeslagen"];
const STATUSSEN: readonly string[] = ["loopt", "wacht", "klaar", "gestopt", "mislukt"];

/** Wat een bericht over de delegaties van zijn beurt weet: hun id's (live uit de stroom, na herladen van het bericht) en,
 *  zolang de beurt loopt, de stand uit de stroom. Daarna haalt de werkplek de stand bij de api. */
export interface DelegatieWeergave {
  ids: string[];
  live?: DelegatieVoortgang[];
}

/** De weergave uit de stroom; leeg als de beurt niets delegeerde. */
export function weergaveUitStroom(live: DelegatieVoortgang[]): DelegatieWeergave | undefined {
  return live.length ? { ids: live.map((d) => d.regie_id), live } : undefined;
}

/** De weergave van een bewaard bericht; leeg zonder id's. */
export function weergaveUitBericht(ids: unknown): DelegatieWeergave | undefined {
  const lijst = Array.isArray(ids) ? ids.filter((x): x is string => typeof x === "string" && x !== "") : [];
  return lijst.length ? { ids: lijst } : undefined;
}

/** Wat het blok toont: zolang de beurt loopt de stroom, daarna de api, met de stroom als terugval voor een delegatie die
 *  de api (nog) niet gaf. In de volgorde van de id's. */
export function teTonen(w: DelegatieWeergave, api: Delegatie[] | null, loopt: boolean): DelegatieVoortgang[] {
  const live = new Map((w.live ?? []).map((d) => [d.regie_id, d]));
  const bijApi = new Map((api ?? []).map((d) => [d.id, d]));
  return w.ids.flatMap((id) => {
    const l = live.get(id);
    if (loopt && l) return [l];
    const a = bijApi.get(id);
    return a ? [voortgangUitDelegatie(a)] : l ? [l] : [];
  });
}

/** Uitkomsten van graph-qa die hier anders heten. `niet_gestart` is de beginwaarde van een `Afloop`: het kind kwam niet aan
 *  bod (het plafond van het plan, een stop), dus "niet aan bod", geen fout (bugonderzoek ADR-016, B3). */
const UITKOMST_ALS: Record<string, TaakStand> = { niet_gestart: "overgeslagen" };

/** De uitkomst van een kind als stand. Een onbekende uitkomst is `mislukt`: dat zei graph-qa ook (`eindstand`), en een
 *  label dat een fout verzwijgt is erger dan een te streng label. Een kind van de regie draagt de uitkomst van zijn run
 *  (`klaar`, `gestopt`, `mislukt`). */
export function standVan(uitkomst: unknown): TaakStand {
  const u = tekst(uitkomst);
  if (!u) return "loopt";
  if (UITKOMST_ALS[u]) return UITKOMST_ALS[u];
  if (STANDEN.includes(u)) return u as TaakStand;
  console.warn(`Onbekende uitkomst van een subagent: ${u}`);
  return "mislukt";
}

function taakUit(v: unknown): DelegatieTaak | undefined {
  if (!isObject(v)) return undefined;
  return { titel: tekst(v.titel) || "Deelopdracht", profiel: tekst(v.profiel), stand: "gepland" };
}

/** De extra's uit het eind van een kind: het model, de afbakening en de periode. */
function extraVan(v: Record<string, unknown>): Partial<DelegatieTaak> {
  const modellen = teksten(v.modellen);
  const model = tekst(v.model) || modellen[modellen.length - 1] || "";
  const rapport = isObject(v.rapport) ? v.rapport : v;
  const afbakening = teksten(rapport.afbakening);
  const periode = getallen(rapport.periode);
  const zelf = Array.isArray(v.zelf_beantwoord) ? v.zelf_beantwoord.filter(isObject).length : 0;
  return {
    ...(zelf ? { zelfBeantwoord: zelf } : {}),
    ...(model ? { model } : {}),
    ...(afbakening.length ? { afbakening } : {}),
    ...(periode.length ? { periode } : {}),
  };
}

/** Verwerk één `regie`- of `regie_taak`-event. Geeft `undefined` als het event niet klopt: de stand blijft dan staan. */
export function verwerkDelegatieEvent(lijst: DelegatieVoortgang[], ev: unknown): DelegatieVoortgang[] | undefined {
  if (!isObject(ev) || (ev.type !== "regie" && ev.type !== "regie_taak")) return undefined;
  const id = tekst(ev.regie_id);
  if (!id) return undefined;
  const plek = lijst.findIndex((d) => d.regie_id === id);
  const oud = plek >= 0 ? lijst[plek] : undefined;
  const zet = (d: DelegatieVoortgang) =>
    plek >= 0 ? lijst.map((x, i) => (i === plek ? d : x)) : [...lijst, d];

  if (ev.type === "regie") {
    if (ev.fase === "start") {
      const plan = isObject(ev.plan) ? ev.plan : {};
      const taken = (Array.isArray(plan.taken) ? plan.taken : []).map(taakUit).filter((t): t is DelegatieTaak => !!t);
      // Een herhaald start-event (het opnieuw verbinden speelt de log vanaf het begin) laat wat er al stond staan.
      if (oud && !oud.afgerond) return lijst;
      return zet({ regie_id: id, soort: ev.soort === "subagent" ? "subagent" : "regie", hervat: ev.hervat === true,
        afgerond: false, status: "loopt", taken });
    }
    if (ev.fase !== "eind" || !oud) return undefined;
    const status = STATUSSEN.includes(tekst(ev.uitkomst)) ? (tekst(ev.uitkomst) as Delegatie["status"]) : "klaar";
    const kinderen = Array.isArray(ev.kinderen) ? ev.kinderen.filter(isObject) : [];
    const taken = oud.taken.map((t, i) => {
      // Per deelgesprek, en anders op de plek in het plan; bij het hervatten noemt het eind alle kinderen van de
      // delegatie en het begin alleen het hervatte.
      const kind = kinderen.find((k) => t.gesprek_id && k.gesprek_id === t.gesprek_id) ?? (oud.hervat ? undefined : kinderen[i]);
      if (kind) return { ...t, stand: standVan(kind.uitkomst), ...(tekst(kind.gesprek_id) ? { gesprek_id: tekst(kind.gesprek_id) } : {}),
        ...extraVan(kind) };
      return t.stand === "gepland" || t.stand === "loopt" ? { ...t, stand: "overgeslagen" as const } : t;
    });
    return zet({ ...oud, afgerond: true, status, taken });
  }

  // `regie_taak`: één kind.
  if (!oud) return undefined;
  const index = typeof ev.index === "number" && Number.isInteger(ev.index) && ev.index >= 0 ? ev.index : 0;
  const taken = [...oud.taken];
  while (taken.length <= index) taken.push({ titel: "Deelopdracht", profiel: "", stand: "gepland" });
  const huidig = taken[index];
  const basis: DelegatieTaak = {
    ...huidig,
    ...(tekst(ev.titel) ? { titel: tekst(ev.titel) } : {}),
    ...(tekst(ev.profiel) ? { profiel: tekst(ev.profiel) } : {}),
    ...(tekst(ev.gesprek_id) ? { gesprek_id: tekst(ev.gesprek_id) } : {}),
  };
  if (ev.fase === "start") {
    taken[index] = { ...basis, stand: "loopt", ...(tekst(ev.gekozen_model) && !basis.model ? { model: tekst(ev.gekozen_model) } : {}) };
  } else if (ev.fase === "eind") {
    taken[index] = { ...basis, stand: standVan(ev.uitkomst), ...extraVan(ev) };
  } else {
    return undefined;
  }
  return zet({ ...oud, taken });
}

/** Een delegatie van de api als stand. Een subagent draagt per kind zijn afloop (`uitkomst.kinderen`, in de volgorde van
 *  het plan); een regie alleen tellingen, dus daar volgt elk kind de stand van de regie. */
export function voortgangUitDelegatie(d: Delegatie): DelegatieVoortgang {
  const plan = isObject(d.plan) ? d.plan : {};
  const kinderen = Array.isArray(d.uitkomst?.kinderen) ? (d.uitkomst.kinderen as unknown[]).filter(isObject) : [];
  const status = STATUSSEN.includes(d.status) ? d.status : "mislukt";
  const taken = (Array.isArray(plan.taken) ? plan.taken : []).map(taakUit).filter((t): t is DelegatieTaak => !!t)
    .map((t, i): DelegatieTaak => {
      const kind = kinderen[i];
      if (kind) return { ...t, stand: standVan(kind.uitkomst),
        ...(tekst(kind.gesprek_id) ? { gesprek_id: tekst(kind.gesprek_id) } : {}), ...extraVan(kind) };
      // Nog geen afloop: een wachtende delegatie zonder kinderen wacht op de bevestiging (§A5); een lopende is bezig.
      const stand: TaakStand = status === "loopt" ? (d.soort === "subagent" && i > 0 ? "gepland" : "loopt")
        : status === "wacht" ? "gepland" : d.soort === "regie" ? status : "overgeslagen";
      return { ...t, stand };
    });
  return { regie_id: d.id, soort: d.soort === "subagent" ? "subagent" : "regie", hervat: false,
    afgerond: status !== "loopt", status, taken };
}

/** De tekst bij een stand, voor het blok en de sidebar. */
export const STAND_TEKST: Record<TaakStand, string> = {
  gepland: "gepland",
  loopt: "loopt",
  vraag: "wacht op antwoord",
  klaar: "klaar",
  afgesloten: "afgesloten",
  niet_gelukt: "niet gelukt",
  gestopt: "gestopt",
  budget_op: "budget op",
  mislukt: "mislukt",
  overgeslagen: "niet aan bod",
};

/** De toon van het label: groen is af, geel vraagt iets van de jurist, rood ging mis; grijs zegt niets. */
export function standToon(stand: TaakStand): "groen" | "geel" | "rood" | "neutraal" | "lint" {
  switch (stand) {
    case "klaar": return "groen";
    case "vraag": return "geel";
    case "loopt": return "lint";
    case "mislukt": case "budget_op": case "niet_gelukt": return "rood";
    default: return "neutraal";
  }
}

/** De kop van het blok: wat er loopt, en de tellingen per stand ("2 subagents · 1 klaar · 1 wacht op antwoord"). */
export function delegatieSamenvatting(d: DelegatieVoortgang): string {
  const n = d.taken.length;
  const wie = d.soort === "regie" ? (n === 1 ? "deelgesprek" : "deelgesprekken") : (n === 1 ? "subagent" : "subagents");
  const tel = new Map<TaakStand, number>();
  for (const t of d.taken) tel.set(t.stand, (tel.get(t.stand) ?? 0) + 1);
  const delen = [...tel.entries()].map(([s, aantal]) => `${aantal} ${STAND_TEKST[s]}`);
  return [`${n} ${wie}`, ...delen].join(" · ");
}

/** De metaregel van één kind: profiel, model, afbakening en periode. */
export function taakMeta(t: DelegatieTaak): string {
  return [
    t.profiel ? `subagent ${t.profiel}` : "",
    t.model ?? "",
    t.afbakening?.length ? `afbakening: ${t.afbakening.join(", ")}` : "",
    t.periode?.length ? `periode ${t.periode.join("–")}` : "",
    t.zelfBeantwoord ? `${t.zelfBeantwoord} ${t.zelfBeantwoord === 1 ? "vraag" : "vragen"} door Lex beantwoord uit het dossier` : "",
  ].filter(Boolean).join(" · ");
}

/** Per deelgesprek de stand, uit de delegaties van één of meer oudergesprekken: voor de sidebar. Een deelgesprek dat in
 *  meer delegaties voorkomt (hervatten), krijgt de stand van de nieuwste; de api levert ze nieuwste eerst. */
export function standenPerDeelgesprek(delegaties: Delegatie[]): Record<string, TaakStand> {
  const uit: Record<string, TaakStand> = {};
  for (const d of delegaties) {
    for (const t of voortgangUitDelegatie(d).taken) {
      if (t.gesprek_id && !(t.gesprek_id in uit)) uit[t.gesprek_id] = t.stand;
    }
  }
  return uit;
}

/** Een regie-kind heeft geen afloop per deelgesprek bij de api: de sidebar toont dan de stand van de regie op elk
 *  deelgesprek dat haar `delegatie_id` draagt. */
export function standVanDeelgesprek(
  g: { id: string; delegatie_id?: string }, perGesprek: Record<string, TaakStand>, delegaties: Delegatie[],
): TaakStand | undefined {
  if (perGesprek[g.id]) return perGesprek[g.id];
  const d = g.delegatie_id ? delegaties.find((x) => x.id === g.delegatie_id) : undefined;
  if (!d || d.soort !== "regie") return undefined;
  return d.status === "wacht" ? "gepland" : (d.status as TaakStand);
}

/** Alleen wat klopt uit de lijst van de api: een rare rij breekt het scherm niet. */
export function parseDelegaties(body: unknown): Delegatie[] {
  if (!Array.isArray(body)) return [];
  return body.filter((d): d is Delegatie => isObject(d) && typeof d.id === "string" && typeof d.gesprek_id === "string"
    && typeof d.status === "string" && STATUSSEN.includes(d.status))
    .map((d) => ({ ...d, plan: isObject(d.plan) ? d.plan : {}, uitkomst: isObject(d.uitkomst) ? d.uitkomst : {} }));
}
