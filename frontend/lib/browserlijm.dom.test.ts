// @vitest-environment happy-dom
//
// Drie kleine browsermodules met een eigen afspraak die alleen de browserregressie zag (kwaliteitsmeting PR #1801):
// - het instellingenvenster opent met een stap in de geschiedenis, wisselt van tab zonder stap en sluit terug
//   (frontend/CLAUDE.md: "geef in die state alleen de eigen markering mee");
// - kopiëren zegt altijd of het lukte, en de stand gaat na een tijd terug (of blijft, bij een eenmalig token);
// - het UI-spoor meet een handeling zonder hem te veranderen, en een browserfout gaat zonder tekst van de gebruiker mee.
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { kiesInstellingenTab, openInstellingen, sluitInstellingen, zetLijstStand } from "./instellingenVenster";
import { kopieerNaarKlembord, useKopieer } from "./kopieer";
import { meldBrowserfout, meldSpoor, metSpoor } from "./uiSpoor";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("instellingenVenster", () => {
  beforeEach(() => window.history.replaceState({ next: "eigen-stand" }, "", "/werkgebieden/wg1?tab=x#kop"));

  it("openen zet een stap met alleen de eigen markering, en houdt de rest van de URL", () => {
    const push = vi.spyOn(window.history, "pushState");
    openInstellingen("account");
    expect(push).toHaveBeenCalledWith({ instellingenGeopend: true }, "", "/werkgebieden/wg1?tab=x&instellingen=account#kop");
  });

  it("een tabwissel vervangt de stap en laat de lijststand van de vorige tab vallen", () => {
    window.history.replaceState({ instellingenGeopend: true }, "", "/?instellingen=methodes&q=zoek&segment=s&onderdeel=o");
    const vervang = vi.spyOn(window.history, "replaceState");
    kiesInstellingenTab("verbruik");
    expect(vervang).toHaveBeenLastCalledWith({ instellingenGeopend: true }, "", "/?instellingen=verbruik");
    kiesInstellingenTab("methodes", { q: "termijn", segment: null });
    expect(vervang).toHaveBeenLastCalledWith({ instellingenGeopend: true }, "", "/?instellingen=methodes&q=termijn");
  });

  it("de lijststand bijwerken zonder stap; null haalt een parameter weg", () => {
    window.history.replaceState({}, "", "/?instellingen=methodes&q=oud");
    const vervang = vi.spyOn(window.history, "replaceState");
    zetLijstStand({ q: null, onderdeel: "skill:wetsanalyse" });
    expect(vervang).toHaveBeenLastCalledWith({}, "", "/?instellingen=methodes&onderdeel=skill%3Awetsanalyse");
  });

  it("sluiten na openen: terug in de geschiedenis", () => {
    window.history.replaceState({ instellingenGeopend: true }, "", "/?instellingen=account");
    const terug = vi.spyOn(window.history, "back").mockImplementation(() => {});
    sluitInstellingen();
    expect(terug).toHaveBeenCalledTimes(1);
  });

  it("sluiten na binnenkomen via een link: alleen de parameter weg, op dezelfde pagina", () => {
    window.history.replaceState({}, "", "/workbench?gesprek=g1&instellingen=account&q=x");
    const terug = vi.spyOn(window.history, "back");
    sluitInstellingen();
    expect(terug).not.toHaveBeenCalled();
    expect(window.location.pathname + window.location.search).toBe("/workbench?gesprek=g1");
  });
});

