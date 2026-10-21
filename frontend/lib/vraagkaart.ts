// Lex stelt met de analist een werkgebied samen (startactiviteit a en activiteit 1, graph-qa
// `agent/werkgebied_intake.py`): naam, aanleiding, context, doel, analysevraag, praktijkvoorbeeld,
// deelvragen, wat erbuiten valt, en dan pas de bronnen: de regelingen, en per deelvraag een kaartje met
// de bepalingen die erbij horen (`deel`).
//
// Elke vraag komt als kaartje: een `vraagkaart`-event, en hetzelfde kaartje op het bewaarde bericht
// (`Bericht.vraagkaart`, api `gesprek_contracts.Vraagkaart`), zodat het na herladen nog te
// beantwoorden is. Een klik start een gewone beurt met `intake_actie`; de volgorde van de vragen is
// van graph-qa, niet van de werkplek. De werkplek kiest alleen welk kaartje nog bedienbaar is: het
// laatste in de thread.
//
// Pure functies, zodat ze zonder DOM te testen zijn (lib/vraagkaart.test.ts).

export const STAPPEN = ["naam", "aanleiding", "context", "doel", "analysevraag", "praktijkvoorbeeld", "deelvragen",
  "buiten", "regelingen", "bepalingen"] as const;
export type IntakeStap = (typeof STAPPEN)[number] | "samenvatting";
/** De vaste kaartjes vóór de bepalingen; daarna één per deelvraag (graph-qa `VASTE_STAPPEN`). */
const VASTE_STAPPEN = STAPPEN.length - 1;

/** Bij de bepalingen: het kaartje van welke deelvraag (zonder deelvragen: de analysevraag). */
export interface IntakeDeel {
  index: number;
  totaal: number;
  deelvraag: string | null;
}

/** De waarde van "Weet ik (nog) niet" (graph-qa `ONBEKEND`). */
export const ONBEKEND = "onbekend";

export interface VraagOptie {
  label: string;
  waarde: string;
  bron: Record<string, unknown>;
  /** De tweede regel onder de optie ("wet · 2 delen over ‘box 3’"), uit de graaf. */
  omschrijving: string;
}

export interface Vraagkaart {
  intake_id: string;
  soort: "vraag" | "samenvatting";
  stap: IntakeStap;
  nr: number;
  totaal: number;
  /** Alleen bij de bepalingen. */
  deel: IntakeDeel | null;
  vraag: string;
  toelichting: string;
  opties: VraagOptie[];
  meerkeuze: boolean;
  vrije_tekst: boolean;
  /** Meer dan één eigen antwoord (de deelvragen): de dock biedt "+ Nog een" en stuurt `teksten`. */
  meer_tekst: boolean;
  overslaanbaar: boolean;
  /** Wat Lex uit je eerste zin haalde: voorgeselecteerd, nooit stil aangenomen. */
  vooringevuld: string[];
  /** Bij `soort: "samenvatting"`: wat er aangemaakt wordt. */
  samenvatting: Samenvatting | null;
  /** ‹: er is een eerdere stap. */
  terug: boolean;
  /** ›: deze stap had al een antwoord (na terugbladeren). */
  beantwoord: boolean;
}

export interface Samenvatting {
  naam: string;
  aanleiding: string;
  context: string;
  doel: string;
  analysevraag: string;
  praktijkvoorbeeld: string;
  deelvragen: string[];
  afbakening: string;
  bronnen: string[];
}

/** Op het user-bericht van een klik (api `Bericht.intake_antwoord`): zo herkent de thread een antwoord. */
export interface AntwoordOp {
  intake_id: string;
  stap: IntakeStap;
  deel?: number;
  actie: IntakeActie["actie"];
}

/** Een klik op een kaartje, zoals graph-qa hem verwacht (`ChatRequest.intake_actie`). */
export interface IntakeActie {
  intake_id: string;
  stap: IntakeStap;
  /** Bij de bepalingen: het deel van het kaartje; een ander deel is een oud kaartje. */
  deel?: number;
  actie: "antwoord" | "overslaan" | "wijzig" | "aanmaken" | "afbreken";
  keuzes?: string[];
  tekst?: string;
  /** Meer dan één eigen antwoord (`meer_tekst`). */
  teksten?: string[];
  naar?: string;
  naar_deel?: number;
}

const tekst = (v: unknown) => (typeof v === "string" ? v : "");
const lijst = (v: unknown) => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);
const STAP_SET = new Set<string>([...STAPPEN, "samenvatting"]);

