import { afterEach, describe, expect, it, vi } from "vitest";

import {
  bestandsnaamUit,
  haalActieveRun,
  haalDelegaties,
  luisterNaarDelegaties,
  naarInloggen,
  parseError,
  stopRun,
  vergeetDelegaties,
  volgRun,
} from "./api";

// Aanvulling op `api.test.ts` (kwaliteitsmeting PR #1801): de randen van de SSE-parser die daar niet langskwamen –
// een frame dat over twee stukken van de stroom valt, de reeks zonder eigen handler, de bron- en regie-events –
// en de helpers met een eigen beslissing (een 401 naar het inlogscherm, de drie uitkomsten van de actieve run, de
// bestandsnaam van een download, de gedeelde stand van de delegaties).

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** Een stroom die de stukken precies zo levert als opgegeven, dus ook midden in een frame of een teken. */
function stroom(stukken: (string | Uint8Array)[]) {
  return new Response(new ReadableStream<Uint8Array>({
    start(c) {
      for (const s of stukken) c.enqueue(typeof s === "string" ? new TextEncoder().encode(s) : s);
      c.close();
    },
  }), { status: 200, headers: { "Content-Type": "text/event-stream" } });
}
const frame = (e: unknown) => `data: ${JSON.stringify(e)}\r\n\r\n`;

describe("verwerkSseStroom – stukken en randen", () => {
  it("een frame dat over twee stukken valt, en een teken dat midden in de UTF-8 breekt", async () => {
    const tekst = frame({ type: "token", content: "één paragraaf §" });
    const bytes = new TextEncoder().encode(tekst + frame({ type: "done" }));
    // Splits midden in de "é" (twee bytes) en midden in de \r\n.
    const midden = bytes.indexOf(0xc3) + 1;
    vi.stubGlobal("fetch", vi.fn(async () => stroom([bytes.slice(0, midden), bytes.slice(midden, midden + 25), bytes.slice(midden + 25)])));
    const token = vi.fn(), klaar = vi.fn();
    await volgRun("r", { onToken: token, onDone: klaar });
    expect(token).toHaveBeenCalledWith("één paragraaf §");
    expect(klaar).toHaveBeenCalledWith("klaar");
  });

  it("slaat heartbeats, frames zonder data en onleesbare JSON over", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => stroom([": ping\n\n", "event: x\n\n", "data: {kapot\n\n", frame({ type: "status", message: "Bron" }), frame({ type: "done" })])));
    const status = vi.fn(), leeft = vi.fn();
    await volgRun("r", { onStatus: status, onLeeft: leeft });
    expect(status).toHaveBeenCalledWith("Bron");
    // Een heartbeat of een onleesbaar frame telt niet als levensteken; alleen een event.
    expect(leeft).toHaveBeenCalledTimes(2);
  });

  it("een reeks-event zonder eigen handler valt door naar de gewone afhandeling", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => stroom([frame({ type: "token", content: "deel", onderdeel: "urn:lid1" }), frame({ type: "done" })])));
    const token = vi.fn();
    await volgRun("r", { onToken: token });
    expect(token).toHaveBeenCalledWith("deel");
  });

  it("met een reeks-handler gaan reeks, onderdeel en ingedeelde events daarheen, en niet naar de gewone", async () => {
    const events = [{ type: "reeks", totaal: 2 }, { type: "onderdeel", index: 0 }, { type: "token", content: "x", onderdeel: "urn:lid1" }];
    vi.stubGlobal("fetch", vi.fn(async () => stroom([...events.map(frame), frame({ type: "done" })])));
    const reeks = vi.fn(), token = vi.fn();
    await volgRun("r", { onReeksEvent: reeks, onToken: token });
    expect(reeks.mock.calls.map((c) => c[0].type)).toEqual(["reeks", "onderdeel", "token"]);
    expect(token).not.toHaveBeenCalled();
  });

  it("bron_uit en bronstand laten alleen regels met de vereiste velden door", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => stroom([
      frame({ type: "bron_uit", bronnen: [{ naam: "kst", label: "Kamerstukken", reden: "uit" }, { naam: "x" }, null] }),
      frame({ type: "bronstand", bronnen: [{ naam: "kst", reden: "straat" }, { reden: "straat" }] }),
      frame({ type: "bronstand", bronnen: "geen lijst" }),
      frame({ type: "done" }),
    ])));
    const uit = vi.fn(), stand = vi.fn();
    await volgRun("r", { onBronUit: uit, onBronstand: stand });
    expect(uit).toHaveBeenCalledWith([{ naam: "kst", label: "Kamerstukken", reden: "uit" }]);
    expect(stand).toHaveBeenCalledTimes(1);
    expect(stand).toHaveBeenCalledWith([{ naam: "kst", reden: "straat" }]);
  });

  it("regie en regie_taak gaan naar de delegatie; alleen fase eind is het eind van een taak", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => stroom([
      frame({ type: "regie", plan: [] }),
      frame({ type: "regie_taak", fase: "start" }),
      frame({ type: "regie_taak", fase: "eind" }),
      frame({ type: "regie_taak" }),
      frame({ type: "done" }),
    ])));
    const delegatie = vi.fn(), taak = vi.fn();
    await volgRun("r", { onDelegatie: delegatie, onRegieTaak: taak });
    expect(delegatie).toHaveBeenCalledTimes(4);
    expect(taak.mock.calls.map((c) => c[0])).toEqual(["start", "eind", "start"]);
  });

  it("een gestructureerd event dat zijn schema niet haalt, komt niet bij de handler maar breekt de beurt niet", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.stubGlobal("fetch", vi.fn(async () => stroom([
      frame({ type: "antwoord", antwoord: { kapot: true } }),
      frame({ type: "vraagkaart", vraagkaart: 3 }),
      frame({ type: "hergebruik", hergebruik: "nee" }),
      frame({ type: "meting", contextopbouw: "nee" }),
      frame({ type: "done", uitkomst: "gestopt" }),
    ])));
    const h = { onAntwoord: vi.fn(), onVraagkaart: vi.fn(), onHergebruik: vi.fn(), onContextopbouw: vi.fn(), onDone: vi.fn() };
    await volgRun("r", h);
    for (const f of [h.onAntwoord, h.onVraagkaart, h.onHergebruik, h.onContextopbouw]) expect(f).not.toHaveBeenCalled();
    expect(h.onDone).toHaveBeenCalledWith("gestopt");
  });

  it("geen body is een fout, geen stille afloop", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 200 })));
    await expect(volgRun("r", {})).rejects.toMatchObject({ status: 0, detail: "Geen agentstroom." });
  });

  it("haakt aan op het gevraagde punt, met het run-id als één segment", async () => {
    const f = vi.fn(async () => stroom([frame({ type: "done" })]));
    vi.stubGlobal("fetch", f);
    await volgRun("a/b", {}, 17);
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe("/api/annotatie/run/a%2Fb/events?vanaf=17");
  });
});

