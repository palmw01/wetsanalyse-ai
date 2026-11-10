"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { haalConnectors } from "./api";
import { connectorLijst, type ConnectorLijst } from "./connectorLijst";

const LEEG: ConnectorLijst = { beschikbaar: [], laden: null };

/** De lijst van het menu *Bronnen en tools* voor dit venster (`lib/connectorLijst.ts`): bij elke mount de laatst bekende
 *  stand, en meteen een verse poging op de achtergrond. `actief` false (de demo) haalt niets op. */
export function useConnectorLijst(actief: boolean) {
  const stand = useSyncExternalStore(connectorLijst.abonneer, connectorLijst.lees, () => LEEG);
  const ververs = useCallback(() => { if (actief) void connectorLijst.ververs(haalConnectors); }, [actief]);
  useEffect(() => { ververs(); }, [ververs]);
  return { ...(actief ? stand : LEEG), ververs, legBronstandOver: connectorLijst.legBronstandOver };
}
