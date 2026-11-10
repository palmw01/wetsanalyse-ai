/** De lijst van het menu *Bronnen en tools* (ADR-013) voor dit venster: wat de beheerder aanzette en of de omgeving het
 *  aanbiedt (`GET /api/connectors`), met hoe het laatste ophalen afliep.
 *
 *  Eén lijst per venster, niet per gesprek: `WorkbenchShell` mount de werkplek opnieuw bij elk gesprek (`mountKey`), en
 *  een eigen state begon dan leeg, zodat het menu wegbleef tot de BFF antwoordde – bij een koude graph-qa seconden lang.
 *  Nu toont een nieuwe mount meteen de laatst bekende lijst en ververst hij op de achtergrond.
 *
 *  Laden is geen oordeel. Is de stand niet vast te stellen (een fout, of `onbekend` omdat graph-qa koud start), dan
 *  volgt een korte reeks herpogingen (`HERPOGINGEN`) en staat `controleert` aan: het menu toont dan "wordt
 *  gecontroleerd". Pas als de reeks op is, is het `onbekend` of `laden: "mislukt"` met een melding; de lijst blijft staan.
 *
 *  Zonder React, zodat het in vitest te toetsen is; `useConnectorLijst` is de hook erbovenop. */
import { uitBronstand, type BeschikbareConnector, type BronstandRegel } from "./connectorsMenu";

export interface ConnectorLijst {
  beschikbaar: BeschikbareConnector[];
  /** `null`: nog nooit opgehaald in dit venster. `mislukt` pas als alle pogingen van een reeks faalden. */
  laden: "ok" | "mislukt" | null;
  /** Er loopt een poging, of er komt er nog een: een `onbekend` is dan nog geen oordeel maar "wordt gecontroleerd". */
  controleert: boolean;
}

export type Haal = () => Promise<{ connectors?: BeschikbareConnector[] }>;

/** Wachttijden (ms) vóór de volgende poging als de stand niet vast te stellen was. Samen ruim een koude start van
 *  graph-qa (`minReplicas: 0`). Daarna geen timer meer: een nieuwe reeks begint pas bij focus, het openen van het menu
 *  of een beurt. */
export const HERPOGINGEN = [2_000, 4_000, 8_000, 16_000];

export interface Opties {
  /** Plant `f` over `ms`; geeft een functie die het plan intrekt. Voor tests. */
  wacht?: (ms: number, f: () => void) => () => void;
  /** De wachttijden; standaard `HERPOGINGEN`, of `window.__connectorHerpogingen` in de browsertest. */
  herpogingen?: () => number[];
}

const standaardWacht = (ms: number, f: () => void) => {
  const t = setTimeout(f, ms);
  return () => clearTimeout(t);
};
const standaardHerpogingen = () =>
  (globalThis as { __connectorHerpogingen?: number[] }).__connectorHerpogingen ?? HERPOGINGEN;

const heeftOnbekend = (lijst: BeschikbareConnector[]) => lijst.some((c) => c.beschikbaarheid === "onbekend");

export function maakConnectorLijst({ wacht = standaardWacht, herpogingen = standaardHerpogingen }: Opties = {}) {
  let stand: ConnectorLijst = { beschikbaar: [], laden: null, controleert: false };
  let lopend: Promise<void> | null = null;
  let gepland: (() => void) | null = null;
  let laatsteHaal: Haal | null = null;
  const luisteraars = new Set<() => void>();
  const zet = (nieuw: ConnectorLijst) => {
    stand = nieuw;
    luisteraars.forEach((f) => f());
  };

  /** Eén poging van de reeks; `n` = hoeveel herpogingen er al geweest zijn. */
  const poging = (haal: Haal, n: number): Promise<void> => {
    lopend = haal()
      .then((r) => ({ ok: true as const, beschikbaar: r.connectors ?? [] }))
      .catch(() => ({ ok: false as const, beschikbaar: stand.beschikbaar }))
      .then((uitkomst) => {
        lopend = null;
        const onzeker = !uitkomst.ok || heeftOnbekend(uitkomst.beschikbaar);
        const wachttijden = herpogingen();
        const nogEen = onzeker && n < wachttijden.length;
        if (nogEen) gepland = wacht(wachttijden[n], () => { gepland = null; void poging(haal, n + 1); });
        zet({
          beschikbaar: uitkomst.beschikbaar,
          // Tijdens de reeks blijft een fout onzichtbaar: pas als de pogingen op zijn, is het ophalen mislukt.
          laden: uitkomst.ok ? "ok" : nogEen ? stand.laden : "mislukt",
          controleert: nogEen,
        });
      });
    if (!stand.controleert) zet({ ...stand, controleert: true });
    return lopend;
  };

  return {
    lees: (): ConnectorLijst => stand,
    abonneer(f: () => void): () => void {
      luisteraars.add(f);
      return () => { luisteraars.delete(f); };
    },
    /** Haal de lijst opnieuw op, als begin van een reeks. Loopt er al een reeks (een poging of een geplande), dan
     *  gebeurt er niets extra: geen dubbele verzoeken en geen tweede timer. */
    ververs(haal: Haal): Promise<void> {
      laatsteHaal = haal;
      if (lopend) return lopend;
      if (gepland) return Promise.resolve();
      return poging(haal, 0);
    },
    /** Wat graph-qa in een beurt over de omgeving vaststelde (`bronstand`-event). Wordt een bron daardoor `onbekend`,
     *  dan begint een reeks: eerst "wordt gecontroleerd", geen oordeel. */
    legBronstandOver(regels: BronstandRegel[]) {
      const beschikbaar = uitBronstand(stand.beschikbaar, regels);
      if (!beschikbaar.some((c, i) => c !== stand.beschikbaar[i])) return;
      zet({ ...stand, beschikbaar });
      if (heeftOnbekend(beschikbaar) && laatsteHaal && !lopend && !gepland) void poging(laatsteHaal, 0);
    },
  };
}

/** De lijst van dit venster. */
export const connectorLijst = maakConnectorLijst();
