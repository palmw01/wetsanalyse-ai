import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

// Melding gebruiker 23 nov 2026: de annotatie in lijn met de begrippen en de afleidingsregels. Een markering in de review
// is gebouwd uit dezelfde gedeelde onderdelen als een passage van een begrip en een rij naar een object; geen eigen stijl.
describe("de review in lijn met begrip en regel", () => {
  const kaart = bron("components/werkplek/ReviewQueue.tsx");

  it("het kaartje heeft het kader van een rij (RIJ_KADER), met de aandacht in de linkerrand", () => {
    expect(kaart).toMatch(/className=\{`\$\{RIJ_KADER\} border-l-4/);
    expect(kaart).not.toMatch(/rounded-kaart border border-line border-l-4 bg-paper p-3 shadow-zacht/);
    expect(bron("components/ui/Pagina.tsx")).toMatch(/\$\{RIJ_KADER\} text-left transition/);
  });

  it("het citaat is de gedeelde PassageCitaat, net als bij een begrip", () => {
    expect(kaart).toMatch(/<PassageCitaat data-kaart-citaat/);
    expect(kaart).not.toMatch(/italic text-ink">“\{el\.tekst\}”/);
    expect(bron("components/werkgebieden/BegripPassages.tsx")).toMatch(/<PassageCitaat tekst=/);
  });

  it("op slot is de klasse een KlasseLabel; het oordeel een StatusLabel", () => {
    expect(kaart).toMatch(/<KlasseLabel klasse=\{el\.klasse\}>/);
    expect(kaart).toMatch(/<StatusLabel toon=\{el\.lifecycle === "rejected" \? "rood" : "groen"\}>/);
  });

  it("de metaregel zoals onder een rij: text-xs, zonder lijn erboven", () => {
    const meta = kaart.slice(kaart.indexOf("data-kaart-meta"), kaart.indexOf(">", kaart.indexOf("data-kaart-meta")));
    expect(meta).toMatch(/text-xs text-muted/);
    expect(meta).not.toMatch(/border-t|text-3xs/);
  });

  it("de filters zijn FilterChips in een KeuzeRij, zoals in de overzichten", () => {
    expect(kaart).toMatch(/<KeuzeRij label="Filter de reviewlijst"/);
    expect(kaart).toMatch(/<FilterChip key=\{f\.waarde\}/);
    expect(kaart).not.toMatch(/aria-pressed=\{filter === f\.waarde\}/);
  });
});
