/** De lijst van het menu *Bronnen en tools* (ADR-013) voor dit venster: wat de beheerder aanzette en of de omgeving het
 *  aanbiedt (`GET /api/connectors`), met hoe het laatste ophalen afliep.
 *
 *  Eén lijst per venster, niet per gesprek: `WorkbenchShell` mount de werkplek opnieuw bij elk gesprek (`mountKey`), en
 *  een eigen state begon dan leeg, zodat het menu wegbleef tot de BFF antwoordde – bij een koude graph-qa seconden lang.
 *  Nu toont een nieuwe mount meteen de laatst bekende lijst en ververst hij op de achtergrond. Een mislukte poging laat
 *  de lijst staan en zegt dat ze niet te controleren is (`laden: "mislukt"`): nooit stil leeg.
 *
 *  Zonder React, zodat het in vitest te toetsen is; `useConnectorLijst` is de hook erbovenop. */
import { uitBronstand, type BeschikbareConnector, type BronstandRegel } from "./connectorsMenu";

export interface ConnectorLijst {
  beschikbaar: BeschikbareConnector[];
  /** `null`: nog nooit opgehaald in dit venster. */
  laden: "ok" | "mislukt" | null;
}

export type Haal = () => Promise<{ connectors?: BeschikbareConnector[] }>;

export function maakConnectorLijst() {
  let stand: ConnectorLijst = { beschikbaar: [], laden: null };
  let lopend: Promise<void> | null = null;
  const luisteraars = new Set<() => void>();
  const zet = (nieuw: ConnectorLijst) => {
    stand = nieuw;
    luisteraars.forEach((f) => f());
  };
  return {
    lees: (): ConnectorLijst => stand,
    abonneer(f: () => void): () => void {
      luisteraars.add(f);
      return () => { luisteraars.delete(f); };
    },
    /** Haal de lijst opnieuw op. Loopt er al een poging, dan wacht deze daarop (geen dubbele verzoeken). */
    ververs(haal: Haal): Promise<void> {
      lopend ??= haal()
        .then((r) => zet({ beschikbaar: r.connectors ?? [], laden: "ok" }))
        .catch(() => zet({ ...stand, laden: "mislukt" }))
        .finally(() => { lopend = null; });
      return lopend;
    },
    /** Wat graph-qa in een beurt over de omgeving vaststelde (`bronstand`-event). */
    legBronstandOver(regels: BronstandRegel[]) {
      const beschikbaar = uitBronstand(stand.beschikbaar, regels);
      if (beschikbaar.some((c, i) => c !== stand.beschikbaar[i])) zet({ ...stand, beschikbaar });
    },
  };
}

/** De lijst van dit venster. */
export const connectorLijst = maakConnectorLijst();
