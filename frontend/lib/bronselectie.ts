// De bronselectie per deelvraag (spoor J; api `app/bronselectie.py`, `GET /v1/werkgebieden/{id}/bronselectie`).
//
// Lex begeleidt de bronselectie in het gesprek met vraagkaarten (`modus: "bronselectie"`, `lib/vraagkaart.ts`);
// de stand – per deelvraag de voortgang, de bronnen met hun rol bij díé deelvraag, de voorstellen en hun stand
// hier, de onderzoekspunten – staat bij de api. Het paneel naast het gesprek en de pagina Bronselectie lezen
// hetzelfde overzicht. De voortgang is de stand van het wérk, niet de dekkingscheck met begrippen (`deelvragen.ts`).
//
// Pure functies, zodat ze zonder DOM te testen zijn (lib/bronselectie.test.ts).

export type Voortgang = "niet_gestart" | "in_behandeling" | "voorlopig_afgerond" | "beoordeeld";
export type KandidaatStand = "voorgesteld" | "later" | "uitgesloten" | "opgenomen";
export type BewijsSoort = "verwijzing" | "definitie" | "structuur" | "tekst" | "gelijkenis";

export interface BronHier {
  selectie_id: string;
  bron_iri: string;
  label: string;
  /** De rol bij deze deelvraag (die van de selectie als er geen eigen rol is). */
  rol: "analyseren" | "context";
}

export interface KandidaatHier {
  id: string;
  bron_iri: string;
  label: string;
  rol: "kern" | "afhankelijkheid" | "aanverwant";
  bewijs_soorten: BewijsSoort[];
  stand: KandidaatStand;
  /** Het besluit geldt voor het hele werkgebied (een uitsluiting of *later* van vóór spoor J). */
  overal: boolean;
  /** Al opgenomen bij een andere deelvraag. */
  elders_opgenomen: boolean;
  reden: string;
}

export interface DeelvraagSelectie {
  id: string;
  nr: number;
  vraag: string;
  status: Voortgang;
  fase: "kern" | "afhankelijkheden" | "afronden";
  open_punten: { tekst: string }[];
  revisie: number;
  gewijzigd_door: string | null;
  gewijzigd: string | null;
  opnieuw_bekijken: boolean;
  klaar: boolean;
  bronnen: BronHier[];
  kandidaten: KandidaatHier[];
  telling: { voorgesteld: number; later: number; uitgesloten: number; opgenomen: number };
  beoordelen: { mag: boolean; redenen: string[] };
}

export interface Zoekdekking {
  gezocht: boolean;
  verouderd: boolean;
  volledig: boolean;
  onvolledig: string[];
  reden: string;
}

export interface BronselectieOverzicht {
  werkgebied_id: string;
  naam: string;
  revisie: number;
  modus: "deelvragen" | "analysevraag";
  deelvragen: DeelvraagSelectie[];
  actief: string | null;
  volgende: string | null;
  alle_klaar: boolean;
  zonder_deelvraag: { id: string; bron_iri: string; label: string }[];
  zoekdekking: Zoekdekking;
}

export const VOORTGANG_LABEL: Record<Voortgang, string> = {
  niet_gestart: "Nog niet gestart",
  in_behandeling: "In behandeling",
  voorlopig_afgerond: "Voorlopig afgerond",
  beoordeeld: "Beoordeeld",
};

/** Kleur alleen waar de stand een oordeel draagt: beoordeeld is groen, opnieuw bekijken geel. */
export function voortgangToon(d: Pick<DeelvraagSelectie, "status" | "opnieuw_bekijken">): "groen" | "geel" | "neutraal" {
  if (d.opnieuw_bekijken) return "geel";
  return d.status === "beoordeeld" ? "groen" : "neutraal";
}

export const STAND_LABEL: Record<KandidaatStand, string> = {
  voorgesteld: "voorstel", later: "later", uitgesloten: "uitgesloten", opgenomen: "opgenomen",
};

/** Een tekstuele overeenkomst is geen bewijs van noodzaak; een verwijzing of definitie in de graaf wel van
 *  een relatie. Zo noemt de werkplek het, ook als Lex het al op het kaartje zei. */
export const BEWIJS_LABEL: Record<BewijsSoort, string> = {
  verwijzing: "verwijzing in de wet",
  definitie: "definitie van een term",
  structuur: "zelfde deel van de regeling",
  tekst: "tekstuele overeenkomst",
  gelijkenis: "lijkt op de tekst (zwak)",
};

const tekst = (v: unknown) => (typeof v === "string" ? v : "");
const getal = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : 0);
const obj = (v: unknown) => (v && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : {});
const een = <T extends string>(v: unknown, mag: readonly T[], anders: T): T => (mag.includes(v as T) ? v as T : anders);

const VOORTGANGEN = ["niet_gestart", "in_behandeling", "voorlopig_afgerond", "beoordeeld"] as const;
const STANDEN = ["voorgesteld", "later", "uitgesloten", "opgenomen"] as const;
const BEWIJZEN = ["verwijzing", "definitie", "structuur", "tekst", "gelijkenis"] as const;

