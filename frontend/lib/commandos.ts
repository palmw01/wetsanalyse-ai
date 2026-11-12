import { actieveConnectors, schakelbaar, type ConnectorStand } from "./connectorsMenu";
import type { Suggestie } from "./vraagLex";

/** `/commando's` in het invoerveld van de werkplek.
 *
 *  Een commando is geen tweede router. Er zijn drie soorten:
 *  - **suggestie**: een suggestie uit het register van `lib/vraagLex.ts` die een `commando` draagt. Uitvoeren is precies
 *    een klik op die suggestie: dezelfde tekst in de thread, dezelfde `actie` of hetzelfde `doel`, dus zonder
 *    supervisor-aanroep bij graph-qa. Welke er zijn, hangt af van de context: het onderwerp, of anders het werkgebied
 *    (de suggesties die de werkplek nu toont).
 *  - **client**: een handeling in de werkplek zelf, zonder beurt en dus zonder tokens: een nieuw gesprek, een bron aan of
 *    uit, de lijst met commando's.
 *  - **gereserveerd**: een naam die al vastligt voor een functie die nog komt (`/compact`, contextbeheer). Staat in de
 *    lijst, niet te kiezen.
 *
 *  `/` doet alleen iets als eerste teken in het invoerveld: het is tekst, geen sneltoets. Een `/`-tekst zonder bekend
 *  commando gaat ongewijzigd als vraag naar Lex. */

export type ClientHandeling = "nieuw" | "bron" | "help";

export type Commando =
  | { soort: "suggestie"; naam: string; hulp: string; suggestie: Suggestie }
  | { soort: "client"; naam: string; hulp: string; handeling: ClientHandeling; argument?: "connector" }
  | { soort: "gereserveerd"; naam: string; hulp: string };

/** De commando's die geen suggestie zijn. De volgorde is die van het menu, na de commando's van de context. */
export const CLIENT_COMMANDOS: Extract<Commando, { soort: "client" | "gereserveerd" }>[] = [
  { soort: "client", naam: "nieuw", hulp: "Begin een nieuw gesprek (in een werkgebied: in dat werkgebied)", handeling: "nieuw" },
  { soort: "client", naam: "bron", hulp: "Zet een bron naast de wet aan of uit voor dit gesprek", handeling: "bron", argument: "connector" },
  { soort: "client", naam: "help", hulp: "Toon alle commando's die hier kunnen", handeling: "help" },
  { soort: "gereserveerd", naam: "compact", hulp: "Het gesprek samenvatten om ruimte te maken – komt nog" },
];

/** Een geldige commandonaam: kleine letters en streepjes. */
export const NAAM_RE = /^[a-z]+(-[a-z]+)*$/;

export interface Stand {
  /** De suggesties die de werkplek nu toont (onderwerp, of anders het werkgebied). */
  suggesties: Suggestie[];
  connectors: ConnectorStand;
  /** Er loopt een beurt: een suggestiecommando kan dan niet. */
  bezig: boolean;
  /** Het tokenbudget is op: een suggestiecommando kan dan niet. */
  geblokkeerd: boolean;
}

/** De commando's van deze context: eerst die van de suggesties (in hun volgorde, elke naam één keer), dan de rest. `/bron`
 *  alleen als er een bron is om aan of uit te zetten. */
export function beschikbaar(stand: Stand): Commando[] {
  const gezien = new Set<string>();
  const uit: Commando[] = [];
  for (const s of stand.suggesties) {
    if (!s.commando || gezien.has(s.commando.naam)) continue;
    gezien.add(s.commando.naam);
    uit.push({ soort: "suggestie", naam: s.commando.naam, hulp: s.commando.hulp, suggestie: s });
  }
  for (const c of CLIENT_COMMANDOS) {
    if (gezien.has(c.naam)) continue;
    if (c.soort === "client" && c.argument === "connector" && !connectorOpties(stand.connectors).length) continue;
    uit.push(c);
  }
  return uit;
}

/** `/naam rest`: alleen met `/` als eerste teken. `null` als de tekst geen commandovorm heeft. */
export function ontleed(invoer: string): { naam: string; rest: string; metSpatie: boolean } | null {
  const m = /^\/([a-z-]*)(\s+([\s\S]*))?$/.exec(invoer);
  if (!m) return null;
  return { naam: m[1], rest: (m[3] ?? "").trim(), metSpatie: m[2] != null };
}

export interface ConnectorOptie { naam: string; label: string; aan: boolean }

