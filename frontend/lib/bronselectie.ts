// De bronselectie per deelvraag (spoor J; api `app/bronselectie.py`, `GET /v1/werkgebieden/{id}/bronselectie`).
//
// Lex begeleidt de bronselectie in het gesprek met vraagkaarten (`modus: "bronselectie"`, `lib/vraagkaart.ts`);
// de stand – per deelvraag de voortgang, de bronnen met hun rol bij díé deelvraag, de voorstellen en hun stand
// hier, de onderzoekspunten – staat bij de api. Het paneel naast het gesprek en de pagina Bronselectie lezen
// hetzelfde overzicht. De voortgang is de stand van het wérk; de rijen van de deelvragen elders tonen haar ook
// (`deelvraagStand`, spoor K): begrippen horen bij het werkgebied, niet bij een deelvraag.
//
// Pure functies, zodat ze zonder DOM te testen zijn (lib/bronselectie.test.ts).

export type Voortgang = "niet_gestart" | "in_behandeling" | "voorlopig_afgerond" | "beoordeeld";
/** `niet_gekozen`: bij het beantwoorden van het kaartje niet aangevinkt (de api leidt het af uit de fase). Er is
 *  geen *later*: wie de vragen doorloopt, kiest; opnieuw doorlopen maakt er weer een keuze van. */
export type KandidaatStand = "voorgesteld" | "niet_gekozen" | "uitgesloten" | "opgenomen" | "onbekend";
/** De vier zoekvragen van de bronselectie (skill `zoekvragen-bronselectie.md`). */
export type Zoekvraag = "a" | "b" | "c" | "d";
export const ZOEKVRAAG_LABEL: Record<Zoekvraag, string> = {
  a: "bestaansrecht", b: "rechtsgeldigheid", c: "rechtsgevolgen", d: "nadere invulling",
};
/** "zoekvraag a · bestaansrecht" – één label per zoekvraag, in de volgorde a–d. */
export const zoekvraagZin = (z: Zoekvraag) => `zoekvraag ${z} · ${ZOEKVRAAG_LABEL[z]}`;

export type BewijsSoort = "grondslag" | "genoemd" | "verwijzing" | "definitie" | "structuur" | "tekst" | "gelijkenis";

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
  /** Bij welke zoekvraag (a–d) het voorstel hoort, uit het bewijs (`detail.zoekvraag`); leeg als geen. */
  zoekvragen: Zoekvraag[];
  stand: KandidaatStand;
  /** De uitsluiting geldt voor het hele werkgebied. */
  overal: boolean;
  /** Al opgenomen bij een andere deelvraag. */
  elders_opgenomen: boolean;
  reden: string;
  /** Opgenomen is een lid of onderdeel van de kandidaat, niet het geheel (per lid opnemen); anders leeg. */
  opgenomen_delen: { bron_iri: string; label: string }[];
}

/** De leden van een artikel uit zijn samenhang (`GET samenhang`): wat het artikel in de opbouw direct bevat, in de
 *  volgorde van de api. Leeg voor een bepaling zonder leden – dan valt er niets apart op te nemen. */
