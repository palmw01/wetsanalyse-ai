/**
 * De ruimte van een testrun op acceptatie (Lex Bench §20.5 stap 5, testplan keten-e2e voorstel 3; bevinding O-1).
 *
 * Een run van de E2E of Lex Bench maakt werkgebieden en gesprekken op acceptatie. Daar werkt ook de gebruiker, en het
 * account kan gedeeld zijn: op 10 nov 2026 raakte een bulkverwijdering een meting en een gesprek van de gebruiker. Twee
 * regels houden dat voortaan tegen:
 *
 * - **Een naamconventie.** Wat een run maakt, begint met een runvoorvoegsel (`acc-test-…` of `Bench …`).
 * - **Verwijderen alleen in de eigen ruimte.** Een verwijderende aanroep via `bff` mag alleen op een gesprek of
 *   werkgebied met dat voorvoegsel, en een werkgebied alleen als dit account het maakte. Een bulkroute en alles wat
 *   gedeeld is (een annotatielaag, een generiek begrip, het beheer) weigert de vangrail altijd.
 *
 * `opruimen` (O-1) zoekt per run wat de run maakte, ook gesprekken in een werkgebied en deelgesprekken onder een ouder,
 * en wist pas met `bevestig: true`. Zonder bevestiging geeft hij alleen de lijst.
 */
import type { BffAntwoord } from "./client.js";

/** Waarmee de naam van iets wat een run maakte, begint. */
export const VOORVOEGSELS = ["acc-test-", "Bench "] as const;

export interface Bff {
  bff(methode: string, pad: string, body?: unknown): Promise<BffAntwoord>;
}

export const inRunruimte = (naam: unknown): boolean =>
  typeof naam === "string" && VOORVOEGSELS.some((v) => naam.startsWith(v));

/** Of een aanroep iets verwijdert of wist: een DELETE, of een route die op verwijderen of wissen eindigt. */
export function isVerwijderend(methode: string, pad: string): boolean {
  const zonderQuery = pad.split("?")[0];
  return methode.toUpperCase() === "DELETE" || /\/(verwijder|wis|wissen|verwijderen)$/.test(zonderQuery);
}

export interface Oordeel {
  mag: boolean;
  reden: string;
}

const NEE = (reden: string): Oordeel => ({ mag: false, reden });
const JA: Oordeel = { mag: true, reden: "" };

const BULK = new Set(["groep", "verwijderen", "archiveren"]);

/** Hoort dit gesprek bij een testrun? De titel heeft het voorvoegsel, of het hangt in een werkgebied of onder een
 *  ouder die bij de run hoort. Gesprekken zijn per gebruiker gescopet, dus een gesprek van een ander is hier niet te
 *  lezen. */
async function gesprekInRunruimte(c: Bff, id: string, ik: string, diepte = 0): Promise<Oordeel> {
  const g = await c.bff("GET", `/api/gesprekken/${encodeURIComponent(id)}`);
  if (g.status !== 200) return NEE(`Het gesprek is niet te lezen (status ${g.status}); verwijderen kan alleen na controle.`);
  const gesprek = (g.data ?? {}) as { titel?: unknown; werkgebied_id?: unknown; ouder_id?: unknown };
  if (inRunruimte(gesprek.titel)) return JA;
  if (typeof gesprek.werkgebied_id === "string" && gesprek.werkgebied_id) {
    const w = await werkgebiedInRunruimte(c, gesprek.werkgebied_id, ik);
    if (w.mag) return JA;
  }
  if (typeof gesprek.ouder_id === "string" && gesprek.ouder_id && diepte < 5) {
    const o = await gesprekInRunruimte(c, gesprek.ouder_id, ik, diepte + 1);
    if (o.mag) return JA;
  }
  return NEE(`Dit gesprek ("${String(gesprek.titel)}") hoort niet bij een testrun: de titel begint niet met `
    + `${VOORVOEGSELS.join(" of ")}, en het hangt niet in een werkgebied of onder een gesprek van een run.`);
}

async function werkgebiedInRunruimte(c: Bff, id: string, ik: string): Promise<Oordeel> {
  const w = await c.bff("GET", `/api/werkgebieden/${encodeURIComponent(id)}`);
  if (w.status !== 200) return NEE(`Het werkgebied is niet te lezen (status ${w.status}); verwijderen kan alleen na controle.`);
  const wg = (w.data ?? {}) as { naam?: unknown; aangemaakt_door?: unknown };
  if (!inRunruimte(wg.naam)) {
    return NEE(`Dit werkgebied ("${String(wg.naam)}") hoort niet bij een testrun: de naam begint niet met ${VOORVOEGSELS.join(" of ")}.`);
  }
  if (wg.aangemaakt_door !== ik) return NEE(`Dit werkgebied is gemaakt door een ander account dan ${ik}.`);
  return JA;
}

/** Mag deze verwijderende aanroep? Leest het object op (naam, wie het maakte) voor het oordeel. Een aanroep die niets
 *  verwijdert, mag altijd. */
