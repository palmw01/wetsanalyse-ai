import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SamenhangKnoop, SamenhangRelatie } from "@/lib/samenhang";

import { berekenLayout, structuurVan, type Posities } from "./layout";
import { bouwModel, type GraafBron } from "./model";
import type { LayoutBericht, LayoutVerzoek } from "./rekenaar";

// De rekenaar is de enige ingang van de UI naar de layout (`layoutVoor`): cache of worker, met voortgang en afbreken.
// `graaf.test.ts` toetst de layout zelf; hier het protocol met de worker en de cache, die in node niet bestaan:
// een nep-worker die het échte workerscript draait, en een cache die we in de hand hebben.

const cache = vi.hoisted(() => ({ bewaard: undefined as Posities | undefined, bewaar: vi.fn() }));
vi.mock("./cache", async (orig) => ({
  ...(await orig<typeof import("./cache")>()),
  leesLayout: async () => cache.bewaard,
  bewaarLayout: cache.bewaar,
}));

const { layoutVoor } = await import("./rekenaar");

const IW = "urn:bwb:BWBR0004770", A9 = `${IW}:artikel:9`, L1 = `${A9}:lid:1`, L2 = `${A9}:lid:2`;
const knoop = (id: string, soort: SamenhangKnoop["soort"], label: string): SamenhangKnoop =>
  ({ id, soort, label, tekst: "", klasse: "", lifecycle: "", element_id: "", bwb_id: "BWBR0004770", artikel: "9", lid: "", rand: false });
const bevat = (bron: string, doel: string): SamenhangRelatie => ({ bron, doel, soort: "bevat", anker_tekst: "", groep: "structuur" });
const BRON: GraafBron = {
  knopen: [knoop(IW, "regeling", "Invorderingswet 1990"), knoop(A9, "artikel", "Artikel 9"), knoop(L1, "lid", "Lid 1")],
  relaties: [bevat(IW, A9), bevat(A9, L1)],
};

/** Een worker zoals de browser hem maakt, maar in dit proces: `gedrag` bepaalt wat hij terugstuurt. */
type Gedrag = "echt" | "fout" | "stil" | "kapot";
let gedrag: Gedrag = "echt";
const workers: NepWorker[] = [];
class NepWorker {
  onmessage: ((e: MessageEvent<LayoutBericht>) => void) | null = null;
  onerror: ((e: { message: string }) => void) | null = null;
  beëindigd = false;
  verzoek?: LayoutVerzoek;
  constructor(public url: URL) { workers.push(this); }
  terminate() { this.beëindigd = true; }
  postMessage(verzoek: LayoutVerzoek) {
    this.verzoek = verzoek;
    queueMicrotask(() => {
      if (gedrag === "stil") return;
      if (gedrag === "kapot") return this.onerror?.({ message: "" });
      if (gedrag === "fout") return this.onmessage?.({ data: { soort: "fout", reden: "te groot" } } as MessageEvent<LayoutBericht>);
      this.onmessage?.({ data: { soort: "voortgang", fractie: 0.5 } } as MessageEvent<LayoutBericht>);
      const pos = berekenLayout(verzoek.structuur);
      const ids = [...pos.keys()];
      const xy = new Float64Array(ids.flatMap((id) => pos.get(id)!));
      this.onmessage?.({ data: { soort: "klaar", ids, xy } } as MessageEvent<LayoutBericht>);
    });
  }
}

beforeEach(() => {
  gedrag = "echt";
  workers.length = 0;
  cache.bewaard = undefined;
  cache.bewaar.mockReset();
  vi.stubGlobal("Worker", NepWorker);
});
afterEach(() => vi.unstubAllGlobals());

