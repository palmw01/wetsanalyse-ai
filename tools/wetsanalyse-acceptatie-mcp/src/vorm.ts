/**
 * Compacte vormen voor een agent (B-1, verslag E2E Rekeningafspraken 16 nov 2026). Een agent leest elk antwoord in zijn
 * context. `werkgebied_lezen` was na één annotatie van twaalf bepalingen 184k tekens; vier agents liepen daarop vast.
 * Hier staat wat een tool teruggeeft als de agent niet om alles vraagt. Pure functies, zodat ze te testen zijn.
 */

type Obj = Record<string, unknown>;

/** Het aantal tekens van een elementtekst in het overzicht; de hele tekst staat in `weergave_lezen`. */
export const TEKST_KORT = 120;

/** Wat een element in een lijst draagt: genoeg om het te vinden en te kiezen, niet om het te beoordelen. */
export function kortElement(e: Obj): Obj {
  const tekst = typeof e.tekst === "string" ? e.tekst : "";
  return {
    id: e.id,
    klasse: e.klasse,
    tekst: tekst.length > TEKST_KORT ? `${tekst.slice(0, TEKST_KORT)}…` : tekst,
    lifecycle: e.lifecycle,
    aandacht: e.aandacht,
    eigenaar_iri: e.eigenaar_iri,
  };
}

function tel(lijst: Obj[], sleutel: string): Record<string, number> {
  const uit: Record<string, number> = {};
  for (const x of lijst) {
    const k = String(x[sleutel] ?? "");
    uit[k] = (uit[k] ?? 0) + 1;
  }
  return uit;
}

/**
 * Het overzicht van de inventaris: de selecties en per bepaling, klasse en lifecycle een telling, zonder de elementen.
 * Met `bron_iri` de elementen van die bepaling in de korte vorm.
 */
export function inventarisOverzicht(inv: Obj, bronIri?: string): Obj {
  const elementen = Array.isArray(inv.elementen) ? (inv.elementen as Obj[]) : [];
  const uit: Obj = {
    selecties: inv.selecties,
    volledig: inv.volledig,
    aantal: elementen.length,
    afgewezen: Array.isArray(inv.afgewezen) ? inv.afgewezen.length : 0,
    vervangen: Array.isArray(inv.vervangen) ? inv.vervangen.length : 0,
    per_bepaling: tel(elementen, "eigenaar_iri"),
    per_klasse: tel(elementen, "klasse"),
    per_lifecycle: tel(elementen, "lifecycle"),
  };
  if (bronIri) uit.elementen = elementen.filter((e) => e.eigenaar_iri === bronIri).map(kortElement);
  return uit;
}

/** De nieuwste regels van de audit (de api geeft ze nieuwste eerst, hoogstens 100), met hoeveel er gelezen zijn: de
 *  hele audit groeit met elke handeling. */
export function auditStaart(audit: unknown, n = 15): Obj {
  const binnen = (audit as Obj | null)?.audit;
  const regels = Array.isArray(audit) ? audit : Array.isArray(binnen) ? binnen : [];
  return { gelezen: regels.length, nieuwste: regels.slice(0, n) };
}
