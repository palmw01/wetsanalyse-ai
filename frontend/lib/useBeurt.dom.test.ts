// @vitest-environment happy-dom
//
// `useBeurt` met een DOM (testplan werkplek 6, Lex Bench §20.5 stap 6). De rekenkern (`beurtFase`, `beurtLus`) heeft
// zijn eigen tests; hier gaat het om de lijm die tot nu toe alleen de browserregressie zag: de stopknop, het weer
// aanhaken op een beurt die doorliep, en dat een tweede beurt in dezelfde tick het venster niet krijgt (de 409 bij de
// agent vangt alleen wat er dan toch doorkomt).
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BeurtScherm } from "./useBeurt";

const api = vi.hoisted(() => ({
  volgRun: vi.fn(),
  stopRun: vi.fn(),
  haalActieveRun: vi.fn(),
}));
vi.mock("./api", () => api);

const { useBeurt } = await import("./useBeurt");

/** Een run die loopt tot de test hem afrondt, of tot de kijker loskoppelt (dan een AbortError, zoals `fetch`). */
function lopendeRun() {
  let klaar!: () => void;
  let signaal: AbortSignal | undefined;
  api.volgRun.mockImplementation((_id: string, handlers: { onDone?: (u: string) => void }, _v: number, s?: AbortSignal) => {
    signaal = s;
    return new Promise<void>((resolve, reject) => {
      klaar = () => { handlers.onDone?.("klaar"); resolve(); };
      s?.addEventListener("abort", () => reject(new DOMException("losgekoppeld", "AbortError")));
    });
  });
  return { klaar: () => klaar(), signaal: () => signaal };
}

function scherm(): BeurtScherm & { [k: string]: ReturnType<typeof vi.fn> } {
  return {
    schrijfStroom: vi.fn(),
    handlers: vi.fn(() => ({})),
    opKlaar: vi.fn(async () => {}),
    opMislukt: vi.fn(),
    opNaverwerkingFout: vi.fn(),
    voorHervatten: vi.fn(() => "ant-hervat"),
    onBeurtKlaar: vi.fn(),
  } as never;
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("useBeurt [R08]", () => {
  it("geeft het venster maar aan één beurt: een tweede claim in dezelfde tick faalt", () => {
    const { result } = renderHook(() => useBeurt(scherm()));
    let eerste = false, tweede = true;
    act(() => {
      eerste = result.current.claim();
      tweede = result.current.claim();
    });
    expect([eerste, tweede]).toEqual([true, false]);
    expect(result.current.fase).toEqual({ soort: "starten" });
    act(() => result.current.vrij());
    expect(result.current.magStarten()).toBe(true);
  });

  it("de stopknop vraagt één keer om te stoppen en blijft in de stopt-stand tot de run afloopt", async () => {
    const run = lopendeRun();
    api.stopRun.mockResolvedValue(undefined);
    const s = scherm();
    const { result } = renderHook(() => useBeurt(s));
    act(() => { result.current.claim(); });
    let volgen!: Promise<void>;
    act(() => { volgen = result.current.volg("run-1", "g1", "ant-1"); });
    await waitFor(() => expect(result.current.runId).toBe("run-1"));

    await act(async () => { await result.current.stop(); });
    await act(async () => { await result.current.stop(); });
    expect(api.stopRun).toHaveBeenCalledTimes(1);
    expect(api.stopRun).toHaveBeenCalledWith("run-1");
    expect(result.current.stopt).toBe(true);
    expect(result.current.bezig).toBe(true);

    await act(async () => { run.klaar(); await volgen; });
    expect(result.current.bezig).toBe(false);
    expect(s.opKlaar).toHaveBeenCalledTimes(1);
    expect(s.onBeurtKlaar).toHaveBeenCalledTimes(1);
  });

  it("mislukt het stopverzoek, dan loopt de beurt door en staat de knop weer aan", async () => {
    lopendeRun();
    api.stopRun.mockRejectedValue(new Error("netwerk"));
    const { result } = renderHook(() => useBeurt(scherm()));
    act(() => { result.current.claim(); });
    act(() => { void result.current.volg("run-2", "g1", "ant-1"); });
    await waitFor(() => expect(result.current.runId).toBe("run-2"));
    await act(async () => { await result.current.stop(); });
    expect(result.current.stopt).toBe(false);
    expect(result.current.bezig).toBe(true);
  });

  it("weg navigeren koppelt alleen de kijker los: de run wordt niet gestopt", async () => {
    const run = lopendeRun();
    const { result, unmount } = renderHook(() => useBeurt(scherm()));
    act(() => { result.current.claim(); });
    act(() => { void result.current.volg("run-3", "g1", "ant-1"); });
    await waitFor(() => expect(run.signaal()).toBeDefined());
    unmount();
    expect(run.signaal()?.aborted).toBe(true);
    expect(api.stopRun).not.toHaveBeenCalled();
  });

  it("herstellen: een run die doorliep wordt opgepakt, met een eigen bubbel", async () => {
    const run = lopendeRun();
    api.haalActieveRun.mockResolvedValue({ run_id: "run-4", status: "loopt" });
    const s = scherm();
    const { result } = renderHook(() => useBeurt(s));
    let hervat!: Promise<void>;
    act(() => { hervat = result.current.hervat("g1", []); });
    await waitFor(() => expect(result.current.runId).toBe("run-4"));
    expect(s.voorHervatten).toHaveBeenCalledWith("run-4");
    expect(api.volgRun.mock.calls[0][0]).toBe("run-4");
    await act(async () => { run.klaar(); await hervat; });
    expect(result.current.bezig).toBe(false);
  });

  it("herstellen zonder zekerheid doet niets, en een verdwenen run wordt gemeld", async () => {
    const s = scherm();
    const { result } = renderHook(() => useBeurt(s));
    api.haalActieveRun.mockResolvedValue("onbekend");
    await act(async () => { await result.current.hervat("g1", []); });
    expect(api.volgRun).not.toHaveBeenCalled();
    expect(result.current.runVerdwenen).toBe(false);

    act(() => result.current.onthoud("g1", "run-weg"));
    api.haalActieveRun.mockResolvedValue(null);
    await act(async () => { await result.current.hervat("g1", []); });
    expect(result.current.runVerdwenen).toBe(true);
    expect(s.voorHervatten).not.toHaveBeenCalled();
  });
});
