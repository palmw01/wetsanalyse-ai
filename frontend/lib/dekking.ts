import type { NodeDekking } from "./annotatieNode";

/** De kleur van de dekkingslaag in de 3D-graaf. Tussen de rand- en teksttint van aandacht-geel
 *  (`globals.css`) in: de randtint zelf is als draadmodel op het lichte doek te bleek. */
export const DEKKINGSKLEUR = "#c4893f";

/** De ongedekte zinsdelen per bronnode – de sleutel is ook de knoop-id in de samenhangsgraaf. */
export function ongedektPerBron(delen: { bron_iri: string; tekst: string }[]): Record<string, string[]> {
  const uit: Record<string, string[]> = {};
  for (const d of delen) (uit[d.bron_iri] ??= []).push(d.tekst);
  return uit;
}

/** De dekking per bronnode, zoals het overzicht in het paneel hem toont. */
export interface DekkingRegel {
  bron_iri: string;
  bekeken: number;
  totaal: number;
  /** Dimensies die niet volledig draaiden, met hun stand. */
  onvolledig: { dimensie: string; stand: "gedeeltelijk" | "overgeslagen" }[];
  ongedekt: number;
}

/** Per bronnode: hoeveel detectiedimensies volledig draaiden, welke niet, en hoeveel zinsdelen geen
 *  enkele treffer gaven. In de volgorde van de bron (`volgorde`), niet in die van de meting. */
export function dekkingPerBron(dekking: NodeDekking | undefined, volgorde: string[]): DekkingRegel[] {
  const structureel = dekking?.structureel ?? {};
  const plek = (iri: string) => { const i = volgorde.indexOf(iri); return i < 0 ? volgorde.length : i; };
  return Object.entries(structureel)
    .map(([bron_iri, m]) => {
      const dims = Object.entries(m.dimensies ?? {});
      return {
        bron_iri,
        bekeken: dims.filter(([, s]) => s === "uitgevoerd").length,
        totaal: dims.length,
        onvolledig: dims.filter(([, s]) => s !== "uitgevoerd")
          .map(([dimensie, stand]) => ({ dimensie, stand: stand as "gedeeltelijk" | "overgeslagen" })),
        ongedekt: (m.ongedekt ?? []).length,
      };
    })
    .sort((a, b) => plek(a.bron_iri) - plek(b.bron_iri));
}
