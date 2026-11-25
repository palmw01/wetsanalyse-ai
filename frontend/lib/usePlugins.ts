"use client";

// De plugins die de beheerder aanbiedt, voor het hele venster (plan contenttoets, C4): zoals de connectorlijst toont een
// nieuwe mount (ander gesprek) meteen de laatst bekende stand en haalt hij hoogstens één keer tegelijk op.

import { useEffect, useState } from "react";

import { haalPlugins } from "./api";
import type { AangebodenPlugin } from "./plugins";

let laatst: AangebodenPlugin[] = [];
let bezig: Promise<AangebodenPlugin[]> | null = null;

export function usePlugins(aan: boolean): AangebodenPlugin[] {
  const [lijst, setLijst] = useState<AangebodenPlugin[]>(laatst);
  useEffect(() => {
    if (!aan) return;
    let levend = true;
    bezig ??= haalPlugins().finally(() => { bezig = null; });
    void bezig.then((l) => { laatst = l; if (levend) setLijst(l); });
    return () => { levend = false; };
  }, [aan]);
  return lijst;
}
