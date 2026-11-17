// @vitest-environment happy-dom
//
// `useOnbewaardBewaker` met een DOM (testplan werkplek 6, Lex Bench §20.5 stap 6): een link elders op de pagina en een
// paneelwissel wachten op de jurist zolang er iets onbewaard openstaat. Zonder wijzigingen gaat alles gewoon door.
// `beforeunload` (herladen, sluiten) staat bij de eigenaar van de wijzigingen, niet in deze hook.
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const { useOnbewaardBewaker } = await import("./useOnbewaardBewaker");

function link(href: string): HTMLAnchorElement {
  const a = document.createElement("a");
  a.setAttribute("href", href);
  a.textContent = "naar elders";
  document.body.appendChild(a);
  return a;
}

function klik(el: Element): MouseEvent {
  const e = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
  act(() => { el.dispatchEvent(e); });
  return e;
}

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/werkgebieden/w1");
});
afterEach(() => { cleanup(); document.body.innerHTML = ""; });

describe("useOnbewaardBewaker [R08]", () => {
  it("een link naar een andere pagina wacht op de jurist, en Toch gaat er alsnog heen", () => {
    const { result } = renderHook(() => useOnbewaardBewaker(true));
    const e = klik(link("/werkgebieden?tab=bronnen"));
    expect(e.defaultPrevented).toBe(true);
    expect(result.current.wachtend?.handeling).toBe("verlaten");
    expect(router.push).not.toHaveBeenCalled();

    act(() => result.current.toch());
    expect(router.push).toHaveBeenCalledWith("/werkgebieden?tab=bronnen");
    expect(result.current.wachtend).toBeNull();
  });

  it("Blijf houdt de jurist op de pagina", () => {
    const { result } = renderHook(() => useOnbewaardBewaker(true));
    klik(link("/annotaties"));
    act(() => result.current.blijf());
    expect(result.current.wachtend).toBeNull();
    expect(router.push).not.toHaveBeenCalled();
  });

  it("zonder onbewaarde wijzigingen gaat een link gewoon door", () => {
    const { result } = renderHook(() => useOnbewaardBewaker(false));
    const e = klik(link("/annotaties"));
    expect(e.defaultPrevented).toBe(false);
    expect(result.current.wachtend).toBeNull();
  });

  it("een link naar dezelfde pagina of een nieuw tabblad vraagt niets", () => {
    const { result } = renderHook(() => useOnbewaardBewaker(true));
    expect(klik(link("/werkgebieden/w1")).defaultPrevented).toBe(false);
    const nieuw = link("/annotaties");
    nieuw.target = "_blank";
    expect(klik(nieuw).defaultPrevented).toBe(false);
    expect(result.current.wachtend).toBeNull();
  });

  it("een paneelwissel via bewaak wacht, ook als de wijziging pas na de render ontstond", () => {
    let onbewaard = false;
    const { result, rerender } = renderHook(() => useOnbewaardBewaker(onbewaard));
    const wissel = result.current.bewaak;
    const doe = vi.fn();
    onbewaard = true;
    rerender();
    // De functie van de vorige render leest de stand van nu (FB-05).
    act(() => wissel(doe, "wisselen"));
    expect(doe).not.toHaveBeenCalled();
    expect(result.current.wachtend?.handeling).toBe("wisselen");
    act(() => result.current.toch());
    expect(doe).toHaveBeenCalledTimes(1);
  });

  it("verdwijnen de wijzigingen, dan vervalt een open vraag", () => {
    let onbewaard = true;
    const { result, rerender } = renderHook(() => useOnbewaardBewaker(onbewaard));
    act(() => result.current.bewaak(vi.fn(), "sluiten"));
    expect(result.current.wachtend).not.toBeNull();
    onbewaard = false;
    rerender();
    expect(result.current.wachtend).toBeNull();
  });
});
