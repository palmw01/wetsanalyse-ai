/** Wat je in de ketting ziet, in woorden: één zin, en daarachter wat er bewust niet staat. Puur, zodat elke
 *  uitkomst getest is: een graaf die niet zegt wat hij toont, is ruis. */
import type { Samenhang } from "@/lib/samenhang";

const aantal = (n: number, een: string, meer: string) => `${n} ${n === 1 ? een : meer}`;

function naamVan(k: Samenhang, id: string): string {
  const knoop = k.knopen.find((x) => x.id === id);
  if (knoop?.vindplaats) return knoop.vindplaats;
  // Een oudere import heeft geen vindplaats, en "Lid 2" zegt los niets.
  if (knoop?.soort === "lid" && knoop.artikel) return `Artikel ${knoop.artikel}, lid ${knoop.lid}`;
  return knoop?.label || id;
}

/** De zin boven de ketting. `eersteBron`: Lex noemde geen bepaling, dit is de eerste bron. */
export function ketenZin(k: Samenhang, eersteBron = false): string {
  const doelen = k.doelen ?? [];
  const regeling = k.knopen.find((x) => x.soort === "regeling")?.label ?? "de regeling";
  const markeringen = k.knopen.filter((x) => x.soort === "markering").length;
  const begrippen = k.knopen.filter((x) => x.soort === "begrip").length;
  const verwijzingen = k.relaties.filter((r) => r.soort === "verwijst_naar").length;
  const doel = doelen.length === 1 ? naamVan(k, doelen[0]) : `${doelen.length} bepalingen`;
  const inhoud = `${aantal(markeringen, "markering", "markeringen")}, ${aantal(begrippen, "begrip", "begrippen")} en ${aantal(verwijzingen, "verwijzing", "verwijzingen")}`;
  const zinnen = [`Je ziet de weg van ${regeling} naar ${doel}, met ${inhoud}. De rest van de regeling staat er niet bij.`];
  if (eersteBron) zinnen.push("Lex noemt geen bepaling; dit is de eerste bron.");
  if (k.begrippen_beschikbaar === false) zinnen.push("De begrippen zijn nu niet opgehaald.");
  else if (!begrippen) zinnen.push("Geen wettelijke definitie in de graaf bij de termen in deze bepaling.");
  const i = k.ingekort;
  const teVeel = Object.values(i?.markeringen ?? {}).reduce((s, n) => s + n, 0);
  if (teVeel) zinnen.push(`${aantal(teVeel, "markering staat", "markeringen staan")} er niet bij: te veel om te tonen.`);
  const kinderen = Object.values(i?.kinderen ?? {}).reduce((s, n) => s + n, 0);
  if (kinderen) zinnen.push(`${aantal(kinderen, "onderdeel staat", "onderdelen staan")} er niet bij: te veel om te tonen.`);
  if (i?.begrippen) zinnen.push(`${aantal(i.begrippen, "begrip staat", "begrippen staan")} er niet bij.`);
  if (i?.onzekere_verwijzingen) zinnen.push(`${aantal(i.onzekere_verwijzingen, "verwijzing met een onzeker doel staat", "verwijzingen met een onzeker doel staan")} er niet bij.`);
  return zinnen.join(" ");
}
