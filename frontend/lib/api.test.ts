import { afterEach, describe, expect, it, vi } from "vitest";
import { isApiError, login2fa, loginVerify, parseError, startRun, volgRun } from "./api";
import type { AgentGrounding } from "./types";

describe("parseError", () => {
  it("haalt een string-detail uit de JSON-body", async () => {
    const res = new Response(JSON.stringify({ detail: "Onbekend project" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
    const err = await parseError(res);
    expect(err).toMatchObject({ status: 404, detail: "Onbekend project" });
    expect(err.retryAfter).toBeUndefined();
  });

  it("stringificeert een niet-string detail (bv. validatiefouten)", async () => {
    const res = new Response(JSON.stringify({ detail: [{ msg: "te lang" }] }), {
      status: 422,
      headers: { "Content-Type": "application/json" },
    });
    const err = await parseError(res);
    expect(err.status).toBe(422);
    expect(err.detail).toContain("te lang");
  });

  it("valt terug op statusText zonder JSON-body", async () => {
    const res = new Response("kapot", { status: 502, statusText: "Bad Gateway" });
    const err = await parseError(res);
    expect(err.status).toBe(502);
    expect(err.detail).toBe("Bad Gateway");
  });

  it("leest de Retry-After-header als getal", async () => {
    const res = new Response(JSON.stringify({ detail: "te druk" }), {
      status: 429,
      headers: { "Content-Type": "application/json", "Retry-After": "12" },
    });
    const err = await parseError(res);
    expect(err.retryAfter).toBe(12);
  });
});

function sseResponse(frames: string[]): Response {
  const enc = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) controller.enqueue(enc.encode(f));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

describe("verwerkSseStroom – via volgRun", () => {
  afterEach(() => vi.restoreAllMocks());

  it("splitst token/sources/doel/element-frames (incl. \\r\\n) naar de juiste handlers", async () => {
    const element = { klasse: "Rechtssubject", tekst: "de ontvanger" };
    const frames = [
      `data: ${JSON.stringify({ type: "status", message: "Graaf bevragen: get_artikel" })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "reason", content: "Ik zoek dit op." })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "token", content: "Antwoord " })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "token", content: "hier." })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "sources", sources: [{ label: "IW art. 9", uri: "x" }] })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "doel", doel: { bwbId: "BWBR0004770", artikel: "9", lid: "1" } })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "element", element })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "ontbrekend", items: [{ klasse: "Rechtsfeit", reden: "handeling" }] })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "done" })}\r\n\r\n`,
    ];
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frames)));

    let tekst = "";
    let denk = "";
    let doel: unknown = null;
    const elementen: unknown[] = [];
    let ontbrekend: unknown[] = [];
    let bronnen: unknown[] = [];
    await volgRun("run-1", {
      onStatus: (m) => (denk += `[${m}]`),
      onReason: (t) => (denk += t),
      onToken: (t) => (tekst += t),
      onSources: (b) => (bronnen = b),
      onDoel: (d) => (doel = d),
      onElement: (e) => elementen.push(e),
      onOntbrekend: (items) => (ontbrekend = items),
    });

    expect(tekst).toBe("Antwoord hier."); // token = alléén het eindantwoord
    expect(denk).toBe("[Graaf bevragen: get_artikel]Ik zoek dit op."); // status + reason = denkproces
    expect(bronnen).toEqual([{ label: "IW art. 9", uri: "x" }]);
    expect(doel).toEqual({ bwbId: "BWBR0004770", artikel: "9", lid: "1" });
    // Het schema vult de velden aan die de agent wegliet. Dat is geen kosmetiek: `VoorstelElement`
    // eist ze, dus vóór de validatie kreeg de UI een object dat niet aan zijn eigen type voldeed.
    expect(elementen).toEqual([
      { ...element, lid: "", toelichting: "", vindplaats: "", alternatieven: [], grounded: false },
    ]);
    expect(ontbrekend).toEqual([{ klasse: "Rechtsfeit", reden: "handeling" }]);
  });

  it("slaat een misvormd event over en laat de rest van de beurt doorlopen", async () => {
    // De regel achter agentEvents.ts: één frame dat zijn vorm niet haalt kost de jurist niet zijn
    // hele antwoord. Hier mist het element zijn `tekst` (zonder letterlijk fragment valt er niets
    // brongetrouws te tonen) en draagt het doel geen bwbId — beide horen te verdwijnen, terwijl de
    // tokens ervoor en erna gewoon aankomen.
    const stil = vi.spyOn(console, "warn").mockImplementation(() => {});
    const frames = [
      `data: ${JSON.stringify({ type: "token", content: "voor " })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "element", element: { klasse: "Rechtssubject" } })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "doel", doel: { artikel: "9" } })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "token", content: "na" })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "done" })}\r\n\r\n`,
    ];
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frames)));

    let tekst = "";
    const elementen: unknown[] = [];
    let doel: unknown = null;
    await volgRun("run-1", {
      onToken: (t) => (tekst += t),
      onElement: (e) => elementen.push(e),
      onDoel: (d) => (doel = d),
    });

    expect(tekst).toBe("voor na"); // de stroom liep door
    expect(elementen).toEqual([]);
    expect(doel).toBeNull();
    expect(stil).toHaveBeenCalledTimes(2);
    // De waarschuwing benoemt wél wát er sneuvelde, maar draagt geen wettekst mee.
    expect(stil.mock.calls[0]?.[0]).toContain("element");
  });

  it("vult ontbrekende velden van een element aan in plaats van ze door te laten", async () => {
    // VoorstelElement eist lid/toelichting/vindplaats/alternatieven/grounded. Een agent die ze
    // weglaat leverde vóór de validatie een object op dat niet aan zijn eigen type voldeed.
    const frames = [
      `data: ${JSON.stringify({ type: "element", element: { klasse: "Rechtsfeit", tekst: "betaalt" } })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "done" })}\r\n\r\n`,
    ];
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frames)));

    const elementen: unknown[] = [];
    await volgRun("run-1", { onElement: (e) => elementen.push(e) });

    expect(elementen).toEqual([
      {
        klasse: "Rechtsfeit",
        tekst: "betaalt",
        lid: "",
        toelichting: "",
        vindplaats: "",
        alternatieven: [],
        grounded: false,
      },
    ]);
  });

  it("geeft een waarschuwing door zonder de beurt te laten mislukken", async () => {
    // De api laat een markering die zijn schema niet haalt vallen in plaats van de hele ronde te
    // weigeren. Dat maakt een luide fout stil, dus meldt de agent het – maar het is geen `error`:
    // de rest staat er wél en de stream loopt gewoon door tot `done`.
    const frames = [
      `data: ${JSON.stringify({ type: "waarschuwing", message: "2 markeringen niet opgeslagen." })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "token", content: "Klaar." })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "done" })}\r\n\r\n`,
    ];
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frames)));

    let waarschuwing = "";
    let tekst = "";
    await volgRun("run-1", {
      onWaarschuwing: (m) => (waarschuwing = m),
      onToken: (t) => (tekst += t),
    });

    expect(waarschuwing).toBe("2 markeringen niet opgeslagen.");
    expect(tekst).toBe("Klaar.");
  });
});

