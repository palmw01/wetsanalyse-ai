/** De layout van een model ophalen: uit de cache, of gerekend in een worker met voortgang. Dit is de
 *  enige ingang die de UI gebruikt; `layout.ts` blijft puur en testbaar. */
import { bewaarLayout, layoutSleutel, leesLayout, naarReeksen, uitReeksen } from "./cache";
import { plaatsAnnotaties, structuurVan, type Posities, type Structuur } from "./layout";
import type { GraafModel } from "./model";

export interface LayoutVerzoek {
  structuur: Structuur;
  vast?: { ids: string[]; xy: Float64Array };
}
export type LayoutBericht =
  | { soort: "voortgang"; fractie: number }
  | { soort: "klaar"; ids: string[]; xy: Float64Array }
  | { soort: "fout"; reden: string };

function rekenInWorker(verzoek: LayoutVerzoek, opVoortgang?: (f: number) => void, signal?: AbortSignal): Promise<Posities> {
  return new Promise((klaar, faal) => {
    if (signal?.aborted) return faal(new DOMException("Afgebroken", "AbortError"));
    // De vorm `new Worker(new URL(…, import.meta.url))` is wat de bundler herkent en meeneemt.
    const worker = new Worker(new URL("./layout.worker.ts", import.meta.url), { type: "module" });
    const stop = () => {
      worker.terminate();
      faal(new DOMException("Afgebroken", "AbortError"));
    };
    signal?.addEventListener("abort", stop, { once: true });
    const einde = () => {
      signal?.removeEventListener("abort", stop);
      worker.terminate();
    };
    worker.onmessage = (e: MessageEvent<LayoutBericht>) => {
      const b = e.data;
      if (b.soort === "voortgang") opVoortgang?.(b.fractie);
      else if (b.soort === "klaar") {
        einde();
        klaar(uitReeksen(b.ids, b.xy));
      } else {
        einde();
        faal(new Error(`De layout van de graaf kon niet worden berekend: ${b.reden}`));
      }
    };
    worker.onerror = (e) => {
      einde();
      faal(new Error(`De layout van de graaf kon niet worden berekend: ${e.message || "de rekenaar startte niet"}`));
    };
    worker.postMessage(verzoek, verzoek.vast ? [verzoek.vast.xy.buffer] : []);
  });
}

export interface LayoutResultaat {
  posities: Posities;
  /** Uit de cache: er was niets te rekenen (de UI toont dan geen laadbalk). */
  uitCache: boolean;
}

/** Posities voor alle knopen van het model.
 *
 *  - Zonder `vast` (een nieuwe kaart): uit de cache als de structuur bekend is, anders gerekend en
 *    bewaard.
 *  - Met `vast` (bijladen in een bestaande kaart): bestaande knopen blijven staan, alleen nieuwe worden
 *    geplaatst. Niets nieuw in de wettekst – alleen annotaties veranderd – dan wordt er niets gerekend.
 *    Zo'n uitkomst hangt af van wat er eerder lag en gaat de cache niet in.
 *
 *  Markeringen en klassen worden daarna afgeleid (`plaatsAnnotaties`). */
export async function layoutVoor(g: GraafModel, opties: { vast?: Posities; opVoortgang?: (f: number) => void; signal?: AbortSignal } = {}): Promise<LayoutResultaat> {
  const structuur = structuurVan(g);
  const { vast } = opties;
  if (vast) {
    const nieuw = structuur.knopen.some((k) => !vast.has(k.id));
    const posities = nieuw
      ? await rekenInWorker({ structuur, vast: naarReeksen(new Map(structuur.knopen.filter((k) => vast.has(k.id)).map((k) => [k.id, vast.get(k.id)!]))) }, opties.opVoortgang, opties.signal)
      : new Map(structuur.knopen.map((k) => [k.id, vast.get(k.id)!]));
    return { posities: plaatsAnnotaties(g, posities), uitCache: !nieuw };
  }
  const sleutel = await layoutSleutel(structuur);
  const bewaard = await leesLayout(sleutel);
  if (bewaard && structuur.knopen.every((k) => bewaard.has(k.id))) {
    return { posities: plaatsAnnotaties(g, bewaard), uitCache: true };
  }
  const posities = await rekenInWorker({ structuur }, opties.opVoortgang, opties.signal);
  void bewaarLayout(sleutel, posities);
  return { posities: plaatsAnnotaties(g, posities), uitCache: false };
}
