// Waar de beurt van dit venster staat: één waarde in plaats van `bezig`, `bezigRef`, `runId` en `stopt` naast elkaar.
//
// - `rust`: er loopt hier niets; een nieuwe beurt mag beginnen;
// - `starten`: een vraag is aangenomen en de werkplek maakt het gesprek aan of start de run;
// - `volgen`: de werkplek kijkt mee met een run;
// - `herstellen`: de verbinding met de run viel weg en de werkplek wacht om opnieuw aan te haken. De run zelf loopt
//   door bij de agent.
//
// `stopt`: stoppen is gevraagd maar nog niet gebeurd. De agent stopt op een nodegrens; dat kan tientallen seconden
// duren, en de knop hoort dat te tonen.
//
// Puur, zodat vitest de overgangen kan toetsen. `useBeurt` houdt de stand ook synchroon in een ref bij: twee Enters in
// dezelfde tick mogen geen twee beurten starten.

export type BeurtFase =
  | { soort: "rust" }
  | { soort: "starten" }
  | { soort: "volgen"; runId: string; stopt: boolean }
  | { soort: "herstellen"; runId: string; poging: number; stopt: boolean };

export type FaseActie =
  /** Een nieuwe beurt claimt het venster (alleen vanuit rust). */
  | { type: "claim" }
  /** De werkplek haakt aan bij een run (een verse beurt, een 409, of hervatten). */
  | { type: "aangehaakt"; runId: string }
  /** De verbinding viel weg; de werkplek wacht. */
  | { type: "verbroken"; poging: number }
  | { type: "stopGevraagd" }
  | { type: "stopMislukt" }
  /** De beurt is voorbij, of is nooit begonnen (een fout vóór de run). */
  | { type: "einde" };

export const RUST: BeurtFase = { soort: "rust" };

export function faseReducer(f: BeurtFase, a: FaseActie): BeurtFase {
  switch (a.type) {
    case "claim": return f.soort === "rust" ? { soort: "starten" } : f;
    case "aangehaakt": return { soort: "volgen", runId: a.runId, stopt: "stopt" in f ? f.stopt : false };
    case "verbroken":
      return f.soort === "volgen" || f.soort === "herstellen"
        ? { soort: "herstellen", runId: f.runId, poging: a.poging, stopt: f.stopt } : f;
    case "stopGevraagd": return f.soort === "volgen" || f.soort === "herstellen" ? { ...f, stopt: true } : f;
    case "stopMislukt": return f.soort === "volgen" || f.soort === "herstellen" ? { ...f, stopt: false } : f;
    case "einde": return RUST;
  }
}

/** Mag er een nieuwe beurt beginnen? Alleen als er hier niets loopt. */
export function magStarten(f: BeurtFase): boolean {
  return f.soort === "rust";
}

/** Toont de werkplek dat hij bezig is (stopknop, invoer dicht)? */
export function isBezig(f: BeurtFase): boolean {
  return f.soort !== "rust";
}

/** De run waarmee de werkplek nu verbonden is of opnieuw verbindt. */
export function lopendeRunId(f: BeurtFase): string | null {
  return f.soort === "volgen" || f.soort === "herstellen" ? f.runId : null;
}

/** Kan de stopknop iets doen? Er is een run, en stoppen is nog niet gevraagd. */
export function stopBaar(f: BeurtFase): boolean {
  return (f.soort === "volgen" || f.soort === "herstellen") && !f.stopt;
}

export function stoptNu(f: BeurtFase): boolean {
  return (f.soort === "volgen" || f.soort === "herstellen") && f.stopt;
}
