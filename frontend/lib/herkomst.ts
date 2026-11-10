/** De herkomst van een bron: welke wet, waar in de wet, welke stand (het bronvenster, PR 1). Eén plek voor het label van een
 *  bepaling, de kop van het paneel en de meldingen over de stand – elke plek die een bepaling noemt gebruikt deze functies,
 *  zodat er nergens "Lid 2" zonder regeling staat of een eigen `${label}, ${regeling}` (`app/herkomst.test.ts`).
 *
 *  Puur: de data komt van de aanroeper (een vindplaats uit het antwoord, `BepalingDetail` uit de api, de toestanden van een
 *  werkgebied). Wat er niet is, blijft weg; er wordt niets geraden. */
import type { AntwoordVindplaats, TekstBij } from "@/lib/antwoord";
import type { BronDoel } from "@/lib/bronDoel";
import { bepalingEnRegeling } from "@/lib/bronnenPerDeelvraag";
import { datumTekst } from "@/lib/graaf/knoopinfo";
import { vindplaatsVan } from "@/lib/samenhang";
import { bronHref, normaliseerJci } from "@/lib/url";

/** Een plek in de opbouw van een regeling (`Structuurdeel` in `api/app/bepaling_graaf_contract.py`). */
export interface Deel { soort: string; nummer: string; titel?: string }

export interface Herkomst {
  /** De bepaling zelf: "Artikel 9, lid 2, onderdeel k". Bij een hele regeling de regeling. */
  bepaling: string;
  /** De citeertitel, anders het BWB-id; leeg als de bepaling de regeling zelf is. */
  regeling: string;
  bwb_id: string;
  /** De plek boven het artikel, kort ("H VI › Afd. 1") en voluit ("Hoofdstuk VI – Aansprakelijkheid › Afdeling 1"). */
  plek: string;
  plekVoluit: string;
  /** Sinds wanneer de tekst in de graaf geldt (ISO), als bekend. */
  stand?: string;
  /** De bepaling op wetten.overheid.nl, met de toestand als die bekend is. */
  href?: string;
}

/** Wat een plek over een bepaling weet. Alles behalve `iri` is optioneel: een chip kent label en regeling, het paneel ook
 *  de plek en de stand. */
export interface HerkomstBron {
  iri: string;
  label?: string;
  regeling?: string;
  jci?: string;
  plaats?: readonly Deel[];
  geldig_vanaf?: string | null;
  /** De publieke link als de api hem gaf (`bwb:bronUrl` of `owl:sameAs`). */
  url?: string;
}

const KORT: Record<string, string> = { hoofdstuk: "H", afdeling: "Afd.", paragraaf: "§", titel: "Titel", deel: "Deel", boek: "Boek" };
const GEEN_PLEK = new Set(["artikel", "lid", "onderdeel", "regeling"]);

