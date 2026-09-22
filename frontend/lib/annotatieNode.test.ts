import { describe, expect, it } from "vitest";
import { codepointOffset, segmentAnker, mergeToolExecution, parseToolExecution, elementVergrendeld,
  nodeLink, nodeError, type NodeWeergave, type NodeElement, type ToolExecution } from "./annotatieNode";

describe("canonieke bronnode-annotaties", () => {
  it("maakt een gestructureerd revisieconflict handelbaar en bewaart laagmeldingen", async () => {
    const conflict = await nodeError(new Response(JSON.stringify({ detail: { fout: "revisie_conflict", revisie: 2 } }), { status: 412 }));
    expect(conflict.message).toContain("intussen gewijzigd");
    expect(conflict.message).toContain("Laad opnieuw");
    const locked = await nodeError(new Response(JSON.stringify({ detail: "Heropen de laag voordat je haar wijzigt." }), { status: 409 }));
    expect(locked.message).toBe("Heropen de laag voordat je haar wijzigt.");
  });
  it("vertaalt DOM UTF-16 naar lokale Unicode posities zonder siblingtekst", () => {
    const segment = { bron_iri: "urn:lid2", type: "Lid", label: "Lid 2", tekst: "A😀 café", bron_hash: "sha256", volgorde: 2 };
    expect(codepointOffset(segment.tekst, 3)).toBe(2);
    expect(segmentAnker(segment, 1, 3)).toEqual({ bron_iri: "urn:lid2", start: 1, eind: 2, tekst: "😀", bron_hash: "sha256" });
    expect(segmentAnker(segment, 4, 8).tekst).toBe("café");
  });
  it("blokkeert uitsluitend de eigenaarlaag van een element", () => {
    const view = { lagen: [{ bron_iri: "urn:lid1", status: "geaccordeerd" }, { bron_iri: "urn:lid2", status: "in_review" }] } as NodeWeergave;
    expect(elementVergrendeld(view, { eigenaar_iri: "urn:lid1" } as NodeElement)).toBe(true);
    expect(elementVergrendeld(view, { eigenaar_iri: "urn:lid2" } as NodeElement)).toBe(false);
  });
  it("bewaart node en bronversie in deelbare links", () => {
    const url = new URL(nodeLink({ bron_iri: "urn:lid:1/a", snapshot_id: "v2" }), "http://localhost");
    expect(url.pathname).toBe("/annotaties/node");
    expect(url.searchParams.get("bron_iri")).toBe("urn:lid:1/a");
    expect(url.searchParams.get("snapshot_id")).toBe("v2");
  });
});
describe("werkelijk uitgevoerd toolspoor", () => {
  const started: ToolExecution = { run_id: "run", call_id: "call", tool: "search_annotaties", phase: "started" };
  it("ontdubbelt replay en draait afgeronde calls niet terug", () => {
    const done = { ...started, phase: "completed" as const, aantal: 4 };
    const events = mergeToolExecution(mergeToolExecution([started], done), started);
    expect(events).toEqual([done]);
    expect(mergeToolExecution(events, done)).toEqual([done]);
    expect(mergeToolExecution(events, { ...done, run_id: "andere-run" })).toHaveLength(2);
  });
  it("normaliseert wire phases en behoudt expliciete storing", () => {
    expect(parseToolExecution({ ...started, phase: "start" })?.phase).toBe("started");
    expect(parseToolExecution({ ...started, phase: "end", status: "unavailable" })?.phase).toBe("failed");
    expect(parseToolExecution({ tool: "verzonnen" })).toBeUndefined();
  });
});