describe("haalActieveRun – drie uitkomsten", () => {
  it("null is: er loopt niets", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(null)));
    expect(await haalActieveRun("g1")).toBeNull();
  });

  it("een fout of een onbereikbare BFF is onbekend, niet: er loopt niets", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 502 })));
    expect(await haalActieveRun("g1")).toBe("onbekend");
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("offline"); }));
    expect(await haalActieveRun("g1")).toBe("onbekend");
  });

  it("een antwoord met een verkeerde vorm telt als geen run", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ iets: "anders" })));
    expect(await haalActieveRun("g 1")).toBeNull();
  });
});

describe("stopRun", () => {
  it("een geweigerd stopverzoek gooit de fout van de server", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: "Al klaar." }, { status: 409 })));
    await expect(stopRun("r1")).rejects.toMatchObject({ status: 409, detail: "Al klaar." });
  });
});

describe("naarInloggen – een verlopen sessie", () => {
  function venster(pathname: string, search = "") {
    const loc = { pathname, search, origin: "http://werkplek.test", href: `http://werkplek.test${pathname}${search}` };
    vi.stubGlobal("window", { location: loc });
    return loc;
  }

  it("zonder window (de server) doet het niets", () => {
    expect(() => naarInloggen()).not.toThrow();
  });

  it("op het inlogscherm zelf blijft het staan", async () => {
    const loc = venster("/login", "?x=1");
    await parseError(new Response("", { status: 401 }));
    expect(loc.href).toBe("http://werkplek.test/login?x=1");
  });

  it("een 401 stuurt één keer naar het inlogscherm, met de huidige plek als terugweg", async () => {
    const loc = venster("/werkgebieden/wg-1", "?tab=bronnen");
    await parseError(Response.json({ detail: "Niet ingelogd." }, { status: 401 }));
    expect(loc.href).toBe("http://werkplek.test/login?callbackUrl=%2Fwerkgebieden%2Fwg-1%3Ftab%3Dbronnen");
    // Een tweede 401 in hetzelfde paginaleven navigeert niet opnieuw.
    loc.href = "ongewijzigd";
    await parseError(new Response("", { status: 401 }));
    expect(loc.href).toBe("ongewijzigd");
  });
});

describe("bestandsnaamUit", () => {
  it.each([
    [`attachment; filename="art-9.pdf"`, "art-9.pdf"],
    [`attachment; filename=art-9.csv`, "art-9.csv"],
    // De RFC 5987-vorm gaat voor, want alleen die draagt tekens buiten ASCII.
    [`attachment; filename="fallback.md"; filename*=UTF-8''bel%C3%A9id.md`, "beléid.md"],
    [`attachment; filename*=utf-8''%E0%A4%A; filename="terugval.md"`, "terugval.md"],
    [null, undefined],
    ["inline", undefined],
  ])("%s → %s", (header, naam) => {
    expect(bestandsnaamUit(header)).toBe(naam);
  });
});

describe("haalDelegaties – één verzoek per gesprek", () => {
  it("deelt het antwoord tot het vergeten wordt, en vertelt dat aan wie luistert", async () => {
    const f = vi.fn(async () => Response.json({ delegaties: [] }));
    vi.stubGlobal("fetch", f);
    await Promise.all([haalDelegaties("g1"), haalDelegaties("g1")]);
    expect(f).toHaveBeenCalledTimes(1);
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe("/api/delegaties?gesprek_id=g1&limit=50");

    const luisteraar = vi.fn();
    const stop = luisterNaarDelegaties(luisteraar);
    vergeetDelegaties("g1");
    expect(luisteraar).toHaveBeenCalledWith("g1");
    await haalDelegaties("g1");
    expect(f).toHaveBeenCalledTimes(2);

    stop();
    vergeetDelegaties();
    expect(luisteraar).toHaveBeenCalledTimes(1);
  });

  it("een fout geeft een lege lijst, en de volgende keer wordt het opnieuw gevraagd", async () => {
    const f = vi.fn(async () => new Response("", { status: 500 }));
    vi.stubGlobal("fetch", f);
    expect(await haalDelegaties("g2")).toEqual([]);
    await haalDelegaties("g2");
    expect(f).toHaveBeenCalledTimes(2);
  });
});
