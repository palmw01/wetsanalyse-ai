import { isApiError } from "./api";
import { isKlaarOmAfTeRonden } from "./annotatieOverzicht";
import { jasVolgorde } from "./jas";
import type { LidRegel } from "./selectie";
import type {
  AgentDoel,
  AgentDoelInvoer,
  AgentHergebruik,
  AgentKandidaat,
  AnnotatieElement,
  GraafArtikel,
  DocumentStatus,
  Lifecycle,
} from "./types";

// Presentatie-helpers voor de annotatie-workbench (statuslabels/kleuren).

export const DOCUMENT_STATUS_LABEL: Record<DocumentStatus, string> = {
  in_review: "In behandeling",
  geaccordeerd: "Afgerond",
  gepromoveerd: "In de graaf",
};

// De toon van het label per status (`StatusLabel`): in behandeling = geel, afgerond = groen, in de graaf =
// lintblauw.
export const DOCUMENT_STATUS_TOON: Record<DocumentStatus, "geel" | "groen" | "lint"> = {
  in_review: "geel",
  geaccordeerd: "groen",
  gepromoveerd: "lint",
};

export function documentStatusLabel(status: DocumentStatus): string {
  return DOCUMENT_STATUS_LABEL[status] ?? status;
}

/** Hoe de stand van een annotatie in beeld komt: het label van de status, behalve wanneer er niets meer te beoordelen is
 *  en alleen het afronden nog ontbreekt. Neutraal, want dat is geen oordeel: groen is voor wat de jurist heeft afgerond.
 *
 *  De kaart en het paneel lopen hier allebei langs, zodat één annotatie op beide plekken hetzelfde zegt. */
export function documentStand(
  d: Parameters<typeof isKlaarOmAfTeRonden>[0],
): { label: string; toon: "geel" | "groen" | "lint" | "neutraal"; uitleg?: string } {
  if (isKlaarOmAfTeRonden(d)) return {
    label: "Klaar om af te ronden",
    toon: "neutraal",
    uitleg: "Alle markeringen zijn beoordeeld. Afronden doe je zelf, met Annotatie afronden.",
  };
  return { label: documentStatusLabel(d.status), toon: DOCUMENT_STATUS_TOON[d.status] };
}

// --- de brontekst van een bepaling ------------------------------------------------------------------

/** De artikeltekst als regels: wat er op het scherm komt, mét het lidnummer dat erbij hoort.
 *
 *  Eén plek waar de weergave wordt opgebouwd, zodat het documentpaneel, de sortering, de ankers en de
 *  lid-toewijzing over dezelfde tekst praten. Het lidnummer reist apart mee omdat het niet uit de
 *  volgorde is af te leiden (zie `lidUitOffset`). Lege leden vallen weg – die zouden een lege regel in
 *  de bron zetten en alle offsets erna verschuiven. */
export function regelsVan(info: GraafArtikel): LidRegel[] {
  return info.leden_teksten
    .filter((l) => l.tekst.trim())
    .map((l) => ({ lid: l.lid ?? "", regel: l.lid ? `${l.lid}. ${l.tekst}` : l.tekst }));
}

/** De regels als één brontekst. Twee nieuwe regels ertussen – dezelfde scheiding waar `lidUitOffset`
 *  en de ankers van uitgaan. */
export function bronVan(regels: LidRegel[]): string {
  return regels.map((r) => r.regel).join("\n\n");
}

/** Mensleesbare aanduiding van een kandidaat-bepaling ("Artikel 36a, lid 1 – Invorderingswet 1990"). */
export function kandidaatLabel(k: AgentKandidaat): string {
  const bepaling = `Artikel ${k.artikel}${k.lid ? `, lid ${k.lid}` : ""}`;
  return k.citeertitel ? `${bepaling} – ${k.citeertitel}` : bepaling;
}

/** De gekozen kandidaat als **doel**: hiermee hoeft de agent niets meer te zoeken.
 *
 *  Dit is de belangrijkste plek voor een meegegeven doel. De jurist wees zojuist één bepaling aan
 *  uit een lijst; die opnieuw in natuurlijke taal laten opzoeken is niet alleen verspilling, het is
 *  de enige stap waar de keten alsnog bij een ándere bepaling kan uitkomen.
 */
