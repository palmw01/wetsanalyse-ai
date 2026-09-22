import { describe, expect, it } from "vitest";

import { parseHergebruik } from "./agentEvents";
import {
  doelInvoerVan,
  doelVoorOpnieuw,
  hergebruikTekst,
  LIFECYCLE_LABEL,
  splitsVerouderd,
} from "./annotatie";
import type { AgentHergebruik } from "./types";

const telling = { markeringen: 12, beoordeeld: 5, afgewezen: 0, te_beoordelen: 7 };

describe("parseHergebruik", () => {
  it("leest de leden zoals graph-qa ze stuurt ({lid, hash, iri})", () => {
    const h = parseHergebruik({
      slug: "laag1", volledig: true, bijgewerkt: "2026-09-01",
      leden: [{ lid: "1", hash: "h1", iri: "urn:bwb:x" }, { lid: "2", hash: "h2", iri: "" }],
      telling,
    });
    expect(h).toEqual({ slug: "laag1", volledig: true, bijgewerkt: "2026-09-01", leden: ["1", "2"], telling });
  });

  it("zonder slug is er niets om naar te wijzen", () => {
    expect(parseHergebruik({ volledig: true, leden: [] })).toBeUndefined();
  });

  it("een half event valt terug op nullen in plaats van te breken", () => {
    const h = parseHergebruik({ slug: "laag1" });
    expect(h?.leden).toEqual([]);
    expect(h?.telling.markeringen).toBe(0);
    expect(h?.volledig).toBe(false);
  });
});

describe("hergebruikTekst", () => {
  const basis: AgentHergebruik = { slug: "s", leden: ["2"], volledig: true, bijgewerkt: "", telling };

  it("zegt bij volledig hergebruik dat er niets opnieuw is bekeken", () => {
    expect(hergebruikTekst(basis)).toBe(
      "Lid 2 was al geannoteerd en de wettekst is sindsdien niet veranderd. Dit is de bestaande " +
        "annotatie (12 markeringen, waarvan 5 beoordeeld en 7 nog te beoordelen).",
    );
  });

  it("noemt meerdere leden, en een artikel zonder leden als het artikel", () => {
    expect(hergebruikTekst({ ...basis, leden: ["1", "3"], volledig: false })).toMatch(/^Leden 1, 3 kwam ongewijzigd/);
    expect(hergebruikTekst({ ...basis, leden: [""] })).toMatch(/^Dit artikel was al geannoteerd/);
  });

  it("enkelvoud bij één markering", () => {
    expect(hergebruikTekst({ ...basis, telling: { ...telling, markeringen: 1 } })).toContain("1 markering,");
  });
});

describe("opnieuw annoteren", () => {
  it("gebruikt het doel van de beurt als dat er is, anders het artikel van de laag", () => {
    const doel = { bwbId: "BWBR0004770", artikel: "9", lid: "2" };
    const doc = { bwbId: "BWBR0004770", artikel: "9", citeertitel: "IW 1990" };
    expect(doelVoorOpnieuw(doel, doc)).toBe(doel);
    expect(doelVoorOpnieuw(undefined, doc)).toEqual({ bwbId: "BWBR0004770", artikel: "9", citeertitel: "IW 1990" });
    expect(doelVoorOpnieuw(undefined, undefined)).toBeUndefined();
  });

  it("neemt van een doel-event alleen de aanduiding mee, niet de tekst", () => {
    expect(
      doelInvoerVan({ bwbId: "B", artikel: "9", lid: "", leden_teksten: [{ lid: "", tekst: "…" }] }),
    ).toEqual({ bwbId: "B", artikel: "9" });
    expect(doelInvoerVan(null)).toBeUndefined();
  });
});

describe("splitsVerouderd", () => {
  it("scheidt de historie van wat actueel is, met behoud van volgorde", () => {
    const { actueel, historie } = splitsVerouderd([
      { id: "a" }, { id: "b", verouderd: true }, { id: "c", verouderd: false },
    ]);
    expect(actueel.map((e) => e.id)).toEqual(["a", "c"]);
    expect(historie.map((e) => e.id)).toEqual(["b"]);
  });
});

it("elke lifecycle heeft een label", () => {
  expect(Object.keys(LIFECYCLE_LABEL).sort()).toEqual(
    ["critic_checked", "edited", "human_approved", "published", "rejected", "reused", "voorgesteld"],
  );
});