describe("een stroom die breekt of stilvalt", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("merkt een fout van de agent zélf als definitief", async () => {
    // Zowel dit als "de BFF kan graph-qa niet bereiken" is een 502; alleen `agentFout` scheidt ze,
    // en dáár hangt aan of opnieuw aanhaken zin heeft.
    const frames = [
      `data: ${JSON.stringify({ type: "token", content: "Halve " })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "error", message: "Agent mislukt." })}\r\n\r\n`,
    ];
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frames)));

    await expect(volgRun("run-1", {})).rejects.toMatchObject({
      status: 502,
      detail: "Agent mislukt.",
      agentFout: true,
    });
  });

  it("meldt een levensteken bij het eerste event", async () => {
    // Hierop haalt de werkplek de "verbinding weg"-melding weg. Zonder dit zou een geslaagd
    // heraanhaken pas aan het eind van de beurt zichtbaar zijn.
    const frames = [
      `data: ${JSON.stringify({ type: "status", message: "Bezig" })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "token", content: "Ja." })}\r\n\r\n`,
    ];
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frames)));

    let levenstekens = 0;
    await volgRun("run-1", { onLeeft: () => levenstekens++ });
    expect(levenstekens).toBe(2);
  });

  it("verwerpt een stroom die stilvalt in plaats van eeuwig te wachten", async () => {
    // Een halfopen socket levert nooit een fout en nooit `done`: de werkplek bleef "bezig" tonen
    // zonder ooit het herstelpad te raken. De heartbeat van de agent (~15 s) hoort de bewaking
    // telkens te resetten; blijft ook die weg, dan is de verbinding weg.
    vi.useFakeTimers();
    const stil = new ReadableStream<Uint8Array>({ start() {} }); // levert niets, sluit nooit
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(stil, { status: 200 })),
    );

    const belofte = volgRun("run-1", {});
    const uitkomst = expect(belofte).rejects.toMatchObject({ status: 0 });
    await vi.advanceTimersByTimeAsync(45_000);
    await uitkomst;
  });
});