export function doelVanKandidaat(k: AgentKandidaat): AgentDoelInvoer {
  return {
    bwbId: k.bwbId,
    artikel: k.artikel,
    ...(k.lid ? { lid: k.lid } : {}),
    ...(k.citeertitel ? { citeertitel: k.citeertitel } : {}),
    // Een optie van de keuzekaart wijst de bronnode zelf aan: dan valt er niets meer te zoeken,
    // ook niet bij twee artikelen met hetzelfde nummer (bijvoorbeeld in een bijlage).
    ...(k.bron_iri ? { bron_iri: k.bron_iri } : {}),
    ...(k.label ? { label: k.label } : {}),
  };
}

/** De opdracht die volgt als de jurist een kandidaat kiest.
 *
 *  Blijft naast `doelVanKandidaat` bestaan: dit is de **leesbare** vraag in de thread, en die hoort
 *  te zeggen wat er gebeurt. Het bwbId gaat er nog steeds in mee – draait er ooit een beurt zonder
 *  doel (een oudere client, of een agent die het veld negeert), dan is de tekst nog steeds
 *  eenduidig genoeg om bij de juiste bepaling uit te komen.
 */
export function kandidaatPrompt(k: AgentKandidaat): string {
  const bepaling = `artikel ${k.artikel}${k.lid ? ` lid ${k.lid}` : ""}`;
  const regeling = k.citeertitel ? `${k.citeertitel} (${k.bwbId})` : k.bwbId;
  return `Annoteer ${bepaling} van de ${regeling}.`;
}

/** Raakt een selectie het bereik van de actieve markering?
 *
 *  Zo ja, dan pas je die markering aan in plaats van een tweede te maken. Aanraken op de rand telt
 *  mee (`eind === start`): uitbreiden begint per definitie waar de markering ophoudt.
 */
export function overlaptSelectie(
  selectie: { start: number; eind: number },
  bereik: { start: number; eind: number },
): boolean {
  return selectie.start <= bereik.eind && selectie.eind >= bereik.start;
}

// --- de reviewlijst ordenen -----------------------------------------------------------------------

/** Door een jurist bevestigd. Dezelfde definitie als `BEOORDEELD` in `api/app/annotatie_v2_contracts.py`;
 *  `api/tests/test_lifecycle_drift.py` bewaakt dat. */
export const BEOORDEELD_LIFECYCLES = ["human_approved", "edited", "published"];
/** Elementen waar de jurist al over besloten heeft. Ook `edited`: een aanpassing ís een besluit. Dezelfde definitie als
 *  `AFGEHANDELD` in de api. */
export const BESLIST_LIFECYCLES = ["human_approved", "edited", "published", "rejected"];

export type ReviewFilter = "alles" | "te_beoordelen" | "aandacht";

export function isBeslist(el: { lifecycle: string }): boolean {
  return BESLIST_LIFECYCLES.includes(el.lifecycle);
}

/** Draagt dit element een oordeel? De regel van een eigen markering zelf telt niet (`heeft_oordeel` in de api). */
export function heeftOordeel(el: { beslissingen?: { type: string }[] }): boolean {
  return !!el.beslissingen?.some((b) => b.type !== "markering");
}

/** De voorstellen die zonder twijfel uit de keten kwamen: geen aandachtspunt, een klasse, en nog niemand besloot erover.
 *  Dit is wat *Akkoord met de groene* in één handeling bevestigt; geel en rood bekijkt de jurist één voor één. */
export function groeneVoorstellen<T extends { lifecycle: string; klasse: string; herkomst: string; aandacht?: string | null; verouderd?: boolean }>(
  elementen: T[],
): T[] {
  return elementen.filter((e) => e.lifecycle === "voorgesteld" && !!e.klasse && e.herkomst !== "mens" && !e.verouderd
    && e.aandacht !== "geel" && e.aandacht !== "rood");
}

/** Staat dit ontbrekend-item inmiddels als markering in het document?
 *
 *  Matcht op klasse + genormaliseerd fragment. **Verworpen elementen tellen niet mee**: die heb je
 *  net weggestuurd, dus "inmiddels gemarkeerd" is dan precies het omgekeerde van wat er gebeurde —
 *  en het item bleef onaanklikbaar staan terwijl je hem juist opnieuw wilde kunnen toevoegen.
 *  Dezelfde regel als in `DocumentPaneel`, dat verworpen markeringen ook niet meer oplicht. */
export function alGemarkeerd(elementen: AnnotatieElement[], klasse: string, fragment: string): boolean {
  const sleutel = (k: string, t: string) => `${k}|${t.split(/\s+/).join(" ").toLowerCase()}`;
  const tekst = fragment.trim();
  if (!tekst) return false;
  return elementen.some(
    (e) => e.lifecycle !== "rejected" && sleutel(e.klasse, e.tekst) === sleutel(klasse, tekst),
  );
}

