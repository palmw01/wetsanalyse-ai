import { describe, expect, it } from "vitest";

import { geenTrefferZin, gelezenZin, invoerVoor, toegevoegdZin, toevoegFout } from "./bepalingToevoegen";
import type { BepalingTreffer } from "./types";

const T: BepalingTreffer = {
  bron_iri: "urn:bwb:BWBR0024096:artikel:9:o:d", soort: "onderdeel", vindplaats: "Artikel 9.2, onderdeel d",
  titel: "", fragment: "de dagtekening van het aanslagbiljet;",
};
const fout = (status: number, detail: string, data?: Record<string, unknown>) => ({ status, detail, data });

describe("bepaling toevoegen", () => {
  it("verstuurt altijd de bron-IRI uit de boom, de reden ingekort en optioneel", () => {
    expect(invoerVoor(T, "context", "  waarom  ", 4)).toEqual({
      bron_iri: T.bron_iri, rol: "context", reden: "waarom", verwachte_revisie: 4, bereik: "onderliggend",
    });
    expect(invoerVoor(T, "analyseren", "x".repeat(3000), 1).reden).toHaveLength(2000);
  });

  it("zegt wat er gelezen is als er niets gevonden is", () => {
    expect(gelezenZin({ artikel: "9", lid: "7", onderdeel: "", tekst: "" })).toBe("artikel 9, lid 7");
    expect(geenTrefferZin("Invorderingswet 1990", { artikel: "9", lid: "7", onderdeel: "", tekst: "" }))
      .toMatch(/^Artikel 9, lid 7 staat niet in Invorderingswet 1990\./);
    expect(geenTrefferZin("Leidraad Invordering 2008", { artikel: "", lid: "", onderdeel: "", tekst: "bodem" }))
      .toMatch(/“bodem”/);
  });

  it("vertaalt elke fout naar een zin bij het formulier", () => {
    expect(toevoegFout(fout(412, "x", { fout: "revisie_conflict" })).soort).toBe("conflict");
    expect(toevoegFout(fout(409, "x", { fout: "al_opgenomen" })).soort).toBe("al_opgenomen");
    expect(toevoegFout(fout(409, "Uitgesloten", { status: "uitgesloten" })).soort).toBe("uitgesloten");
    const keuze = toevoegFout(fout(422, "Het gevraagde lid 7 bestaat niet", {
      melding: "Het gevraagde lid 7 bestaat niet", opties: [{ bron_iri: "urn:bwb:B:artikel:9:lid:1", label: "Lid 1" }, { nope: 1 }],
    }));
    expect(keuze).toEqual({ soort: "keuze", tekst: "Het gevraagde lid 7 bestaat niet",
      opties: [{ bron_iri: "urn:bwb:B:artikel:9:lid:1", label: "Lid 1", fragment: undefined }] });
    expect(toevoegFout(fout(422, "Bepaling niet gevonden")).soort).toBe("invoer");
    expect(toevoegFout(fout(503, "weg")).soort).toBe("graaf");
    expect(toevoegFout(new Error("x")).soort).toBe("anders");
  });

  it("bevestigt in de woorden van wat er gebeurde", () => {
    expect(toegevoegdZin(T, 2)).toBe("Artikel 9.2, onderdeel d is toegevoegd bij deelvraag 2.");
    expect(toegevoegdZin(T, null)).toBe("Artikel 9.2, onderdeel d is opgenomen in het werkgebied.");
  });
});
