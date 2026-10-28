// De indeling van de sidebar (spoor G1): gesprekken onder hun werkgebied, losse gesprekken onder
// *Recente gesprekken*, en gearchiveerde apart. Zuiver, zodat vitest het zonder DOM toetst.

import type { GesprekSamenvatting } from "./types";

export interface WerkgebiedGroep {
  id: string;
  naam: string;
  gesprekken: GesprekSamenvatting[];
}

export interface GesprekIndeling {
  werkgebieden: WerkgebiedGroep[];
  recent: GesprekSamenvatting[];
  archief: GesprekSamenvatting[];
}

/** De api levert de lijst nieuwste eerst; die volgorde blijft binnen elke groep staan, en de
 *  werkgebieden komen in de volgorde van hun nieuwste gesprek. Een gearchiveerd gesprek staat alleen
 *  in het archief, ook als het bij een werkgebied hoort. */
export function deelIn(gesprekken: GesprekSamenvatting[]): GesprekIndeling {
  const groepen = new Map<string, WerkgebiedGroep>();
  const recent: GesprekSamenvatting[] = [];
  const archief: GesprekSamenvatting[] = [];
  for (const g of gesprekken) {
    if (g.gearchiveerd) {
      archief.push(g);
      continue;
    }
    if (!g.werkgebied_id) {
      recent.push(g);
      continue;
    }
    let groep = groepen.get(g.werkgebied_id);
    if (!groep) {
      groep = { id: g.werkgebied_id, naam: g.werkgebied_naam || "Werkgebied", gesprekken: [] };
      groepen.set(g.werkgebied_id, groep);
    }
    groep.gesprekken.push(g);
  }
  return { werkgebieden: [...groepen.values()], recent, archief };
}

/** Welke werkgebiedgroepen dichtgeklapt staan, per browser. Een open groep is de standaard: wie een
 *  gesprek in een werkgebied begint, wil het terugzien. */
const SLEUTEL = "lex.sidebar.dicht";

export function leesDicht(): Set<string> {
  try {
    const ruw = window.localStorage.getItem(SLEUTEL);
    const lijst: unknown = ruw ? JSON.parse(ruw) : [];
    return new Set(Array.isArray(lijst) ? lijst.filter((x): x is string => typeof x === "string") : []);
  } catch {
    return new Set();
  }
}

export function bewaarDicht(dicht: Set<string>): void {
  try {
    window.localStorage.setItem(SLEUTEL, JSON.stringify([...dicht]));
  } catch {
    // Geen opslag (privévenster, geblokkeerd): de stand geldt dan alleen voor deze sessie.
  }
}
