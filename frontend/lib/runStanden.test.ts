import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  type ActieveRun, heeftSpoor, maakPeiler, markeerGezien, netAfgerond, parseActieveRuns, PEIL_INTERVAL_MS, standenUit,
} from "@/lib/runStanden";
import { kaleTitel, tabTitel } from "@/lib/tabTitel";
import type { LopendeRuns } from "@/lib/lopendeRun";

const run = (run_id: string, conversation_id: string, status: ActieveRun["status"]): ActieveRun =>
  ({ run_id, conversation_id, status });

describe("standen per gesprek", () => {
  it("lopend is bezig, afgerond en ongezien is nieuw", () => {
    const runs = [run("r1", "A", "loopt"), run("r2", "B", "klaar"), run("r3", "C", "mislukt"), run("r4", "D", "gestopt")];
    expect(standenUit(runs, new Set(["r4"]), null)).toEqual({ A: "loopt", B: "nieuw", C: "nieuw" });
  });

  it("het open gesprek heeft nooit een nieuw antwoord, wel een lopende beurt", () => {
    expect(standenUit([run("r1", "A", "klaar")], new Set(), "A")).toEqual({});
    expect(standenUit([run("r1", "A", "loopt")], new Set(), "A")).toEqual({ A: "loopt" });
  });

  it("een lopende beurt wint van een eerder antwoord in hetzelfde gesprek", () => {
    expect(standenUit([run("r1", "B", "klaar"), run("r2", "B", "loopt")], new Set(), null)).toEqual({ B: "loopt" });
  });
});

describe("gezien", () => {
  it("een afgeronde run in het open gesprek telt als gezien; lopend nog niet", () => {
    const runs = [run("r1", "A", "klaar"), run("r2", "A", "loopt"), run("r3", "B", "klaar")];
    expect([...markeerGezien(new Set(), runs, "A")]).toEqual(["r1"]);
  });

  it("het register houdt alleen wat de agent nog noemt", () => {
    expect([...markeerGezien(new Set(["oud", "r3"]), [run("r3", "B", "klaar")], null)]).toEqual(["r3"]);
  });
});

describe("spoor", () => {
  it("een lopende run of een onbekende beurt in wa_lopende_run is een spoor", () => {
    expect(heeftSpoor({}, [run("r1", "A", "loopt")], new Set())).toBe(true);
    expect(heeftSpoor({ A: "r9" }, [], new Set())).toBe(true);
    expect(heeftSpoor({ A: "r9" }, [], new Set(["r9"]))).toBe(false);
    expect(heeftSpoor({}, [run("r1", "A", "klaar")], new Set())).toBe(false);
  });
});

describe("net afgerond", () => {
  it("telt een run die liep of die we nog niet kenden, niet bij de eerste peiling", () => {
    expect(netAfgerond(null, [run("r1", "A", "klaar")])).toEqual([]);
    expect(netAfgerond([run("r1", "A", "loopt")], [run("r1", "A", "klaar"), run("r2", "B", "mislukt")])).toEqual(["r1", "r2"]);
    expect(netAfgerond([run("r1", "A", "klaar")], [run("r1", "A", "klaar")])).toEqual([]);
  });
});

describe("de vorm van het antwoord", () => {
  it("laat rare rijen vallen en geeft null bij geen lijst", () => {
    expect(parseActieveRuns(null)).toBeNull();
    expect(parseActieveRuns({ runs: [] })).toBeNull();
    expect(parseActieveRuns([{ run_id: "r1", conversation_id: "A", status: "loopt" }, { run_id: 1 },
      { run_id: "r2", conversation_id: "B", status: "raar" },
      { run_id: "r3", conversation_id: "C", status: "klaar", afgerond_op: "2026-11-07T10:00:00Z" }])).toEqual([
      { run_id: "r1", conversation_id: "A", status: "loopt" },
      { run_id: "r3", conversation_id: "C", status: "klaar", afgerond_op: "2026-11-07T10:00:00Z" },
    ]);
  });
});