describe("volgRun – aanhaken bij een lopende beurt", () => {
  afterEach(() => vi.restoreAllMocks());

  it("meldt het volgnummer terug, zodat aanhaken na een onderbreking op het juiste punt begint", async () => {
    const frames = [
      `data: ${JSON.stringify({ type: "token", content: "een ", seq: 4 })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "token", content: "antwoord", seq: 5 })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "done", seq: 6 })}\r\n\r\n`,
    ];
    const nep = vi.fn(async (_url: string | URL) => sseResponse(frames));
    vi.stubGlobal("fetch", nep);

    let tekst = "";
    const seqs: number[] = [];
    await volgRun("run-1", { onToken: (t) => (tekst += t), onSeq: (n) => seqs.push(n) }, 4);

    expect(tekst).toBe("een antwoord");
    expect(seqs).toEqual([4, 5, 6]);
    // De cursor gaat mee in de URL: je vraagt precies wat je miste, niet de hele beurt opnieuw.
    expect(String(nep.mock.calls[0]?.[0])).toContain("vanaf=4");
  });

  it("benoemt een gat in plaats van stilzwijgend een verminkte tekst te leveren", async () => {
    const frames = [
      `data: ${JSON.stringify({ type: "gat", weggevallen: 12 })}\r\n\r\n`,
      `data: ${JSON.stringify({ type: "token", content: "de rest", seq: 12 })}\r\n\r\n`,
    ];
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frames)));

    let gat = 0;
    let tekst = "";
    await volgRun("run-1", { onGat: (n) => (gat = n), onToken: (t) => (tekst += t) });

    expect(gat).toBe(12);
    expect(tekst).toBe("de rest");
  });
});

describe("grounding-event", () => {
  afterEach(() => vi.restoreAllMocks());

  it("levert het niveau door, zodat 'niets te controleren' niet als 'gecontroleerd' leest", async () => {
    const frames = [
      `data: ${JSON.stringify({ type: "token", content: "Een antwoord." })}\r\n\r\n`,
      `data: ${JSON.stringify({
        type: "grounding", grounded: true, cited: 0, unsupported: [],
        niet_letterlijk: [], niveau: "onbepaald",
      })}\r\n\r\n`,
    ];
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frames)));

    const gevangen: AgentGrounding[] = [];
    await volgRun("run-1", { onGrounding: (x) => gevangen.push(x) });

    expect(gevangen[0]).toEqual({
      niveau: "onbepaald", grounded: true, cited: 0, unsupported: [], niet_letterlijk: [],
    });
  });

  it("valt terug op grounded als een oudere agent nog geen niveau stuurt", async () => {
    const frames = [
      `data: ${JSON.stringify({ type: "grounding", grounded: false, cited: 2, unsupported: ["BWBR9999999"] })}\r\n\r\n`,
    ];
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frames)));

    const gevangen: AgentGrounding[] = [];
    await volgRun("run-1", { onGrounding: (x) => gevangen.push(x) });

    expect(gevangen[0]?.niveau).toBe("ongegrond");
    expect(gevangen[0]?.niet_letterlijk).toEqual([]);
  });
});