/** Lifecycles met een eindoordeel. Bewust NIET hetzelfde begrip als `isBeslist`, dat de filters en de telling
 *  stuurt: `edited` telt wel als beslist maar blijft bewerkbaar, want een klasse wijzigen en er daarna een
 *  toelichting bij typen is één doorlopende handeling. */
const VERGRENDELDE_LIFECYCLES = ["human_approved", "rejected", "published"];

/** Waarom een element niet zomaar te wijzigen is. Dezelfde regel als `slot_van` in de api, met dezelfde gevallen
 *  in `slotregel.json`: zo verschijnt er geen knop waar de server een 409 geeft.
 *  - `alleen-lezen`: verouderd, er kan niets meer.
 *  - `laag`: de laag is afgerond; eerst de laag heropenen.
 *  - `element`: een eindoordeel; heropenen of een opmerking kan, de rest niet.
 *  Je eigen markering staat meteen op `human_approved`, maar dat is "gemaakt", niet "beoordeeld": wat je zelf
 *  maakte blijft bewerkbaar en te wissen, tot er een oordeel op ligt. */
export type Slot = "geen" | "element" | "laag" | "alleen-lezen";

export function slotVan(
  el: { lifecycle: string; herkomst: string; verouderd?: boolean; beslissingen?: { type: string }[] },
  laagStatus?: string | null,
): Slot {
  if (el.verouderd) return "alleen-lezen";
  if (laagStatus && laagStatus !== "in_review") return "laag";
  if (VERGRENDELDE_LIFECYCLES.includes(el.lifecycle) && (el.herkomst !== "mens" || heeftOordeel(el))) return "element";
  return "geen";
}

/** Een afgerond document is in zijn geheel bevroren – ook voor een nieuwe agent-ronde. De api
 *  weigert elke mutatie met een 409; de UI laat het slot zien in plaats van die fout af te wachten. */
export function isDocumentVergrendeld(doc: { status: DocumentStatus }): boolean {
  return doc.status === "geaccordeerd";
}

/** Hoort dit element bij de gekozen filterstand? */
export function pastInFilter(el: AnnotatieElement, filter: ReviewFilter): boolean {
  if (filter === "te_beoordelen") return !isBeslist(el);
  if (filter === "aandacht") return el.aandacht === "rood" || el.aandacht === "geel";
  return true;
}

/** Lidnummer als getal, voor sorteren. Lexicaal zou "10" vóór "2" zetten; een leeg lid komt eerst. */
function lidRang(lid: string): number {
  const n = Number.parseInt(lid, 10);
  return Number.isNaN(n) ? -1 : n;
}

/** Sorteer de reviewlijst in één vaste, inhoudelijke volgorde: de canonieke JAS-tabel.
 *
 *  Niet op aandacht (🔴🟡🟢) of voortgang: beide veranderen terwijl je reviewt. Keur je iets goed,
 *  dan springt het naar achteren en schuift de rest op – je raakt je plek kwijt en een kaart staat
 *  nooit twee keer op dezelfde hoogte. Scherpstellen op twijfelgevallen doen de filters.
 *
 *  Sleutels van grof naar fijn: klasse (wa-tabelvolgorde) → lid → positie in de tekst →
 *  invoervolgorde. Geen van die vier verandert door reviewen; alleen als jíj de klasse wijzigt
 *  verhuist een element, en dan hóórt het ergens anders.
 *
 *  `posities` is de offset per element-id in de brontekst (het artefact berekent die met dezelfde
 *  `vindPositie` als de weergave). Ontbreekt hij, dan sorteert deze functie een niveau grover in
 *  plaats van te struikelen; een element dat niet in de tekst te vinden is komt achteraan binnen
 *  zijn eigen klasse.
 */
export function sorteerReview(
  elementen: AnnotatieElement[],
  posities?: Map<string, number>,
): AnnotatieElement[] {
  const positie = (el: AnnotatieElement) => posities?.get(el.id) ?? Number.POSITIVE_INFINITY;
  return elementen
    .map((el, i) => ({ el, i }))
    .sort((a, b) => {
      const klasse = jasVolgorde(a.el.klasse) - jasVolgorde(b.el.klasse);
      if (klasse !== 0) return klasse;
      const lid = lidRang(a.el.lid) - lidRang(b.el.lid);
      if (lid !== 0) return lid;
      // Let op: niet `pa - pb` – met twee keer Infinity levert dat NaN, en met één Infinity een
      // waarde die de "niet gevonden"-kaart niet betrouwbaar achteraan zet.
      const pa = positie(a.el);
      const pb = positie(b.el);
      if (pa !== pb) return pa === Number.POSITIVE_INFINITY ? 1 : pb === Number.POSITIVE_INFINITY ? -1 : pa - pb;
      return a.i - b.i;
    })
    .map(({ el }) => el);
}

