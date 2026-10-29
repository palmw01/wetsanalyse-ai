import { expect, it } from "vitest";
import { bronNummer } from "./bronNummer";

it("houdt opsommingstekens letterlijk en behoudt de conventie voor genummerde onderdelen", () => {
  for (const n of ["–", "—", "-", "•", "·", "●", "a.", "1°."]) expect(bronNummer(n)).toBe(n);
  expect(bronNummer("a")).toBe("a.");
  expect(bronNummer("1°")).toBe("1°.");
  expect(bronNummer("1")).toBe("1.");
  expect(bronNummer()).toBe("");
});