describe("de peiler", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  function opzet(antwoorden: ActieveRun[][], lopend: { waarde: LopendeRuns }) {
    const haal = vi.fn(async () => antwoorden.shift() ?? []);
    const gezien: ActieveRun[][] = [];
    const p = maakPeiler({ haal, leesLopend: () => lopend.waarde, onRuns: (r) => gezien.push(r) });
    return { p, haal, gezien };
  }

  it("peilt elke 5 s zolang er een run loopt, en stopt als hij klaar is", async () => {
    const lopend = { waarde: {} as LopendeRuns };
    const { p, haal } = opzet([[run("r1", "B", "loopt")], [run("r1", "B", "loopt")], [run("r1", "B", "klaar")]], lopend);
    await p.peil();
    expect(haal).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(PEIL_INTERVAL_MS);
    await vi.advanceTimersByTimeAsync(PEIL_INTERVAL_MS);
    expect(haal).toHaveBeenCalledTimes(3);
    await vi.advanceTimersByTimeAsync(PEIL_INTERVAL_MS * 5);
    expect(haal).toHaveBeenCalledTimes(3);
    p.stop();
  });

  it("zonder spoor peilt hij niet vanzelf; een nieuw spoor in de opslag start het", async () => {
    const lopend = { waarde: {} as LopendeRuns };
    const { p, haal } = opzet([[], [run("r2", "A", "loopt")]], lopend);
    await p.peil();
    await vi.advanceTimersByTimeAsync(PEIL_INTERVAL_MS * 3);
    expect(haal).toHaveBeenCalledTimes(1);
    lopend.waarde = { A: "r2" };
    await vi.advanceTimersByTimeAsync(PEIL_INTERVAL_MS);
    expect(haal).toHaveBeenCalledTimes(2);
    p.stop();
  });

  it("een spoor dat blijft staan terwijl de run voorbij is, laat hem niet eeuwig peilen", async () => {
    const lopend = { waarde: { A: "weg" } as LopendeRuns };
    const { p, haal } = opzet([[], []], lopend);
    await p.peil();
    await vi.advanceTimersByTimeAsync(PEIL_INTERVAL_MS * 4);
    expect(haal).toHaveBeenCalledTimes(1);
    p.stop();
  });

  it("na stop doet hij niets meer", async () => {
    const lopend = { waarde: { A: "r1" } as LopendeRuns };
    const { p, haal } = opzet([], lopend);
    p.stop();
    await p.peil();
    await vi.advanceTimersByTimeAsync(PEIL_INTERVAL_MS * 3);
    expect(haal).not.toHaveBeenCalled();
  });

  it("een storing laat de vorige stand staan", async () => {
    const haal = vi.fn<() => Promise<ActieveRun[] | null>>()
      .mockResolvedValueOnce([run("r1", "B", "loopt")]).mockResolvedValueOnce(null);
    const onRuns = vi.fn();
    const p = maakPeiler({ haal, leesLopend: () => ({}), onRuns });
    await p.peil();
    await p.peil();
    expect(onRuns).toHaveBeenCalledTimes(1);
    p.stop();
  });
});

describe("de tabtitel", () => {
  it("Bezig zolang er iets loopt, Klaar bij een nieuw antwoord in een verborgen tab, anders gewoon", () => {
    expect(tabTitel("Lex · Wetsanalyse", { bezig: true, klaarVerborgen: false })).toBe("Bezig · Lex · Wetsanalyse");
    expect(tabTitel("Lex · Wetsanalyse", { bezig: true, klaarVerborgen: true })).toBe("Klaar · Lex · Wetsanalyse");
    expect(tabTitel("Bezig · Lex · Wetsanalyse", { bezig: false, klaarVerborgen: false })).toBe("Lex · Wetsanalyse");
    expect(kaleTitel("Klaar · Lex")).toBe("Lex");
  });
});
