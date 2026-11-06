// Lex stelt met de analist een werkgebied samen (startactiviteit a en activiteit 1, graph-qa
// `agent/werkgebied_intake.py`): naam, aanleiding, context, doel, analysevraag, praktijkvoorbeeld,
// deelvragen, wat erbuiten valt, de regelingen (het zoekbereik) en de gebeurtenis. De bronnen per deelvraag komen
// daarna uit de bronselectie (4 nov 2026: één lijn, je kiest ze één keer). Een oud kaartje van de stap `bepalingen`
// (met `deel`) is nog te lezen.
//
// Elke vraag komt als kaartje: een `vraagkaart`-event, en hetzelfde kaartje op het bewaarde bericht
// (`Bericht.vraagkaart`, api `gesprek_contracts.Vraagkaart`), zodat het na herladen nog te
// beantwoorden is. Een klik start een gewone beurt met `intake_actie`; de volgorde van de vragen is
// van graph-qa, niet van de werkplek. De werkplek kiest alleen welk kaartje nog bedienbaar is: het
// laatste in de thread.
//
// Hetzelfde kaartje vult ook het dossier van een bestaand werkgebied aan (`modus: "aanvullen"`): alleen de
// gevraagde velden, vooringevuld, en een samenvatting toen → nu met *Opslaan* (`actie: "opslaan"`).
//
// En dezelfde kaartjes dragen de bronselectie per deelvraag (spoor J, `modus: "bronselectie"`, graph-qa
// `agent/bronselectie.py`): de stand staat bij de api, het kaartje noemt zijn deelvraag (`deelvraag_id`), en
// "n van N" is de deelvraag van het totaal.
//
// Pure functies, zodat ze zonder DOM te testen zijn (lib/vraagkaart.test.ts).

export const STAPPEN = ["naam", "aanleiding", "context", "doel", "analysevraag", "praktijkvoorbeeld", "deelvragen",
  "buiten", "regelingen", "gebeurtenis"] as const;
/** De kaartjes van de bronselectie (graph-qa `bronselectie.KAARTSTAPPEN`). */
export const BRONSELECTIE_STAPPEN = ["bs_gebeurtenis", "bs_kies", "bs_bepalingen", "bs_afhankelijkheden", "bs_afronden", "bs_verder",
  "bs_toevoegen"] as const;
/** De keuzekaart van de begrippen-agent (`modus: "begrip"`, graph-qa `kaart_beurt.keuzekaart`). */
export const BEGRIP_STAPPEN = ["begrip_kiezen"] as const;
/** `thema` (spoor I7) is een kaartje van het aanvullen alleen: het samenstellen kent het niet (`STAPPEN`). */
/** `bepalingen`: een kaartje van vóór 4 nov 2026, alleen nog om te lezen. */
export type IntakeStap = (typeof STAPPEN)[number] | "thema" | "samenvatting" | "bepalingen" | (typeof BRONSELECTIE_STAPPEN)[number]
  | (typeof BEGRIP_STAPPEN)[number];

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

/** Wat één invoerregel op een kaartje is (`Vraagkaart.regel`, 4 nov 2026): "deelvraag", "bepaling". */
export interface Regel { enkel: string; voorbeeld: string }

/** De teksten van de invoerregels (`MeerRegels`): zonder `regel` de deelvragen, zoals het altijd was. */
export function regelNamen(r: Regel | null) {
  const enkel = r?.enkel || "deelvraag";
  return {
    enkel,
    label: `Eigen ${enkel}`,
    lijst: `Je eigen ${enkel}en`,
    eerste: r?.voorbeeld ? `Bijv. ‘${r.voorbeeld}’` : `Typ een eigen ${enkel}…`,
    volgende: `Nog een ${enkel}…`,
  };
}

