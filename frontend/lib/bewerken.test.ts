import { describe, expect, it } from "vitest";

import { bewerkToets, isGewijzigd } from "./bewerken";

describe("bewerken", () => {
  it("Escape annuleert, Ctrl/⌘+Enter slaat op, Enter alleen in een veld van één regel", () => {
    expect(bewerkToets({ key: "Escape" }, false)).toBe("annuleren");
    expect(bewerkToets({ key: "Enter", ctrlKey: true }, false)).toBe("opslaan");
    expect(bewerkToets({ key: "Enter", metaKey: true }, false)).toBe("opslaan");
    expect(bewerkToets({ key: "Enter" }, false)).toBeNull();
    expect(bewerkToets({ key: "Enter" }, true)).toBe("opslaan");
    expect(bewerkToets({ key: "Enter", shiftKey: true }, true)).toBeNull();
    expect(bewerkToets({ key: "Enter", isComposing: true }, true)).toBeNull();
    expect(bewerkToets({ key: "a" }, true)).toBeNull();
  });

  it("gewijzigd telt geen witruimte aan de randen en geen sleutelvolgorde", () => {
    expect(isGewijzigd("Wie?", " Wie? ")).toBe(false);
    expect(isGewijzigd({ a: "x", b: "y" }, { b: "y ", a: "x" })).toBe(false);
    expect(isGewijzigd({ a: "x" }, { a: "z" })).toBe(true);
    expect(isGewijzigd(["a"], ["a", "b"])).toBe(true);
  });
});
