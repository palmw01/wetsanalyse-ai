/** Een cache voor de accountstatus per gebruiker (`auth.ts`), los van Auth.js zodat vitest hem kan toetsen.
 *
 *  - Een bekende status (`actief`, `ingetrokken`) geldt `geldigMs` – de herverificatiegrens.
 *  - "onbekend" (de api antwoordde niet) geldt kort, `onbekendMs`. Zonder die regel wachtte tijdens een
 *    hapering of koude start van de api élk BFF-verzoek eerst tot 10 s op `/v1/auth/me`, en pas daarna
 *    op de proxy: één trage api maakte elk scherm dubbel zo traag (acceptatie, 28 okt 2026).
 *  - Aanroepen die tegelijk lopen, delen één verzoek: een pagina die vijf routes tegelijk opent, vraagt
 *    de status één keer.
 */
export interface StatusCacheOpties {
  geldigMs: number;
  onbekendMs: number;
  /** Boven dit aantal ruimt hij verlopen regels op. */
  max?: number;
  nu?: () => number;
}

export function maakStatusCache<S extends { status: string }>(
  haal: (id: string) => Promise<S>,
  { geldigMs, onbekendMs, max = 500, nu = Date.now }: StatusCacheOpties,
): (id: string) => Promise<S> {
  const cache = new Map<string, { status: S; tot: number }>();
  const lopend = new Map<string, Promise<S>>();

  return async (id) => {
    const t = nu();
    const bekend = cache.get(id);
    if (bekend && bekend.tot > t) return bekend.status;
    const al = lopend.get(id);
    if (al) return al;
    const p = haal(id)
      .then((status) => {
        const klaar = nu();
        if (cache.size > max) for (const [k, v] of cache) if (v.tot <= klaar) cache.delete(k);
        cache.set(id, { status, tot: klaar + (status.status === "onbekend" ? onbekendMs : geldigMs) });
        return status;
      })
      .finally(() => lopend.delete(id));
    lopend.set(id, p);
    return p;
  };
}
