"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { haalConnectors } from "./api";
import { connectorLijst, type ConnectorLijst } from "./connectorLijst";
import { moetVerversen } from "./connectorsMenu";

const LEEG: ConnectorLijst = { beschikbaar: [], laden: null, controleert: false };

/** Hoe vaak terugkomen in het venster (focus, zichtbaar) hoogstens een nieuwe poging start. */
const TERUGKOMST_MS = 15_000;

/** De lijst van het menu *Bronnen en tools* voor dit venster (`lib/connectorLijst.ts`): bij elke mount de laatst bekende
 *  stand, en meteen een verse poging op de achtergrond. `actief` false (de demo) haalt niets op. */
export function useConnectorLijst(actief: boolean) {
  const stand = useSyncExternalStore(connectorLijst.abonneer, connectorLijst.lees, () => LEEG);
  const ververs = useCallback(() => { if (actief) void connectorLijst.ververs(haalConnectors); }, [actief]);
  useEffect(() => { ververs(); }, [ververs]);
  // Was de stand na de herpogingen nog niet vast te stellen, dan opnieuw zodra de jurist terugkomt in het venster
  // (focus, zichtbaar worden), hoogstens eens per `TERUGKOMST_MS`. Geen timer: zonder handeling geen verzoek.
  useEffect(() => {
    if (!actief) return;
    let laatst = 0;
    const terug = () => {
      if (document.visibilityState === "hidden" || Date.now() - laatst < TERUGKOMST_MS) return;
      const s = connectorLijst.lees();
      if (s.controleert || !moetVerversen({ beschikbaar: s.beschikbaar, laden: s.laden ?? undefined })) return;
      laatst = Date.now();
      void connectorLijst.ververs(haalConnectors);
    };
    window.addEventListener("focus", terug);
    document.addEventListener("visibilitychange", terug);
    return () => {
      window.removeEventListener("focus", terug);
      document.removeEventListener("visibilitychange", terug);
    };
  }, [actief]);
  return { ...(actief ? stand : LEEG), ververs, legBronstandOver: connectorLijst.legBronstandOver };
}
