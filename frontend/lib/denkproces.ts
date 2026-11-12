// Het denkproces van een beurt: de stappen (statusregels) en de tussentekst van het model, nooit het antwoord.
//
// Dit is de enige plek in de werkplek die een denkproces opbouwt; `stroomReducer` (de beurt) en `verwerkReeksEvent`
// (een reeks, per onderdeel) roepen hem aan, en `app/eenDenkproces.test.ts` houdt dat zo. graph-qa bouwt het bewaarde
// bericht met dezelfde regel (`agent/narratie.py`, `denk_bij`), en `tools/graph-qa/tests/data/denkproces-vectoren.json`
// houdt de twee gelijk: live en na herladen staat er hetzelfde. Een `token` (het antwoord) heeft hier geen ingang.

/** Er viel narratie weg (`gat`): het denkproces zegt het, in plaats van stil korter te zijn. */
export const GAT_IN_DENK = "· (een deel van het spoor is niet bewaard)";

/** Een `reason` direct na een statusregel begint op een eigen regel: de eerste ronde van het model draagt geen
 *  alinea-scheiding, en dan plakte "· Lex · zoekt in de kennisgraaf" aan "Ik zoek …". Gelijk aan
 *  `narratie.met_regelgrens` in graph-qa. */
export function metRegelgrens(denk: string, tekst: string): string {
  const laatste = denk.slice(denk.lastIndexOf("\n") + 1);
  return tekst && laatste.startsWith("· ") && !tekst.startsWith("\n") ? "\n" + tekst : tekst;
}

export type DenkSoort = "status" | "reason" | "gat";

/** Het denkproces na één event: een statusregel op een eigen regel, narratie die doorloopt, een gat als regel. */
export function denkBij(denk: string, soort: DenkSoort, tekst = ""): string {
  switch (soort) {
    case "status": return denk + (denk ? "\n" : "") + "· " + tekst;
    case "reason": return denk + metRegelgrens(denk, tekst);
    case "gat": return denk + (denk ? "\n" : "") + GAT_IN_DENK;
  }
}