/** De bronnen die je met `/bron` kunt omzetten: wat de beheerder aanzette en de omgeving aanbiedt. */
export function connectorOpties(stand: ConnectorStand): ConnectorOptie[] {
  const aan = actieveConnectors(stand);
  return stand.beschikbaar.filter(schakelbaar).map((c) => ({ naam: c.naam, label: c.label, aan: aan.includes(c.naam) }));
}

/** Eén regel in het menu. `aanvulling` is de tekst die Tab in het veld zet; `uitvoer` wat Enter doet. */
export interface Regel {
  sleutel: string;
  label: string;
  hulp: string;
  aanvulling: string;
  /** Waarom deze regel nu niet kan; dan doet Enter niets. */
  uit?: string;
  uitvoer: Uitvoer | null;
}

export type Uitvoer =
  | { soort: "suggestie"; suggestie: Suggestie }
  | { soort: "client"; handeling: ClientHandeling; argument?: string };

/** Waarom een commando nu niet kan, of `undefined`. */
function uitReden(c: Commando, stand: Stand): string | undefined {
  if (c.soort === "gereserveerd") return "komt nog";
  if (c.soort === "suggestie" && !c.suggestie.invullen) {
    if (stand.geblokkeerd) return "je tokenbudget is op";
    if (stand.bezig) return "Lex is nog bezig";
  }
  return undefined;
}

function regelVan(c: Commando, stand: Stand): Regel {
  const uit = uitReden(c, stand);
  const vraagtArgument = c.soort === "client" && !!c.argument;
  return {
    sleutel: c.naam,
    label: `/${c.naam}`,
    hulp: c.hulp,
    aanvulling: `/${c.naam}${vraagtArgument ? " " : ""}`,
    uit,
    // Een commando dat een argument vraagt, voert Enter niet zonder uit: dan vult hij aan.
    uitvoer: uit || vraagtArgument ? null
      : c.soort === "suggestie" ? { soort: "suggestie", suggestie: c.suggestie }
      : c.soort === "client" ? { soort: "client", handeling: c.handeling } : null,
  };
}

/** De regels van het menu bij deze invoer, of `null` als het menu dicht is (geen `/` vooraan). Een lege lijst: geen
 *  commando – Enter verstuurt de tekst dan als vraag.
 *
 *  - `/` of `/dee`: de commando's waarvan de naam zo begint, dan die waarin het getypte voorkomt; past geen naam, dan de
 *    hulpteksten (`/definitie` vindt `/brondefinitie`, `/taal` de uitleg);
 *  - `/bron ` en verder: de bronnen om om te zetten;
 *  - een ander commando met een spatie erachter: het menu is dicht, de tekst is een vraag. */
export function menuRegels(invoer: string, stand: Stand): Regel[] | null {
  const o = ontleed(invoer);
  if (!o) return null;
  const lijst = beschikbaar(stand);
  if (o.metSpatie) {
    const c = lijst.find((x) => x.naam === o.naam);
    if (!c || c.soort !== "client" || c.argument !== "connector") return null;
    const zoek = o.rest.toLowerCase();
    return connectorOpties(stand.connectors)
      .filter((k) => !zoek || k.naam.startsWith(zoek) || k.label.toLowerCase().includes(zoek))
      .map((k) => ({
        sleutel: `bron:${k.naam}`,
        label: `/bron ${k.naam}`,
        hulp: `${k.label} staat nu ${k.aan ? "aan – zet uit" : "uit – zet aan"}`,
        aanvulling: `/bron ${k.naam}`,
        uitvoer: { soort: "client", handeling: "bron", argument: k.naam },
      }));
  }
  const begin = lijst.filter((c) => c.naam.startsWith(o.naam));
  const inNaam = o.naam ? lijst.filter((c) => !c.naam.startsWith(o.naam) && c.naam.includes(o.naam)) : [];
  // De hulptekst alleen als geen naam past: anders vult "deelvraag" in elke hulp het menu.
  const elders = inNaam.length || begin.length || !o.naam ? inNaam
    : lijst.filter((c) => c.hulp.toLowerCase().includes(o.naam));
  // De exacte naam eerst: `/annoteer` kiest `annoteer`, niet `annoteer-deelvragen`.
  const exact = begin.filter((c) => c.naam === o.naam);
  return [...exact, ...begin.filter((c) => c.naam !== o.naam), ...elders].map((c) => regelVan(c, stand));
}
