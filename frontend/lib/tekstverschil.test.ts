import { describe, expect, it } from "vitest";

import { blokken, tekstverschil, verschilZin } from "./tekstverschil";

const soorten = (oud: string, nieuw: string) => tekstverschil(oud, nieuw).regels.map((r) => `${r.soort[0]}:${r.tekst}`);

describe("tekstverschil", () => {
  it("gelijke teksten hebben geen verschil, ook met een andere regelovergang of een afsluitende regel", () => {
    expect(tekstverschil("a\nb\n", "a\r\nb")).toMatchObject({ erbij: 0, weg: 0, grof: false });
    expect(tekstverschil("", "").regels).toEqual([]);
    expect(verschilZin(tekstverschil("a", "a"))).toBe("geen verschil");
  });

  it("een regel erbij, een regel weg en een gewijzigde regel, met hun regelnummers", () => {
    expect(soorten("a\nb\nc", "a\nx\nb\nc")).toEqual(["g:a", "e:x", "g:b", "g:c"]);
    expect(soorten("a\nb\nc", "a\nc")).toEqual(["g:a", "w:b", "g:c"]);
    const v = tekstverschil("a\nb\nc", "a\nB\nc");
    expect(v.regels).toEqual([
      { soort: "gelijk", tekst: "a", oud: 1, nieuw: 1 }, { soort: "weg", tekst: "b", oud: 2, nieuw: null },
      { soort: "erbij", tekst: "B", oud: null, nieuw: 2 }, { soort: "gelijk", tekst: "c", oud: 3, nieuw: 3 }]);
    expect(verschilZin(v)).toBe("1 regel erbij, 1 regel weg");
  });

  it("een lege tekst naast een volle: alles erbij of alles weg", () => {
    expect(tekstverschil("", "a\nb")).toMatchObject({ erbij: 2, weg: 0 });
    expect(tekstverschil("a\nb", "")).toMatchObject({ erbij: 0, weg: 2 });
    expect(verschilZin({ erbij: 3, weg: 0 })).toBe("3 regels erbij");
  });

  it("oud en nieuw samen zijn precies de twee teksten", () => {
    const oud = "een\ntwee\ndrie\nvier\nvijf", nieuw = "nul\neen\ndrie\nvier en een half\nvijf\nzes";
    const { regels } = tekstverschil(oud, nieuw);
    expect(regels.filter((r) => r.soort !== "erbij").map((r) => r.tekst).join("\n")).toBe(oud);
    expect(regels.filter((r) => r.soort !== "weg").map((r) => r.tekst).join("\n")).toBe(nieuw);
  });

  it("een lang bestand met één wijziging is snel, en boven de grens is het midden één blok", () => {
    const regels = Array.from({ length: 20_000 }, (_, i) => `regel ${i}`);
    const anders = [...regels]; anders[10_000] = "anders";
    const start = performance.now();
    expect(tekstverschil(regels.join("\n"), anders.join("\n"))).toMatchObject({ erbij: 1, weg: 1, grof: false });
    expect(performance.now() - start).toBeLessThan(1000);
    const grof = tekstverschil("a\nb\nc\nd", "w\nx\ny\nz", 10);
    expect(grof).toMatchObject({ grof: true, erbij: 4, weg: 4 });
  });
});

describe("blokken", () => {
  it("toont de wijziging met context en klapt de rest in", () => {
    const oud = Array.from({ length: 30 }, (_, i) => `r${i}`);
    const nieuw = [...oud]; nieuw[15] = "anders";
    const b = blokken(tekstverschil(oud.join("\n"), nieuw.join("\n")).regels, 2);
    expect(b.map((x) => [x.soort, x.regels.length])).toEqual([["gelijk", 13], ["regels", 6], ["gelijk", 12]]);
    expect(blokken(tekstverschil("a\nb", "a\nb").regels).map((x) => x.soort)).toEqual(["gelijk"]);
    expect(blokken([])).toEqual([]);
  });
});
