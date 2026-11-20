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

/** Het aantal tekens van een definitie in het begrippenoverzicht; de hele kaart staat in `begrip_lezen` met een id. */
export const DEFINITIE_KORT = 200;

function kort(tekst: unknown, n: number): string {
  const t = typeof tekst === "string" ? tekst : "";
  return t.length > n ? `${t.slice(0, n)}…` : t;
}

/**
 * Alle begrippen van een werkgebied in één overzicht (Termijnen e2e, 20 nov 2026: `begrip_lezen` zonder id was 346k
 * tekens, met `vorm=kort` nog 209k). Per begrip wat nodig is om er een te kiezen en te zien wat openstaat: naam,
 * status, revisie, een korte definitie, alternatieve termen, het aantal passages, de aandachtspunten en of het
 * NL-SBB-conform is met de meldingen zonder herhaling. De relaties als (van, type, naar); de voorstellen alleen geteld.
 */
export function begrippenOverzicht(lijst: unknown, conformiteit: unknown, samenhang: unknown): Obj {
  const begrippen = (Array.isArray((lijst as Obj | null)?.begrippen) ? (lijst as Obj).begrippen : []) as Obj[];
  const conform = (((conformiteit as Obj | null)?.begrippen ?? {}) as Record<string, Obj>);
  const sh = (samenhang ?? {}) as Obj;
  const namen = new Map(begrippen.map((b) => [String(b.id), String((b.inhoud as Obj | undefined)?.naam ?? b.naam ?? "")]));
  const relaties = (Array.isArray(sh.relaties) ? sh.relaties : []) as Obj[];
  return {
    aantal: begrippen.length,
    per_status: tel(begrippen, "status"),
    begrippen: begrippen.map((b) => {
      const inhoud = (b.inhoud ?? {}) as Obj;
      const c = conform[String(b.id)] ?? {};
      const meldingen = Array.isArray(c.meldingen) ? (c.meldingen as Obj[]) : [];
      return {
        id: b.id,
        naam: inhoud.naam ?? b.naam,
        status: b.status,
        revisie: b.revisie,
        definitie: kort(inhoud.definitie, DEFINITIE_KORT),
        alternatieve_termen: inhoud.alternatieve_termen ?? [],
        aantal_koppelingen: b.aantal_koppelingen,
        aandachtspunten: b.aandachtspunten ?? [],
        conform: c.conform ?? null,
        meldingen: [...new Set(meldingen.map((m) => `${m.ernst}: ${m.melding}`))],
      };
    }),
    relaties: relaties.map((r) => ({
      van: namen.get(String(r.van_begrip)) ?? r.van_naam ?? r.van_begrip,
      type: r.type,
      naar: namen.get(String(r.naar_begrip)) ?? r.naar_naam ?? r.naar_begrip,
      id: r.id,
    })),
    voorstellen: Array.isArray(sh.voorstellen) ? sh.voorstellen.length : 0,
  };
}
