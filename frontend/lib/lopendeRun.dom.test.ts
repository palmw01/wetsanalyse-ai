// @vitest-environment happy-dom
//
// Het browserdeel van `lib/lopendeRun.ts`: het register in `localStorage` en `wachtMetWekker`, de wachttijd tussen twee
// pogingen om weer aan te haken als de stroom wegviel (frontend/CLAUDE.md §De beurt is van de server). De pure functies
// staan in `lopendeRun.test.ts`.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { leesLopendeRuns, schrijfLopendeRuns, wachtMetWekker } from "./lopendeRun";

function zichtbaarheid(stand: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => stand });
}

beforeEach(() => {
  vi.useFakeTimers();
  window.localStorage.clear();
  zichtbaarheid("visible");
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function geblokkeerdeOpslag() {
  // Geblokkeerde sitedata: al het opvragen van `localStorage` gooit (SecurityError), zoals in een streng privévenster.
  const echt = Object.getOwnPropertyDescriptor(window, "localStorage");
  Object.defineProperty(window, "localStorage", { configurable: true, get: () => { throw new DOMException("geblokkeerd", "SecurityError"); } });
  return () => { if (echt) Object.defineProperty(window, "localStorage", echt); };
}

describe("wachtMetWekker", () => {
  it("wacht de volle tijd zonder wekker", async () => {
    let klaar: boolean | undefined;
    void wachtMetWekker(6000, () => true).then((w) => { klaar = w; });
    await vi.advanceTimersByTimeAsync(5999);
    expect(klaar).toBeUndefined();
    await vi.advanceTimersByTimeAsync(1);
    expect(klaar).toBe(true);
  });

  it("het netwerk terug (online) wekt meteen", async () => {
    const wacht = wachtMetWekker(15_000, () => true);
    window.dispatchEvent(new Event("online"));
    expect(await wacht).toBe(true);
  });

  it("een tabblad dat zichtbaar wordt wekt; verborgen worden niet", async () => {
    let klaar: boolean | undefined;
    void wachtMetWekker(15_000, () => true).then((w) => { klaar = w; });
    zichtbaarheid("hidden");
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(0);
    expect(klaar).toBeUndefined();
    zichtbaarheid("visible");
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(0);
    expect(klaar).toBe(true);
  });

  it("is het venster intussen weg, dan niet opnieuw aanhaken", async () => {
    let leeft = true;
    const wacht = wachtMetWekker(3000, () => leeft);
    leeft = false;
    await vi.advanceTimersByTimeAsync(3000);
    expect(await wacht).toBe(false);
  });

  it("ruimt zijn luisteraars op: een tweede wekker na afloop doet niets", async () => {
    const weg = vi.spyOn(window, "removeEventListener");
    const wacht = wachtMetWekker(1000, () => true);
    window.dispatchEvent(new Event("online"));
    await wacht;
    expect(weg).toHaveBeenCalledWith("online", expect.any(Function));
    // Na afloop staat de timer niet meer: geen tweede afloop.
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("het register van lopende runs", () => {
  it("leest wat er geschreven is, en rommel is leeg", () => {
    schrijfLopendeRuns({ g1: "r1" });
    expect(leesLopendeRuns()).toEqual({ g1: "r1" });
    window.localStorage.setItem("wa_lopende_run", "{kapot");
    expect(leesLopendeRuns()).toEqual({});
  });

  it("een opslag die weigert, breekt niets", () => {
    schrijfLopendeRuns({ g1: "r1" });
    const herstel = geblokkeerdeOpslag();
    try {
      expect(() => schrijfLopendeRuns({ g2: "r2" })).not.toThrow();
      expect(leesLopendeRuns()).toEqual({});
    } finally {
      herstel();
    }
  });
});
