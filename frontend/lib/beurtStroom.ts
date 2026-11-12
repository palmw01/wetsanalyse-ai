// Wat er van één poging om een beurt te volgen binnenkomt, als één stand.
//
// Dit waren de losse `let`s in `WerkplekClient.volgBeurt`. Ze staan hier als reducer, omdat vitest node-env draait
// zonder DOM, en omdat het opnieuw verbinden de eventlog vanaf `seq 0` terugspeelt: elke poging begint met een lege
// stand (`LEGE_STAND`), en dezelfde events geven dan dezelfde stand. Wat een event direct op de bubbel zet (bronnen,
// grounding, het sjabloon, het overzicht, het kaartje) blijft een schrijfactie in het component; hier staat alleen
// wat zich ophoopt en wat het einde van de beurt bepaalt.

import type { AgentDoel, AgentHergebruik, AgentKandidaat, AgentKeuze, BeurtMeting, Bevestiging } from "./types";
import type { Artefact } from "./artefact";
import { type NodeDoel } from "./annotatieNode";
import { verwerkReeksEvent, type Reeks } from "./reeks";
import { denkBij } from "./denkproces";
import type { Vervolg } from "./vraagLex";

/** Het `opgeslagen`-event: de agent legde de beurt vast. De werkplek schrijft een beurt nooit zelf weg. */
export interface Opgeslagen {
  run_id: string;
  artefact?: Artefact;
  annotatie_doel?: NodeDoel;
  bevestiging?: Bevestiging;
  vervolg?: Vervolg;
}

export interface StroomStand {
  tekst: string;
  denk: string;
  /** Een reeks (meerdere onderdelen in één run): de stroom wordt per onderdeel ingedeeld. */
  reeks: Reeks | null;
  kandidaten: AgentKandidaat[];
  keuze?: AgentKeuze;
  doel: AgentDoel | null;
  hergebruik?: AgentHergebruik;
  meting?: BeurtMeting;
  opgeslagen: Opgeslagen | null;
  /** Kwam er iets over déze verbinding binnen? Dan telt een volgende breuk als een verse onderbreking. */
  ontving: boolean;
}

export const LEGE_STAND: StroomStand = {
  tekst: "", denk: "", reeks: null, kandidaten: [], doel: null, opgeslagen: null, ontving: false,
};

export type StroomEvent =
  | { type: "leeft" }
  | { type: "status"; bericht: string }
  | { type: "reason"; tekst: string }
  | { type: "token"; tekst: string }
  | { type: "doel"; doel: AgentDoel }
  | { type: "kandidaten"; kandidaten: AgentKandidaat[]; keuze?: AgentKeuze }
  | { type: "reeks"; event: Record<string, unknown> }
  | { type: "hergebruik"; hergebruik: AgentHergebruik }
  | { type: "meting"; meting?: BeurtMeting }
  /** De eventlog van de run is gecapt: er viel narratie weg. */
  | { type: "gat" }
  | { type: "opgeslagen"; uitkomst: Opgeslagen };

/** Er viel narratie weg. Stond er al antwoordtekst, dan is die mogelijk onvolledig en komt het gat daar; anders raakte
 *  het alleen het denkproces, en zou een "…" in het antwoord een gat suggereren dat er niet is. */
export const GAT_IN_TEKST = "\n\n…\n\n";

export function stroomReducer(s: StroomStand, e: StroomEvent): StroomStand {
  switch (e.type) {
    case "leeft": return s.ontving ? s : { ...s, ontving: true };
    case "status": return { ...s, denk: denkBij(s.denk, "status", e.bericht) };
    case "reason": return { ...s, denk: denkBij(s.denk, "reason", e.tekst) };
    case "token": return { ...s, tekst: s.tekst + e.tekst };
    case "doel": return { ...s, doel: e.doel };
    case "kandidaten": return { ...s, kandidaten: e.kandidaten, keuze: e.keuze };
    case "reeks": {
      const volgende = verwerkReeksEvent(s.reeks, e.event);
      return !volgende || volgende === s.reeks ? s : { ...s, reeks: volgende };
    }
    case "hergebruik": return { ...s, hergebruik: e.hergebruik };
    case "meting": return { ...s, meting: e.meting };
    case "gat": return s.tekst
      ? { ...s, tekst: s.tekst + GAT_IN_TEKST }
      : { ...s, denk: denkBij(s.denk, "gat") };
    case "opgeslagen": return { ...s, opgeslagen: e.uitkomst };
  }
}

/** Wat het item wordt als de stroom netjes afliep, in deze volgorde:
 *  - `reeks`: legt zichzelf per onderdeel vast (graph-qa); het blok staat al in beeld;
 *  - `kandidaten`: een keuzelijst in de thread, geen uitkomst die is vastgelegd;
 *  - `opgeslagen`: de agent legde het vast; nu alleen nog tonen wat er staat – de api is de bron;
 *  - `leeg`: geen `opgeslagen` en geen tekst: het gesprek werd verwijderd terwijl de beurt liep;
 *  - `tekst`: een gewoon antwoord, dat al in beeld staat. */
export type Afronding = "reeks" | "kandidaten" | "opgeslagen" | "leeg" | "tekst";

export function afronding(s: StroomStand): Afronding {
  if (s.reeks) return "reeks";
  if (s.kandidaten.length) return "kandidaten";
  if (s.opgeslagen) return "opgeslagen";
  return s.tekst.trim() ? "tekst" : "leeg";
}

/** Tokens en denkregels komen tientallen keren per seconde binnen. Elke keer de thread bijwerken renderde het hele
 *  gesprek per token; met deze planner hooguit één keer per frame.
 *  - `plan()`: schrijf bij het volgende frame (een tweede aanroep in hetzelfde frame doet niets);
 *  - `nu()`: schrijf de wachtende stand meteen weg. Vóór elke andere bijwerking van dit item, zodat er nooit een
 *    oudere tekst overheen komt;
 *  - `annuleer()`: gooi het wachtende frame weg. Bij een fout, zodat een half frame met oudere tekst de melding of
 *    het herstel niet overschrijft. */
export function frameplanner(
  schrijf: () => void,
  raf: (f: () => void) => number = (f) => requestAnimationFrame(f),
  caf: (id: number) => void = (id) => cancelAnimationFrame(id),
) {
  let frame = 0;
  return {
    plan() {
      if (frame) return;
      frame = raf(() => { frame = 0; schrijf(); });
    },
    nu() {
      if (!frame) return;
      caf(frame);
      frame = 0;
      schrijf();
    },
    annuleer() {
      if (frame) caf(frame);
      frame = 0;
    },
  };
}
