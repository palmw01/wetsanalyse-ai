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

/** De connectors die in deze beurt aanstaan, in de volgorde van `beschikbaar`. */
export function actieveConnectors({ beschikbaar, gesprek, werkgebied }: ConnectorStand): string[] {
  const gekozen = gesprek ?? werkgebied ?? beschikbaar.map((c) => c.naam);
  return beschikbaar.map((c) => c.naam).filter((n) => gekozen.includes(n));
}

/** Waar de stand vandaan komt, voor de toelichting in het menu. */
export function herkomstVan({ gesprek, werkgebied }: ConnectorStand): "gesprek" | "werkgebied" | "standaard" {
  return gesprek != null ? "gesprek" : werkgebied != null ? "werkgebied" : "standaard";
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
