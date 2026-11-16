import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// @ts-expect-error – een .mjs-hulpbestand van de browserscripts, zonder typen
import { sse } from "../scripts/nepApi.mjs";

/** De nep-api van de browserscripts (Lex Bench §20.5 stap 2, testplan werkplek voorstel 2 en 4).
 *  - Eén `sse()` in de vorm van graph-qa (`\r\n`, `seq`), in `scripts/nepApi.mjs`; geen kopie per script.
 *  - Een onbekend pad is een fout: elk script met een nep-api valt terug op `onbekend(route, …)` en eindigt met
 *    `controleerOnbekend()`. Wat nog niet is omgezet, staat in `NOG_TOEGEEFLIJK`; die lijst mag alleen krimpen. */

const SCRIPTS = join(__dirname, "..", "scripts");

/** Scripts die een onbekend pad nog stil beantwoorden. Alleen weghalen; een nieuw script komt hier nooit bij. */
const NOG_TOEGEEFLIJK = new Set<string>([
  "test-annotatie-nodes.mjs",
  "test-antwoordweergave.mjs",
  "test-artefacten.mjs",
  "test-begrippen-verdieping.mjs",
  "test-bronkandidaten.mjs",
  "test-connectors-menu.mjs",
  "test-connectors.mjs",
  "test-rondleiding.mjs",
  "test-runstanden.mjs",
  "test-samenhang.mjs",
  "test-sidebar-groepen.mjs",
  "test-toetsen.mjs",
  "test-werkgebied-annoteren.mjs",
]);

function scriptsMetNepApi(): { naam: string; tekst: string }[] {
  return readdirSync(SCRIPTS)
    .filter((n) => /^test-.*\.mjs$/.test(n))
    .map((naam) => ({ naam, tekst: readFileSync(join(SCRIPTS, naam), "utf8") }))
    .filter((s) => s.tekst.includes('.route("**/api/**"'));
}

const isStreng = (tekst: string) => /return onbekend\(route\b/.test(tekst) && /controleerOnbekend\(\);/.test(tekst);

describe("[R21] de nep-api van de browserscripts", () => {
  it("vindt de scripts", () => {
    expect(scriptsMetNepApi().length).toBeGreaterThan(30);
  });

  it("valt in elk script terug op een fout, behalve in de scripts die nog omgezet moeten worden", () => {
    const toegeeflijk = scriptsMetNepApi().filter((s) => !isStreng(s.tekst)).map((s) => s.naam).sort();
    expect(toegeeflijk.filter((n) => !NOG_TOEGEEFLIJK.has(n)), "een nieuw script beantwoordt een onbekend pad stil").toEqual([]);
    expect([...NOG_TOEGEEFLIJK].filter((n) => !toegeeflijk.includes(n)), "al streng: haal het uit NOG_TOEGEEFLIJK").toEqual([]);
  });

  it("heeft één sse(): geen eigen kopie in een script", () => {
    const kopieen = readdirSync(SCRIPTS).filter((n) => n !== "nepApi.mjs" && n.endsWith(".mjs"))
      .filter((n) => /const sse\s*=|function sse\s*\(/.test(readFileSync(join(SCRIPTS, n), "utf8")));
    expect(kopieen).toEqual([]);
  });

  it("maakt frames zoals sse-starlette: \\r\\n, met seq, en vanaf een volgnummer", () => {
    const body: string = sse([{ type: "token", content: "a" }, { type: "done" }], { vanaf: 1 });
    expect(body).toBe('data: {"seq":1,"type":"done"}\r\n\r\n');
    expect(sse([{ type: "done" }], { ping: true })).toBe(': ping\r\n\r\ndata: {"seq":0,"type":"done"}\r\n\r\n');
  });
});