/** Streng: een kaartje zonder intake, met een onbekende stap of zonder vraag wordt niet getoond. Liever
 *  geen kaartje dan een kaartje dat een klik naar een niet-bestaande stap stuurt. */
export function parseVraagkaart(ruw: unknown): Vraagkaart | undefined {
  if (!ruw || typeof ruw !== "object") return undefined;
  const r = ruw as Record<string, unknown>;
  const intake_id = tekst(r.intake_id), stap = tekst(r.stap), vraag = tekst(r.vraag);
  if (!/^[A-Za-z0-9-]{1,64}$/.test(intake_id) || !STAP_SET.has(stap) || !vraag) return undefined;
  const opties = Array.isArray(r.opties) ? r.opties.flatMap((o): VraagOptie[] => {
    const x = (o ?? {}) as Record<string, unknown>;
    return tekst(x.label) && tekst(x.waarde)
      ? [{ label: tekst(x.label), waarde: tekst(x.waarde), omschrijving: tekst(x.omschrijving),
          bron: x.bron && typeof x.bron === "object" ? x.bron as Record<string, unknown> : {} }]
      : [];
  }) : [];
  const s = r.samenvatting && typeof r.samenvatting === "object" ? r.samenvatting as Record<string, unknown> : null;
  const getal = (v: unknown, terug: number) => (typeof v === "number" && Number.isInteger(v) && v > 0 ? v : terug);
  const d = r.deel && typeof r.deel === "object" ? r.deel as Record<string, unknown> : null;
  const deel = stap === "bepalingen" && d && typeof d.index === "number" && Number.isInteger(d.index) && d.index >= 0
    ? { index: d.index, totaal: getal(d.totaal, d.index + 1), deelvraag: tekst(d.deelvraag) || null } : null;
  return {
    intake_id, stap: stap as IntakeStap, vraag, deel,
    soort: r.soort === "samenvatting" ? "samenvatting" : "vraag",
    nr: getal(r.nr, 1), totaal: getal(r.totaal, STAPPEN.length),
    toelichting: tekst(r.toelichting),
    opties,
    meerkeuze: r.meerkeuze === true,
    vrije_tekst: r.vrije_tekst !== false,
    meer_tekst: r.meer_tekst === true,
    overslaanbaar: r.overslaanbaar === true,
    vooringevuld: Array.isArray(r.vooringevuld) ? r.vooringevuld.filter((v): v is string => typeof v === "string") : [],
    terug: r.terug === true,
    beantwoord: r.beantwoord === true,
    samenvatting: s && r.soort === "samenvatting" ? {
      naam: tekst(s.naam), aanleiding: tekst(s.aanleiding), context: tekst(s.context), doel: tekst(s.doel),
      analysevraag: tekst(s.analysevraag), praktijkvoorbeeld: tekst(s.praktijkvoorbeeld),
      deelvragen: lijst(s.deelvragen), afbakening: tekst(s.afbakening), bronnen: lijst(s.bronnen),
    } : null,
  };
}

/** De beginstand van een kaartje: de vooringevulde waarden die als optie bestaan zijn geselecteerd; een
 *  vooringevulde waarde zonder optie staat in het eigen-tekstveld. Bij `meer_tekst` (de deelvragen)
 *  krijgt elke eigen waarde een eigen regel, met een lege regel erachter. */
export function beginstand(k: Vraagkaart): { gekozen: string[]; eigen: string; teksten: string[] } {
  const waarden = new Set(k.opties.map((o) => o.waarde));
  const gekozen = k.vooringevuld.filter((v) => waarden.has(v));
  const eigenWaarden = k.vooringevuld.filter((v) => !waarden.has(v));
  return {
    gekozen: k.meerkeuze ? gekozen : gekozen.slice(0, 1),
    eigen: k.meer_tekst ? "" : (eigenWaarden[0] ?? ""),
    teksten: k.meer_tekst ? [...eigenWaarden, ""] : [],
  };
}

/** Wat er bij een klik in het gesprek komt te staan: de leesbare weergave van het antwoord. graph-qa
 *  leest de `intake_actie`, niet deze tekst; ze staat er voor de jurist en voor de historie. */
