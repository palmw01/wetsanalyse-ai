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
      ? [{ label: tekst(x.label), waarde: tekst(x.waarde), bron: x.bron && typeof x.bron === "object" ? x.bron as Record<string, unknown> : {} }]
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
  if (actie.actie === "wijzig") return `Pas ${STAP_NAAM[actie.naar as IntakeStap] ?? "dit"} aan.`;
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

/** Welk kaartje in de thread nog te bedienen is: het laatste, zolang er daarna geen werkgebied uit
 *  deze intake is aangemaakt. Eerdere kaartjes tonen alleen wat er gevraagd werd. */
export function actiefKaartje<T extends { id: string; vraagkaart?: Vraagkaart; werkgebiedAangemaakt?: boolean }>(
  items: T[],
): string | undefined {
  for (let i = items.length - 1; i >= 0; i--) {
    if (items[i].werkgebiedAangemaakt) return undefined;
    if (items[i].vraagkaart) return items[i].id;
  }
  return undefined;
}
