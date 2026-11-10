/** Per browser bewaren wat alleen deze kijker aangaat (de breedte van het paneel, of het is ingeklapt, de open tabs).
 *  Elke toegang in try/catch: in een privévenster, met geblokkeerde opslag of in een voorbeeld gooit `localStorage`,
 *  en dan werkt alles gewoon zonder. Lees pas na het mounten – de server kent geen opslag. */
export function leesOpslag<T>(sleutel: string, lees: (ruw: unknown) => T | undefined): T | undefined {
  try {
    const ruw = window.localStorage.getItem(sleutel);
    return ruw === null ? undefined : lees(JSON.parse(ruw));
  } catch {
    return undefined;
  }
}

export function schrijfOpslag(sleutel: string, waarde: unknown): void {
  try {
    if (waarde === undefined) window.localStorage.removeItem(sleutel);
    else window.localStorage.setItem(sleutel, JSON.stringify(waarde));
  } catch {
    /* geen opslag: dan niet bewaard */
  }
}
