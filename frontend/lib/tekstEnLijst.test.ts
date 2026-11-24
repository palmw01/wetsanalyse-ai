import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  AANDEEL_MAX, AANDEEL_MIN, AANDEEL_STANDAARD, AANDEEL_STAP, SPLIT_DETAIL_BREED, TEKST_EN_LIJST_BREED, TEKST_MAX_SMAL,
  aandeelNaToets, aandeelUitPositie, begrensAandeel, leesAandeel,
} from "@/lib/tekstEnLijst";

const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");
const css = bron("app/globals.css");
const breed = css.slice(css.indexOf("@container tekst-en-lijst"));

// Melding gebruiker 23 nov 2026: vergroot stonden wettekst en kaartjes onder elkaar, de tekst geperst tot 45% en de
// kaartjes met veel witruimte. Breed genoeg nu naast elkaar; smal zoals het was.
describe("tekst en lijst", () => {
  it("gaat naast elkaar op de breedte van het blok zelf, niet van het scherm", () => {
    expect(css).toMatch(/\.tekst-en-lijst-schil \{[^}]*container-type: inline-size/);
    expect(css).toContain(`@container tekst-en-lijst (min-width: ${TEKST_EN_LIJST_BREED})`);
    expect(css).not.toMatch(/@media[^{]*\{[^}]*\.tekst-en-lijst/);
  });

  it("smal: de tekst bovenin hoogstens 45%, de lijst eronder, elk met een eigen scroll", () => {
    const smal = css.slice(css.indexOf(".tekst-en-lijst > [data-tekst-kolom]"), css.indexOf("@container tekst-en-lijst"));
    expect(smal).toMatch(new RegExp(`\\[data-tekst-kolom\\] \\{[^}]*max-height: ${TEKST_MAX_SMAL};[^}]*overflow-y: auto`));
    expect(smal).toMatch(/\[data-lijst-kolom\] \{[^}]*overflow-y: auto/);
  });

  it("breed: naast elkaar, de tekst over de volle hoogte met het grootste deel van de breedte", () => {
    expect(breed).toMatch(/\.tekst-en-lijst \{[^}]*flex-direction: row/);
    expect(breed).toMatch(new RegExp(`\\[data-tekst-kolom\\] \\{[^}]*flex: 0 0 var\\(--tekst-aandeel, ${AANDEEL_STANDAARD}%\\);[^}]*max-height: none`));
    expect(AANDEEL_STANDAARD).toBeGreaterThan(50);
  });

  it("de scheiding staat er alleen naast elkaar, en tekent zelf de lijn", () => {
    const smal = css.slice(css.indexOf(".tekst-en-lijst-schil"), css.indexOf("@container tekst-en-lijst"));
    expect(smal).toMatch(/\[data-tekst-scheiding\] \{[^}]*display: none/);
    expect(breed).toMatch(/\[data-tekst-scheiding\] \{[^}]*display: block/);
  });

  it("breed: de kaartjes compacter, zonder iets weg te laten (alleen padding en marges)", () => {
    for (const anker of ["data-review-kaart", "data-kaart-citaat", "data-kaart-meta"]) {
      const regel = breed.slice(breed.indexOf(`[${anker}]`), breed.indexOf("}", breed.indexOf(`[${anker}]`)));
      expect(regel, anker).toMatch(/padding|margin/);
      expect(regel, anker).not.toMatch(/display: none|visibility|overflow: hidden/);
    }
    const kaart = bron("components/werkplek/ReviewQueue.tsx");
    for (const anker of ["data-review-kaart", "data-kaart-citaat", "data-kaart-meta"]) expect(kaart).toContain(anker);
  });

  it("de annotatie gebruikt het in elke plek: één weergave voor paneel, vergroot en pagina", () => {
    const inhoud = bron("components/werkplek/ArtefactInhoud.tsx");
    expect(inhoud).toMatch(/<TekstEnLijst\b/);
    expect(inhoud).not.toMatch(/max-h-\[45%\]/);
    // Geen variant per plek: de layout hangt niet aan de stand van het paneel.
    expect(bron("components/ui/TekstEnLijst.tsx")).not.toMatch(/usePaneel\(|isVergroot\(|\.plek\b/);
  });
});

// Melding gebruiker 23 nov 2026: "de vensters ook handmatig kunnen schalen". De verdeling is te verslepen, met de
// pijltjes te verzetten en per browser bewaard; één scheiding voor het hele app (`components/ui/Scheiding.tsx`).
describe("de verdeling tussen tekst en lijst", () => {
  it("blijft binnen de grenzen", () => {
    expect(begrensAandeel(10)).toBe(AANDEEL_MIN);
    expect(begrensAandeel(99)).toBe(AANDEEL_MAX);
    expect(begrensAandeel(50.4)).toBe(50);
  });

  it("volgt de wijzer: de positie in het blok als deel van de breedte", () => {
    expect(aandeelUitPositie(600, 100, 1000)).toBe(50);
    expect(aandeelUitPositie(100, 100, 1000)).toBe(AANDEEL_MIN);
    expect(aandeelUitPositie(1100, 100, 1000)).toBe(AANDEEL_MAX);
    expect(aandeelUitPositie(500, 0, 0)).toBe(AANDEEL_STANDAARD);
  });

  it("de pijltjes: → maakt de tekst breder, ← smaller, Home en End naar de grenzen", () => {
    expect(aandeelNaToets(57, "ArrowRight")).toBe(57 + AANDEEL_STAP);
    expect(aandeelNaToets(57, "ArrowLeft")).toBe(57 - AANDEEL_STAP);
    expect(aandeelNaToets(AANDEEL_MAX, "ArrowRight")).toBe(AANDEEL_MAX);
    expect(aandeelNaToets(57, "Home")).toBe(AANDEEL_MIN);
    expect(aandeelNaToets(57, "End")).toBe(AANDEEL_MAX);
    expect(aandeelNaToets(57, "a")).toBeNull();
  });

  it("leest alleen een geldig bewaard getal", () => {
    expect(leesAandeel(60)).toBe(60);
    expect(leesAandeel(20)).toBeUndefined();
    expect(leesAandeel("60")).toBeUndefined();
    expect(leesAandeel(Number.NaN)).toBeUndefined();
  });

  it("één scheiding voor de app: het zijpaneel en tekst en lijst gebruiken dezelfde", () => {
    expect(bron("components/ui/Zijpaneel.tsx")).toMatch(/<Scheiding\b/);
    expect(bron("components/ui/TekstEnLijst.tsx")).toMatch(/<Scheiding\b/);
    for (const pad of ["components/ui/Zijpaneel.tsx", "components/ui/TekstEnLijst.tsx"])
      expect(bron(pad), pad).not.toMatch(/role="separator"|setPointerCapture/);
  });

  it("Over deze bepaling is één blok: onder de annotatie en in het bronvenster", () => {
    expect(bron("components/annotaties/NodeAnnotatiePaneel.tsx")).toMatch(/<OverDezeBepaling\b/);
    expect(bron("components/wettekst/BronVenster.tsx")).toMatch(/<OverDezeBepaling\b/);
    expect(bron("components/wettekst/BronVenster.tsx")).not.toMatch(/titel="Over deze bepaling"/);
  });
});

// Melding gebruiker 23 nov 2026: begrip, regel en annotatie in lijn. Een object met een zijkolom (`SplitDetail`) kiest net
// als tekst en lijst op de breedte van het blok, en begrip en regel gebruiken het op elke plek.
describe("een object met een zijkolom", () => {
  it("gaat naast elkaar op de breedte van het blok, niet van het scherm", () => {
    expect(css).toMatch(/\.split-detail-schil \{[^}]*container-type: inline-size/);
    expect(css).toContain(`@container split-detail (min-width: ${SPLIT_DETAIL_BREED})`);
    expect(bron("components/ui/Pagina.tsx")).not.toMatch(/lg:grid-cols-\[minmax\(0,1fr\)_20rem\]/);
  });

  it("begrip en regel: dezelfde indeling op de pagina, in het paneel en vergroot", () => {
    const regel = bron("components/werkgebieden/RegelInhoud.tsx");
    expect(regel).toMatch(/<SplitDetail hoofd=\{hoofd\} zij=\{zij\} \/>/);
    expect(regel).not.toMatch(/weergave === "pagina" \? <SplitDetail/);
    const begrip = bron("components/werkgebieden/BegripInhoud.tsx");
    expect(begrip.match(/<SplitDetail\b/g)?.length).toBe(3);
  });
});
