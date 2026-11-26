import { actieveConnectors, schakelbaar, type ConnectorStand } from "./connectorsMenu";
import { PLUGINS } from "./plugins";
import type { CommandoContext, OnderwerpSoort, Suggestie } from "./vraagLex";

/** `/commando's` in het invoerveld van de werkplek.
 *
 *  Een commando is geen tweede router. Er zijn drie soorten:
 *  - **suggestie**: een suggestie uit het register van `lib/vraagLex.ts` die een `commando` draagt. Uitvoeren is precies
 *    een klik op die suggestie: dezelfde tekst in de thread, dezelfde `actie` of hetzelfde `doel`, dus zonder dat een
 *    model bij graph-qa de route kiest (geen centrale agent). Welke er zijn, hangt af van de context: het onderwerp, of anders het werkgebied
 *    (de suggesties die de werkplek nu toont).
 *  - **client**: een handeling in de werkplek zelf, zonder beurt en dus zonder tokens: een nieuw gesprek, een bron aan of
 *    uit, de lijst met commando's.
 *  - **plugin**: een plugin naast de wetsanalyse (`lib/plugins.ts`), met tekst erachter: `/contenttoets <tekst>`. Enter op de
 *    regel vult het commando aan; daarna sluit het menu en gaat de hele tekst als vraag naar Lex, die het commando zonder
 *    model herkent (graph-qa `agent/contenttoets.py`).
 *
 *  **De catalogus (ADR-014).** Wat Lex kan, staat niet hier: een suggestiecommando wijst naar een `actie` uit graph-qa
 *  (`ACTIE_TAAK` en de andere actielijsten in `agent/models.py`), of naar het annotatiedoel. Dat is een ingang van een
 *  `Onderdeel` in de catalogus. `tools/graph-qa/tests/test_catalogus.py` toetst dat elk commando via zijn actie (of zijn
 *  annotatiedoel) naar precies één onderdeel wijst (ADR-014 §7). De clientcommando's zijn bediening van de werkplek,
 *  geen onderdeel van Lex, en horen dus niet in de catalogus.
 *
 *  `/` doet alleen iets als eerste teken in het invoerveld: het is tekst, geen sneltoets. Een `/`-tekst zonder bekend
 *  commando gaat ongewijzigd als vraag naar Lex. */

export type ClientHandeling = "nieuw" | "bron" | "context" | "help";

export type Commando =
  | { soort: "suggestie"; naam: string; hulp: string; suggestie: Suggestie }
  | { soort: "client"; naam: string; hulp: string; handeling: ClientHandeling; argument?: "connector" }
  | { soort: "plugin"; naam: string; hulp: string; argument: "tekst" };

/** De commando's van de plugins: na die van de context, vóór de clientcommando's. */
export const PLUGIN_COMMANDOS: Extract<Commando, { soort: "plugin" }>[] =
  PLUGINS.map((p) => ({ soort: "plugin", naam: p.commando, hulp: p.hulp, argument: "tekst" }));

/** De commando's die geen suggestie zijn. De volgorde is die van het menu, na de commando's van de context. */
export const CLIENT_COMMANDOS: Extract<Commando, { soort: "client" }>[] = [
  { soort: "client", naam: "nieuw", hulp: "Begin een nieuw gesprek (in een werkgebied: in dat werkgebied)", handeling: "nieuw" },
  { soort: "client", naam: "bron", hulp: "Zet een bron naast de wet aan of uit voor dit gesprek", handeling: "bron", argument: "connector" },
  { soort: "client", naam: "context", hulp: "Toon hoe de context van de laatste beurt is opgebouwd en wat de beurt kostte", handeling: "context" },
  { soort: "client", naam: "help", hulp: "Toon alle commando's die hier kunnen", handeling: "help" },
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
  /** De plugins die in dit gesprek aanstaan (`lib/plugins.ts`); zonder dit veld alle plugins (een test, de demo). */
  plugins?: readonly string[];
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
  for (const c of PLUGIN_COMMANDOS) {
    if (gezien.has(c.naam) || (stand.plugins && !stand.plugins.includes(c.naam))) continue;
    gezien.add(c.naam);
    uit.push(c);
  }
  for (const c of CLIENT_COMMANDOS) {
    if (gezien.has(c.naam)) continue;
    if (nietHier(c, stand)) continue;
    uit.push(c);
  }
  return uit;
}

/** Waarom een commando in deze context niet in het menu staat (los van de context van de suggesties), of `undefined`. */
function nietHier(c: Commando, stand: Stand): string | undefined {
  if (c.soort === "client" && c.argument === "connector" && !connectorOpties(stand.connectors).length)
    return "alleen als de beheerder een bron naast de wet aanbiedt";
  return undefined;
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
  if ((c.soort === "suggestie" && !c.suggestie.invullen) || c.soort === "plugin") {
    if (stand.geblokkeerd) return "je tokenbudget is op";
    if (stand.bezig) return "Lex is nog bezig";
  }
  return undefined;
}

