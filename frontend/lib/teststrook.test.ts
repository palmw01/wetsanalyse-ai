import { describe, expect, it } from "vitest";
import { bewaarWeggeklikt, leesWeggeklikt, loginSleutel, strookWeggeklikt, TESTSTROOK_SLEUTEL } from "./teststrook";

function geheugen(): Storage {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, v),
    removeItem: (k) => void m.delete(k),
    clear: () => m.clear(),
    key: () => null,
    get length() {
      return m.size;
    },
  };
}

const kapot = {
  getItem: () => {
    throw new Error("geblokkeerd");
  },
  setItem: () => {
    throw new Error("geblokkeerd");
  },
};

describe("loginSleutel", () => {
  it("is userid plus inlogmoment", () => {
    expect(loginSleutel("an1", 1700000000000)).toBe("an1:1700000000000");
  });

  it("verschilt per login en per account", () => {
    expect(loginSleutel("an1", 1)).not.toBe(loginSleutel("an1", 2));
    expect(loginSleutel("an1", 1)).not.toBe(loginSleutel("an2", 1));
  });

  it("geeft niets zonder userid of inlogmoment", () => {
    expect(loginSleutel(undefined, 1)).toBeUndefined();
    expect(loginSleutel("", 1)).toBeUndefined();
    expect(loginSleutel("an1", undefined)).toBeUndefined();
    expect(loginSleutel("an1", Number.NaN)).toBeUndefined();
  });
});

describe("strookWeggeklikt", () => {
  it("alleen bij dezelfde login", () => {
    expect(strookWeggeklikt("an1:1", "an1:1")).toBe(true);
    expect(strookWeggeklikt("an1:1", "an1:2")).toBe(false);
    expect(strookWeggeklikt("an1:1", "an2:1")).toBe(false);
    expect(strookWeggeklikt(null, "an1:1")).toBe(false);
  });

  it("blijft staan zonder sleutel", () => {
    expect(strookWeggeklikt(undefined, undefined)).toBe(false);
    expect(strookWeggeklikt("", undefined)).toBe(false);
  });
});

describe("opslag", () => {
  it("bewaart en leest de sleutel", () => {
    const opslag = geheugen();
    expect(leesWeggeklikt(opslag)).toBeNull();
    bewaarWeggeklikt("an1:1", opslag);
    expect(opslag.getItem(TESTSTROOK_SLEUTEL)).toBe("an1:1");
    expect(leesWeggeklikt(opslag)).toBe("an1:1");
  });

  it("gooit niet als de opslag geblokkeerd is", () => {
    expect(leesWeggeklikt(kapot)).toBeNull();
    expect(() => bewaarWeggeklikt("an1:1", kapot)).not.toThrow();
  });

  it("zonder opslag (server) niets", () => {
    expect(leesWeggeklikt(undefined)).toBeNull();
  });
});
