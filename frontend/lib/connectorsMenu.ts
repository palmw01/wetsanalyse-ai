/** Het menu *Bronnen en tools* boven het invoerveld (ADR-013, fase 1b): welke bronconnectors in dit gesprek aanstaan.
 *
 *  Wetgeving (de graaf) staat altijd aan en is geen connector. De stand komt, in deze volgorde, van het gesprek
 *  (`Gesprek.connectors`), van het werkgebied (`standaard_connectors`) of is alles wat de beheerder aanzette. Wat de
 *  beheerder (of de straat) niet aanbiedt, gaat nooit aan, ook niet als een oud gesprek het noemt. graph-qa krijgt de
 *  stand per beurt als `bronnen` en toetst hem zelf ook. */

/** Of de straat de connector aanbiedt: `aan`, of `onbekend` als graph-qa niet te lezen was (`GET /v1/bronnen`). Een
 *  onbekende connector staat in het menu zonder schakelaar: een schakelaar die niets doet, is erger dan geen. */
export type Beschikbaarheid = "aan" | "onbekend";

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
}

/** Het ene leesmodel van het menu, in de BFF: wat de beheerder aanzette (het register), met per connector of de straat
 *  hem aanbiedt (graph-qa `GET /v1/bronnen`). Wat de straat niet aanbiedt, valt weg: incident van 8 nov 2026,
 *  Kamerstukken ✓ terwijl de straat hem niet aanbood. Kan graph-qa niet worden gelezen (`straat` null), dan is elke
 *  connector `onbekend` (review ADR-013, punt 2): zichtbaar, maar niet te schakelen, tot de stand weer bekend is. */
export function metBeschikbaarheid<T extends { naam: string }>(
  register: T[],
  straat: { naam: string; straat: boolean }[] | null,
): (T & { beschikbaarheid: Beschikbaarheid })[] {
  if (!straat) return register.map((c) => ({ ...c, beschikbaarheid: "onbekend" as const }));
  const aan = new Set(straat.filter((b) => b.straat).map((b) => b.naam));
  return register.filter((c) => aan.has(c.naam)).map((c) => ({ ...c, beschikbaarheid: "aan" as const }));
}

/** Kan de jurist deze connector nu aan- of uitzetten? Niet als de beschikbaarheid onbekend is. */
export function schakelbaar(c: BeschikbareConnector): boolean {
  return c.beschikbaarheid !== "onbekend";
}

/** Staat er een connector met een onbekende beschikbaarheid in het menu? Dan haalt de werkplek de stand opnieuw op. */
export function heeftOnbekend(stand: ConnectorStand): boolean {
  return stand.beschikbaar.some((c) => !schakelbaar(c));
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
export function actieveConnectors({ beschikbaar, gesprek, werkgebied }: ConnectorStand): string[] {
  const gekozen = gesprek ?? werkgebied ?? beschikbaar.map((c) => c.naam);
  return beschikbaar.map((c) => c.naam).filter((n) => gekozen.includes(n));
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
  if (!c || !schakelbaar(c)) return nu;
  return nu.includes(naam) ? nu.filter((n) => n !== naam) : actieveConnectors({ ...stand, gesprek: [...nu, naam] });
}

/** De onderdelen van de regel op de knop: Wetgeving · Kamerstukken · Rechtspraak, elk aan of uit. De werkplek tekent het
 *  vinkje als icoon (`components/ui/Icoon`), niet als teken: dat valt buiten de subset van het font. */
export function menuRegel(stand: ConnectorStand): { label: string; aan: boolean; onbekend?: true }[] {
  const aan = actieveConnectors(stand);
  return [{ label: "Wetgeving", aan: true }, ...stand.beschikbaar.map((c) =>
    schakelbaar(c) ? { label: c.label, aan: aan.includes(c.naam) } : { label: c.label, aan: false, onbekend: true as const })];
}

/** De toegankelijke naam van de knop: "Bronnen: Wetgeving aan, Kamerstukken aan, Rechtspraak uit". */
export function menuNaam(stand: ConnectorStand): string {
  return `Bronnen: ${menuRegel(stand).map((d) => `${d.label} ${d.onbekend ? "onbekend" : d.aan ? "aan" : "uit"}`).join(", ")}`;
}
