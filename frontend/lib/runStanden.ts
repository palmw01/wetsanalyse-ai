"use client";

// Welke gesprekken zijn bezig, en waar staat een antwoord dat je nog niet zag? (E6)
//
// De werkplek volgt alleen de run van het open gesprek. Wissel je van gesprek, dan loopt de beurt
// door bij de agent, maar zag je in de sidebar en in de tabtitel niets meer. Deze peiler vraagt de
// agent welke runs er lopen of net eindigden (`GET /api/annotatie/run?actief=1`) en leidt daaruit
// per gesprek een stand af.
//
// Peilen kost een verzoek en wekt een op nul geschaalde agent, dus niet blind elke paar seconden:
// - één keer bij het laden, bij focus, als het tabblad zichtbaar wordt en bij `verversSignaal`;
// - daarnaast elke 5 s, maar alleen zolang er een spoor is: een beurt in `wa_lopende_run` waarvan we
//   nog niet weten dat hij voorbij is, of een run die bij de vorige peiling nog liep.
//
// De logica staat als pure functies en een timer-gedreven peiler zonder React, zodat vitest (node,
// geen DOM) hem kan draaien; de hook onderaan is het dunne laagje eromheen.

import { useEffect, useRef, useState } from "react";

import { leesLopendeRuns, type LopendeRuns } from "@/lib/lopendeRun";

export const PEIL_INTERVAL_MS = 5_000;
const GEZIEN_SLEUTEL = "wa_runs_gezien";

export type RunStatus = "loopt" | "klaar" | "gestopt" | "mislukt";

export interface ActieveRun {
  run_id: string;
  conversation_id: string;
  status: RunStatus;
  afgerond_op?: string;
}

/** Wat de sidebar per gesprek toont: bezig, of een afgerond antwoord dat je nog niet zag. */
export type GesprekRunStand = "loopt" | "nieuw";

const STATUSSEN: readonly string[] = ["loopt", "klaar", "gestopt", "mislukt"];

/** Alleen wat klopt: de lijst is een hulpmiddel, een rare rij mag het scherm niet breken. `null` als de body geen
 *  lijst is (een storing, of een oude agent): dan weten we niets en blijft de vorige stand staan. */
export function parseActieveRuns(body: unknown): ActieveRun[] | null {
  if (!Array.isArray(body)) return null;
  return body.flatMap((r): ActieveRun[] => {
    const x = r as Record<string, unknown> | null;
    if (!x || typeof x.run_id !== "string" || typeof x.conversation_id !== "string") return [];
    if (typeof x.status !== "string" || !STATUSSEN.includes(x.status)) return [];
    return [{
      run_id: x.run_id, conversation_id: x.conversation_id, status: x.status as RunStatus,
      ...(typeof x.afgerond_op === "string" ? { afgerond_op: x.afgerond_op } : {}),
    }];
  });
}

/** De stand per gesprek. Lopend wint van nieuw; het open gesprek heeft nooit een *nieuw*: dat lees je al. */
export function standenUit(
  runs: readonly ActieveRun[], gezien: ReadonlySet<string>, activeId: string | null,
): Record<string, GesprekRunStand> {
  const uit: Record<string, GesprekRunStand> = {};
  for (const r of runs) {
    if (r.status === "loopt") uit[r.conversation_id] = "loopt";
    else if (r.conversation_id !== activeId && !gezien.has(r.run_id) && !uit[r.conversation_id])
      uit[r.conversation_id] = "nieuw";
  }
  return uit;
}

/** Het register na het bekijken van het open gesprek. Bewust beperkt tot de runs die de agent nog noemt: een run
 *  valt na tien minuten uit de lijst en komt niet terug, dus zijn id hoeft dan niet meer bewaard. */
export function markeerGezien(
  gezien: ReadonlySet<string>, runs: readonly ActieveRun[], activeId: string | null,
): Set<string> {
  const uit = new Set<string>();
  for (const r of runs) {
    if (gezien.has(r.run_id) || (r.status !== "loopt" && r.conversation_id === activeId)) uit.add(r.run_id);
  }
  return uit;
}

/** Is er reden om over vijf seconden weer te kijken? */
export function heeftSpoor(
  lopend: LopendeRuns, runs: readonly ActieveRun[], afgedaan: ReadonlySet<string>,
): boolean {
  return runs.some((r) => r.status === "loopt") || Object.values(lopend).some((id) => !afgedaan.has(id));
}

/** Welke runs zijn sinds de vorige peiling klaar gekomen? Een run die we nog niet kenden telt mee: die kan eindigen
 *  tussen twee peilingen in. */
export function netAfgerond(vorige: readonly ActieveRun[] | null, nu: readonly ActieveRun[]): string[] {
  if (vorige === null) return [];
  const eerder = new Map(vorige.map((r) => [r.run_id, r.status]));
  return nu.filter((r) => r.status !== "loopt" && (eerder.get(r.run_id) ?? "loopt") === "loopt").map((r) => r.run_id);
}

// --- de peiler (zonder React) -----------------------------------------------------------------

export interface PeilerOpties {
  /** Haalt de runs op; `null` bij een storing. */
  haal: () => Promise<ActieveRun[] | null>;
  leesLopend: () => LopendeRuns;
  onRuns: (runs: ActieveRun[], vorige: ActieveRun[] | null) => void;
  intervalMs?: number;
}

export interface Peiler {
  peil: () => Promise<void>;
  stop: () => void;
}

