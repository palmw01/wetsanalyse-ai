/** De hele kennisgraaf ophalen (`GET /v1/annotatie/graaf` via de v2-proxy). */
import { nodeRequest } from "@/lib/annotatieNode";
import type { KennisgraafAntwoord } from "./model";

/** Alle regelingen, of een keuze (BWB-id's). Het antwoord is ~2 MB JSON en komt gecomprimeerd. */
export function haalKennisgraaf(bwbIds: readonly string[] = []): Promise<KennisgraafAntwoord> {
  const params = new URLSearchParams(bwbIds.map((b) => ["bwb_id", b]));
  return nodeRequest(`graaf${bwbIds.length ? `?${params}` : ""}`);
}
