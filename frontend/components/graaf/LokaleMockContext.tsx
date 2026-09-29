"use client";

import { createContext, useContext } from "react";

/** Een lokaal voorbeeld mag ook vanuit gedeelde chrome nooit echte mutaties starten. */
export const LokaleMockContext = createContext<((melding: string) => void) | null>(null);
export const useLokaleMock = () => useContext(LokaleMockContext);
