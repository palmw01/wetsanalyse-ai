import { describe, expect, it } from "vitest";

import { maakStatusCache } from "./statusCache";

type S = { status: "actief" | "onbekend" | "ingetrokken" };

function opzet(antwoorden: S[]) {
  let t = 0;
  let n = 0;
  const haal = async () => antwoorden[Math.min(n++, antwoorden.length - 1)];
  const cache = maakStatusCache<S>(haal, { geldigMs: 300_000, onbekendMs: 30_000, nu: () => t });
  return { cache, tijd: (ms: number) => (t = ms), aanroepen: () => n };
}

describe("maakStatusCache", () => {
  it("houdt een bekende status de herverificatietijd vast", async () => {
    const o = opzet([{ status: "actief" }, { status: "ingetrokken" }]);
    expect((await o.cache("u")).status).toBe("actief");
    o.tijd(299_999);
    expect((await o.cache("u")).status).toBe("actief");
    o.tijd(300_001);
    expect((await o.cache("u")).status).toBe("ingetrokken");
    expect(o.aanroepen()).toBe(2);
  });

  it("onthoudt onbekend kort: een trage api kost niet elk verzoek opnieuw de wachttijd", async () => {
    const o = opzet([{ status: "onbekend" }, { status: "actief" }]);
    expect((await o.cache("u")).status).toBe("onbekend");
    o.tijd(29_000);
    expect((await o.cache("u")).status).toBe("onbekend");
    expect(o.aanroepen()).toBe(1);
    o.tijd(30_001);
    expect((await o.cache("u")).status).toBe("actief");
  });

  it("laat aanroepen die tegelijk lopen één verzoek delen", async () => {
    let los: (s: S) => void = () => {};
    let n = 0;
    const cache = maakStatusCache<S>(() => (n++, new Promise<S>((r) => (los = r))), { geldigMs: 1000, onbekendMs: 100 });
    const vijf = Array.from({ length: 5 }, () => cache("u"));
    los({ status: "actief" });
    expect((await Promise.all(vijf)).map((s) => s.status)).toEqual(Array(5).fill("actief"));
    expect(n).toBe(1);
  });

  it("probeert na een fout van de haler opnieuw", async () => {
    let n = 0;
    const cache = maakStatusCache<S>(async () => {
      if (n++ === 0) throw new Error("weg");
      return { status: "actief" };
    }, { geldigMs: 1000, onbekendMs: 100 });
    await expect(cache("u")).rejects.toThrow("weg");
    expect((await cache("u")).status).toBe("actief");
  });
});
