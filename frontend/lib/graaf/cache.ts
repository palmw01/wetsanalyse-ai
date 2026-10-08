/** De layoutcache: posities in IndexedDB, zodat de hele kennisgraaf de tweede keer direct in beeld
 *  staat. De sleutel is een hash van de structuur (knopen en relaties die de layout vormen) plus
 *  `LAYOUT_VERSIE`: dezelfde structuur geeft dezelfde layout, dus een treffer is altijd juist, en een
 *  herimport of een andere layoutcode geeft vanzelf een nieuwe sleutel.
 *
 *  Opslag is een gemak, geen voorwaarde: in een privévenster, met geblokkeerde sitedata of zonder
 *  IndexedDB (node) geeft lezen `undefined` en is bewaren een no-op. Dan wordt er gewoon gerekend. */
import { LAYOUT_VERSIE, type Posities, type Structuur } from "./layout";

const DB = "wetsanalyse-graaf";
const STORE = "layouts";
/** Hoeveel layouts er blijven staan: genoeg voor de hele graaf en een paar antwoorden. */
const BEWAAR = 8;

interface Opgeslagen {
  sleutel: string;
  ids: string[];
  xy: Float64Array;
  tijd: number;
}

export async function layoutSleutel(s: Structuur): Promise<string> {
  const knopen = s.knopen.map((k) => `${k.id}|${k.soort}`).sort();
  const relaties = s.relaties.map((r) => `${r.bron}|${r.soort}|${r.doel}`).sort();
  const tekst = JSON.stringify([LAYOUT_VERSIE, knopen, relaties]);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(tekst));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Posities als twee platte reeksen: zo gaan ze zonder kopie door `postMessage` en de opslag. */
export function naarReeksen(pos: Posities): { ids: string[]; xy: Float64Array } {
  const ids = [...pos.keys()];
  const xy = new Float64Array(ids.length * 2);
  ids.forEach((id, i) => {
    const [x, y] = pos.get(id)!;
    xy[2 * i] = x;
    xy[2 * i + 1] = y;
  });
  return { ids, xy };
}

export function uitReeksen(ids: readonly string[], xy: Float64Array): Posities {
  return new Map(ids.map((id, i) => [id, [xy[2 * i], xy[2 * i + 1]]]));
}

function open(): Promise<IDBDatabase | undefined> {
  return new Promise((klaar) => {
    try {
      if (typeof indexedDB === "undefined") return klaar(undefined);
      const verzoek = indexedDB.open(DB, 1);
      verzoek.onupgradeneeded = () => verzoek.result.createObjectStore(STORE, { keyPath: "sleutel" });
      verzoek.onsuccess = () => klaar(verzoek.result);
      verzoek.onerror = () => klaar(undefined);
      verzoek.onblocked = () => klaar(undefined);
    } catch {
      klaar(undefined);
    }
  });
}

function wacht<T>(verzoek: IDBRequest<T>): Promise<T> {
  return new Promise((klaar, faal) => {
    verzoek.onsuccess = () => klaar(verzoek.result);
    verzoek.onerror = () => faal(verzoek.error);
  });
}

export async function leesLayout(sleutel: string): Promise<Posities | undefined> {
  const db = await open();
  if (!db) return undefined;
  try {
    const rij = await wacht(db.transaction(STORE).objectStore(STORE).get(sleutel)) as Opgeslagen | undefined;
    return rij && rij.xy.length === rij.ids.length * 2 ? uitReeksen(rij.ids, rij.xy) : undefined;
  } catch {
    return undefined;
  } finally {
    db.close();
  }
}

export async function bewaarLayout(sleutel: string, pos: Posities): Promise<void> {
  const db = await open();
  if (!db) return;
  try {
    const store = db.transaction(STORE, "readwrite").objectStore(STORE);
    await wacht(store.put({ sleutel, ...naarReeksen(pos), tijd: Date.now() } satisfies Opgeslagen));
    // De oudste weg zodra er meer dan BEWAAR staan; een layout van de hele graaf is ~100 kB.
    const alle = await wacht(store.getAll()) as Opgeslagen[];
    for (const oud of alle.sort((a, b) => b.tijd - a.tijd).slice(BEWAAR)) store.delete(oud.sleutel);
  } catch {
    // Vol of geblokkeerd: de volgende keer wordt er opnieuw gerekend.
  } finally {
    db.close();
  }
}