export async function toetsVerwijderen(c: Bff, methode: string, pad: string, ik: string): Promise<Oordeel> {
  if (!isVerwijderend(methode, pad)) return JA;
  const delen = pad.split("?")[0].split("/").filter(Boolean); // ["api", "gesprekken", "<id>", …]
  if (delen.length < 3 || BULK.has(delen[2]) || delen.includes("groep")) {
    return NEE("Een bulkroute verwijdert ook wat niet van deze run is. Gebruik `opruimen` voor de ruimte van een run.");
  }
  const [, soort, id] = delen;
  if (!ik) return NEE("Het account is niet te bepalen (/api/account/me); verwijderen kan alleen na controle.");
  if (soort === "gesprekken") return gesprekInRunruimte(c, id, ik);
  if (soort === "werkgebieden") return werkgebiedInRunruimte(c, id, ik);
  return NEE("Dit verwijdert iets wat gedeeld is (een annotatielaag, een generiek begrip, het beheer). Dat doet een testrun niet.");
}

export interface GesprekRij {
  id: string;
  titel: string;
  werkgebied_id?: string;
  ouder_id?: string;
}

export interface WerkgebiedRij {
  id: string;
  naam: string;
  aangemaakt_door: string;
  revisie: number;
}

export interface Opruimplan {
  voorvoegsel: string;
  werkgebieden: WerkgebiedRij[];
  gesprekken: GesprekRij[];
}

/** Wat een run maakte: werkgebieden met het voorvoegsel die dit account maakte, en elk gesprek met het voorvoegsel,
 *  in zo'n werkgebied of onder zo'n gesprek (ook een deelgesprek van een deelgesprek). Deelgesprekken eerst. */
export function opruimplan(voorvoegsel: string, ik: string, werkgebieden: WerkgebiedRij[], gesprekken: GesprekRij[]): Opruimplan {
  if (!inRunruimte(voorvoegsel)) throw new Error(`Het voorvoegsel moet beginnen met ${VOORVOEGSELS.join(" of ")}.`);
  const wg = werkgebieden.filter((w) => w.naam.startsWith(voorvoegsel) && w.aangemaakt_door === ik);
  const wgIds = new Set(wg.map((w) => w.id));
  const gekozen = new Set(gesprekken.filter((g) => g.titel.startsWith(voorvoegsel) || (g.werkgebied_id && wgIds.has(g.werkgebied_id)))
    .map((g) => g.id));
  let erbij = true;
  while (erbij) {
    erbij = false;
    for (const g of gesprekken) {
      if (g.ouder_id && gekozen.has(g.ouder_id) && !gekozen.has(g.id)) {
        gekozen.add(g.id);
        erbij = true;
      }
    }
  }
  const diepte = (g: GesprekRij): number => {
    let d = 0;
    for (let x = g; x.ouder_id; d++) {
      const ouder = gesprekken.find((o) => o.id === x.ouder_id);
      if (!ouder) break;
      x = ouder;
    }
    return d;
  };
  const lijst = gesprekken.filter((g) => gekozen.has(g.id)).sort((a, b) => diepte(b) - diepte(a));
  return { voorvoegsel, werkgebieden: wg, gesprekken: lijst };
}

/** Voer het plan uit: eerst de gesprekken (deelgesprekken vóór hun ouder), dan de werkgebieden; elk langs de vangrail. */
export async function voerUit(c: Bff, plan: Opruimplan, ik: string): Promise<{ verwijderd: string[]; geweigerd: string[] }> {
  const verwijderd: string[] = [];
  const geweigerd: string[] = [];
  const paden = [
    ...plan.gesprekken.map((g) => `/api/gesprekken/${encodeURIComponent(g.id)}`),
    ...plan.werkgebieden.map((w) => `/api/werkgebieden/${encodeURIComponent(w.id)}?verwachte_revisie=${w.revisie}`),
  ];
  for (const pad of paden) {
    const oordeel = await toetsVerwijderen(c, "DELETE", pad, ik);
    if (!oordeel.mag) {
      geweigerd.push(`${pad}: ${oordeel.reden}`);
      continue;
    }
    const r = await c.bff("DELETE", pad);
    if (r.status < 300) verwijderd.push(pad);
    else geweigerd.push(`${pad}: status ${r.status}`);
  }
  return { verwijderd, geweigerd };
}

/** Lees alles wat dit account ziet: alle werkgebieden, en de eigen gesprekken (actief én gearchiveerd), per pagina. */
export async function leesRuimte(c: Bff): Promise<{ ik: string; werkgebieden: WerkgebiedRij[]; gesprekken: GesprekRij[] }> {
  const me = await c.bff("GET", "/api/account/me");
  const ik = String((me.data as { userid?: unknown } | null)?.userid ?? "");
  if (me.status !== 200 || !ik) throw new Error(`Het account is niet te bepalen (status ${me.status}).`);
  const w = await c.bff("GET", "/api/werkgebieden");
  if (w.status !== 200) throw new Error(`De werkgebieden zijn niet te lezen (status ${w.status}).`);
  const werkgebieden = ((w.data as { werkgebieden?: WerkgebiedRij[] } | null)?.werkgebieden ?? []);
  const gesprekken: GesprekRij[] = [];
  for (let offset = 0; offset < 10_000; offset += 200) {
    const g = await c.bff("GET", `/api/gesprekken?limit=200&offset=${offset}`);
    if (g.status !== 200) throw new Error(`De gesprekken zijn niet te lezen (status ${g.status}).`);
    const pagina = (g.data as GesprekRij[] | null) ?? [];
    gesprekken.push(...pagina);
    if (pagina.length < 200) break;
  }
  return { ik, werkgebieden, gesprekken };
}
