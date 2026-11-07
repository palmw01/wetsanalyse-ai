import { describe, expect, it } from "vitest";
import { GAT_IN_DENK, GAT_IN_TEKST, LEGE_STAND, afronding, frameplanner, stroomReducer, type StroomEvent } from "./beurtStroom";

const speel = (events: StroomEvent[]) => events.reduce(stroomReducer, LEGE_STAND);
const ART = "urn:bwb:BWBR0004770:artikel:9";
const REEKS_START = {
  type: "reeks", fase: "start", run_id: "run-1", totaal: 2,
  ouder: { bron_iri: ART, label: "Artikel 9" },
  onderdelen: [{ bron_iri: `${ART}:lid:1`, label: "Lid 1" }, { bron_iri: `${ART}:lid:2`, label: "Lid 2" }],
};

describe("stroomReducer", () => {
  it("hoopt tekst en denkregels op zoals de werkplek ze toont", () => {
    const s = speel([
      { type: "status", bericht: "Graaf bevragen" }, { type: "status", bericht: "Antwoord" },
      { type: "reason", tekst: " – nog even" }, { type: "token", tekst: "Het " }, { type: "token", tekst: "antwoord." },
    ]);
    expect(s.denk).toBe("· Graaf bevragen\n· Antwoord – nog even");
    expect(s.tekst).toBe("Het antwoord.");
  });

  it("een gat komt in de tekst als die er al is, anders in het denkproces", () => {
    expect(speel([{ type: "token", tekst: "Half" }, { type: "gat" }]).tekst).toBe("Half" + GAT_IN_TEKST);
    const zonder = speel([{ type: "status", bericht: "Bron" }, { type: "gat" }]);
    expect(zonder.tekst).toBe("");
    expect(zonder.denk).toBe("· Bron\n" + GAT_IN_DENK);
    expect(speel([{ type: "gat" }]).denk).toBe(GAT_IN_DENK);
  });

  it("leeft zet `ontving`, en verder niets", () => {
    expect(LEGE_STAND.ontving).toBe(false);
    const s = speel([{ type: "leeft" }]);
    expect(s).toEqual({ ...LEGE_STAND, ontving: true });
    expect(stroomReducer(s, { type: "leeft" })).toBe(s);
  });

  it("een event dat de reeks niet raakt, laat de stand gelijk", () => {
    expect(speel([{ type: "reeks", event: { type: "status", message: "x" } }])).toBe(LEGE_STAND);
    const r = speel([{ type: "token", tekst: "Inleiding" }, { type: "reeks", event: REEKS_START }]);
    expect(r.reeks?.runId).toBe("run-1");
    expect(r.tekst).toBe("Inleiding");
  });

  it("tool-events worden samengevoegd per aanroep", () => {
    const s = speel([
      { type: "tool", event: { type: "tool_execution", run_id: "r", call_id: "c1", tool: "t", phase: "start" } as never },
      { type: "tool", event: { type: "tool_execution", run_id: "r", call_id: "c1", tool: "t", phase: "end", status: "ok" } as never },
    ]);
    expect(s.toolExecutions).toHaveLength(1);
  });

  it("dezelfde eventlog twee keer afspelen geeft dezelfde stand (opnieuw verbinden vanaf seq 0)", () => {
    const log: StroomEvent[] = [
      { type: "leeft" }, { type: "status", bericht: "Bron" }, { type: "token", tekst: "Antwoord" },
      { type: "opgeslagen", uitkomst: { run_id: "r1" } },
    ];
    expect(speel(log)).toEqual(speel(log));
    expect(speel(log).tekst).toBe("Antwoord");
  });

  it("de stand begint elke keer leeg: LEGE_STAND wordt niet gewijzigd", () => {
    speel([{ type: "token", tekst: "x" }, { type: "kandidaten", kandidaten: [{ bron_iri: ART } as never] }]);
    expect(LEGE_STAND.tekst).toBe("");
    expect(LEGE_STAND.kandidaten).toEqual([]);
  });
});

describe("afronding", () => {
  it("reeks > kandidaten > opgeslagen > tekst/leeg", () => {
    const kand: StroomEvent = { type: "kandidaten", kandidaten: [{ bron_iri: ART } as never] };
    const opg: StroomEvent = { type: "opgeslagen", uitkomst: { run_id: "r" } };
    expect(afronding(speel([{ type: "reeks", event: REEKS_START }, kand, opg]))).toBe("reeks");
    expect(afronding(speel([kand, opg]))).toBe("kandidaten");
    expect(afronding(speel([opg]))).toBe("opgeslagen");
    expect(afronding(speel([{ type: "token", tekst: "Antwoord" }]))).toBe("tekst");
    expect(afronding(speel([{ type: "token", tekst: "  " }]))).toBe("leeg");
    expect(afronding(LEGE_STAND)).toBe("leeg");
  });
});

describe("frameplanner", () => {
  function nepFrames() {
    const wachtend = new Map<number, () => void>();
    let volgend = 0;
    return {
      raf: (f: () => void) => { wachtend.set(++volgend, f); return volgend; },
      caf: (id: number) => { wachtend.delete(id); },
      frame: () => { const fs = [...wachtend.values()]; wachtend.clear(); fs.forEach((f) => f()); },
      wachtend: () => wachtend.size,
    };
  }

  it("honderd tokens in één frame geven één schrijfbeurt", () => {
    const f = nepFrames();
    let geschreven = 0;
    const p = frameplanner(() => { geschreven++; }, f.raf, f.caf);
    for (let i = 0; i < 100; i++) p.plan();
    expect(geschreven).toBe(0);
    f.frame();
    expect(geschreven).toBe(1);
    p.plan();
    f.frame();
    expect(geschreven).toBe(2);
  });

  it("nu() schrijft de wachtende stand meteen, en het frame schrijft daarna niet nog eens", () => {
    const f = nepFrames();
    const log: string[] = [];
    let tekst = "a";
    const p = frameplanner(() => log.push(tekst), f.raf, f.caf);
    p.plan();
    tekst = "ab";
    p.nu();
    expect(log).toEqual(["ab"]);
    f.frame();
    expect(log).toEqual(["ab"]);
    p.nu(); // niets wachtend: geen schrijfbeurt
    expect(log).toEqual(["ab"]);
  });

  it("annuleer() gooit het wachtende frame weg", () => {
    const f = nepFrames();
    let geschreven = 0;
    const p = frameplanner(() => { geschreven++; }, f.raf, f.caf);
    p.plan();
    p.annuleer();
    expect(f.wachtend()).toBe(0);
    f.frame();
    expect(geschreven).toBe(0);
  });
});
