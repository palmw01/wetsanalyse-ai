import { nodeRequest } from "./annotatieNode";
import { pathSegment } from "./url";

/** Eén revisie van een laag (`GET lagen/{id}/revisies`): wie, wanneer en wat er gebeurde. De api
 *  bewaart niet hoe de laag er toen uitzag – dit is een logboek, geen terugblik. */
export interface Revisie {
  revisie: number;
  actor: string;
  tijdstip: string;
  acties: { actie: string; element_id?: string; status?: string }[];
}

export function haalRevisies(laagId: string): Promise<Revisie[]> {
  return nodeRequest(`lagen/${pathSegment(laagId)}/revisies`);
}

const ACTIE: Record<string, string> = {
  "element-gemaakt": "markering gemaakt",
  approve: "akkoord", edit: "aangepast", grens: "andere grens", reject: "verworpen", heropen: "heropend", comment: "opmerking",
  "element-verwijderd": "markering gewist",
  "bron-gewijzigd": "verouderd door gewijzigde wettekst",
  "laag-bron-gewijzigd": "heropend door gewijzigde wettekst",
};

/** Een actie in gewone taal; een onbekende actie verschijnt als zichzelf. */
export function actieTekst(a: Revisie["acties"][number]): string {
  if (a.actie === "laag-status") return a.status === "geaccordeerd" ? "afgerond" : "heropend";
  return ACTIE[a.actie] ?? a.actie;
}

/** Eén regel per revisie. Een ronde van Lex is één gebeurtenis, ook als hij twintig markeringen
 *  maakte; de rest telt per soort ("akkoord (2), aangepast"). */
export function revisieSamenvatting(r: Revisie): string {
  if (r.acties.some((a) => a.actie === "batch")) {
    const n = r.acties.filter((a) => a.actie === "element-gemaakt").length;
    return `ronde van Lex: ${n ? `${n} ${n === 1 ? "markering" : "markeringen"}` : "geen nieuwe markeringen"}`;
  }
  const tel = new Map<string, number>();
  for (const a of r.acties) tel.set(actieTekst(a), (tel.get(actieTekst(a)) ?? 0) + 1);
  return [...tel].map(([t, n]) => (n > 1 ? `${t} (${n})` : t)).join(", ") || "gewijzigd";
}

/** De elementen die in deze revisie geraakt zijn, zonder dubbelen en in volgorde. */
export function geraakteElementen(r: Revisie): string[] {
  return [...new Set(r.acties.flatMap((a) => (a.element_id ? [a.element_id] : [])))];
}
