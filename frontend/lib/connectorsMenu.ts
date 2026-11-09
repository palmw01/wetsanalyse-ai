/** Het menu *Bronnen en tools* boven het invoerveld (ADR-013, fase 1b): welke bronconnectors in dit gesprek aanstaan.
 *
 *  Wetgeving (de graaf) staat altijd aan en is geen connector. De stand komt, in deze volgorde, van het gesprek
 *  (`Gesprek.connectors`), van het werkgebied (`standaard_connectors`) of is alles wat de beheerder aanzette. Wat de
 *  beheerder (of de straat) niet aanbiedt, gaat nooit aan, ook niet als een oud gesprek het noemt. graph-qa krijgt de
 *  stand per beurt als `bronnen` en toetst hem zelf ook. */

/** Of de straat de connector aanbiedt: `aan`; `onbekend` als graph-qa niet te lezen was (`GET /v1/bronnen`); of
 *  `niet_aangeboden` als de beheerder hem aanzette maar deze omgeving hem niet aanbiedt. Alleen `aan` krijgt een
 *  schakelaar: een schakelaar die niets doet, is erger dan geen. De andere twee staan er wél, met de reden: het menu
 *  verdwijnt nooit stil. */
export type Beschikbaarheid = "aan" | "onbekend" | "niet_aangeboden";

export interface BeschikbareConnector {
  naam: string;
  label: string;
  brontype: string;
  /** Ontbreekt bij een oudere BFF: dan `aan`. */
  beschikbaarheid?: Beschikbaarheid;
}

export interface ConnectorStand {
  /** Wat de beheerder aanzette (`GET /api/connectors`). Leeg = geen menu. */
  beschikbaar: BeschikbareConnector[];
  /** De eigen stand van het gesprek; `null`/`undefined` = de standaard. */
  gesprek?: string[] | null;
  /** De standaard van het werkgebied van het gesprek; `null`/`undefined` = alles wat beschikbaar is. */
  werkgebied?: string[] | null;
  /** `mislukt`: de laatste poging om de lijst op te halen faalde. `beschikbaar` is dan de laatst bekende lijst. */
  laden?: "ok" | "mislukt";
}

/** Het ene leesmodel van het menu, in de BFF: wat de beheerder aanzette (het register), met per connector of de straat
 *  hem aanbiedt (graph-qa `GET /v1/bronnen`). Wat de straat niet aanbiedt, is `niet_aangeboden`: zichtbaar, nooit aan
 *  (incident van 8 nov 2026: Kamerstukken ✓ terwijl de straat hem niet aanbood). Kan graph-qa niet worden gelezen
 *  (`straat` null), dan is elke connector `onbekend` (review ADR-013, punt 2). */
export function metBeschikbaarheid<T extends { naam: string }>(
  register: T[],
  straat: { naam: string; straat: boolean }[] | null,
): (T & { beschikbaarheid: Beschikbaarheid })[] {
  if (!straat) return register.map((c) => ({ ...c, beschikbaarheid: "onbekend" as const }));
  const aan = new Set(straat.filter((b) => b.straat).map((b) => b.naam));
  return register.map((c) => ({ ...c, beschikbaarheid: aan.has(c.naam) ? "aan" as const : "niet_aangeboden" as const }));
}

/** Kan de jurist deze connector nu aan- of uitzetten? Niet als de beschikbaarheid onbekend is. */
export function schakelbaar(c: BeschikbareConnector): boolean {
  return (c.beschikbaarheid ?? "aan") === "aan";
}

/** Staat het menu er? Met een connector bij de beheerder, of als het ophalen mislukte: dan zegt het menu dát, in plaats
 *  van stil te verdwijnen. Zonder connector en zonder storing is er alleen wetgeving, en dus geen menu. */
export function toonMenu(stand: ConnectorStand): boolean {
  return stand.beschikbaar.length > 0 || stand.laden === "mislukt";
}

/** Moet de werkplek de stand opnieuw ophalen (bij het openen van het menu, na een beurt)? Als het ophalen mislukte, of
 *  als graph-qa niet te lezen was. `niet_aangeboden` is een vaste stand van de omgeving: geen reden om te peilen. */