export interface Vraagkaart {
  intake_id: string;
  /** Een werkgebied samenstellen, het dossier van een bestaand werkgebied aanvullen, de bronselectie, of welk begrip. */
  modus: "samenstellen" | "aanvullen" | "bronselectie" | "begrip";
  /** Bij de bronselectie: de deelvraag van het kaartje (`analysevraag` zonder deelvragen; leeg bij de keuze). */
  deelvraag_id: string;
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
  /** Meer dan één eigen antwoord: één regel is één ding, de dock biedt "+ Nog een …" en stuurt `teksten`. */
  meer_tekst: boolean;
  /** Wat één regel is; leeg = de deelvragen. */
  regel: Regel | null;
  overslaanbaar: boolean;
  /** Wat Lex uit je eerste zin haalde: voorgeselecteerd, nooit stil aangenomen. */
  vooringevuld: string[];
  /** Bij `soort: "samenvatting"`: wat er aangemaakt wordt. */
  samenvatting: Samenvatting | null;
  /** ‹: er is een eerdere stap. */
  terug: boolean;
  /** ›: deze stap had al een antwoord (na terugbladeren). */
  beantwoord: boolean;
  /** `paneel` (bronselectie, 3 nov 2026): een compact kaartje dat naar het paneel verwijst; beslissen gebeurt
   *  daar, *Klaar* (`actie: klaar`) gaat verder. `telling` komt dan uit `samenvatting`. */
  weergave: "kaart" | "paneel";
  telling: { kandidaten: number; opgenomen: number } | null;
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
  /** Het zoekbereik (de namen van de regelingen) en de gebeurtenis; een oud kaartje droeg `bronnen`. */
  regelingen: string[];
  gebeurtenis: string;
  bronnen: string[];
  /** Bij het aanvullen: alleen wat verandert. Leeg = er verandert niets, en er is niets op te slaan. */
  wijzigingen: Wijziging[];
}

/** Eén veld van het dossier dat het aanvullen verandert: wat er stond, en wat het wordt. */
export interface Wijziging {
  veld: string;
  label: string;
  toen: string;
  nu: string;
}

/** Op het user-bericht van een klik (api `Bericht.intake_antwoord`): zo herkent de thread een antwoord. */
export interface AntwoordOp {
  intake_id: string;
  stap: IntakeStap;
  deel?: number;
  actie: IntakeActie["actie"];
  deelvraag_id?: string;
}

/** Een klik op een kaartje, zoals graph-qa hem verwacht (`ChatRequest.intake_actie`). */
export interface IntakeActie {
  intake_id: string;
  stap: IntakeStap;
  /** Bij de bepalingen: het deel van het kaartje; een ander deel is een oud kaartje. */
  deel?: number;
  actie: "antwoord" | "overslaan" | "wijzig" | "aanmaken" | "opslaan" | "afbreken" | "klaar";
  keuzes?: string[];
  tekst?: string;
  /** Meer dan één eigen antwoord (`meer_tekst`). */
  teksten?: string[];
  naar?: string;
  naar_deel?: number;
  /** Bij de bronselectie: de deelvraag van het kaartje. */
  deelvraag_id?: string;
}

