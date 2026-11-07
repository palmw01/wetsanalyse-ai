// Eén run volgen tot hij echt afloopt: aanhaken, en bij een weggevallen verbinding wachten en opnieuw aanhaken.
//
// Dit was een recursieve `volgBeurt` in `WerkplekClient`: elke breuk riep zichzelf opnieuw aan. Nu is het één lus per
// run, met de afhankelijkheden ingespoten, zodat vitest hem kan doorlopen zonder DOM, netwerk of klok. De regels
// zelf staan in `lib/lopendeRun.ts` (`naEenGebrokenStream`, `definitieveStroomfout`, `herstelWachttijd`).
//
// - Alleen `done` sluit een beurt: `verwerkSseStroom` gooit bij een stroom die zonder `done` sluit, en dan haakt de
//   lus opnieuw aan.
// - Elke poging begint met een lege stand: opnieuw aanhaken speelt de eventlog vanaf `seq 0` terug.
// - Losgekoppeld (unmount, van gesprek wisselen, de stopknop koppelt niet los) is geen einde en geen fout: de run
//   draait door bij de agent.

import type { FaseActie } from "./beurtFase";
import { LEGE_STAND, stroomReducer, type StroomEvent, type StroomStand } from "./beurtStroom";
import { definitieveStroomfout, herstelWachttijd, naEenGebrokenStream } from "./lopendeRun";

export type LusUitkomst =
  /** De stroom liep tot `done`. */
  | { soort: "klaar"; stand: StroomStand }
  /** Een fout waar opnieuw aanhaken niet bij helpt (`definitieveStroomfout`). */
  | { soort: "mislukt"; stand: StroomStand; fout: unknown }
  /** Wij koppelden zelf los, of het venster is weg. */
  | { soort: "losgekoppeld" };

/** Wat een poging krijgt: zijn eigen stand, en de reducer erop. */
export interface PogingStand {
  pas: (e: StroomEvent) => StroomStand;
  stand: () => StroomStand;
}

export interface LusDeps {
  /** Eén poging: haak aan vanaf `seq 0` en verwerk de stroom tot het einde. Gooit bij een breuk of fout. */
  poging: (p: PogingStand) => Promise<void>;
  /** Wacht `ms`; `false` = niet meer opnieuw aanhaken (het venster is weg). */
  wacht: (ms: number) => Promise<boolean>;
  /** Leeft het venster nog? */
  levend: () => boolean;
  /** De verbinding viel weg; de lus gaat wachten. `poging` telt vanaf 0. */
  opVerbroken?: (poging: number) => void;
  /** Na elke poging die begon, wat de afloop ook is. */
  naPoging?: () => void;
  /** Eén keer, als de lus terugkomt (klaar, mislukt of losgekoppeld). Niet tussen twee pogingen: dan loopt de beurt nog. */
  opEinde?: () => void;
}

/** Wat de lus met de fase van het venster doet. Tussen twee pogingen loopt de run door bij de agent, dus staat de fase op
 *  `herstellen` (stopknop zichtbaar, geen nieuwe beurt) en niet op rust: anders kon een getypte vraag of `hervat` een
 *  tweede lus op dezelfde run starten. Rust komt pas als de lus echt terugkomt. */
export function faseHaken(zet: (a: FaseActie) => void): Required<Pick<LusDeps, "opVerbroken" | "opEinde">> {
  return {
    opVerbroken: (poging) => zet({ type: "verbroken", poging }),
    opEinde: () => zet({ type: "einde" }),
  };
}

/** Is dit een door onszelf afgebroken stream, of een echte fout? */
export function isAfgebroken(e: unknown): boolean {
  return (e as Error)?.name === "AbortError";
}

export async function volgTotEinde(deps: LusDeps): Promise<LusUitkomst> {
  try {
    return await lus(deps);
  } finally {
    deps.opEinde?.();
  }
}

async function lus(deps: LusDeps): Promise<LusUitkomst> {
  // Kwam er iets over een verbinding binnen, dan telt de volgende breuk als een verse onderbreking en begint de
  // wachttijd weer onderaan – anders zou een lange beurt met twee losse dips in de hoogste backoff blijven hangen.
  let herstel = 0;
  for (;;) {
    // Het venster is tussen het besluit en dit moment verdwenen: niet alsnog aanhaken. De run loopt door.
    if (!deps.levend()) return { soort: "losgekoppeld" };
    let stand = LEGE_STAND;
    const p: PogingStand = { pas: (e) => (stand = stroomReducer(stand, e)), stand: () => stand };
    let besluit: ReturnType<typeof naEenGebrokenStream>;
    try {
      await deps.poging(p);
      return { soort: "klaar", stand };
    } catch (e) {
      besluit = naEenGebrokenStream(isAfgebroken(e), deps.levend(), definitieveStroomfout(e));
      if (besluit === "negeren") return { soort: "losgekoppeld" };
      if (besluit === "melden") return { soort: "mislukt", stand, fout: e };
      deps.opVerbroken?.(herstel);
    } finally {
      deps.naPoging?.();
    }
    // Even wachten: valt de verbinding weg doordat de dienst opnieuw opstart, dan is meteen opnieuw proberen
    // gegarandeerd weer mis. De wachttijd loopt op, maar `wacht` wordt gewekt zodra het netwerk terug is of het
    // tabblad weer in beeld komt (`wachtMetWekker`).
    if (!deps.levend() || !(await deps.wacht(herstelWachttijd(herstel)))) return { soort: "losgekoppeld" };
    herstel = stand.ontving ? 0 : herstel + 1;
  }
}
