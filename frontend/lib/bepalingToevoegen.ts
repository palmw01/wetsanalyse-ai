// *Bepaling toevoegen* (3 nov 2026): één onderdeel voor het gesprek en de tab Bronnen. De jurist kiest een
// regeling, typt een vindplaats en kiest uit wat de graaf echt kent; daarna koppelt hij haar aan een deelvraag (of
// aan het hele werkgebied). Hier de zuivere rekenkern: welke invoer naar welke route gaat, en welke fout welke zin
// wordt. Het onderdeel zelf staat in `components/werkgebieden/BepalingToevoegen.tsx`.

import { foutTekst, isApiError } from "./api";
import type { BepalingTreffer, BepalingZoekAntwoord, BronRol, BronselectieInvoer } from "./types";

/** De keuze "geen deelvraag": opnemen in het werkgebied, zonder koppeling. */
export const HEEL_WERKGEBIED = "";

export const MAX_REDEN = 2000;

/** Wat er verstuurd wordt: altijd een bron-IRI uit de boom (geen vrije tekst die de api moet raden). */
export function invoerVoor(t: BepalingTreffer, rol: BronRol, reden: string, revisie: number): BronselectieInvoer {
  return { bron_iri: t.bron_iri, rol, reden: reden.trim().slice(0, MAX_REDEN), verwachte_revisie: revisie, bereik: "onderliggend" };
}

/** Hoe de getypte invoer gelezen is, in woorden: "artikel 9, lid 7". Leeg als er geen nummer in stond. */
export function gelezenZin(g: BepalingZoekAntwoord["gelezen"]): string {
  if (!g.artikel) return "";
  return [`artikel ${g.artikel}`, g.lid && `lid ${g.lid}`, g.onderdeel && `onderdeel ${g.onderdeel}`]
    .filter(Boolean).join(", ");
}

/** Wat de jurist ziet als er niets gevonden is: wat er gelezen is en waar er gezocht is – nooit alleen "niets". */
export function geenTrefferZin(regeling: string, g: BepalingZoekAntwoord["gelezen"]): string {
  const wat = gelezenZin(g);
  return wat
    ? `${wat[0].toUpperCase()}${wat.slice(1)} staat niet in ${regeling}. Controleer het nummer; een beleidsregel kent geen leden maar subdivisies (9.2).`
    : `Geen artikel in ${regeling} met “${g.tekst}” in de kop. Typ een nummer, zoals 9 lid 2 of 21.1.`;
}

export type ToevoegFout =
  | { soort: "al_opgenomen"; tekst: string }
  | { soort: "uitgesloten"; tekst: string }
  | { soort: "keuze"; tekst: string; opties: { bron_iri: string; label: string; fragment?: string }[] }
  | { soort: "invoer"; tekst: string }
  | { soort: "graaf"; tekst: string }
  | { soort: "conflict"; tekst: string }
  | { soort: "anders"; tekst: string };

/** Een mislukte toevoeging als iets wat het formulier kan tonen, bij het veld waar het over gaat. */
export function toevoegFout(e: unknown): ToevoegFout {
  if (!isApiError(e)) return { soort: "anders", tekst: foutTekst(e, "De bepaling is niet toegevoegd.") };
  const data = (e.data ?? {}) as Record<string, unknown>;
  if (e.status === 412) {
    return { soort: "conflict", tekst: "Iemand anders wijzigde het werkgebied net. Probeer het nog eens: je keuze staat er nog." };
  }
  if (e.status === 409 && data.fout === "al_opgenomen") {
    return { soort: "al_opgenomen",
      tekst: "Deze bepaling staat al in het werkgebied, met een andere rol. Pas die rol aan bij de bron, of koppel haar aan een deelvraag." };
  }
  if (e.status === 409 && data.status === "uitgesloten") {
    return { soort: "uitgesloten", tekst: "Deze bepaling is voor het hele werkgebied uitgesloten. Heropen haar eerst bij de bronnen." };
  }
  if (e.status === 422 && Array.isArray(data.opties)) {
    const opties = (data.opties as Record<string, unknown>[])
      .filter((o) => typeof o?.bron_iri === "string")
      .map((o) => ({ bron_iri: String(o.bron_iri), label: String(o.label ?? o.bron_iri),
        fragment: typeof o.fragment === "string" ? o.fragment : undefined }));
    return { soort: "keuze", tekst: e.detail, opties };
  }
  if (e.status === 422 || e.status === 404) return { soort: "invoer", tekst: e.detail };
  if (e.status === 503 || e.status === 502 || e.status === 504) {
    return { soort: "graaf", tekst: "De kennisgraaf is tijdelijk niet bereikbaar. Probeer het zo nog eens." };
  }
  return { soort: "anders", tekst: foutTekst(e, "De bepaling is niet toegevoegd.") };
}

/** De bevestiging na toevoegen, in de woorden van wat er gebeurde. */
export function toegevoegdZin(t: BepalingTreffer, deelvraagNr: number | null): string {
  return deelvraagNr ? `${t.vindplaats} is toegevoegd bij deelvraag ${deelvraagNr}.` : `${t.vindplaats} is opgenomen in het werkgebied.`;
}
