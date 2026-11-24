// @vitest-environment happy-dom
//
// `useBegrip` en `useRegel` dragen elke mutatie op een gedeeld object (frontend/CLAUDE.md §Werkgebieden: "gedeeld, dus
// elke mutatie draagt de revisie in beeld"). Wat hier vastligt: de revisie die meegaat, een 412 die de nieuwste stand
// laadt en dat zegt zonder de handeling stil te herhalen, een fout van een formulier die daar blijft, een verwijderd
// begrip als toestand, en een opname (oude versie) die niets laadt en niets muteert.
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Begrip } from "./types";

const api = vi.hoisted(() => ({
  haalBegrip: vi.fn(), haalGeneriekBegrip: vi.fn(), lijstBegrippen: vi.fn(), haalKaartVoorstellen: vi.fn(),
  haalHerbeoordelingen: vi.fn(), verwijderBegrip: vi.fn(), verwijderGeneriek: vi.fn(), wijzigBegrip: vi.fn(),
  wijzigGeneriek: vi.fn(), neemKaartVoorstelOver: vi.fn(), wijsKaartVoorstelAf: vi.fn(),
  haalRegel: vi.fn(), lijstRegels: vi.fn(), haalRegelKeten: vi.fn(),
}));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("./api")>()), ...api }));
vi.mock("@/lib/uiSpoor", () => ({ metSpoor: (_n: string, f: () => unknown) => f() }));

const { useBegrip } = await import("./useBegrip");
const { useRegel, useRegelKeten } = await import("./useRegel");

const begrip = (revisie: number, extra: Partial<Begrip> = {}) =>
  ({ id: "b1", revisie, naam: "termijn", inhoud: {}, koppelingen: [], ...extra }) as unknown as Begrip;
const conflict = { status: 412, detail: "Revisie verouderd.", data: { fout: "revisie_conflict" } };

beforeEach(() => {
  for (const f of Object.values(api)) f.mockReset();
  api.haalBegrip.mockResolvedValue(begrip(3));
  api.lijstBegrippen.mockResolvedValue({ begrippen: [] });
  api.haalKaartVoorstellen.mockResolvedValue({ voorstellen: [] });
  api.haalHerbeoordelingen.mockResolvedValue({ begrippen: [] });
});
afterEach(cleanup);

const inWerkgebied = { soort: "werkgebied", werkgebiedId: "wg1" } as const;

