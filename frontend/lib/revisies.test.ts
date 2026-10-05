import { afterEach, describe, expect, it, vi } from "vitest";
import { actieTekst, geraakteElementen, haalRevisies, revisieSamenvatting, type Revisie } from "./revisies";

const r = (acties: Revisie["acties"]): Revisie => ({ revisie: 1, actor: "a", tijdstip: "2026-10-05T10:00:00+00:00", acties });

describe("revisieSamenvatting", () => {
  it("vat een ronde van Lex samen als één gebeurtenis", () => {
    expect(revisieSamenvatting(r([{ actie: "element-gemaakt", element_id: "e1" }, { actie: "element-gemaakt", element_id: "e2" }, { actie: "batch" }])))
      .toBe("ronde van Lex: 2 markeringen");
    expect(revisieSamenvatting(r([{ actie: "batch" }]))).toBe("ronde van Lex: geen nieuwe markeringen");
  });

  it("telt beslissingen per soort", () => {
    expect(revisieSamenvatting(r([{ actie: "approve", element_id: "e1" }, { actie: "approve", element_id: "e2" }, { actie: "edit", element_id: "e3" }])))
      .toBe("akkoord (2), aangepast");
  });

  it("noemt afronden en een onbekende actie bij naam", () => {
    expect(actieTekst({ actie: "laag-status", status: "geaccordeerd" })).toBe("afgerond");
    expect(actieTekst({ actie: "laag-status", status: "in_review" })).toBe("heropend");
    expect(actieTekst({ actie: "iets-nieuws" })).toBe("iets-nieuws");
    expect(revisieSamenvatting(r([]))).toBe("gewijzigd");
  });
});

describe("geraakteElementen", () => {
  it("geeft elk element één keer, in volgorde", () => {
    expect(geraakteElementen(r([{ actie: "edit", element_id: "b" }, { actie: "comment", element_id: "a" }, { actie: "approve", element_id: "b" }, { actie: "batch" }])))
      .toEqual(["b", "a"]);
  });
});

describe("haalRevisies", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("vraagt de revisies van één laag via de v2-proxy", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json([]));
    vi.stubGlobal("fetch", fetch);
    await haalRevisies("laag1");
    expect(String(fetch.mock.calls[0][0])).toBe("/api/annotatie/v2/lagen/laag1/revisies");
  });
});