export function moetVerversen(stand: ConnectorStand): boolean {
  return stand.laden === "mislukt" || stand.beschikbaar.some((c) => c.beschikbaarheid === "onbekend");
}

/** Eén regel uit het `bronstand`-event van graph-qa (`agent/bronstand.py`): per connector of hij aanstaat, en zo niet,
 *  waarom. */
export interface BronstandRegel {
  naam: string;
  reden: string;
}

/** Wat graph-qa in een beurt over de omgeving vaststelde, over de stand van het menu gelegd. Alleen de redenen die over
 *  de omgeving gaan, tellen: `straat` (niet aangeboden), `register_onleesbaar` (onbekend) en `aan`. Een bron die het
 *  gesprek, het werkgebied of de beheerder uitzette, zegt niets over de beschikbaarheid. */
export function uitBronstand(beschikbaar: BeschikbareConnector[], regels: BronstandRegel[]): BeschikbareConnector[] {
  const per = new Map(regels.map((r) => [r.naam, r.reden]));
  const nieuw = (c: BeschikbareConnector): Beschikbaarheid | undefined => {
    const reden = per.get(c.naam);
    return reden === "straat" ? "niet_aangeboden" : reden === "register_onleesbaar" ? "onbekend" : reden === "aan" ? "aan" : undefined;
  };
  return beschikbaar.map((c) => {
    const b = nieuw(c);
    return b && b !== c.beschikbaarheid ? { ...c, beschikbaarheid: b } : c;
  });
}

/** Wat het menu boven de lijst meldt, of niets. Een mislukte lijst gaat voor: dan is alles onzeker. */
export function menuMelding(stand: ConnectorStand): string | null {
  if (stand.laden === "mislukt") {
    return stand.beschikbaar.length
      ? "De bronnen zijn nu niet te controleren. Dit is de laatst bekende stand."
      : "De bronnen zijn nu niet te controleren.";
  }
  const weg = stand.beschikbaar.filter((c) => c.beschikbaarheid === "niet_aangeboden").map((c) => c.label);
  const onbekend = stand.beschikbaar.filter((c) => c.beschikbaarheid === "onbekend").map((c) => c.label);
  const zinnen = [
    weg.length ? `${opsomming(weg)} ${weg.length > 1 ? "staan" : "staat"} aan, maar ${weg.length > 1 ? "zijn" : "is"} op deze omgeving niet beschikbaar.` : "",
    onbekend.length ? `Of ${opsomming(onbekend)} nu bereikbaar ${onbekend.length > 1 ? "zijn" : "is"}, is niet te controleren.` : "",
  ].filter(Boolean);
  return zinnen.length ? zinnen.join(" ") : null;
}