describe("kopieer", () => {
  function klembord(gedrag: "lukt" | "faalt") {
    const writeText = vi.fn(async () => { if (gedrag === "faalt") throw new Error("geweigerd"); });
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    return writeText;
  }

  it("kopieerNaarKlembord zegt of het lukte, en gooit nooit", async () => {
    expect(await kopieerNaarKlembord("a")).toBe(true);
    klembord("faalt");
    expect(await kopieerNaarKlembord("a")).toBe(false);
  });

  it("useKopieer: gekopieerd, en na de duur weer leeg", async () => {
    vi.useFakeTimers();
    const writeText = klembord("lukt");
    const { result } = renderHook(() => useKopieer(1500));
    await act(async () => { await result.current.kopieer("tekst"); });
    expect(writeText).toHaveBeenCalledWith("tekst");
    expect(result.current.stand).toBe("gekopieerd");
    await act(async () => { vi.advanceTimersByTime(1500); });
    expect(result.current.stand).toBe("");
  });

  it("met duur null blijft gekopieerd staan (een eenmalig token), en mislukt blijft altijd staan", async () => {
    vi.useFakeTimers();
    klembord("lukt");
    const blijvend = renderHook(() => useKopieer(null));
    await act(async () => { await blijvend.result.current.kopieer("wa_pat_x"); });
    await act(async () => { vi.advanceTimersByTime(60_000); });
    expect(blijvend.result.current.stand).toBe("gekopieerd");

    klembord("faalt");
    const mislukt = renderHook(() => useKopieer());
    await act(async () => { await mislukt.result.current.kopieer("x"); });
    await act(async () => { vi.advanceTimersByTime(60_000); });
    expect(mislukt.result.current.stand).toBe("mislukt");
    act(() => mislukt.result.current.wis());
    expect(mislukt.result.current.stand).toBe("");
  });
});

describe("uiSpoor", () => {
  async function verzonden(beacon: ReturnType<typeof vi.fn>) {
    return Promise.all(beacon.mock.calls.map(async ([url, blob]) => ({ url, body: JSON.parse(await (blob as Blob).text()) })));
  }
  function stubBeacon() {
    const beacon = vi.fn(() => true);
    Object.defineProperty(navigator, "sendBeacon", { configurable: true, value: beacon });
    return beacon;
  }

  it("metSpoor: gestart, dan gelukt met de duur; de uitkomst van de handeling blijft", async () => {
    const beacon = stubBeacon();
    expect(await metSpoor("gesprek_hernoemen", async () => 42)).toBe(42);
    const b = await verzonden(beacon);
    expect(b.map((x) => x.url)).toEqual(["/api/ui-spoor", "/api/ui-spoor"]);
    expect(b[0].body).toEqual({ actie: "gesprek_hernoemen", uitkomst: "gestart" });
    expect(b[1].body).toMatchObject({ actie: "gesprek_hernoemen", uitkomst: "gelukt" });
    expect(typeof b[1].body.duur_ms).toBe("number");
  });

  it("metSpoor: een fout gaat door naar de aanroeper, met de http-status in het spoor", async () => {
    const beacon = stubBeacon();
    const fout = { status: 412, detail: "Revisie verouderd." };
    await expect(metSpoor("begrip_verwijderen", async () => { throw fout; })).rejects.toBe(fout);
    const b = await verzonden(beacon);
    expect(b[1].body).toMatchObject({ actie: "begrip_verwijderen", uitkomst: "mislukt", status: 412 });
    // De reden van de api (tekst die over de inhoud kan gaan) gaat niet mee.
    expect(JSON.stringify(b[1].body)).not.toContain("Revisie");
  });

  it("een beacon die gooit of ontbreekt, breekt de handeling niet", async () => {
    Object.defineProperty(navigator, "sendBeacon", { configurable: true, value: () => { throw new Error("te groot"); } });
    expect(() => meldSpoor({ actie: "review_beslissing", uitkomst: "gestart" })).not.toThrow();
    Object.defineProperty(navigator, "sendBeacon", { configurable: true, value: undefined });
    expect(await metSpoor("review_beslissing", async () => "ok")).toBe("ok");
  });

  it("meldBrowserfout: naam en digest, nooit de melding; een afgebroken verzoek is ruis", async () => {
    const beacon = stubBeacon();
    meldBrowserfout("route", new DOMException("weg", "AbortError"));
    expect(beacon).not.toHaveBeenCalled();
    const fout = Object.assign(new TypeError("kan 'Artikel 9 van jurist-a' niet lezen"), { digest: "abc-123" });
    meldBrowserfout("globaal", fout);
    const [{ body }] = await verzonden(beacon);
    expect(body).toEqual({ soort: "fout", plek: "globaal", naam: "TypeError", digest: "abc-123" });
  });
});
