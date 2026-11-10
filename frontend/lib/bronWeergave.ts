/** De pure kern van de wettekstweergave (het bronvenster, PR 2): welke markeringen er in de tekst staan, en de cache van
 *  de weergaven per bepaling. Getest in `bronWeergave.test.ts`; `useBron.ts` is de React-schil eromheen. */
import type { NodeElement, NodeWeergave } from "@/lib/annotatieNode";

/** De markeringen die in de lopende tekst horen: niet verouderd (de tekst van het lid veranderde) en niet verworpen. Eén
 *  regel voor elke plek die wettekst toont. */
export function actueleElementen(view: Pick<NodeWeergave, "elementen"> | null | undefined): NodeElement[] {
  return (view?.elementen ?? []).filter((e) => !e.verouderd && e.lifecycle !== "rejected");
}

/** Een cache van weergaven per bepaling: de laatste geslaagde lezing bewaard, een lopende lezing gedeeld. Een nieuwe
 *  lezing vraagt altijd de server (de markeringen kunnen intussen veranderd zijn); wat bewaard is, toont meteen. */
export function maakWeergaveCache<T>(haal: (iri: string) => Promise<T>, max = 64) {
  const bewaard = new Map<string, T>();
  const lopend = new Map<string, Promise<T>>();
  return {
    bewaard: (iri: string): T | undefined => bewaard.get(iri),
    haal(iri: string): Promise<T> {
      const al = lopend.get(iri);
      if (al) return al;
      const p = haal(iri).then((w) => {
        bewaard.delete(iri);
        if (bewaard.size >= max) bewaard.delete(bewaard.keys().next().value as string);
        bewaard.set(iri, w);
        return w;
      }).finally(() => lopend.delete(iri));
      lopend.set(iri, p);
      return p;
    },
    vergeet(iri?: string) { if (iri) bewaard.delete(iri); else bewaard.clear(); },
  };
}