describe("startRun – er loopt er al een", () => {
  afterEach(() => vi.restoreAllMocks());

  it("gooit bij 409, mét het id van de lopende run erbij", async () => {
    // Twee gelijktijdige beurten op één gesprek zouden door elkaar heen in het agent-geheugen
    // schrijven (thread_id == conversation_id) – vandaar dat de server weigert en verwijst.
    //
    // Gooien en niet stilzwijgend de bestaande run teruggeven: deze vráág is niet aangenomen. Gaf
    // `startRun` hier gewoon de lopende run terug, dan verscheen het antwoord op de vórige vraag
    // onder de nieuwe, en ging de nieuwe stilzwijgend verloren. De aanroeper kan met `loopendeRun`
    // alsnog aanhaken – maar dan wél wetend dat er iets anders speelt.
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ detail: { reden: "run_loopt_al", run_id: "run-bestaand" } }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    )));

    await expect(startRun("nog een vraag", "gesprek-1")).rejects.toMatchObject({
      status: 409,
      loopendeRun: "run-bestaand",
    });
  });

  it("weigert een run-antwoord dat zijn vorm niet haalt", async () => {
    // De run_id stuurt alles wat erna komt: aanhaken, stoppen, het idempotent wegschrijven van de
    // uitkomst. Een antwoord zonder bruikbare run_id doorlaten levert een beurt op die nergens meer
    // te vinden is — beter meteen als storing tonen.
    const stil = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ conversation_id: "gesprek-1", status: "loopt" }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    )));

    await expect(startRun("een vraag", "gesprek-1")).rejects.toMatchObject({ status: 502 });
    expect(stil).toHaveBeenCalled();
  });

  it("laat een echte fout wél een fout zijn", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ detail: "Agent onbereikbaar" }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    )));
    await expect(startRun("vraag", "gesprek-1")).rejects.toMatchObject({ status: 502 });
  });
});

describe("isApiError", () => {
  it("herkent een ApiError-vorm", () => {
    expect(isApiError({ status: 404, detail: "x" })).toBe(true);
  });
  it("wijst andere waarden af", () => {
    expect(isApiError(new Error("boom"))).toBe(false);
    expect(isApiError(null)).toBe(false);
    expect(isApiError("tekst")).toBe(false);
  });
});

// Een storing mag nooit als "verkeerd wachtwoord" bij de gebruiker aankomen: dat is precies het
// moment waarop iemand aan zijn geheugen gaat twijfelen in plaats van aan de infrastructuur. De
// API wijst een login af met een 200 + `ok: false`, dus alleen een 5xx is hier een storing.
describe("loginVerify / login2fa – storing vs. afwijzing", () => {
  afterEach(() => vi.restoreAllMocks());

  function antwoord(body: unknown, status: number): Response {
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }

  it("laat een gewone afwijzing ongemoeid (200 met ok:false)", async () => {
    const body = { ok: false, code: "invalid", userid: "", email: "", role: "" };
    vi.stubGlobal("fetch", vi.fn(async () => antwoord(body, 200)));
    await expect(loginVerify("jan", "fout")).resolves.toMatchObject({ ok: false, code: "invalid" });
  });

  it("houdt 429 een rate-limit, geen storing", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => antwoord({ detail: "te druk" }, 429)));
    await expect(loginVerify("jan", "x")).resolves.toMatchObject({ code: "rate" });
  });

  it("gooit bij een 504 (API antwoordde niet op tijd)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => antwoord({ detail: "niet op tijd" }, 504)));
    await expect(loginVerify("jan", "goed")).rejects.toMatchObject({ status: 504 });
  });

  it("gooit bij een 502 (API onbereikbaar)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => antwoord({ detail: "onbereikbaar" }, 502)));
    await expect(login2fa("jan", "123456", false)).rejects.toMatchObject({ status: 502 });
  });

  it("laat de 401 van de 2FA-route een afwijzing (ticket verlopen), geen storing", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => antwoord({ ok: false, code: "invalid" }, 401)));
    await expect(login2fa("jan", "123456", false)).resolves.toMatchObject({ code: "invalid" });
  });
});