/** Streng waar het iets uitmaakt (een deelvraag zonder id telt niet), vergevend in de details. */
export function parseBronselectie(ruw: unknown): BronselectieOverzicht | undefined {
  const r = obj(ruw);
  if (!tekst(r.werkgebied_id) || !Array.isArray(r.deelvragen)) return undefined;
  const deelvragen = r.deelvragen.flatMap((x): DeelvraagSelectie[] => {
    const d = obj(x);
    if (!tekst(d.id)) return [];
    const t = obj(d.telling), b = obj(d.beoordelen);
    return [{
      id: tekst(d.id), nr: getal(d.nr), vraag: tekst(d.vraag),
      status: een(d.status, VOORTGANGEN, "niet_gestart"),
      fase: een(d.fase, ["kern", "afhankelijkheden", "afronden"] as const, "kern"),
      open_punten: Array.isArray(d.open_punten) ? d.open_punten.flatMap((p) => tekst(obj(p).tekst) ? [{ tekst: tekst(obj(p).tekst) }] : []) : [],
      revisie: getal(d.revisie), gewijzigd_door: tekst(d.gewijzigd_door) || null, gewijzigd: tekst(d.gewijzigd) || null,
      opnieuw_bekijken: d.opnieuw_bekijken === true, klaar: d.klaar === true,
      bronnen: Array.isArray(d.bronnen) ? d.bronnen.flatMap((y): BronHier[] => {
        const s = obj(y);
        return tekst(s.selectie_id) ? [{ selectie_id: tekst(s.selectie_id), bron_iri: tekst(s.bron_iri), label: tekst(s.label),
          rol: s.rol === "context" ? "context" : "analyseren" }] : [];
      }) : [],
      kandidaten: Array.isArray(d.kandidaten) ? d.kandidaten.flatMap((y): KandidaatHier[] => {
        const k = obj(y);
        return tekst(k.id) ? [{ id: tekst(k.id), bron_iri: tekst(k.bron_iri), label: tekst(k.label),
          rol: een(k.rol, ["kern", "afhankelijkheid", "aanverwant"] as const, "aanverwant"),
          bewijs_soorten: Array.isArray(k.bewijs_soorten) ? k.bewijs_soorten.filter((s): s is BewijsSoort => BEWIJZEN.includes(s as BewijsSoort)) : [],
          stand: een(k.stand, STANDEN, "voorgesteld"), overal: k.overal === true, elders_opgenomen: k.elders_opgenomen === true,
          reden: tekst(k.reden) }] : [];
      }) : [],
      telling: { voorgesteld: getal(t.voorgesteld), later: getal(t.later), uitgesloten: getal(t.uitgesloten), opgenomen: getal(t.opgenomen) },
      beoordelen: { mag: b.mag === true, redenen: Array.isArray(b.redenen) ? b.redenen.filter((x): x is string => typeof x === "string") : [] },
    }];
  });
  const z = obj(r.zoekdekking);
  return {
    werkgebied_id: tekst(r.werkgebied_id), naam: tekst(r.naam), revisie: getal(r.revisie),
    modus: r.modus === "analysevraag" ? "analysevraag" : "deelvragen", deelvragen,
    actief: tekst(r.actief) || null, volgende: tekst(r.volgende) || null, alle_klaar: r.alle_klaar === true,
    zonder_deelvraag: Array.isArray(r.zonder_deelvraag) ? r.zonder_deelvraag.flatMap((y) => {
      const k = obj(y);
      return tekst(k.id) ? [{ id: tekst(k.id), bron_iri: tekst(k.bron_iri), label: tekst(k.label) }] : [];
    }) : [],
    zoekdekking: { gezocht: z.gezocht === true, verouderd: z.verouderd === true, volledig: z.volledig === true,
      onvolledig: Array.isArray(z.onvolledig) ? z.onvolledig.filter((x): x is string => typeof x === "string") : [],
      reden: tekst(z.reden) },
  };
}

/** Wat er over het zoeken te zeggen is. Leeg = er is gezocht, op deze stand, en niets was afgekapt. */
export function zoekBeperkingen(z: Zoekdekking): string[] {
  const uit: string[] = [];
  if (!z.gezocht) uit.push("Er is nog niet gezocht" + (z.reden ? `: ${z.reden}` : "") + ".");
  if (z.verouderd) uit.push("De laatste zoekopdracht hoort bij een eerdere stand van het werkgebied.");
  if (z.onvolledig.length) uit.push(`Niet alles is doorzocht (${z.onvolledig.join(", ")}): de voorstellen kunnen onvolledig zijn.`);
  return uit;
}

/** "n van m afgerond" over de deelvragen; afgerond = voorlopig afgerond of beoordeeld, op de scope van nu. */
export function voortgangZin(o: BronselectieOverzicht): string {
  const klaar = o.deelvragen.filter((d) => d.klaar).length;
  if (o.modus === "analysevraag") return o.deelvragen[0]?.klaar ? "Afgerond" : VOORTGANG_LABEL[o.deelvragen[0]?.status ?? "niet_gestart"];
  return `${klaar} van ${o.deelvragen.length} ${o.deelvragen.length === 1 ? "deelvraag" : "deelvragen"} afgerond`;
}

/** De slotzin van de controle: nooit "volledig", altijd binnen de afbakening en wat er beschikbaar was. */
export function slotZin(o: BronselectieOverzicht): string {
  const alles = o.deelvragen.every((d) => d.status === "beoordeeld" && !d.opnieuw_bekijken);
  return alles && !zoekBeperkingen(o.zoekdekking).length
    ? "De bronselectie is beoordeeld binnen de vastgestelde afbakening en de beschikbare bronnen. Dat is geen oordeel dat de analyse juridisch volledig is."
    : "De bronselectie is nog niet beoordeeld binnen de afbakening; hierboven staat wat openstaat.";
}
