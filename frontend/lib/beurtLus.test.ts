import { describe, expect, it } from "vitest";
import { isAfgebroken, volgTotEinde, type LusDeps, type PogingStand } from "./beurtLus";
import { herstelWachttijd } from "./lopendeRun";

/** Een poging uit een script: welke events komen er binnen, en eindigt hij met `done` of met een fout. */
type Stap = { events?: Parameters<PogingStand["pas"]>[0][]; fout?: unknown };

const breuk = () => Object.assign(new Error("stroom gesloten zonder done"), { status: 502 });
const afbreken = () => Object.assign(new Error("aborted"), { name: "AbortError" });

function lus(stappen: Stap[], extra: Partial<LusDeps> = {}) {
  const log: string[] = [];
  const wachttijden: number[] = [];
  const standen: string[] = [];
  let n = 0;
  const deps: LusDeps = {
    levend: () => true,
    wacht: async (ms) => { wachttijden.push(ms); return true; },
    opVerbroken: (poging) => log.push(`verbroken:${poging}`),
    naPoging: () => log.push("na"),
    poging: async (p) => {
      const stap = stappen[Math.min(n++, stappen.length - 1)];
      standen.push(p.stand().tekst); // de stand aan het begin van elke poging
      log.push("poging");
      for (const e of stap.events ?? []) p.pas(e);
      if (stap.fout) throw stap.fout;
    },
    ...extra,
  };
  return { uitkomst: volgTotEinde(deps), log, wachttijden, standen, pogingen: () => n };
}

describe("volgTotEinde", () => {
  it("een stroom die tot done loopt is klaar, met zijn stand", async () => {
    const t = lus([{ events: [{ type: "token", tekst: "Antwoord." }] }]);
    const u = await t.uitkomst;
    expect(u.soort).toBe("klaar");
    expect(u.soort === "klaar" && u.stand.tekst).toBe("Antwoord.");
    expect(t.log).toEqual(["poging", "na"]);
  });

  it("een breuk: wachten, opnieuw aanhaken vanaf een lege stand, en dan klaar", async () => {
    const t = lus([
      { events: [{ type: "token", tekst: "Half" }], fout: breuk() },
      { events: [{ type: "token", tekst: "Heel antwoord." }] },
    ]);
    const u = await t.uitkomst;
    expect(u.soort === "klaar" && u.stand.tekst).toBe("Heel antwoord.");
    expect(t.standen).toEqual(["", ""]); // geen "HalfHeel antwoord."
    expect(t.log).toEqual(["poging", "verbroken:0", "na", "poging", "na"]);
    expect(t.wachttijden).toEqual([herstelWachttijd(0)]);
  });

  it("de wachttijd loopt op zonder levensteken, en begint opnieuw na een levensteken", async () => {
    const t = lus([
      { fout: breuk() }, { fout: breuk() }, { events: [{ type: "leeft" }], fout: breuk() }, { fout: breuk() }, {},
    ]);
    await t.uitkomst;
    expect(t.wachttijden).toEqual([0, 1, 2, 0].map(herstelWachttijd));
  });

  it("een definitieve fout is mislukt, zonder opnieuw te proberen, met de stand van die poging", async () => {
    const fout = { status: 502, agentFout: true, detail: "De laag is afgerond." };
    const t = lus([{ events: [{ type: "token", tekst: "Deels" }], fout }]);
    const u = await t.uitkomst;
    expect(u).toEqual({ soort: "mislukt", fout, stand: expect.objectContaining({ tekst: "Deels" }) });
    expect(t.pogingen()).toBe(1);
    expect(t.wachttijden).toEqual([]);
    for (const status of [401, 403, 404]) {
      expect((await lus([{ fout: { status } }]).uitkomst).soort).toBe("mislukt");
    }
  });

  it("zelf loskoppelen (AbortError) is geen fout en geen einde", async () => {
    expect(isAfgebroken(afbreken())).toBe(true);
    const t = lus([{ fout: afbreken() }]);
    expect(await t.uitkomst).toEqual({ soort: "losgekoppeld" });
    expect(t.log).toEqual(["poging", "na"]);
  });

  it("verdwijnt het venster tijdens het wachten, dan haakt de lus niet opnieuw aan", async () => {
    let levend = true;
    const t = lus([{ fout: breuk() }, {}], {
      levend: () => levend,
      wacht: async () => { levend = false; return false; },
    });
    expect(await t.uitkomst).toEqual({ soort: "losgekoppeld" });
    expect(t.pogingen()).toBe(1);
  });

  it("is het venster al weg, dan begint er geen poging", async () => {
    const t = lus([{}], { levend: () => false });
    expect(await t.uitkomst).toEqual({ soort: "losgekoppeld" });
    expect(t.pogingen()).toBe(0);
    expect(t.log).toEqual([]);
  });

  it("een breuk terwijl het venster weg is, telt als losgekoppeld", async () => {
    let levend = true;
    const t = lus([{ fout: breuk() }], { poging: async () => { levend = false; throw breuk(); }, levend: () => levend });
    expect(await t.uitkomst).toEqual({ soort: "losgekoppeld" });
  });

  it("500 breuken achter elkaar: een lus, geen recursie", async () => {
    const stappen: Stap[] = [...Array.from({ length: 500 }, () => ({ fout: breuk() })), { events: [{ type: "token", tekst: "ok" }] }];
    const t = lus(stappen);
    const u = await t.uitkomst;
    expect(u.soort === "klaar" && u.stand.tekst).toBe("ok");
    expect(t.pogingen()).toBe(501);
    expect(t.wachttijden.at(-1)).toBe(15_000);
  });
});