export function ledenVan(s: { knopen: { id: string; soort: string; label: string }[]; relaties: { bron: string; doel: string; soort: string }[] },
  artikelIri: string): { bron_iri: string; label: string }[] {
  const kind = new Set(s.relaties.filter((r) => r.soort === "bevat" && r.bron === artikelIri).map((r) => r.doel));
  return s.knopen.filter((k) => k.soort === "lid" && kind.has(k.id)).map((k) => ({ bron_iri: k.id, label: k.label }));
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
  telling: { voorgesteld: number; niet_gekozen: number; uitgesloten: number; opgenomen: number };
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

/** De stand van één deelvraag in een rij (spoor K): de voortgang van haar bronselectie, met kleur alleen als die
 *  een oordeel draagt. Zonder overzicht (nog niet geladen, of een storing) geen label. */
export function deelvraagStand(d: Pick<DeelvraagSelectie, "status" | "opnieuw_bekijken"> | undefined):
  { label: string; toon: "groen" | "geel" | "neutraal" } | null {
  if (!d) return null;
  return { label: d.opnieuw_bekijken ? "Opnieuw bekijken" : VOORTGANG_LABEL[d.status], toon: voortgangToon(d) };
}

/** "3 bronnen", "1 bron", "nog geen bronnen". */
export function bronnenZin(n: number): string {
  return n ? `${n} ${n === 1 ? "bron" : "bronnen"}` : "nog geen bronnen";
}

export const STAND_LABEL: Record<KandidaatStand, string> = {
  voorgesteld: "voorstel", niet_gekozen: "niet gekozen", uitgesloten: "uitgesloten", opgenomen: "opgenomen",
  onbekend: "onbekende stand, herlaad de pagina",
};

/** Een tekstuele overeenkomst is geen bewijs van noodzaak; een verwijzing of definitie in de graaf wel van
 *  een relatie. Zo noemt de werkplek het, ook als Lex het al op het kaartje zei. */
export const BEWIJS_LABEL: Record<BewijsSoort, string> = {
  grondslag: "grondslag van de gebeurtenis",
  genoemd: "zelf genoemd",
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
// Een stand die de werkplek niet kent (een nieuwere api) is geen voorstel: `onbekend` toont dat en biedt geen keuze aan.
const STANDEN = ["voorgesteld", "niet_gekozen", "uitgesloten", "opgenomen", "onbekend"] as const;
const BEWIJZEN = ["grondslag", "genoemd", "verwijzing", "definitie", "structuur", "tekst", "gelijkenis"] as const;

/** De zoekvragen in het bewijs van een voorstel (`detail.zoekvraag`, a–d), elk één keer en op volgorde. */
function zoekvragenUit(bewijs: unknown): Zoekvraag[] {
  if (!Array.isArray(bewijs)) return [];
  const gezien = new Set(bewijs.map((b) => obj(obj(b).detail).zoekvraag).filter((z): z is Zoekvraag =>
    typeof z === "string" && z in ZOEKVRAAG_LABEL));
  return (["a", "b", "c", "d"] as const).filter((z) => gezien.has(z));
}

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
          // De api geeft de zoekvragen; een oude versie van het artefact draagt nog het hele bewijs.
          zoekvragen: Array.isArray(k.zoekvragen) ? k.zoekvragen.filter((z): z is Zoekvraag => typeof z === "string" && z in ZOEKVRAAG_LABEL) : zoekvragenUit(k.bewijs),
          stand: een(k.stand, STANDEN, "onbekend"), overal: k.overal === true, elders_opgenomen: k.elders_opgenomen === true,
          reden: tekst(k.reden),
          opgenomen_delen: Array.isArray(k.opgenomen_delen) ? k.opgenomen_delen.flatMap((x) => {
            const o = obj(x);
            return tekst(o.bron_iri) ? [{ bron_iri: tekst(o.bron_iri), label: tekst(o.label) }] : [];
          }) : [] }] : [];
      }) : [],
      telling: { voorgesteld: getal(t.voorgesteld), niet_gekozen: getal(t.niet_gekozen), uitgesloten: getal(t.uitgesloten),
        opgenomen: getal(t.opgenomen) },
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

/** Een besluit over de bronselectie, waar ook genomen (paneel, *Bepaling toevoegen*): het compacte kaartje in het
 *  gesprek en het paneel laden dan opnieuw. Eén venster-event, zodat ze elkaar niet hoeven te kennen. */
export const BRONSELECTIE_GEWIJZIGD = "wa:bronselectie-gewijzigd";

export function meldBronselectieGewijzigd(werkgebiedId: string): void {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(BRONSELECTIE_GEWIJZIGD, { detail: werkgebiedId }));
}

/** Wat het compacte kaartje telt (3 nov 2026), zoals graph-qa het kaartje opbouwt: bij de kernbepalingen de
 *  kandidaten met rol kern, bij wat eraan hangt de rest. Open = nog voorgesteld of eerder niet gekozen. */
/** De voorstellen in de volgorde van het werk: eerst wat nu op een besluit wacht, dan wat uitgesloten is. Wat je in een
 *  eerdere stap niet koos, staat apart: het telt niet mee op het kaartje van deze stap, en kan alsnog opgenomen worden. */
export function ordenVoorstellen<T extends Pick<KandidaatHier, "stand">>(kandidaten: readonly T[]): { open: T[]; nietGekozen: T[] } {
  const open = kandidaten.filter((k) => k.stand !== "niet_gekozen");
  return { open: [...open.filter((k) => k.stand === "voorgesteld"), ...open.filter((k) => k.stand !== "voorgesteld")],
    nietGekozen: kandidaten.filter((k) => k.stand === "niet_gekozen") };
}

export function paneelTelling(d: Pick<DeelvraagSelectie, "kandidaten">, stap: string): { kandidaten: number; opgenomen: number } {
  const kern = stap === "bs_bepalingen";
  const hier = d.kandidaten.filter((k) => (k.rol === "kern") === kern);
  return { kandidaten: hier.filter((k) => k.stand === "voorgesteld" || k.stand === "niet_gekozen").length,
    opgenomen: hier.filter((k) => k.stand === "opgenomen").length };
}
