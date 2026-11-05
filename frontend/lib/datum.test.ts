import { describe, expect, it } from "vitest";

import { datumTijd } from "./datum";

describe("datumTijd", () => {
  it("toont een moment in Nederlandse tijd", () => {
    expect(datumTijd("2026-11-05T09:42:00Z")).toBe("5 nov 2026, 10:42");
  });

  it("laat leeg en onleesbaar leeg", () => {
    expect(datumTijd(null)).toBe("");
    expect(datumTijd("geen datum")).toBe("");
  });
});