describe("useBegrip", () => {
  it("laadt het begrip met zijn lijst, voorstellen en herbeoordeling", async () => {
    const { result } = renderHook(() => useBegrip({ context: inWerkgebied, begripId: "b1" }));
    await waitFor(() => expect(result.current.begrip?.revisie).toBe(3));
    expect(api.haalBegrip).toHaveBeenCalledWith("wg1", "b1");
    expect(api.lijstBegrippen).toHaveBeenCalledWith("wg1");
    expect(api.haalHerbeoordelingen).toHaveBeenCalledWith("wg1", "b1");
  });

  it("muteert met de revisie in beeld, toont de bevestiging en meldt de wijziging", async () => {
    const gewijzigd = vi.fn();
    const { result } = renderHook(() => useBegrip({ context: inWerkgebied, begripId: "b1", onGewijzigd: gewijzigd }));
    await waitFor(() => expect(result.current.begrip).not.toBeNull());
    const actie = vi.fn(async (r: number) => begrip(r + 1));
    let ok = false;
    await act(async () => { ok = await result.current.muteer(actie, { gelukt: "Opgeslagen." }); });
    expect(ok).toBe(true);
    expect(actie).toHaveBeenCalledWith(3);
    expect(result.current.begrip?.revisie).toBe(4);
    expect(result.current.melding).toEqual({ type: "bevestiging", tekst: "Opgeslagen." });
    expect(gewijzigd).toHaveBeenCalledTimes(1);
  });

  it("412: de nieuwste stand komt in beeld met een waarschuwing, en de handeling wordt niet herhaald", async () => {
    const { result } = renderHook(() => useBegrip({ context: inWerkgebied, begripId: "b1" }));
    await waitFor(() => expect(result.current.begrip).not.toBeNull());
    api.haalBegrip.mockResolvedValue(begrip(5));
    const actie = vi.fn(async () => { throw conflict; });
    let ok = true;
    await act(async () => { ok = await result.current.muteer(actie); });
    expect(ok).toBe(false);
    expect(actie).toHaveBeenCalledTimes(1);
    expect(result.current.begrip?.revisie).toBe(5);
    expect(result.current.melding?.type).toBe("waarschuwing");
    expect(result.current.melding?.tekst).toMatch(/Iemand anders wijzigde dit begrip/);
  });

  it("een fout die het formulier zelf toont, komt niet ook als melding", async () => {
    const { result } = renderHook(() => useBegrip({ context: inWerkgebied, begripId: "b1" }));
    await waitFor(() => expect(result.current.begrip).not.toBeNull());
    const fout = { status: 422, detail: "Element buiten het werkgebied." };
    await act(async () => { await result.current.muteer(async () => { throw fout; }, { opFout: () => true }); });
    expect(result.current.melding).toBeNull();
    await act(async () => { await result.current.muteer(async () => { throw fout; }); });
    // Zonder formulier: de reden van de api, letterlijk.
    expect(result.current.melding).toEqual({ type: "waarschuwing", tekst: "Element buiten het werkgebied." });
  });

  it("een verwijderd begrip is een toestand, geen fout", async () => {
    api.haalBegrip.mockRejectedValue({ status: 404, detail: "weg", data: { fout: "verwijderd", soort: "begrip", op: "2026-11-01T10:00:00Z", door: "jurist-a" } });
    const { result } = renderHook(() => useBegrip({ context: inWerkgebied, begripId: "b1" }));
    await waitFor(() => expect(result.current.verwijderd).toEqual({ soort: "begrip", op: "2026-11-01T10:00:00Z", door: "jurist-a" }));
    expect(result.current.fout).toBeNull();
    expect(result.current.begrip).toBeNull();
  });

  it("een andere laadfout is een fout met de reden", async () => {
    api.haalBegrip.mockRejectedValue({ status: 500, detail: "Database weg." });
    const { result } = renderHook(() => useBegrip({ context: inWerkgebied, begripId: "b1" }));
    await waitFor(() => expect(result.current.fout).toBe("Database weg."));
  });

  it("verwijderen laadt daarna de stand (wanneer en door wie) en meldt het; een 412 verwijdert niets", async () => {
    const weg = vi.fn();
    const { result } = renderHook(() => useBegrip({ context: inWerkgebied, begripId: "b1", onVerwijderd: weg }));
    await waitFor(() => expect(result.current.begrip).not.toBeNull());
    api.verwijderBegrip.mockRejectedValueOnce(conflict);
    await act(async () => { await result.current.verwijder(); });
    expect(weg).not.toHaveBeenCalled();
    expect(result.current.melding?.tekst).toMatch(/voordat je het verwijdert/);

    api.verwijderBegrip.mockResolvedValueOnce(undefined);
    await act(async () => { await result.current.verwijder(); });
    expect(api.verwijderBegrip).toHaveBeenLastCalledWith("wg1", "b1", 3);
    expect(weg).toHaveBeenCalledTimes(1);
  });

  it("een generiek begrip gaat over zijn eigen routes", async () => {
    api.haalGeneriekBegrip.mockResolvedValue({ begrip: begrip(7), relaties: [{ id: "r1" }] });
    const { result } = renderHook(() => useBegrip({ context: { soort: "generiek" }, begripId: "b1" }));
    await waitFor(() => expect(result.current.begrip?.revisie).toBe(7));
    expect(result.current.relatiesGeneriek).toEqual([{ id: "r1" }]);
    // Geen lijst en geen herbeoordeling per werkgebied.
    expect(api.lijstBegrippen).not.toHaveBeenCalled();
    expect(api.haalHerbeoordelingen).not.toHaveBeenCalled();
    await act(async () => { await result.current.api.wijzig(7, {} as never); });
    expect(api.wijzigGeneriek).toHaveBeenCalledWith("b1", 7, {});
  });

  it("een verouderd voorstel: toen, nu en voorstel naast elkaar, geen losse melding", async () => {
    const { result } = renderHook(() => useBegrip({ context: inWerkgebied, begripId: "b1" }));
    await waitFor(() => expect(result.current.begrip).not.toBeNull());
    api.neemKaartVoorstelOver.mockRejectedValueOnce({
      status: 409, detail: "verouderd",
      data: { fout: "voorstel_verouderd", toen: { definitie: "oud" }, nu: { definitie: "nu" }, voorstel: { definitie: "nieuw" } },
    });
    let ok = true;
    await act(async () => { ok = await result.current.overnemen({ id: "v1" } as never, undefined as never); });
    expect(ok).toBe(false);
    expect(result.current.verouderd).toEqual({ voorstelId: "v1", toen: "oud", nu: "nu", voorstel: "nieuw" });
    expect(result.current.melding).toBeNull();
  });

  it("een opname laadt niets en muteert niets", async () => {
    const { result } = renderHook(() => useBegrip({ context: inWerkgebied, begripId: "b1", opname: { begrip: begrip(2) } }));
    await act(async () => {});
    expect(api.haalBegrip).not.toHaveBeenCalled();
    expect(result.current.alleenLezen).toBe(true);
    expect(result.current.begrip?.revisie).toBe(2);
  });
});

