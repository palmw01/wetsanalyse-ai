import { strict as assert } from "node:assert";
import { test } from "node:test";

import { checkoutStand, type Git } from "./checkout.js";

const nep = (uit: Record<string, string>): Git => (args) => {
  const k = args.join(" ");
  if (!(k in uit)) throw new Error("onbekend");
  return uit[k];
};

test("waarschuwt als de checkout achter master ligt", () => {
  const s = checkoutStand(nep({
    "rev-parse --abbrev-ref HEAD": "claude/oud", "rev-parse --short HEAD": "abc1234",
    "rev-list --count HEAD..origin/master": "12",
  }));
  assert.deepEqual([s.branch, s.commit, s.achter_op_master], ["claude/oud", "abc1234", 12]);
  assert.match(s.waarschuwing ?? "", /12 commit\(s\) achter origin\/master/);
});

test("zegt niets als de checkout bij is, en geen getal als git het niet weet", () => {
  assert.equal(checkoutStand(nep({
    "rev-parse --abbrev-ref HEAD": "master", "rev-parse --short HEAD": "def5678",
    "rev-list --count HEAD..origin/master": "0",
  })).waarschuwing, undefined);
  assert.equal(checkoutStand(nep({})).achter_op_master, null);
});
