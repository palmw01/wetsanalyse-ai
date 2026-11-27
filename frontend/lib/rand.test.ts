import { describe, expect, it } from "vitest";

import { zonderAchteraan, zonderLaatsteWoord, zonderRand } from "./rand";

const LETTER_OF_CIJFER = (c: string) => /[\p{L}\p{N}]/u.test(c);
const VOORBEELDEN = ["", "a", "abc", "a b", "a b c", "  a", "a  ", "  ", "a  b  ", "--x--", "-", "x-y", "...", "a.", "http://x//",
  "é ü", "a\tb\nc", "ab cd", "«woord»", "(1)", "--", "x", "a,;.\\"];

describe("rand", () => {
  it("doet precies wat de vervangen expressie deed", () => {
    for (const s of VOORBEELDEN) {
      expect(zonderAchteraan(s, "/")).toBe(s.replace(/\/+$/, ""));
      expect(zonderAchteraan(s, ".,;\\")).toBe(s.replace(/[.,;\\]+$/, ""));
      expect(zonderAchteraan(s, ".")).toBe(s.replace(/\.+$/, ""));
      expect(zonderRand(s, "-")).toBe(s.replace(/^-+|-+$/g, ""));
      expect(zonderRand(s, (c) => !LETTER_OF_CIJFER(c))).toBe(s.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, ""));
      expect(zonderLaatsteWoord(s)).toBe(s.replace(/\s+\S*$/, ""));
    }
  });

  it("is lineair op een lange reeks", () => {
    const lang = "/".repeat(200_000) + "x";
    const t0 = performance.now();
    zonderAchteraan(lang, "/");
    zonderRand("-".repeat(200_000) + "x", "-");
    zonderLaatsteWoord(" ".repeat(200_000) + "x");
    expect(performance.now() - t0).toBeLessThan(500);
  });
});
