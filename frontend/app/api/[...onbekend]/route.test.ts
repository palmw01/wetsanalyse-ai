import { describe, expect, it } from "vitest";

import { GET, PATCH } from "./route";

describe("onbekende api-route", () => {
  it("geeft een 404 als JSON met het pad", async () => {
    for (const f of [GET, PATCH]) {
      const r = f(new Request("http://x/api/annotatie/elementen/abc"));
      expect(r.status).toBe(404);
      expect(await r.json()).toEqual({ detail: "Onbekende route.", pad: "/api/annotatie/elementen/abc" });
    }
  });
});
