import assert from "node:assert/strict";
import { test } from "node:test";

import { zonderSlotslash, zonderTags, zonderVoorvoegselnamen } from "./tekst.js";

const VOORBEELDEN = ["", "a", "<a>", "<a", "a<b>c", "<a<b>c", "<<>>", "x>y<z", "<al>tekst</al> en <b", "a:b", "a:b:c", ":x", "x:",
  "PREFIX bwb: <urn:bwb-ns:> SELECT ?a WHERE { ?a bwb:tekst ?t }", "urn:bwb:BWBR0004770:artikel:9", "a.b-c:d%2Fe f", "::", "a: b",
  "http://x//", "/", "//", "abc"];

test("tekst: precies wat de vervangen expressie gaf", () => {
    for (const s of VOORBEELDEN) {
      assert.equal(zonderTags(s), s.replace(/<[^>]*>/g, ""));
      assert.equal(zonderSlotslash(s), s.replace(/\/+$/, ""));
      assert.equal(zonderVoorvoegselnamen(s, " "), s.replace(/[\w.-]*:[\w.%-]*/g, " "));
    }
});

test("tekst: lineair op lange invoer", () => {
    const t0 = performance.now();
    zonderTags("<".repeat(100_000));
    zonderVoorvoegselnamen("a".repeat(100_000), " ");
    zonderSlotslash("/".repeat(100_000) + "x");
    assert.ok(performance.now() - t0 < 500);
});
