import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { LEGE_STAND, stroomReducer, type StroomEvent } from "./beurtStroom";
import { denkBij } from "./denkproces";
import { verwerkReeksEvent } from "./reeks";

// Dezelfde vectoren als graph-qa (`narratie.denk_bij`, `tests/test_denkproces_zonder_antwoord.py`): wie meekijkt en wie
// het bericht herlaadt, ziet hetzelfde denkproces. Deze test draait mee in `scripts/kruistests.sh`.
const VECTOREN = JSON.parse(
  readFileSync(join(__dirname, "../../tools/graph-qa/tests/data/denkproces-vectoren.json"), "utf8"),
) as { gevallen: { naam: string; events: Record<string, unknown>[]; denk: string }[] };

function alsStroomEvent(e: Record<string, unknown>): StroomEvent | null {
  switch (e.type) {
    case "status": return { type: "status", bericht: String(e.message ?? "") };
    case "reason": return { type: "reason", tekst: String(e.content ?? "") };
    case "token": return { type: "token", tekst: String(e.content ?? "") };
    default: return null;
  }
}

describe("denkproces: één regel aan beide kanten", () => {
  for (const geval of VECTOREN.gevallen) {
    it(`denkBij: ${geval.naam}`, () => {
      let denk = "";
      for (const e of geval.events)
        if (e.type === "status" || e.type === "reason")
          denk = denkBij(denk, e.type, String(e.type === "status" ? e.message : e.content));
      expect(denk).toBe(geval.denk);
    });

    it(`de beurt: ${geval.naam}`, () => {
      const stand = geval.events.map(alsStroomEvent).filter((e): e is StroomEvent => e !== null)
        .reduce(stroomReducer, LEGE_STAND);
      expect(stand.denk).toBe(geval.denk);
    });
  }

  it("een token komt nooit in het denkproces", () => {
    const stand = [
      { type: "status", bericht: "Lex · leest artikel 36" },
      { type: "token", tekst: "Het antwoord." },
    ].reduce((s, e) => stroomReducer(s, e as StroomEvent), LEGE_STAND);
    expect(stand.denk).not.toContain("Het antwoord.");
    expect(stand.tekst).toBe("Het antwoord.");
  });

  it("een reeks bouwt het denkproces per onderdeel met dezelfde regel", () => {
    const iri = "urn:bwb:BWBR0004770:artikel:9:lid:1";
    let reeks = verwerkReeksEvent(null, { type: "reeks", fase: "start", run_id: "r", totaal: 1,
      onderdelen: [{ bron_iri: iri, label: "lid 1" }] });
    for (const e of [{ type: "status", message: "Lex · leest lid 1" }, { type: "reason", content: "Ik markeer." }])
      reeks = verwerkReeksEvent(reeks, { ...e, onderdeel: iri });
    expect(reeks?.onderdelen[0].denk).toBe(denkBij(denkBij("", "status", "Lex · leest lid 1"), "reason", "Ik markeer."));
    expect(reeks?.onderdelen[0].denk).toBe("· Lex · leest lid 1\nIk markeer.");
  });
});
