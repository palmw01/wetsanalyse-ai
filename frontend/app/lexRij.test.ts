import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Eén vorm voor een beurt van Lex (15 nov 2026, melding van de gebruiker: bij een annotatie stond het denkproces
 *  onderaan, bij een antwoord bovenaan). Elke soort rij van Lex gaat door `LexRij`, die het denkproces bovenaan zet,
 *  met één label. Een rij die zelf avatar, naam en denkproces opbouwt, komt niet terug. */

const RIJ = readFileSync(join(__dirname, "..", "components/werkplek/ThreadRij.tsx"), "utf8");

describe("een beurt van Lex heeft één vorm", () => {
  it("de naam Lex boven een beurt staat alleen in LexRij", () => {
    expect(RIJ.match(/font-medium text-muted">Lex<\/p>/g)?.length).toBe(1);
  });

  it("het denkproces staat alleen in LexRij en in het spoor per lid van een reeks", () => {
    const plekken = RIJ.match(/<DenkProces /g) ?? [];
    expect(plekken.length).toBe(2);
    expect(RIJ).toContain("spoor={(o, actief) => o.denk && <DenkProces tekst={o.denk} actief={actief} />}");
  });

  it("het denkproces heeft één label", () => {
    expect(RIJ).not.toContain("Zo is dit tot stand gekomen");
    expect(RIJ).not.toMatch(/<DenkProces[^>]*label=/);
  });
});