/** Een tik elke `intervalMs` die alleen bij een spoor een verzoek doet; de tik zelf leest alleen de opslag. */
export function maakPeiler({ haal, leesLopend, onRuns, intervalMs = PEIL_INTERVAL_MS }: PeilerOpties): Peiler {
  let runs: ActieveRun[] | null = null;
  // Beurten uit `wa_lopende_run` waarvan een peiling liet zien dat ze niet meer lopen. Het spoor blijft soms staan
  // (een tabblad dat dichtging voor het opruimde); zonder dit peilde de werkplek dan eeuwig door.
  const afgedaan = new Set<string>();
  let bezig = false;
  let nogEens = false;
  let gestopt = false;

  async function peil(): Promise<void> {
    if (gestopt) return;
    if (bezig) {
      nogEens = true;
      return;
    }
    bezig = true;
    try {
      // Vóór het verzoek gelezen: een beurt die daarna start, staat niet in dit antwoord en is dus niet afgedaan.
      const lopend = leesLopend();
      const nieuw = await haal();
      if (gestopt || nieuw === null) return;
      const loopt = new Set(nieuw.filter((r) => r.status === "loopt").map((r) => r.run_id));
      for (const id of Object.values(lopend)) if (!loopt.has(id)) afgedaan.add(id);
      const vorige = runs;
      runs = nieuw;
      onRuns(nieuw, vorige);
    } finally {
      bezig = false;
      if (nogEens && !gestopt) {
        nogEens = false;
        void peil();
      }
    }
  }

  const tik = setInterval(() => {
    if (!bezig && heeftSpoor(leesLopend(), runs ?? [], afgedaan)) void peil();
  }, intervalMs);

  return {
    peil,
    stop: () => {
      gestopt = true;
      clearInterval(tik);
    },
  };
}

// --- browser-opslag -------------------------------------------------------------------------

export function leesGezien(): Set<string> {
  try {
    const rauw = window.localStorage.getItem(GEZIEN_SLEUTEL);
    const lijst = rauw ? (JSON.parse(rauw) as unknown) : [];
    return new Set(Array.isArray(lijst) ? lijst.filter((x): x is string => typeof x === "string") : []);
  } catch {
    return new Set();
  }
}

export function schrijfGezien(gezien: ReadonlySet<string>): void {
  try {
    window.localStorage.setItem(GEZIEN_SLEUTEL, JSON.stringify([...gezien]));
  } catch {
    /* opslag niet beschikbaar: dan zie je een stip die je al zag, meer niet */
  }
}

async function haalActieveRuns(): Promise<ActieveRun[] | null> {
  try {
    const res = await fetch(`/api/annotatie/run?actief=1`, { cache: "no-store" });
    if (!res.ok) return null;
    return parseActieveRuns(await res.json());
  } catch {
    return null;
  }
}

// --- de hook --------------------------------------------------------------------------------

export interface RunStanden {
  standen: Record<string, GesprekRunStand>;
  /** Loopt er ergens een beurt, ook in het open gesprek? */
  bezig: boolean;
  /** Kwam er een antwoord binnen terwijl het tabblad verborgen was? Weer `false` zodra je kijkt. */
  klaarVerborgen: boolean;
}

export function useRunStanden(activeId: string | null, verversSignaal = 0, aan = true): RunStanden {
  const [runs, setRuns] = useState<ActieveRun[]>([]);
  const [gezien, setGezien] = useState<Set<string>>(() => new Set());
  const [klaarVerborgen, setKlaarVerborgen] = useState(false);
  const peiler = useRef<Peiler | null>(null);

  useEffect(() => {
    if (!aan) return;
    // Na het mounten: de server kent `localStorage` niet.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setGezien(leesGezien());
    const p = maakPeiler({
      haal: haalActieveRuns,
      leesLopend: leesLopendeRuns,
      onRuns: (nieuw, vorige) => {
        setRuns(nieuw);
        if (document.hidden && netAfgerond(vorige, nieuw).length > 0) setKlaarVerborgen(true);
      },
    });
    peiler.current = p;
    void p.peil();
    const bijFocus = () => void p.peil();
    const bijZicht = () => {
      if (document.hidden) return;
      setKlaarVerborgen(false);
      void p.peil();
    };
    window.addEventListener("focus", bijFocus);
    document.addEventListener("visibilitychange", bijZicht);
    return () => {
      p.stop();
      peiler.current = null;
      window.removeEventListener("focus", bijFocus);
      document.removeEventListener("visibilitychange", bijZicht);
    };
  }, [aan]);

  // Een nieuw gesprek, een hernoeming, een beurt die eindigde: de sidebar haalt zijn lijst opnieuw, wij kijken mee.
  useEffect(() => {
    if (verversSignaal > 0) void peiler.current?.peil();
  }, [verversSignaal]);

  // Het open gesprek telt als gezien. Alleen schrijven als er iets verandert, en alleen na een peiling: anders
  // gooide de eerste render het register leeg.
  useEffect(() => {
    if (!aan || runs.length === 0) return;
    const nieuw = markeerGezien(gezien, runs, activeId);
    if (nieuw.size === gezien.size && [...nieuw].every((id) => gezien.has(id))) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setGezien(nieuw);
    schrijfGezien(nieuw);
  }, [aan, runs, gezien, activeId]);

  return {
    standen: aan ? standenUit(runs, gezien, activeId) : {},
    bezig: aan && runs.some((r) => r.status === "loopt"),
    klaarVerborgen: aan && klaarVerborgen,
  };
}
