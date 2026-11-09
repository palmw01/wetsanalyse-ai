import { describe, expect, it } from "vitest";
import { codepointOffset, momentopnameOpslag, segmentAnker,
  nodeLink, nodeError, type NodeWeergave } from "./annotatieNode";

describe("canonieke bronnode-annotaties", () => {
  it("maakt een gestructureerd revisieconflict handelbaar en bewaart laagmeldingen", async () => {
    const conflict = await nodeError(new Response(JSON.stringify({ detail: { fout: "revisie_conflict", revisie: 2 } }), { status: 412 }));
    expect(conflict.message).toContain("intussen gewijzigd");
    expect(conflict.message).toContain("Laad opnieuw");
    const locked = await nodeError(new Response(JSON.stringify({ detail: "Heropen de laag voordat je haar wijzigt." }), { status: 409 }));
    expect(locked.message).toBe("Heropen de laag voordat je haar wijzigt.");
  });
  it("toont de melding van een gestructureerde fout in plaats van de kale status", async () => {
    const fout = await nodeError(new Response(JSON.stringify({ detail: { reden: "slot", melding: "Deze laag is afgerond." } }), { status: 409 }));
    expect(fout.message).toBe("Deze laag is afgerond.");
  });
  it("valt zonder tekst van de server terug op een eigen melding", async () => {
    const fout = await nodeError(new Response("", { status: 500 }));
    expect(fout.message).toBe("Verzoek mislukt (500).");
  });
  it("vertaalt DOM UTF-16 naar lokale Unicode posities zonder siblingtekst", () => {
    const segment = { bron_iri: "urn:lid2", type: "Lid", label: "Lid 2", tekst: "A😀 café", bron_hash: "sha256", volgorde: 2 };
    expect(codepointOffset(segment.tekst, 3)).toBe(2);
    expect(segmentAnker(segment, 1, 3)).toEqual({ bron_iri: "urn:lid2", start: 1, eind: 2, tekst: "😀", bron_hash: "sha256" });
    expect(segmentAnker(segment, 4, 8).tekst).toBe("café");
  });
  it("bewaart node en bronversie in deelbare links", () => {
    const url = new URL(nodeLink({ bron_iri: "urn:lid:1/a", snapshot_id: "v2" }), "http://localhost");
    expect(url.pathname).toBe("/annotaties/node");
    expect(url.searchParams.get("bron_iri")).toBe("urn:lid:1/a");
    expect(url.searchParams.get("snapshot_id")).toBe("v2");
  });
});
describe("momentopnameOpslag", () => {
  const weergave = { doel: { bron_iri: "urn:x" } } as unknown as NodeWeergave;

  it("geeft de opname terug en weigert elke wijziging", async () => {
    const o = momentopnameOpslag(weergave);
    expect(await o.weergave({ bron_iri: "urn:x" })).toBe(weergave);
    expect(o.levend).toBe(false);
    await expect(o.beslis("e1", {})).rejects.toThrow(/alleen te lezen/);
    await expect(o.verwijder({})).rejects.toThrow(/alleen te lezen/);
  });
});