const tekst = (v: unknown) => (typeof v === "string" ? v : "");
const lijst = (v: unknown) => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);
// `bepalingen`: een bewaard kaartje van vóór 4 nov 2026 blijft leesbaar in de thread.
const STAP_SET = new Set<string>([...STAPPEN, "thema", "samenvatting", "bepalingen", ...BRONSELECTIE_STAPPEN, ...BEGRIP_STAPPEN]);
const DEELVRAAG_ID = /^[A-Za-z0-9-]{0,64}$/;

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
  const wijzigingen = s && Array.isArray(s.wijzigingen) ? s.wijzigingen.flatMap((w): Wijziging[] => {
    const x = (w ?? {}) as Record<string, unknown>;
    return tekst(x.veld) && tekst(x.label)
      ? [{ veld: tekst(x.veld), label: tekst(x.label), toen: tekst(x.toen), nu: tekst(x.nu) }] : [];
  }) : [];
  return {
    intake_id, stap: stap as IntakeStap, vraag, deel,
    modus: r.modus === "aanvullen" || r.modus === "bronselectie" || r.modus === "begrip" ? r.modus : "samenstellen",
    deelvraag_id: DEELVRAAG_ID.test(tekst(r.deelvraag_id)) ? tekst(r.deelvraag_id) : "",
    soort: r.soort === "samenvatting" ? "samenvatting" : "vraag",
    nr: getal(r.nr, 1), totaal: getal(r.totaal, STAPPEN.length),
    toelichting: tekst(r.toelichting),
    opties,
    meerkeuze: r.meerkeuze === true,
    vrije_tekst: r.vrije_tekst !== false,
    meer_tekst: r.meer_tekst === true,
    regel: (() => {
      const g = r.regel && typeof r.regel === "object" ? r.regel as Record<string, unknown> : null;
      return g && tekst(g.enkel) ? { enkel: tekst(g.enkel).slice(0, 40), voorbeeld: tekst(g.voorbeeld).slice(0, 200) } : null;
    })(),
    overslaanbaar: r.overslaanbaar === true,
    vooringevuld: Array.isArray(r.vooringevuld) ? r.vooringevuld.filter((v): v is string => typeof v === "string") : [],
    terug: r.terug === true,
    beantwoord: r.beantwoord === true,
    weergave: r.weergave === "paneel" ? "paneel" : "kaart",
    telling: r.weergave === "paneel" && s ? {
      kandidaten: typeof s.kandidaten === "number" ? s.kandidaten : 0,
      opgenomen: typeof s.opgenomen === "number" ? s.opgenomen : 0,
    } : null,
    samenvatting: s && r.soort === "samenvatting" ? {
      naam: tekst(s.naam), aanleiding: tekst(s.aanleiding), context: tekst(s.context), doel: tekst(s.doel),
      analysevraag: tekst(s.analysevraag), praktijkvoorbeeld: tekst(s.praktijkvoorbeeld),
      deelvragen: lijst(s.deelvragen), afbakening: tekst(s.afbakening), regelingen: lijst(s.regelingen),
      gebeurtenis: tekst(s.gebeurtenis), bronnen: lijst(s.bronnen), wijzigingen,
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
  if (actie.actie === "opslaan") return "Sla de wijziging op.";
  if (actie.actie === "afbreken") {
    return k.modus === "aanvullen" ? "Stop met aanvullen." : k.modus === "bronselectie" ? "Zet de bronselectie even stil."
      : k.modus === "begrip" ? "Laat maar." : "Stop met samenstellen.";
  }
  if (actie.actie === "overslaan") {
    if (k.stap === "bs_gebeurtenis") return "Zonder gebeurtenis verder.";
    return k.modus === "bronselectie" ? "Niets erbij; verder." : "Sla deze vraag over.";
  }
  if (actie.actie === "klaar") {
    return actie.tekst?.trim() || (k.stap === "bs_afhankelijkheden" ? "Klaar; ronden we af." : "Klaar met de kernbepalingen; verder.");
  }
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
    keuzes: gekozen, ...(t ? { tekst: t } : {}), ...(ts.length ? { teksten: ts } : {}),
    ...(k.deelvraag_id ? { deelvraag_id: k.deelvraag_id } : {}) };
}

/** Hoe de samenvatting een stap noemt, voor *Aanpassen*. */
export const STAP_NAAM: Record<IntakeStap, string> = {
  naam: "de naam",
  aanleiding: "de aanleiding",
  context: "de context",
  doel: "het doel",
  analysevraag: "de analysevraag",
  praktijkvoorbeeld: "het praktijkvoorbeeld",
  thema: "het thema",
  deelvragen: "de deelvragen",
  regelingen: "de regelingen",
  bepalingen: "de bepalingen",
  gebeurtenis: "de gebeurtenis",
  buiten: "wat erbuiten valt",
  samenvatting: "de samenvatting",
  bs_gebeurtenis: "de gebeurtenis",
  bs_kies: "de keuze van de deelvraag",
  bs_bepalingen: "de kernbepalingen",
  bs_afhankelijkheden: "wat eraan hangt",
  bs_afronden: "het afronden",
  bs_verder: "hoe we verder gaan",
  bs_toevoegen: "de bepaling",
  begrip_kiezen: "het begrip",
};

export function parseAntwoordOp(ruw: unknown): AntwoordOp | undefined {
  if (!ruw || typeof ruw !== "object") return undefined;
  const r = ruw as Record<string, unknown>;
  const intake_id = tekst(r.intake_id), stap = tekst(r.stap), actie = tekst(r.actie) || "antwoord";
  if (!/^[A-Za-z0-9-]{1,64}$/.test(intake_id) || !STAP_SET.has(stap)) return undefined;
  if (!["antwoord", "overslaan", "wijzig", "aanmaken", "opslaan", "afbreken", "klaar"].includes(actie)) return undefined;
  const deel = typeof r.deel === "number" && Number.isInteger(r.deel) && r.deel >= 0 ? r.deel : undefined;
  const dv = tekst(r.deelvraag_id);
  return { intake_id, stap: stap as IntakeStap, ...(deel !== undefined ? { deel } : {}),
    actie: actie as IntakeActie["actie"], ...(dv && DEELVRAAG_ID.test(dv) ? { deelvraag_id: dv } : {}) };
}

