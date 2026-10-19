import { describe, expect, it } from "vitest";

import { filtersUitParams, kaartUrl, kort, paramsVan } from "./begrippenOverzicht";

describe("begrippenoverzicht", () => {
  it("leest de filters uit de URL en laat onzin vallen", () => {
    const f = filtersUitParams(new URLSearchParams("q=termijn&status=concept&status=onzin&status=concept&werkgebied=w%2F1"));
    expect(f).toEqual({ q: "termijn", status: ["concept"], werkgebied: "" });
  });

  it("schrijft dezelfde filters terug, met de api-naam voor het werkgebied", () => {
    const f = { q: " termijn ", status: ["geaccordeerd", "vervangen"] as const, werkgebied: "wg-1" };
    expect(paramsVan({ ...f, status: [...f.status] }, "pagina").toString()).toBe(
      "q=termijn&status=geaccordeerd&status=vervangen&werkgebied=wg-1");
    expect(paramsVan({ ...f, status: [...f.status] }, "api").get("werkgebied_id")).toBe("wg-1");
    expect(paramsVan({ q: "", status: [], werkgebied: "" }, "api").toString()).toBe("");
  });

  it("klikt door naar de kaart in zijn werkgebied", () => {
    expect(kaartUrl("wg 1", "b-2")).toBe("/werkgebieden/wg%201?tab=begrippen&begrip=b-2");
  });

  it("kort een definitie in op een woordgrens met een weglatingsteken", () => {
    expect(kort("a  b", 10)).toBe("a b");
    expect(kort("x".repeat(30), 10)).toBe(`${"x".repeat(10)}…`);
  });
});
