/** Het menu *Bronnen en tools* boven het invoerveld (ADR-013, fase 1b): welke bronconnectors in dit gesprek aanstaan.
 *
 *  Wetgeving (de graaf) staat altijd aan en is geen connector. De stand komt, in deze volgorde, van het gesprek
 *  (`Gesprek.connectors`), van het werkgebied (`standaard_connectors`) of is alles wat de beheerder aanzette. Wat de
 *  beheerder (of de straat) niet aanbiedt, gaat nooit aan, ook niet als een oud gesprek het noemt. graph-qa krijgt de
 *  stand per beurt als `bronnen` en toetst hem zelf ook. */

export interface BeschikbareConnector {
  naam: string;
  label: string;
  brontype: string;
}

export interface ConnectorStand {
  /** Wat de beheerder aanzette (`GET /api/connectors`). Leeg = geen menu. */
  beschikbaar: BeschikbareConnector[];
  /** De eigen stand van het gesprek; `null`/`undefined` = de standaard. */
  gesprek?: string[] | null;
  /** De standaard van het werkgebied van het gesprek; `null`/`undefined` = alles wat beschikbaar is. */
  werkgebied?: string[] | null;
}

/** Wat de straat aanbiedt (graph-qa `GET /v1/bronnen`, `straat`), uit wat de beheerder aanzette. Een schakelaar in
 *  het menu die niets doet, is erger dan geen schakelaar: incident van 8 nov 2026, Kamerstukken ✓ terwijl de straat hem
 *  niet aanbood. Kan graph-qa niet worden gelezen (`straat` null), dan blijft het register: de beurt toetst zelf ook. */
export function alleenInDeStraat<T extends { naam: string }>(
  register: T[],
  straat: { naam: string; straat: boolean }[] | null,
): T[] {
  if (!straat) return register;
  const aan = new Set(straat.filter((b) => b.straat).map((b) => b.naam));
  return register.filter((c) => aan.has(c.naam));
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
  const aangeboden = new Set(stand.beschikbaar.map((c) => c.naam));
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
 *  zelf (alleen wetgeving). */
export function beurtBronnen(stand: ConnectorStand): {
  bronnen?: string[];
  bronnen_herkomst?: "gesprek" | "werkgebied" | "standaard";
} {
  if (!stand.beschikbaar.length) return {};
  return { bronnen: actieveConnectors(stand), bronnen_herkomst: herkomstVan(stand) };
}

/** Eén connector om: de nieuwe eigen stand van het gesprek. */
export function wissel(stand: ConnectorStand, naam: string): string[] {
  const nu = actieveConnectors(stand);
  return nu.includes(naam) ? nu.filter((n) => n !== naam) : actieveConnectors({ ...stand, gesprek: [...nu, naam] });
}

/** De onderdelen van de regel op de knop: Wetgeving · Kamerstukken · Rechtspraak, elk aan of uit. De werkplek tekent het
 *  vinkje als icoon (`components/ui/Icoon`), niet als teken: dat valt buiten de subset van het font. */
export function menuRegel(stand: ConnectorStand): { label: string; aan: boolean }[] {
  const aan = actieveConnectors(stand);
  return [{ label: "Wetgeving", aan: true }, ...stand.beschikbaar.map((c) => ({ label: c.label, aan: aan.includes(c.naam) }))];
}

/** De toegankelijke naam van de knop: "Bronnen: Wetgeving aan, Kamerstukken aan, Rechtspraak uit". */
export function menuNaam(stand: ConnectorStand): string {
  return `Bronnen: ${menuRegel(stand).map((d) => `${d.label} ${d.aan ? "aan" : "uit"}`).join(", ")}`;
}