/** De gegevens van een klik, zoals ze op het user-bericht komen (api `IntakeAntwoord`). */
export function antwoordOp(a: IntakeActie): AntwoordOp {
  return { intake_id: a.intake_id, stap: a.stap, ...(typeof a.deel === "number" ? { deel: a.deel } : {}), actie: a.actie,
    ...(a.deelvraag_id ? { deelvraag_id: a.deelvraag_id } : {}) };
}

/** Het kaartje vóór dit (‹): de vorige stap; vanaf de samenvatting de laatste (de gebeurtenis). Bij het aanvullen
 *  kent de werkplek de gevraagde stappen niet: graph-qa neemt dan de laatste gevraagde stap die niet na deze komt. */
export function vorige(k: Vraagkaart): { naar: IntakeStap; naar_deel?: number } | undefined {
  if (!k.terug) return undefined;
  if (k.stap === "samenvatting") return { naar: STAPPEN[STAPPEN.length - 1] };
  // Het thema staat bij het aanvullen na het praktijkvoorbeeld; vanaf de afbakening vraagt de werkplek de
  // deelvragen, en graph-qa maakt daar het thema van (`VOLGORDE_AANVULLEN`).
  if (k.stap === "thema") return { naar: "praktijkvoorbeeld" };
  const i = STAPPEN.indexOf(k.stap as (typeof STAPPEN)[number]);
  return i > 0 ? { naar: STAPPEN[i - 1] } : undefined;
}

/** Is dit de laatste vraag vóór de samenvatting? Dan heet de knop *Verzend*. Bij het aanvullen is dat de
 *  laatste gevraagde stap. */
export function isLaatsteVraag(k: Vraagkaart): boolean {
  // Bij de bronselectie staat elk kaartje op zichzelf: wat erna komt, hangt af van het antwoord.
  if (k.modus === "bronselectie" || k.modus === "begrip") return true;
  if (k.modus === "aanvullen") return k.soort === "vraag" && k.nr >= k.totaal;
  return k.stap === STAPPEN[STAPPEN.length - 1];
}

/** Eén vraag met het antwoord erop, voor de Vragen-kaart in de thread. */
export interface VraagPaar {
  stap: IntakeStap;
  /** Bij de bepalingen: het deel (een paar per deelvraag). */
  deel?: number;
  /** Bij de bronselectie: de deelvraag (een paar per deelvraag en stap). */
  deelvraag_id?: string;
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
        // Bij de bronselectie komt dezelfde stap per deelvraag terug, en ook bij dezelfde deelvraag (verder
        // onderzoeken): dat is een nieuw antwoord in de reeks, geen vervanging van het vorige.
        const eerder = k.modus === "bronselectie" ? -1
          : huidig.paren.findIndex((p) => p.stap === k.stap && p.deel === k.deel?.index);
        if (eerder >= 0) huidig.paren.splice(eerder);
        huidig.paren.push({ stap: k.stap, ...(k.deel ? { deel: k.deel.index } : {}),
          ...(k.deelvraag_id ? { deelvraag_id: k.deelvraag_id } : {}), vraag: k.vraag,
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


/** *Klaar* op het compacte kaartje van de bronselectie (`weergave: paneel`): de besluiten staan al bij de api. */
export function klaarActie(k: Vraagkaart): IntakeActie {
  return { intake_id: k.intake_id, stap: k.stap, actie: "klaar", ...(k.deelvraag_id ? { deelvraag_id: k.deelvraag_id } : {}) };
}

/** De bronselectie stilzetten vanaf het compacte kaartje: dezelfde actie als *Zet de bronselectie stil* op het
 *  gewone kaartje. De stand blijft bij de api bewaard; Lex zegt hoe je verder gaat. */
export function stilActie(k: Vraagkaart): IntakeActie {
  return { intake_id: k.intake_id, stap: k.stap, actie: "afbreken", ...(k.deelvraag_id ? { deelvraag_id: k.deelvraag_id } : {}) };
}

/** Eigen bepalingen op het compacte kaartje, één per regel (`MeerRegels`): Lex zet ze als voorstel in het paneel. */
export function typActie(k: Vraagkaart, regels: string[]): IntakeActie | undefined {
  const ts = regels.map((x) => x.trim()).filter(Boolean);
  return ts.length ? { intake_id: k.intake_id, stap: k.stap, actie: "antwoord", teksten: ts,
    ...(k.deelvraag_id ? { deelvraag_id: k.deelvraag_id } : {}) } : undefined;
}