describe("useRegel", () => {
  const regel = (revisie: number) => ({ id: "r1", revisie }) as never;

  it("muteert met de revisie in beeld; een 412 laadt opnieuw en zegt dat", async () => {
    api.haalRegel.mockResolvedValue(regel(1));
    const { result } = renderHook(() => useRegel({ werkgebiedId: "wg1", regelId: "r1" }));
    await waitFor(() => expect(result.current.regel).not.toBeNull());
    const actie = vi.fn(async (r: number) => regel(r + 1));
    await act(async () => { await result.current.muteer(actie, "Geaccordeerd."); });
    expect(actie).toHaveBeenCalledWith(1);
    expect(result.current.melding).toEqual({ type: "bevestiging", tekst: "Geaccordeerd." });

    api.haalRegel.mockResolvedValue(regel(9));
    await act(async () => { await result.current.muteer(async () => { throw conflict; }); });
    await waitFor(() => expect((result.current.regel as unknown as { revisie: number }).revisie).toBe(9));
    expect(result.current.melding?.tekst).toMatch(/Iemand anders wijzigde deze regel/);
    expect(result.current.bezig).toBe(false);
  });

  it("een gewone fout geeft de reden; een laadfout zonder reden de standaardzin", async () => {
    api.haalRegel.mockResolvedValue(regel(1));
    const { result } = renderHook(() => useRegel({ werkgebiedId: "wg1", regelId: "r1" }));
    await waitFor(() => expect(result.current.regel).not.toBeNull());
    await act(async () => { await result.current.muteer(async () => { throw { status: 409, detail: "Nog open punten." }; }); });
    expect(result.current.melding).toEqual({ type: "waarschuwing", tekst: "Nog open punten." });

    api.haalRegel.mockRejectedValue(undefined);
    const tweede = renderHook(() => useRegel({ werkgebiedId: "wg1", regelId: "r2" }));
    await waitFor(() => expect(tweede.result.current.fout).toBe("De afleidingsregel kon niet worden geladen."));
  });

  it("een opname muteert niet", async () => {
    const { result } = renderHook(() => useRegel({ werkgebiedId: "wg1", regelId: "r1", opname: regel(4) }));
    let ok = true;
    await act(async () => { ok = await result.current.muteer(async () => regel(5)); });
    expect(ok).toBe(false);
    expect(api.haalRegel).not.toHaveBeenCalled();
  });

  it("useRegelKeten: zonder keten staat de lijst er gewoon", async () => {
    api.lijstRegels.mockResolvedValue([regel(1)]);
    api.haalRegelKeten.mockRejectedValue(new Error("weg"));
    const { result } = renderHook(() => useRegelKeten("wg1"));
    await waitFor(() => expect(result.current.regels).toHaveLength(1));
    expect(result.current.keten).toBeNull();
    expect(result.current.fout).toBeNull();
  });
});