describe("layoutVoor", () => {
  it("rekent in een worker met voortgang, bewaart de uitkomst en ruimt de worker op", async () => {
    const voortgang = vi.fn();
    const { posities, uitCache } = await layoutVoor(bouwModel([BRON]), { opVoortgang: voortgang });
    expect(uitCache).toBe(false);
    expect([...posities.keys()].sort()).toEqual([A9, IW, L1].sort());
    expect(voortgang).toHaveBeenCalledWith(0.5);
    expect(workers).toHaveLength(1);
    expect(workers[0].url.pathname).toMatch(/layout\.worker\.ts$/);
    expect(workers[0].beëindigd).toBe(true);
    expect(cache.bewaar).toHaveBeenCalledTimes(1);
  });

  it("een treffer in de cache rekent niets", async () => {
    cache.bewaard = berekenLayout(structuurVan(bouwModel([BRON])));
    const { uitCache } = await layoutVoor(bouwModel([BRON]));
    expect(uitCache).toBe(true);
    expect(workers).toHaveLength(0);
  });

  it("een cache die niet alle knopen kent, telt niet als treffer", async () => {
    cache.bewaard = new Map([[IW, [0, 0]]]);
    const { uitCache } = await layoutVoor(bouwModel([BRON]));
    expect(uitCache).toBe(false);
    expect(workers).toHaveLength(1);
  });

  it("bijladen: alleen nieuwe wettekst wordt geplaatst, de bestaande knopen gaan mee als vast", async () => {
    const vast = berekenLayout(structuurVan(bouwModel([BRON])));
    const groter: GraafBron = { knopen: [...BRON.knopen, knoop(L2, "lid", "Lid 2")], relaties: [...BRON.relaties, bevat(A9, L2)] };
    const { uitCache } = await layoutVoor(bouwModel([groter]), { vast });
    expect(uitCache).toBe(false);
    expect(workers[0].verzoek?.vast?.ids.sort()).toEqual([...vast.keys()].sort());
    // Een uitkomst die van de vorige kaart afhangt, gaat de cache niet in.
    expect(cache.bewaar).not.toHaveBeenCalled();
  });

  it("een sterrenstel rekent niets en gaat niet langs de cache", async () => {
    const { posities, uitCache } = await layoutVoor(bouwModel([BRON]), { sterrenstel: [A9] });
    expect(uitCache).toBe(true);
    expect(posities.has(A9)).toBe(true);
    expect(workers).toHaveLength(0);
  });

  it("een fout uit de worker wordt een leesbare fout, en de worker gaat weg", async () => {
    gedrag = "fout";
    await expect(layoutVoor(bouwModel([BRON]))).rejects.toThrow("De layout van de graaf kon niet worden berekend: te groot");
    expect(workers[0].beëindigd).toBe(true);
  });

  it("een worker die niet start, zegt dat", async () => {
    gedrag = "kapot";
    await expect(layoutVoor(bouwModel([BRON]))).rejects.toThrow(/de rekenaar startte niet/);
  });

  it("afbreken tijdens het rekenen beëindigt de worker en geeft een AbortError", async () => {
    gedrag = "stil";
    const afbreken = new AbortController();
    const belofte = layoutVoor(bouwModel([BRON]), { signal: afbreken.signal });
    await vi.waitFor(() => expect(workers).toHaveLength(1));
    afbreken.abort();
    await expect(belofte).rejects.toMatchObject({ name: "AbortError" });
    expect(workers[0].beëindigd).toBe(true);
  });

  it("al afgebroken: geen worker", async () => {
    const afbreken = new AbortController();
    afbreken.abort();
    await expect(layoutVoor(bouwModel([BRON]), { signal: afbreken.signal })).rejects.toMatchObject({ name: "AbortError" });
    expect(workers).toHaveLength(0);
  });
});

describe("layout.worker.ts – het protocol aan de andere kant", () => {
  let berichten: { b: LayoutBericht; overdracht?: Transferable[] }[] = [];
  let zelf: { postMessage: (b: LayoutBericht, o?: Transferable[]) => void; onmessage?: (e: { data: LayoutVerzoek }) => void };

  beforeEach(async () => {
    berichten = [];
    zelf = { postMessage: (b, overdracht) => berichten.push({ b, overdracht }) };
    vi.stubGlobal("self", zelf);
    vi.resetModules();
    await import("./layout.worker");
  });

  it("stuurt voortgang (hoogstens per procent) en dan de posities, met de buffer als overdracht", () => {
    const structuur = structuurVan(bouwModel([BRON]));
    zelf.onmessage!({ data: { structuur } });
    const klaar = berichten.at(-1)!;
    expect(klaar.b.soort).toBe("klaar");
    if (klaar.b.soort !== "klaar") return;
    expect(klaar.b.ids.sort()).toEqual([A9, IW, L1].sort());
    expect(klaar.overdracht).toEqual([klaar.b.xy.buffer]);
    const procenten = berichten.filter((x) => x.b.soort === "voortgang").map((x) => Math.floor((x.b as { fractie: number }).fractie * 100));
    expect(new Set(procenten).size).toBe(procenten.length);
  });

  it("houdt vaste posities vast", () => {
    const structuur = structuurVan(bouwModel([BRON]));
    const xy = new Float64Array([123, 456]);
    zelf.onmessage!({ data: { structuur, vast: { ids: [IW], xy } } });
    const klaar = berichten.at(-1)!.b;
    if (klaar.soort !== "klaar") throw new Error("geen uitkomst");
    const i = klaar.ids.indexOf(IW);
    expect([klaar.xy[2 * i], klaar.xy[2 * i + 1]]).toEqual([123, 456]);
  });

  it("een fout tijdens het rekenen wordt een foutbericht, geen dode worker", () => {
    zelf.onmessage!({ data: { structuur: null as unknown as LayoutVerzoek["structuur"] } });
    expect(berichten.at(-1)!.b.soort).toBe("fout");
  });
});