export function antwoordTekst(k: Vraagkaart, actie: IntakeActie): string {
  if (actie.actie === "aanmaken") return "Maak het werkgebied aan.";
  if (actie.actie === "afbreken") return "Stop met samenstellen.";
  if (actie.actie === "overslaan") return "Sla deze vraag over.";
  if (actie.actie === "wijzig") {
    const metDeelvragen = !!k.deel?.deelvraag || !!k.samenvatting?.deelvragen.length;
    if (actie.naar === "bepalingen" && metDeelvragen && typeof actie.naar_deel === "number") {
      return `Terug naar de bepalingen bij deelvraag ${actie.naar_deel + 1}.`;
    }
    return `Terug naar ${STAP_NAAM[actie.naar as IntakeStap] ?? "de vorige vraag"}.`;
  }
  const labels = (actie.keuzes ?? []).map((w) => k.opties.find((o) => o.waarde === w)?.label ?? w);
  const eigen = [...(actie.teksten ?? []), ...(actie.tekst?.trim() ? [actie.tekst.trim()] : [])];
  return [...labels, ...eigen].join("; ") || "—";
}

/** Een antwoord-klik: de keuzes, en eigen tekst alleen als die er is. Zonder iets is er geen antwoord.
 *  `teksten` zijn de eigen regels van een kaartje met `meer_tekst`; lege regels tellen niet. */
export function antwoordActie(k: Vraagkaart, gekozen: string[], eigen: string, teksten: string[] = []):
  IntakeActie | undefined {
  const t = eigen.trim();
  const ts = teksten.map((x) => x.trim()).filter(Boolean);
  if (!gekozen.length && !t && !ts.length) return undefined;
  return { intake_id: k.intake_id, stap: k.stap, ...(k.deel ? { deel: k.deel.index } : {}), actie: "antwoord",
    keuzes: gekozen, ...(t ? { tekst: t } : {}), ...(ts.length ? { teksten: ts } : {}) };
}

/** Hoe de samenvatting een stap noemt, voor *Aanpassen*. */
export const STAP_NAAM: Record<IntakeStap, string> = {
  naam: "de naam",
  aanleiding: "de aanleiding",
  context: "de context",
  doel: "het doel",
  analysevraag: "de analysevraag",
  praktijkvoorbeeld: "het praktijkvoorbeeld",
  deelvragen: "de deelvragen",
  regelingen: "de regelingen",
  bepalingen: "de bepalingen",
  buiten: "wat erbuiten valt",
  samenvatting: "de samenvatting",
};

export function parseAntwoordOp(ruw: unknown): AntwoordOp | undefined {
  if (!ruw || typeof ruw !== "object") return undefined;
  const r = ruw as Record<string, unknown>;
  const intake_id = tekst(r.intake_id), stap = tekst(r.stap), actie = tekst(r.actie) || "antwoord";
  if (!/^[A-Za-z0-9-]{1,64}$/.test(intake_id) || !STAP_SET.has(stap)) return undefined;
  if (!["antwoord", "overslaan", "wijzig", "aanmaken", "afbreken"].includes(actie)) return undefined;
  const deel = typeof r.deel === "number" && Number.isInteger(r.deel) && r.deel >= 0 ? r.deel : undefined;
  return { intake_id, stap: stap as IntakeStap, ...(deel !== undefined ? { deel } : {}),
    actie: actie as IntakeActie["actie"] };
}

/** De gegevens van een klik, zoals ze op het user-bericht komen (api `IntakeAntwoord`). */
export function antwoordOp(a: IntakeActie): AntwoordOp {
  return { intake_id: a.intake_id, stap: a.stap, ...(typeof a.deel === "number" ? { deel: a.deel } : {}), actie: a.actie };
}

/** Het kaartje vóór dit (‹): de vorige stap, of bij de bepalingen het vorige deel. Vanaf de
 *  samenvatting is dat het laatste bepalingen-kaartje. */
export function vorige(k: Vraagkaart): { naar: IntakeStap; naar_deel?: number } | undefined {
  if (!k.terug) return undefined;
  if (k.stap === "samenvatting") return { naar: "bepalingen", naar_deel: Math.max(0, k.totaal - VASTE_STAPPEN - 1) };
  if (k.stap === "bepalingen" && k.deel && k.deel.index > 0) return { naar: "bepalingen", naar_deel: k.deel.index - 1 };
  const i = STAPPEN.indexOf(k.stap as (typeof STAPPEN)[number]);
  return i > 0 ? { naar: STAPPEN[i - 1] } : undefined;
}

/** Is dit de laatste vraag vóór de samenvatting? Dan heet de knop *Verzend*. */
export function isLaatsteVraag(k: Vraagkaart): boolean {
  return k.stap === "bepalingen" && (!k.deel || k.deel.index >= k.deel.totaal - 1);
}

