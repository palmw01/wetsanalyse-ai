import { describe, expect, it } from "vitest";

import { filtersUitParams, kaartUrl, kort, paramsVan } from "./begrippenOverzicht";

describe("begrippenoverzicht", () => {
  it("leest de filters uit de URL en laat onzin vallen; meer statussen lezen als de eerste geldige", () => {
    const f = filtersUitParams(new URLSearchParams("q=termijn&status=onzin&status=concept&status=geaccordeerd&werkgebied=w%2F1"));
    expect(f).toEqual({ q: "termijn", status: "concept", werkgebied: "", mijn: false });
    expect(filtersUitParams(new URLSearchParams("mijn=1")).mijn).toBe(true);
    expect(filtersUitParams(new URLSearchParams("")).status).toBe("");
  });

  it("schrijft dezelfde filters terug, met de api-namen voor werkgebied en mijn", () => {
    const f = { q: " termijn ", status: "geaccordeerd" as const, werkgebied: "wg-1", mijn: true };
    expect(paramsVan(f, "pagina").toString()).toBe("q=termijn&status=geaccordeerd&werkgebied=wg-1&mijn=1");
    expect(paramsVan(f, "api").toString()).toBe("q=termijn&status=geaccordeerd&werkgebied_id=wg-1&mijn=true");
    expect(paramsVan({ q: "", status: "", werkgebied: "", mijn: false }, "api").toString()).toBe("");
    // Heen en terug: de URL geeft dezelfde filters.
    expect(filtersUitParams(paramsVan(f, "pagina"))).toEqual({ ...f, q: "termijn" });
  });

  it("klikt door naar de kaart in zijn werkgebied", () => {
    expect(kaartUrl("wg 1", "b-2")).toBe("/werkgebieden/wg%201/artefacten/begrippen?begrip=b-2");
  });

  it("kort een definitie in op een woordgrens met een weglatingsteken", () => {
    expect(kort("a  b", 10)).toBe("a b");
    expect(kort("x".repeat(30), 10)).toBe(`${"x".repeat(10)}…`);
  });
});
