"use client";

// Fouten die geen error boundary bereiken: uit een event-handler, een timer of een belofte zonder
// `catch`. Zonder deze luisteraars staan ze alleen in de console van de gebruiker.

import { useEffect } from "react";

import { meldBrowserfout } from "@/lib/uiSpoor";

export function BrowserFouten() {
  useEffect(() => {
    const opFout = (e: ErrorEvent) => meldBrowserfout("script", e.error);
    const opBelofte = (e: PromiseRejectionEvent) => meldBrowserfout("belofte", e.reason);
    window.addEventListener("error", opFout);
    window.addEventListener("unhandledrejection", opBelofte);
    return () => {
      window.removeEventListener("error", opFout);
      window.removeEventListener("unhandledrejection", opBelofte);
    };
  }, []);
  return null;
}
