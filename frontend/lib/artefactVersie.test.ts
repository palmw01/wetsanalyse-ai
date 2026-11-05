import { describe, expect, it } from "vitest";

import { beginPlek, isNu, plekLabel, versieTijd } from "./artefactVersie";
import { artefactSleutel, werkgebiedArtefactVan } from "./artefact";

describe("de versiekiezer", () => {
  const ids = ["v1", "v2", "v3"];

  it("een oude versie opent als die versie, de nieuwste en een onbekende als Nu", () => {
    expect(beginPlek(ids, "v1")).toBe(0);
    expect(beginPlek(ids, "v3")).toBe(3);
    expect(beginPlek(ids, "weg")).toBe(3);
    expect(beginPlek(ids, undefined)).toBe(3);
    expect(isNu(3, 3)).toBe(true);
    expect(isNu(2, 3)).toBe(false);
  });

  it("zegt versie n van m, of Nu", () => {
    expect(plekLabel(0, 3)).toBe("Versie 1 van 3");
    expect(plekLabel(3, 3)).toBe("Nu");
  });

  it("de tijd in gewone woorden, in Nederlandse tijd", () => {
    expect(versieTijd("2026-11-05T09:42:00Z")).toMatch(/^5 nov\.?,? 10:42$/);
    expect(versieTijd("geen datum")).toBe("");
  });

  it("de chip draagt zijn versie, en een andere versie is een ander paneel", () => {
    const a = werkgebiedArtefactVan({ soort: "werkgebied", ref: { werkgebied_id: "w1", versie: "v1" }, titel: "W" });
    expect(a?.versie).toBe("v1");
    const b = werkgebiedArtefactVan({ soort: "werkgebied", ref: { werkgebied_id: "w1", versie: "v2" }, titel: "W" });
    expect(artefactSleutel(a!)).not.toBe(artefactSleutel(b!));
    expect(werkgebiedArtefactVan({ soort: "werkgebied", ref: { werkgebied_id: "w1" }, titel: "W" })?.versie).toBeUndefined();
  });
});
