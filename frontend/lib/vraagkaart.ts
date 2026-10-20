// Lex stelt met de analist een werkgebied samen (activiteit 1, graph-qa `agent/werkgebied_intake.py`).
//
// Elke vraag komt als kaartje: een `vraagkaart`-event, en hetzelfde kaartje op het bewaarde bericht
// (`Bericht.vraagkaart`, api `gesprek_contracts.Vraagkaart`), zodat het na herladen nog te
// beantwoorden is. Een klik start een gewone beurt met `intake_actie`; de volgorde van de vragen is
// van graph-qa, niet van de werkplek. De werkplek kiest alleen welk kaartje nog bedienbaar is: het
// laatste in de thread.
//
// Pure functies, zodat ze zonder DOM te testen zijn (lib/vraagkaart.test.ts).

export const STAPPEN = ["naam", "analysevraag", "regelingen", "onderdelen", "buiten"] as const;
export type IntakeStap = (typeof STAPPEN)[number] | "samenvatting";

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
  vraag: string;
  toelichting: string;
  opties: VraagOptie[];
  meerkeuze: boolean;
  vrije_tekst: boolean;
  overslaanbaar: boolean;
  /** Wat Lex uit je eerste zin haalde: voorgeselecteerd, nooit stil aangenomen. */
  vooringevuld: string[];
  /** Bij `soort: "samenvatting"`: wat er aangemaakt wordt. */
  samenvatting: { naam: string; analysevraag: string; afbakening: string; bronnen: string[] } | null;
  /** ‹: er is een eerdere stap. */
  terug: boolean;
  /** ›: deze stap had al een antwoord (na terugbladeren). */
  beantwoord: boolean;
}

/** Op het user-bericht van een klik (api `Bericht.intake_antwoord`): zo herkent de thread een antwoord. */
export interface AntwoordOp {
  intake_id: string;
  stap: IntakeStap;
  actie: IntakeActie["actie"];
}

/** Een klik op een kaartje, zoals graph-qa hem verwacht (`ChatRequest.intake_actie`). */
export interface IntakeActie {
  intake_id: string;
  stap: IntakeStap;
  actie: "antwoord" | "overslaan" | "wijzig" | "aanmaken" | "afbreken";
  keuzes?: string[];
  tekst?: string;
  naar?: string;
}

const tekst = (v: unknown) => (typeof v === "string" ? v : "");
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
  return {
    intake_id, stap: stap as IntakeStap, vraag,
    soort: r.soort === "samenvatting" ? "samenvatting" : "vraag",
    nr: getal(r.nr, 1), totaal: getal(r.totaal, STAPPEN.length),
    toelichting: tekst(r.toelichting),
    opties,
    meerkeuze: r.meerkeuze === true,
    vrije_tekst: r.vrije_tekst !== false,
    overslaanbaar: r.overslaanbaar === true,
    vooringevuld: Array.isArray(r.vooringevuld) ? r.vooringevuld.filter((v): v is string => typeof v === "string") : [],
    terug: r.terug === true,
    beantwoord: r.beantwoord === true,
    samenvatting: s && r.soort === "samenvatting" ? {
      naam: tekst(s.naam), analysevraag: tekst(s.analysevraag), afbakening: tekst(s.afbakening),
      bronnen: Array.isArray(s.bronnen) ? s.bronnen.filter((b): b is string => typeof b === "string") : [],
    } : null,
  };
}

/** De beginstand van een kaartje: de vooringevulde waarden die als optie bestaan zijn geselecteerd; een
 *  vooringevulde waarde zonder optie staat in het eigen-tekstveld. */
export function beginstand(k: Vraagkaart): { gekozen: string[]; eigen: string } {
  const waarden = new Set(k.opties.map((o) => o.waarde));
  const gekozen = k.vooringevuld.filter((v) => waarden.has(v));
  const eigen = k.vooringevuld.find((v) => !waarden.has(v)) ?? "";
  return { gekozen: k.meerkeuze ? gekozen : gekozen.slice(0, 1), eigen };
}

/** Wat er bij een klik in het gesprek komt te staan: de leesbare weergave van het antwoord. graph-qa
 *  leest de `intake_actie`, niet deze tekst; ze staat er voor de jurist en voor de historie. */
export function antwoordTekst(k: Vraagkaart, actie: IntakeActie): string {
  if (actie.actie === "aanmaken") return "Maak het werkgebied aan.";
  if (actie.actie === "afbreken") return "Stop met samenstellen.";
  if (actie.actie === "overslaan") return "Sla deze vraag over.";
  if (actie.actie === "wijzig") return `Terug naar ${STAP_NAAM[actie.naar as IntakeStap] ?? "de vorige vraag"}.`;
  const labels = (actie.keuzes ?? []).map((w) => k.opties.find((o) => o.waarde === w)?.label ?? w);
  return [...labels, ...(actie.tekst?.trim() ? [actie.tekst.trim()] : [])].join("; ") || "—";
}

/** Een antwoord-klik: de keuzes, en eigen tekst alleen als die er is. Zonder iets is er geen antwoord. */
export function antwoordActie(k: Vraagkaart, gekozen: string[], eigen: string): IntakeActie | undefined {
  const t = eigen.trim();
  if (!gekozen.length && !t) return undefined;
  return { intake_id: k.intake_id, stap: k.stap, actie: "antwoord", keuzes: gekozen, ...(t ? { tekst: t } : {}) };
}

/** Hoe de samenvatting een stap noemt, voor *Aanpassen*. */
export const STAP_NAAM: Record<IntakeStap, string> = {
  naam: "de naam",
  analysevraag: "de analysevraag",
  regelingen: "de regelingen",
  onderdelen: "de onderdelen",
  buiten: "wat erbuiten valt",
  samenvatting: "de samenvatting",
};

export function parseAntwoordOp(ruw: unknown): AntwoordOp | undefined {
  if (!ruw || typeof ruw !== "object") return undefined;
  const r = ruw as Record<string, unknown>;
  const intake_id = tekst(r.intake_id), stap = tekst(r.stap), actie = tekst(r.actie) || "antwoord";
  if (!/^[A-Za-z0-9-]{1,64}$/.test(intake_id) || !STAP_SET.has(stap)) return undefined;
  if (!["antwoord", "overslaan", "wijzig", "aanmaken", "afbreken"].includes(actie)) return undefined;
  return { intake_id, stap: stap as IntakeStap, actie: actie as IntakeActie["actie"] };
}

/** De stap vóór deze (‹). Vanaf de samenvatting is dat de laatste vraag. */
export function vorigeStap(k: Vraagkaart): IntakeStap | undefined {
  if (!k.terug) return undefined;
  if (k.stap === "samenvatting") return STAPPEN[STAPPEN.length - 1];
  const i = STAPPEN.indexOf(k.stap as (typeof STAPPEN)[number]);
  return i > 0 ? STAPPEN[i - 1] : undefined;
}

/** Is dit de laatste vraag vóór de samenvatting? Dan heet de knop *Verzend*. */
export function isLaatsteVraag(k: Vraagkaart): boolean {
  return k.stap === STAPPEN[STAPPEN.length - 1];
}

/** Eén vraag met het antwoord erop, voor de Vragen-kaart in de thread. */
export interface VraagPaar {
  stap: IntakeStap;
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
        const eerder = huidig.paren.findIndex((p) => p.stap === k.stap);
        if (eerder >= 0) huidig.paren.splice(eerder);
        huidig.paren.push({ stap: k.stap, vraag: k.vraag, antwoord: x.tekst ?? "",
          overgeslagen: x.antwoordOp.actie === "overslaan" });
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