/** Het volgende (of vorige) element in de getoonde volgorde.
 *
 *  `alleenTeBeoordelen` is het auto-advance-gedrag na een akkoord: doorspringen naar het volgende dat
 *  nog aandacht vraagt in plaats van naar het eerstvolgende in de lijst. Geeft `undefined` als er
 *  niets meer is – dan blijft de selectie staan in plaats van naar het begin te springen.
 */
export function volgendeElement(
  lijst: AnnotatieElement[],
  actiefId: string | undefined,
  richting: 1 | -1 = 1,
  alleenTeBeoordelen = false,
): AnnotatieElement | undefined {
  const kandidaten = alleenTeBeoordelen ? lijst.filter((el) => !isBeslist(el)) : lijst;
  if (kandidaten.length === 0) return undefined;

  const huidig = kandidaten.findIndex((el) => el.id === actiefId);
  if (huidig < 0) {
    // Niets geselecteerd (of het actieve element valt buiten de kandidaten): begin bij de rand.
    return richting === 1 ? kandidaten[0] : kandidaten[kandidaten.length - 1];
  }
  return kandidaten[huidig + richting];
}

// --- een vraag over één markering ------------------------------------------------------------------

/** Drie vragen bij een markering, als één klik – afhankelijk van de klasse.
 *
 *  Een leeg invoerveld met "Wat wil je weten over deze markering?" is een open vraag op het moment
 *  dat je juist snel wilt beoordelen. Daarom:
 *
 *  1. klopt de klasse ("Waarom is dit een …?");
 *  2. de vraag die bij déze functie hoort (`KLASSEVRAAG`: bij een Tijdsaanduiding het startmoment,
 *     bij een Afleidingsregel invoer en uitkomst, …);
 *  3. bij twijfel het alternatief dat de agent zelf voorstelde ("Waarom geen Voorwaarde?") – een
 *     scherpere vraag dan welke vaste formulering ook – en anders de afbakening.
 *
 *  Werkt voor beide elementvormen (het artikeldocument en de bronnode-weergave).
 */
export function vraagSuggesties(el: { klasse: string; alternatieven?: { klasse: string }[] }): string[] {
  if (!el.klasse) {
    // Een terugval: nog geen klasse. De vragen gaan over de keuze zelf.
    const opties = (el.alternatieven ?? []).map((a) => a.klasse).filter(Boolean);
    return [
      "Welke klasse past het best bij dit fragment?",
      opties.length >= 2 ? `Wat is het verschil tussen ${opties[0]} en ${opties[1]} hier?` : "Waarom is de klasse hier onzeker?",
      "Klopt de afbakening van dit fragment?",
    ];
  }
  const anders = el.alternatieven?.find((a) => a.klasse && a.klasse !== el.klasse)?.klasse;
  const eigen = KLASSEVRAAG[el.klasse];
  return [
    `Waarom is dit een ${el.klasse}?`,
    eigen ?? "Klopt de afbakening van dit fragment?",
    anders
      ? `Waarom geen ${anders}?`
      : eigen ? "Klopt de afbakening van dit fragment?" : "Hoe verhoudt dit zich tot de rest van het artikel?",
  ];
}

/** Per JAS-klasse de vraag die de jurist bij die functie het eerst stelt – afgeleid van de
 *  herkenningsvraag in het profiel van de klasse (`.claude/skills/wetsanalyse/references/
 *  jas-klassen-referentie.md`), toegespitst op dít fragment. Elke klasse uit `JAS_KLASSEN` heeft er
 *  een (`annotatie.test.ts`). */
