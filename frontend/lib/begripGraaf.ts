// De begrippen van een werkgebied in de samenhangsgraaf en de NL-SBB-conformiteit (spoor D, fase F3).
// Puur, voor vitest.
//
// Een begrip wordt een knoop `begrip:<id>`, met een lijn `duidt` naar elke markering die het draagt
// (`element:<id>`, zoals de api haar in de samenhang noemt) en een lijn per relatie tussen begrippen. Een
// relatie draagt haar zin (`relatieZin`) als ankertekst: zo staat ze in de inspector als woorden, nooit
// alleen als lijn. Wat de api voorstelt (geel) en wat vastligt, zijn verschillende soorten lijnen.

import { relatieZin } from "./begripRelaties";
import type { GraafBron } from "./graaf/model";
import type { SamenhangKnoop, SamenhangRelatie } from "./samenhang";
import type { BegripRelatie } from "./types";

/** `GET …/begrippen/samenhang` (api/app/begrippen.py). */
export interface BegripSamenhang {
  begrippen: { id: string; iri: string; naam: string; status: string; definitie: string }[];
  koppelingen: { begrip_id: string; element_id: string; rol: "duiding" | "definitie" | "context"; beoordeling: string;
    actualiteit: string }[];
  relaties: BegripRelatie[];
  voorstellen: BegripRelatie[];
}

export function isBegripSamenhang(x: unknown): x is BegripSamenhang {
  const s = x as BegripSamenhang;
  return !!s && typeof s === "object" && Array.isArray(s.begrippen) && Array.isArray(s.koppelingen)
    && Array.isArray(s.relaties) && Array.isArray(s.voorstellen);
}

export const begripKnoopId = (id: string) => `begrip:${id}`;
/** Het begrip-id achter een knoop, of `undefined` als het geen begripsknoop is. */
export const begripIdVan = (knoopId: string) => (knoopId.startsWith("begrip:") ? knoopId.slice(7) : undefined);

const ROL_ZIN: Record<BegripSamenhang["koppelingen"][number]["rol"], string> = {
  duiding: "duidt het begrip aan", definitie: "ondersteunt de definitie", context: "geeft context",
};

function knoop(b: BegripSamenhang["begrippen"][number]): SamenhangKnoop {
  return { id: begripKnoopId(b.id), soort: "begrip", label: b.naam, tekst: b.definitie, klasse: "", lifecycle: "",
    element_id: "", bwb_id: "", artikel: "", lid: "", rand: false, status: b.status };
}

/** Knopen en lijnen voor `useGraafStand` (de toevoeging). Een vervangen begrip staat er met zijn
 *  opvolging; een afgewezen koppeling niet. Een lijn naar een markering die de graaf niet geladen heeft,
 *  valt bij het bouwen van het model vanzelf weg (`bouwModel`). */
export function begripBron(s: BegripSamenhang): GraafBron {
  const namen = new Map(s.begrippen.map((b) => [b.id, b.naam]));
  const relaties: SamenhangRelatie[] = [];
  for (const k of s.koppelingen) {
    if (k.beoordeling === "afgewezen" || !namen.has(k.begrip_id)) continue;
    relaties.push({ bron: begripKnoopId(k.begrip_id), doel: `element:${k.element_id}`, soort: "duidt", groep: "begrippen",
      anker_tekst: ROL_ZIN[k.rol] ?? k.rol });
  }
  const lijn = (r: BegripRelatie, soort: "begripsrelatie" | "begripsvoorstel") => {
    if (!namen.has(r.van_begrip) || !namen.has(r.naar_begrip)) return;
    const zin = relatieZin(r.type, namen.get(r.van_begrip)!, namen.get(r.naar_begrip)!).join(" ");
    relaties.push({ bron: begripKnoopId(r.van_begrip), doel: begripKnoopId(r.naar_begrip), soort, groep: "begrippen",
      anker_tekst: soort === "begripsvoorstel" ? `voorstel van Lex: ${zin}` : zin });
  };
  for (const r of s.relaties) if (r.beoordeling === "akkoord") lijn(r, "begripsrelatie");
  for (const r of s.voorstellen) lijn(r, "begripsvoorstel");
  return { knopen: s.begrippen.map(knoop), relaties };
}

// --- NL-SBB-conformiteit ------------------------------------------------------------------------

export interface ConformiteitMelding { laag: "nl_sbb" | "eigen"; ernst: "fout" | "waarschuwing"; pad: string; melding: string }
/** `GET …/begrippen/conformiteit`: per begrip-id; `conform: null` = niet te toetsen (geen validator). */
export interface Conformiteit {
  beschikbaar: boolean;
  nl_sbb_versie: string;
  begrippen: Record<string, { conform: boolean | null; meldingen: ConformiteitMelding[] }>;
}

export function isConformiteit(x: unknown): x is Conformiteit {
  const c = x as Conformiteit;
  return !!c && typeof c === "object" && typeof c.beschikbaar === "boolean" && !!c.begrippen && typeof c.begrippen === "object";
}

/** De korte naam van een SHACL-pad: `http://www.w3.org/2004/02/skos/core#definition` → `definitie`. */
const VELD: Record<string, string> = {
  prefLabel: "voorkeursterm", altLabel: "alternatieve term", definition: "definitie", inScheme: "begrippenkader",
  comment: "uitleg", scopeNote: "toelichting", source: "bron", example: "voorbeeld", title: "titel",
};
export function veldVanPad(pad: string): string {
  const kort = pad.split(/[#/:]/).pop() ?? "";
  return VELD[kort] ?? kort;
}

/** Wat de kaart zegt: "NL-SBB-conform", "Niet NL-SBB-conform: definitie ontbreekt" of niets (onbekend). */
export function conformZin(stand: Conformiteit["begrippen"][string] | undefined, versie: string): string | null {
  if (!stand || stand.conform === null) return null;
  if (stand.conform) return `NL-SBB-conform (profiel ${versie})`;
  const velden = [...new Set(stand.meldingen.filter((m) => m.laag === "nl_sbb" && m.ernst === "fout").map((m) => veldVanPad(m.pad)))];
  return `Niet NL-SBB-conform (profiel ${versie})${velden.length ? `: ${velden.join(", ")} ontbreekt of klopt niet` : ""}`;
}
