// @vitest-environment happy-dom
//
// De lijm van E6 die `runStanden.test.ts` (node) niet ziet: de hook `useRunStanden` met focus, zichtbaarheid en het
// register in `localStorage`, en de peiler bij twee peilingen tegelijk. De pure functies hebben hun eigen test.
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { leesGezien, maakPeiler, schrijfGezien, useRunStanden, type ActieveRun } from "./runStanden";

const run = (id: string, gesprek: string, status: ActieveRun["status"]): ActieveRun =>
  ({ run_id: id, conversation_id: gesprek, status });

let antwoorden: unknown[] = [];
const fetchMock = vi.fn(async () => Response.json(antwoorden.length > 1 ? antwoorden.shift() : antwoorden[0]));

function geblokkeerdeOpslag() {
  // Geblokkeerde sitedata: al het opvragen van `localStorage` gooit (SecurityError), zoals in een streng privévenster.
  const echt = Object.getOwnPropertyDescriptor(window, "localStorage");
  Object.defineProperty(window, "localStorage", { configurable: true, get: () => { throw new DOMException("geblokkeerd", "SecurityError"); } });
  return () => { if (echt) Object.defineProperty(window, "localStorage", echt); };
}

function verborgen(waarde: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => waarde });
}

beforeEach(() => {
  window.localStorage.clear();
  antwoorden = [[]];
  fetchMock.mockClear();
  vi.stubGlobal("fetch", fetchMock);
  verborgen(false);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useRunStanden", () => {
  it("toont lopend en nieuw per gesprek, en telt het open gesprek als gezien (ook na herladen)", async () => {
    antwoorden = [[run("r1", "A", "loopt"), run("r2", "B", "klaar"), run("r3", "C", "klaar")]];
    const { result } = renderHook(() => useRunStanden("C"));
    await waitFor(() => expect(result.current.standen).toEqual({ A: "loopt", B: "nieuw" }));
    expect(result.current.bezig).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith("/api/annotatie/run?actief=1", { cache: "no-store" });
    // Het open gesprek C is gezien en dat staat bewaard: een volgende pagina toont er geen stip.
    await waitFor(() => expect([...leesGezien()]).toEqual(["r3"]));
  });

  it("uit: geen verzoek en geen stand", async () => {
    const { result } = renderHook(() => useRunStanden("A", 0, false));
    expect(result.current).toEqual({ standen: {}, bezig: false, klaarVerborgen: false });
    await act(async () => {});
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("peilt opnieuw bij focus en bij verversSignaal", async () => {
    const { rerender } = renderHook(({ sig }) => useRunStanden(null, sig), { initialProps: { sig: 0 } });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await act(async () => { window.dispatchEvent(new Event("focus")); });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    rerender({ sig: 1 });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });

  it("een antwoord dat klaar kwam in een verborgen tab: klaarVerborgen, tot je weer kijkt", async () => {
    antwoorden = [[run("r1", "A", "loopt")], [run("r1", "A", "klaar")]];
    const { result } = renderHook(() => useRunStanden(null));
    await waitFor(() => expect(result.current.bezig).toBe(true));
    verborgen(true);
    await act(async () => { window.dispatchEvent(new Event("focus")); });
    await waitFor(() => expect(result.current.klaarVerborgen).toBe(true));
    // Een verborgen tab die weer zichtbaar wordt: de stand gaat terug en er wordt opnieuw gepeild.
    verborgen(false);
    await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });
    await waitFor(() => expect(result.current.klaarVerborgen).toBe(false));
  });

  it("stopt met luisteren na het unmounten", async () => {
    const { unmount } = renderHook(() => useRunStanden(null));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    unmount();
    window.dispatchEvent(new Event("focus"));
    await act(async () => {});
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("een storing (geen lijst) laat de stand staan", async () => {
    antwoorden = [[run("r1", "A", "loopt")], { detail: "kapot" }];
    const { result } = renderHook(() => useRunStanden(null));
    await waitFor(() => expect(result.current.bezig).toBe(true));
    await act(async () => { window.dispatchEvent(new Event("focus")); });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(result.current.standen).toEqual({ A: "loopt" });
  });
});

describe("het register van gezien", () => {
  it("leest alleen strings, en rommel of een ontbrekende sleutel is leeg", () => {
    window.localStorage.setItem("wa_runs_gezien", JSON.stringify(["r1", 3, null, "r2"]));
    expect([...leesGezien()]).toEqual(["r1", "r2"]);
    window.localStorage.setItem("wa_runs_gezien", "{kapot");
    expect(leesGezien().size).toBe(0);
    window.localStorage.setItem("wa_runs_gezien", JSON.stringify({ geen: "lijst" }));
    expect(leesGezien().size).toBe(0);
  });

  it("een opslag die weigert, breekt niets", () => {
    const herstel = geblokkeerdeOpslag();
    try {
      expect(() => schrijfGezien(new Set(["r1"]))).not.toThrow();
      expect(leesGezien().size).toBe(0);
    } finally {
      herstel();
    }
  });
});

describe("maakPeiler – twee peilingen tegelijk", () => {
  it("een peiling tijdens een lopende wordt er één erna, niet een tweede verzoek tegelijk", async () => {
    let los!: (r: ActieveRun[]) => void;
    const haal = vi.fn(() => new Promise<ActieveRun[] | null>((r) => { los = r; }));
    const onRuns = vi.fn();
    const p = maakPeiler({ haal, leesLopend: () => ({}), onRuns, intervalMs: 60_000 });
    const eerste = p.peil();
    void p.peil();
    void p.peil();
    expect(haal).toHaveBeenCalledTimes(1);
    los([]);
    await eerste;
    // Precies één inhaalpeiling, hoe vaak er ook tussendoor gevraagd werd.
    await waitFor(() => expect(haal).toHaveBeenCalledTimes(2));
    los([run("r1", "A", "loopt")]);
    await waitFor(() => expect(onRuns).toHaveBeenCalledTimes(2));
    expect(onRuns.mock.calls[1]).toEqual([[run("r1", "A", "loopt")], []]);
    p.stop();
  });

  it("gestopt tijdens het verzoek: het antwoord komt niet meer door", async () => {
    let los!: (r: ActieveRun[]) => void;
    const onRuns = vi.fn();
    const p = maakPeiler({ haal: () => new Promise((r) => { los = r; }), leesLopend: () => ({}), onRuns });
    const bezig = p.peil();
    p.stop();
    los([run("r1", "A", "loopt")]);
    await bezig;
    expect(onRuns).not.toHaveBeenCalled();
    await p.peil();
    expect(onRuns).not.toHaveBeenCalled();
  });
});