function regelVan(c: Commando, stand: Stand): Regel {
  const uit = uitReden(c, stand);
  const vraagtArgument = (c.soort === "client" && !!c.argument) || c.soort === "plugin";
  return {
    sleutel: c.naam,
    label: `/${c.naam}`,
    hulp: c.hulp,
    aanvulling: `/${c.naam}${vraagtArgument ? " " : ""}`,
    uit,
    // Een commando dat een argument vraagt, voert Enter niet zonder uit: dan vult hij aan.
    uitvoer: uit || vraagtArgument ? null
      : c.soort === "suggestie" ? { soort: "suggestie", suggestie: c.suggestie }
      : c.soort === "client" ? { soort: "client", handeling: c.handeling }
      : null,
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

/** Of een commando een beurt van Lex start. Een suggestie is een beurt, behalve een klaargezette vraag; de client nooit. Een
 *  nieuwe soort commando (een plugin) is een beurt tot hij anders zegt. */
export type Beurt = "beurt" | "klaarzetten" | "geen";

export const BEURT_TEKST: Record<Beurt, string> = {
  beurt: "start een beurt van Lex",
  klaarzetten: "geen beurt: zet een vraag in het veld",
  geen: "geen beurt, geen tokens",
};

/** Eén commando in het overzicht van `/help`. `aanvulling` is wat een klik in het veld zet, net als Tab in het menu. */
export interface HulpRegel {
  naam: string;
  label: string;
  hulp: string;
  beurt: Beurt;
  /** Hoe je hem gebruikt, als dat meer is dan de naam: met een argument (`/bron rechtspraak`), of de vraag die hij in het
   *  veld zet (bij `beurt: "klaarzetten"`). */
  voorbeeld?: string;
  aanvulling: string;
  /** Waarom hij nu niet kan (een beurt loopt, het budget is op). */
  uit?: string;
}

/** Een groep in het overzicht: wat hier kan (zonder `reden`), en per andere context wat daar kan, met waarom het hier niet in
 *  het menu staat. */
export interface HulpGroep {
  sleutel: string;
  titel: string;
  reden?: string;
  regels: HulpRegel[];
}

/** `hier`: alleen wat hier kan, krijgt een reden waarom het nu niet kan. */
function hulpRegel(c: Commando, stand: Stand, hier = false): HulpRegel {
  const { label, hulp, aanvulling } = regelVan(c, stand);
  const uit = hier ? uitReden(c, stand) : undefined;
  const beurt: Beurt = c.soort === "client" ? "geen" : c.soort === "suggestie" && c.suggestie.invullen ? "klaarzetten" : "beurt";
  const argument = "argument" in c ? c.argument : undefined;
  const voorbeeld = argument
    ? `/${c.naam} ${argument === "connector" ? connectorOpties(stand.connectors)[0]?.naam ?? "<bron>" : `<${argument}>`}`
    : c.soort === "suggestie" && c.suggestie.invullen ? `${c.suggestie.tekst.trim()} …` : undefined;
  return { naam: c.naam, label, hulp, beurt, ...(voorbeeld ? { voorbeeld } : {}), aanvulling, ...(uit ? { uit } : {}) };
}

/** Het overzicht van `/help`: eerst wat hier kan (precies het menu bij `/`), dan wat elders kan, gegroepeerd met de reden.
 *  Alles komt uit `beschikbaar`, dezelfde lijst als het menu, zodat een nieuw commando – een suggestie, een clientcommando of
 *  een plugin – vanzelf meekomt. `contexten` zijn alle contexten met hun suggesties (`commandoContexten` in `lib/vraagLex.ts`);
 *  `huidig` is de soort van het onderwerp of het werkgebied waarin je nu werkt. */
export function hulpOverzicht(stand: Stand, contexten: CommandoContext[], huidig?: OnderwerpSoort): HulpGroep[] {
  const hier = beschikbaar(stand);
  const sleutel = (c: Commando) => `${c.naam}|${c.hulp}`;
  const gezien = new Set(hier.map(sleutel));
  const groepen: HulpGroep[] = [{ sleutel: "hier", titel: "Hier", regels: hier.map((c) => hulpRegel(c, stand, true)) }];
  for (const ctx of contexten) {
    if (ctx.soort === huidig) continue;
    const elders = beschikbaar({ ...stand, suggesties: ctx.suggesties }).filter((c) => !gezien.has(sleutel(c)));
    for (const c of elders) gezien.add(sleutel(c));
    if (elders.length) groepen.push({ sleutel: ctx.soort, titel: ctx.titel, reden: ctx.reden, regels: elders.map((c) => hulpRegel(c, stand)) });
  }
  // Wat in geen context in het menu staat, met de reden (`/bron` zonder bron om om te zetten).
  const perReden = new Map<string, Commando[]>();
  for (const c of CLIENT_COMMANDOS) {
    const reden = nietHier(c, stand);
    if (!reden || gezien.has(sleutel(c))) continue;
    perReden.set(reden, [...(perReden.get(reden) ?? []), c]);
  }
  for (const [reden, lijst] of perReden)
    groepen.push({ sleutel: `niet:${reden}`, titel: "Nu niet", reden, regels: lijst.map((c) => hulpRegel(c, stand)) });
  return groepen;
}