/** Eén vraag met het antwoord erop, voor de Vragen-kaart in de thread. */
export interface VraagPaar {
  stap: IntakeStap;
  /** Bij de bepalingen: het deel (een paar per deelvraag). */
  deel?: number;
  vraag: string;
  antwoord: string;
  overgeslagen: boolean;
}

/** Een reeks opeenvolgende vragen van één intake: wat de thread als één "Vragen"-kaart toont. */
export interface VragenGroep {
  sleutel: string;
  intake_id: string;
  /** Wat Lex bij de eerste vraag zei (bijvoorbeeld de uitleg bij "wetsanalyse uitvoeren"). */
  tekst: string;
  paren: VraagPaar[];
  /** De vraag die nog openstaat, als die er is. */
  open?: Vraagkaart;
  /** Het item van de open vraag (sleutel voor wegklikken). */
  openId?: string;
  /** Er loopt een beurt na het laatste antwoord: "Nadenken…". */
  denkt: boolean;
}

type GroepItem = {
  id: string; type: string; tekst?: string; vraagkaart?: Vraagkaart; antwoordOp?: AntwoordOp;
};

/** De thread-weergave van het samenstellen: per item of het een Vragen-kaart draagt (`kop`), of
 *  verdwijnt omdat zijn inhoud in die kaart staat (`verborgen`).
 *
 *  Een groep is een aaneengesloten reeks: een Lex-item met een vraagkaart, het antwoord daarop (een
 *  user-item met `antwoordOp` van dezelfde intake), de volgende vraag, enzovoort. Een ander item – een
 *  getypte tussenvraag en het antwoord van Lex daarop – breekt de reeks; de volgende vraag begint een
 *  nieuwe kaart. Een Lex-item zonder kaartje direct na een antwoord is de lopende beurt (`bezig`): dat
 *  verdwijnt ook, de kaart zegt "Nadenken…". */
export function groepeerVragen<T extends GroepItem>(items: T[], bezig: boolean):
  { groepen: Map<string, VragenGroep>; verborgen: Set<string> } {
  const groepen = new Map<string, VragenGroep>();
  const verborgen = new Set<string>();
  let huidig: VragenGroep | null = null;
  items.forEach((x, i) => {
    if (x.type === "antwoord" && x.vraagkaart) {
      const k = x.vraagkaart;
      if (huidig && huidig.intake_id === k.intake_id) {
        verborgen.add(x.id);
        huidig.open = k; huidig.openId = x.id; huidig.denkt = false;
      } else {
        huidig = { sleutel: x.id, intake_id: k.intake_id, tekst: (x.tekst ?? "").trim(), paren: [], open: k,
          openId: x.id, denkt: false };
        groepen.set(x.id, huidig);
      }
      return;
    }
    if (x.type === "user" && x.antwoordOp && huidig && huidig.intake_id === x.antwoordOp.intake_id) {
      verborgen.add(x.id);
      const k = huidig.open;
      // Terugbladeren is geen antwoord: de vraag waar je naartoe gaat komt als nieuw kaartje. Beantwoord
      // je een stap opnieuw, dan vervangt dat het eerdere paar en wat erna kwam – de reeks begint daar opnieuw.
      if (k && x.antwoordOp.actie !== "wijzig") {
        // Bij de bepalingen is elk deel een eigen vraag: het antwoord op deelvraag 2 vervangt dat op 1 niet.
        const eerder = huidig.paren.findIndex((p) => p.stap === k.stap && p.deel === k.deel?.index);
        if (eerder >= 0) huidig.paren.splice(eerder);
        huidig.paren.push({ stap: k.stap, ...(k.deel ? { deel: k.deel.index } : {}), vraag: k.vraag,
          antwoord: x.tekst ?? "", overgeslagen: x.antwoordOp.actie === "overslaan" });
      }
      huidig.open = undefined; huidig.openId = undefined;
      return;
    }
    if (x.type === "antwoord" && huidig && !huidig.open && bezig && i === items.length - 1) {
      verborgen.add(x.id);
      huidig.denkt = true;
      return;
    }
    huidig = null;
  });
  return { groepen, verborgen };
}

/** De vraag die nu te beantwoorden is: de open vraag van de laatste reeks met vragen – ook als er
 *  daarna een tussenvraag kwam. Is die vraag beantwoord (of afgebroken), dan geen. */
export function openVraag(groepen: Map<string, VragenGroep>): VragenGroep | undefined {
  const laatste = [...groepen.values()].at(-1);
  return laatste?.open ? laatste : undefined;
}
