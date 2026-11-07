import { describe, expect, it } from "vitest";
import { zonderEmoji } from "./zonderEmoji";

describe("zonderEmoji", () => {
  it("haalt emoji weg, met de spatie erachter", () => {
    expect(zonderEmoji("✅ Gevonden in artikel 9.")).toBe("Gevonden in artikel 9.");
    expect(zonderEmoji("Let op ⚠️ de termijn")).toBe("Let op de termijn");
    expect(zonderEmoji("Klaar 👍🏽")).toBe("Klaar ");
    expect(zonderEmoji("Team 👩‍⚖️ beslist")).toBe("Team beslist");
  });

  it("laat tekst, symbolen en Markdown staan", () => {
    const tekst = "**Artikel 9** → lid 1 ↔ lid 2, © BZK, § 3, 10% en € 50:\n- 1. eerste\n- 2. tweede";
    expect(zonderEmoji(tekst)).toBe(tekst);
  });

  it("laat een teken zonder emoji-weergave staan", () => {
    expect(zonderEmoji("Zie ☎ en ⚠ en ✔")).toBe("Zie ☎ en ⚠ en ✔");
  });
});
