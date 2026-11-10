import { describe, expect, it } from "vitest";

import { actueleElementen, maakWeergaveCache } from "./bronWeergave";

describe("bronWeergave", () => {
  it("toont alleen de actuele markeringen", () => {
    const el = (id: string, x: object = {}) => ({ id, lifecycle: "agent_proposed", verouderd: false, ...x });
    const view = { elementen: [el("a"), el("b", { verouderd: true }), el("c", { lifecycle: "rejected" })] } as never;
    expect(actueleElementen(view).map((e) => e.id)).toEqual(["a"]);
    expect(actueleElementen(undefined)).toEqual([]);
  });

  it("deelt een lopende lezing, bewaart de laatste en vraagt altijd opnieuw", async () => {
    let n = 0;
    const cache = maakWeergaveCache(async (iri: string) => `${iri}#${++n}`);
    const [a, b] = await Promise.all([cache.haal("x"), cache.haal("x")]);
    expect([a, b]).toEqual(["x#1", "x#1"]);
    expect(cache.bewaard("x")).toBe("x#1");
    expect(await cache.haal("x")).toBe("x#2");
    cache.vergeet("x");
    expect(cache.bewaard("x")).toBeUndefined();
  });

  it("houdt een mislukte lezing niet vast", async () => {
    let keer = 0;
    const cache = maakWeergaveCache(async () => { if (++keer === 1) throw new Error("weg"); return "ok"; });
    await expect(cache.haal("x")).rejects.toThrow("weg");
    expect(await cache.haal("x")).toBe("ok");
  });
});