function hoofdletter(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** "Hoofdstuk VI – Aansprakelijkheid › Afdeling 1": de plek in gewone woorden, zonder het artikel zelf. */
export function plaatsZin(plaats: readonly Deel[]): string {
  return plaats
    .filter((p) => !GEEN_PLEK.has(p.soort.toLowerCase()))
    .map((p) => [hoofdletter(p.soort.toLowerCase()), p.nummer].filter(Boolean).join(" ") + (p.titel ? ` – ${p.titel}` : ""))
    .join(" › ");
}

/** "H VI › Afd. 1": dezelfde plek, kort genoeg voor de tweede regel van een kop. */
export function plaatsKort(plaats: readonly Deel[]): string {
  return plaats
    .filter((p) => !GEEN_PLEK.has(p.soort.toLowerCase()))
    .map((p) => [KORT[p.soort.toLowerCase()] ?? hoofdletter(p.soort.toLowerCase()), p.nummer].filter(Boolean).join(" "))
    .join(" › ");
}

/** Het label van de bron, tenzij het alleen de staart is van het volle pad uit de IRI: een kaal "Lid 2" of "onderdeel k"
 *  wordt dan "Artikel 9, lid 2". Een eigen naam (een Leidraad-divisie, een anker) blijft staan. */
function eigenLabel(gegeven: string, uitIri: string): string {
  if (!gegeven) return uitIri;
  if (!uitIri) return gegeven;
  const g = gegeven.toLowerCase().replace(/\.$/, "");
  const i = uitIri.toLowerCase();
  // Gelijk op hoofdletters na ("Artikel 9, Lid 2"): de vorm van bronmodel, dan staat er overal hetzelfde.
  return i === g || i.endsWith(` ${g}`) || i.endsWith(`, ${g}`) ? uitIri : gegeven;
}

/** De herkomst van een bepaling uit wat de plek weet. Het label komt uit de IRI (`vindplaatsVan`, de spiegel van
 *  `bronmodel.vindplaats`) als de bron alleen een staart gaf; de regeling is de citeertitel, anders het BWB-id. */
export function herkomstVan(b: HerkomstBron): Herkomst {
  const vp = vindplaatsVan(b.iri);
  const bwb = vp?.bwb_id ?? "";
  // Een label dat de regeling al draagt ("Invorderingswet 1990 – Artikel 9, Lid 1"): splitsen, niet herhalen.
  const gesplitst = bepalingEnRegeling((b.label ?? "").trim());
  // Of het volle label van een chip ("Artikel 9, lid 2, Invorderingswet 1990"): het pad uit de IRI, en de rest is de regeling.
  const uitIri = vp?.label ?? "";
  const staart = uitIri && gesplitst.bepaling.toLowerCase().startsWith(`${uitIri.toLowerCase()}, `)
    ? gesplitst.bepaling.slice(uitIri.length + 2).trim() : "";
  const regeling = (b.regeling ?? "").trim() || gesplitst.regeling || staart || bwb;
  const eigen = staart ? uitIri : eigenLabel(gesplitst.bepaling, uitIri);
  const bepaling = eigen || regeling || b.iri;
  const jci = b.jci ? normaliseerJci(b.jci) : "";
  return {
    bepaling,
    regeling: regeling === bepaling ? "" : regeling,
    bwb_id: bwb,
    plek: plaatsKort(b.plaats ?? []),
    plekVoluit: plaatsZin(b.plaats ?? []),
    stand: b.geldig_vanaf ?? undefined,
    href: bronHref(jci || b.url || b.iri),
  };
}

/** Het label van een bepaling: `kort` alleen de bepaling, `vol` met de regeling erachter ("Artikel 9, lid 2,
 *  Invorderingswet 1990"). */
export function herkomstLabel(h: Herkomst, vorm: "kort" | "vol" = "vol"): string {
  return vorm === "vol" && h.regeling ? `${h.bepaling}, ${h.regeling}` : h.bepaling;
}

/** Het volle label rechtstreeks uit een vindplaats: wat een chip, een link of een rij noemt. */
export function vindplaatsTekst(v: Pick<AntwoordVindplaats, "iri" | "label"> & { regeling?: string }): string {
  return herkomstLabel(herkomstVan(v));
}

/** De tweede regel van de kop: regeling · plek · stand. De link staat er los bij (`href`). */
export function herkomstRegel(h: Herkomst): string[] {
  return [h.regeling, h.plek, h.stand ? `stand ${datumTekst(h.stand)}` : ""].filter(Boolean);
}

/** De props voor `PaneelKop` van een bepaling: de bepaling als titel. De tweede regel tekent `HerkomstRegel`. */
export function herkomstKop(h: Herkomst): { soort: string; titel: string } {
  return { soort: "Bepaling", titel: h.bepaling };
}

/** De korte vindplaats van een annotatie: `art. 9 lid 2`, of `bepaling 25.1` bij een beleidsregel. Het `soort` komt uit de
 *  bronboom van de api en wordt niet uit het nummer geraden: "25" is bij de Invorderingswet een artikel en bij de Leidraad
 *  een divisie. Zonder soort blijft het "art.", wat het bij de wet-achtige regelingen ook is. */
export function bepalingKort(d: { artikel: string; lid: string; soort?: string; label?: string }): string {
  if (d.soort === "Divisie") return `bepaling ${d.artikel}${d.lid ? `, ${d.lid}` : ""}`;
  const basis = `art. ${d.artikel}${d.lid ? ` lid ${d.lid}` : ""}`;
  // Het label van een onderdeel is alleen "Onderdeel c.": zonder artikel en lid zegt dat niets.
  return d.soort === "Onderdeel" && d.label ? `${basis}, ${d.label.replace(/\.$/, "").toLowerCase()}` : basis;
}

/** Het opschrift van een annotatie: "Invorderingswet 1990 – art. 9 lid 2". Ook de naam van het Markdown-bestand. */
export function annotatieKopTekst(info: { citeertitel?: string; artikel: string; soort?: string }, doc: { bwbId: string; lid: string }): string {
  return `${info.citeertitel || doc.bwbId} – ${bepalingKort({ artikel: info.artikel, lid: doc.lid, soort: info.soort })}`;
}

// ── De stand ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

export type StandSoort = "nog-niet-in-werking" | "gelezen-ouder" | "na-peildatum" | "peildatum-onbekend"
  // Een stuk uit een bronconnector (`lib/bronStuk.ts`).
  | "stuk-gewijzigd" | "bewaarde-versie" | "alleen-pdf"
  // Bij welke tekst van de bepaling een stuk hoort (`tekstBijMeldingen`).
  | "eerdere-tekst" | "buiten-peildatum" | "tekststand-onbekend";
export interface StandMeldingData { soort: StandSoort; tekst: string }

export const NOG_NIET_IN_WERKING: StandMeldingData = {
  soort: "nog-niet-in-werking", tekst: "Deze bepaling is nog niet in werking getreden.",
};

/** De toestand die Lex las (`&g=` in de jci van de beurt), als de graaf nu een latere draagt; anders niets. Dan kan de
 *  tekst die het antwoord citeert intussen veranderd zijn, en het paneel zegt dat in plaats van het weg te poetsen. */
export function afwijkendeToestand(gelezenJci: string | undefined, geldigVanaf: string | null | undefined): string | undefined {
  const gelezen = /[&?]g=(\d{4}-\d{2}-\d{2})/.exec(gelezenJci ?? "")?.[1];
  return gelezen && geldigVanaf && geldigVanaf > gelezen ? gelezen : undefined;
}

/** Wat er over de stand te zeggen valt. De graaf draagt één toestand per regeling: een oudere versie kan het paneel niet
 *  tonen, en de melding zegt dat in plaats van een versie te suggereren die er niet is. */
export function standMeldingen(s: {
  geldig_vanaf?: string | null;
  /** De jci die Lex las. */
  gelezenJci?: string;
  /** De peildatum van het werkgebied (ISO), als de bepaling in een werkgebied geopend is. */
  peildatum?: string | null;
  nogNietInWerking?: boolean;
}): StandMeldingData[] {
  const uit: StandMeldingData[] = [];
  if (s.nogNietInWerking) uit.push(NOG_NIET_IN_WERKING);
  const gelezen = afwijkendeToestand(s.gelezenJci, s.geldig_vanaf);
  if (gelezen) {
    uit.push({ soort: "gelezen-ouder", tekst: `Lex las de tekst die gold vanaf ${datumTekst(gelezen)}. De graaf draagt nu een nieuwere toestand: de tekst kan zijn veranderd.` });
  }
  if (s.peildatum && s.geldig_vanaf && s.geldig_vanaf > s.peildatum) {
    uit.push({ soort: "na-peildatum", tekst: `De tekst in de kennisgraaf geldt vanaf ${datumTekst(s.geldig_vanaf)}, na de peildatum van het werkgebied (${datumTekst(s.peildatum)}). Hij kan afwijken van wat op de peildatum gold; een oudere versie heeft de graaf niet.` });
  }
  return uit;
}

/** De periode van de tekst waarbij een stuk hoort, in woorden: "de tekst van 1 mei 2016 tot en met 31 december 2022",
 *  of "de huidige tekst (sinds 1 januari 2023)". Leeg als de bron het niet zegt. */
export function tekstPeriode(t: TekstBij): string {
  if (!t.tekst_vanaf) return "";
  if (t.tekststand === "huidige tekst") return `de huidige tekst (sinds ${datumTekst(t.tekst_vanaf)})`;
  return t.tekst_tot ? `de tekst van ${datumTekst(t.tekst_vanaf)} tot en met ${datumTekst(t.tekst_tot)}`
    : `de tekst sinds ${datumTekst(t.tekst_vanaf)}`;
}

/** Het korte label bij een melding over de tekst, voor een rij in een lijst. */
export const TEKSTSTAND_LABEL: Partial<Record<StandSoort, string>> = {
  "eerdere-tekst": "eerdere tekst", "buiten-peildatum": "niet op de peildatum", "tekststand-onbekend": "tekst onbekend",
};

/** Wat er te zeggen valt over de tekst van de bepaling waarbij een stuk hoort (review ADR-013, 10 nov 2026): een
 *  eerdere tekst dan die in de graaf, een andere dan op de peildatum, of niet vast te stellen. De graaf draagt één
 *  toestand per regeling; de zin suggereert nooit dat de oudere tekst er is. */
export function tekstBijMeldingen(t: TekstBij): StandMeldingData[] {
  const uit: StandMeldingData[] = [];
  if (t.tekststand === "eerdere tekst") {
    const periode = tekstPeriode(t);
    uit.push({ soort: "eerdere-tekst", tekst: `Dit stuk noemt ${periode || "een eerdere tekst van de bepaling"}. De bepaling is daarna gewijzigd: als uitleg van de huidige tekst geldt het niet zonder meer.` });
  } else if (t.tekststand === "onbekend") {
    uit.push({ soort: "tekststand-onbekend", tekst: "Bij welke tekst van de bepaling dit stuk hoort, is niet vast te stellen." });
  }
  if (t.op_peildatum === false) {
    uit.push({ soort: "buiten-peildatum", tekst: "Dit stuk noemt een andere tekst dan die op de peildatum gold." });
  }
  return uit;
}

/** De sleutel van een bron in het venster: dezelfde bron twee keer openen is één tab. */
export function bronSleutel(d: BronDoel): string {
  return d.soort === "bepaling" ? `bepaling:${d.bron_iri}:${d.werkgebied_id ?? ""}` : `stuk:${d.connector}:${d.id}`;
}