export const KLASSEVRAAG: Record<string, string> = {
  Rechtssubject: "Welk recht of welke plicht heeft deze partij in deze bepaling?",
  Rechtsobject: "Op welk recht of welke plicht heeft dit object betrekking?",
  Rechtsbetrekking: "Tussen welke partijen bestaat deze rechtsbetrekking, en waarover?",
  Rechtsfeit: "Welk rechtsgevolg verbindt de bepaling aan dit feit?",
  Voorwaarde: "Voor welk rechtsgevolg geldt deze voorwaarde?",
  Afleidingsregel: "Wat is de invoer en wat de uitkomst van deze afleiding?",
  "Variabele en variabelewaarde": "Welke waarden kan deze variabele aannemen, en waar komen ze vandaan?",
  "Parameter en parameterwaarde": "Wat is de waarde van deze parameter, en waar is die vastgesteld?",
  Operator: "Wat zijn de operanden van deze operator?",
  Tijdsaanduiding: "Vanaf welk moment loopt deze termijn, en wat gebeurt er als hij verstrijkt?",
  Plaatsaanduiding: "Op welk gebied heeft deze plaatsaanduiding betrekking?",
  "Delegatiebevoegdheid en delegatie-invulling": "Wie krijgt hier welke bevoegdheid, en is die al ingevuld?",
  Brondefinitie: "Waar in de regeling wordt dit gedefinieerde begrip gebruikt?",
};

// --- een annotatie die er niet meer is ---------------------------------------------------------

/** Is deze fout "bestaat niet (meer)" in plaats van "het ging even mis"?
 *
 *  De api geeft 404 zowel bij een verwijderd document als bij dat van iemand anders (bewust: dat lekt
 *  het bestaan niet). Beide betekenen voor de UI hetzelfde: opnieuw proberen kan per definitie niet
 *  lukken, dus toon een toestand en geen foutmelding met een retry-knop.
 */
export function isVerwijderd(e: unknown): boolean {
  return isApiError(e) && e.status === 404;
}

/** De mededeling bij een hergebruikte annotatie, in woorden van de jurist.
 *
 *  Volledig: er is niets opnieuw bekeken, en dat moet er staan – anders lijkt het een verse
 *  annotatie. Deels: welke leden kwamen uit de laag; de rest is net opnieuw geannoteerd. */
export function hergebruikTekst(h: AgentHergebruik): string {
  const leden = h.leden.filter((l) => l !== "");
  const wat = leden.length === 0 ? "Dit artikel" : leden.length === 1 ? `Lid ${leden[0]}` : `Leden ${leden.join(", ")}`;
  const t = h.telling;
  const stand = `${t.markeringen} ${t.markeringen === 1 ? "markering" : "markeringen"}, waarvan ${t.beoordeeld} beoordeeld en ${t.te_beoordelen} nog te beoordelen`;
  return h.volledig
    ? `${wat} was al geannoteerd en de wettekst is sindsdien niet veranderd. Dit is de bestaande annotatie (${stand}).`
    : `${wat} kwam ongewijzigd uit de bestaande annotatie (${stand}); de rest is nu opnieuw geannoteerd.`;
}

/** Actuele markeringen en de historie: markeringen van een lid waarvan de wettekst sindsdien
 *  veranderde. Die laatste blijven met hun oordeel bewaard, maar horen niet in de tekst of de
 *  werkvoorraad – ze gaan over tekst die er niet meer staat. */
export function splitsVerouderd<T extends { verouderd?: boolean }>(elementen: T[]): { actueel: T[]; historie: T[] } {
  const actueel: T[] = [];
  const historie: T[] = [];
  for (const el of elementen) (el.verouderd ? historie : actueel).push(el);
  return { actueel, historie };
}

/** Het doel van een afgelopen beurt, in de vorm waarin het mee kan naar een nieuwe (`startRun`).
 *  Zonder de tekst: die haalt de agent zelf op – de graaf is de bron. */
export function doelInvoerVan(doel: AgentDoel | null | undefined): AgentDoelInvoer | undefined {
  if (!doel?.bwbId) return undefined;
  return {
    bwbId: doel.bwbId,
    ...(doel.bron_iri ? { bron_iri: doel.bron_iri } : {}),
    ...(doel.snapshot_id ? { snapshot_id: doel.snapshot_id } : {}),
    ...(doel.label ? { label: doel.label } : {}),
    ...(doel.artikel ? { artikel: doel.artikel } : {}),
    ...(doel.lid ? { lid: doel.lid } : {}),
    ...(doel.nummer ? { nummer: doel.nummer } : {}),
    ...(doel.citeertitel ? { citeertitel: doel.citeertitel } : {}),
  };
}

/** Het oordeel over een markering in woorden. */
export const LIFECYCLE_LABEL: Record<Lifecycle, string> = {
  voorgesteld: "voorstel van Lex",
  human_approved: "akkoord",
  edited: "door jurist aangepast",
  rejected: "verworpen",
  published: "gepubliceerd",
  reused: "hergebruikt",
};