function opsomming(xs: string[]): string {
  return xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} en ${xs[xs.length - 1]}`;
}

/** Een bron die een beurt nodig had maar die uit stond (graph-qa-event `bron_uit`). */
export interface BronUit {
  naam: string;
  label: string;
  reden: string;
}

/** De uitgezette bronnen die de jurist zelf kan aanzetten: die van het gesprek of van de standaard van het werkgebied.
 *  De beheerder en de straat zet je niet aan vanuit het gesprek. */
export function zelfAanTeZetten(bronnen: BronUit[], stand: ConnectorStand): BronUit[] {
  const aangeboden = new Set(stand.beschikbaar.filter(schakelbaar).map((c) => c.naam));
  return bronnen.filter((b) => (b.reden === "gesprek" || b.reden === "werkgebied") && aangeboden.has(b.naam));
}

/** De connectors die in deze beurt aanstaan, in de volgorde van `beschikbaar`. */
export function actieveConnectors(stand: ConnectorStand): string[] {
  const gekozen = gekozenNamen(stand);
  return stand.beschikbaar.filter((c) => c.beschikbaarheid !== "niet_aangeboden" && gekozen.includes(c.naam)).map((c) => c.naam);
}

/** Wat het gesprek, het werkgebied of de standaard kiest, ongeacht of de omgeving het nu aanbiedt. */
function gekozenNamen({ beschikbaar, gesprek, werkgebied }: ConnectorStand): string[] {
  return gesprek ?? werkgebied ?? beschikbaar.map((c) => c.naam);
}

/** Waar de stand vandaan komt, voor de toelichting in het menu. */
export function herkomstVan({ gesprek, werkgebied }: ConnectorStand): "gesprek" | "werkgebied" | "standaard" {
  return gesprek != null ? "gesprek" : werkgebied != null ? "werkgebied" : "standaard";
}

/** Wat een beurt over de bronnen meestuurt: de stand en waar die vandaan komt. Zonder menu niets: graph-qa beslist dan
 *  zelf (alleen wetgeving). Een connector met een onbekende beschikbaarheid houdt zijn opgeslagen keuze: graph-qa
 *  toetst de straat zelf en noemt dan de juiste reden; weglaten zou hem als "uitgezet in het gesprek" melden. */
export function beurtBronnen(stand: ConnectorStand): {
  bronnen?: string[];
  bronnen_herkomst?: "gesprek" | "werkgebied" | "standaard";
} {
  if (!stand.beschikbaar.length) return {};
  return { bronnen: actieveConnectors(stand), bronnen_herkomst: herkomstVan(stand) };
}

/** Eén connector om: de nieuwe eigen stand van het gesprek. Een connector die niet te schakelen is, blijft staan. */
export function wissel(stand: ConnectorStand, naam: string): string[] {
  const nu = actieveConnectors(stand);
  const c = stand.beschikbaar.find((b) => b.naam === naam);
  // Een keuze voor een bron die de omgeving nu niet aanbiedt, blijft bewaard: komt hij terug, dan staat hij weer aan.
  const bewaard = stand.beschikbaar
    .filter((b) => b.beschikbaarheid === "niet_aangeboden" && gekozenNamen(stand).includes(b.naam)).map((b) => b.naam);
  const volgende = !c || !schakelbaar(c) ? nu : nu.includes(naam) ? nu.filter((n) => n !== naam) : [...nu, naam];
  const blijft = new Set([...volgende, ...bewaard]);
  return stand.beschikbaar.map((b) => b.naam).filter((n) => blijft.has(n));
}

/** Hoe één bron op de knop staat. */
export type BronWeergave = "aan" | "uit" | "onbekend" | "niet_aangeboden";

/** Het woord bij een stand op de knop (de vinkje-stand tekent de werkplek als icoon). */
export const STAND_WOORD: Record<Exclude<BronWeergave, "aan">, string> = {
  uit: "uit",
  onbekend: "onbekend",
  niet_aangeboden: "niet beschikbaar",
};

/** De onderdelen van de regel op de knop: Wetgeving · Kamerstukken · Rechtspraak, elk met zijn stand. De werkplek tekent
 *  het vinkje als icoon (`components/ui/Icoon`), niet als teken: dat valt buiten de subset van het font. */
export function menuRegel(stand: ConnectorStand): { label: string; stand: BronWeergave }[] {
  const aan = actieveConnectors(stand);
  const standVan = (c: BeschikbareConnector): BronWeergave =>
    schakelbaar(c) ? (aan.includes(c.naam) ? "aan" : "uit") : c.beschikbaarheid === "niet_aangeboden" ? "niet_aangeboden" : "onbekend";
  return [{ label: "Wetgeving", stand: "aan" }, ...stand.beschikbaar.map((c) => ({ label: c.label, stand: standVan(c) }))];
}

/** De toegankelijke naam van de knop: "Bronnen: Wetgeving aan, Kamerstukken aan, Rechtspraak uit". */
export function menuNaam(stand: ConnectorStand): string {
  const delen = menuRegel(stand).map((d) => `${d.label} ${d.stand === "aan" ? "aan" : STAND_WOORD[d.stand]}`).join(", ");
  return `Bronnen: ${delen}${stand.laden === "mislukt" ? " (nu niet te controleren)" : ""}`;
}
