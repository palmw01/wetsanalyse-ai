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
  /** Wat er per dimensie gevonden werd (alleen dimensies met een telling); `undefined` bij een oudere
   *  meting zonder telling – "gezocht" is dan bekend, "gevonden" niet. */
  gevonden?: { dimensie: string; aantal: number }[];
  /** Zinsdelen die alleen als geheel geraakt werden; `undefined` bij een oudere meting. */
  alleenGeheel?: number;
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
        ...(m.aangetroffen ? { gevonden: dims.filter(([d]) => typeof m.aangetroffen?.[d] === "number")
          .map(([dimensie]) => ({ dimensie, aantal: m.aangetroffen![dimensie] })) } : {}),
        ...(m.alleen_als_geheel ? { alleenGeheel: m.alleen_als_geheel.length } : {}),
      };
    })
    .sort((a, b) => plek(a.bron_iri) - plek(b.bron_iri));
}

/** "Gevonden: tijd 2, voorwaarde 1 · niets: plaats, definitie" – leeg zonder telling. */
export function gevondenTekst(gevonden: DekkingRegel["gevonden"]): string {
  if (!gevonden) return "";
  const wel = gevonden.filter((g) => g.aantal > 0).map((g) => `${g.dimensie} ${g.aantal}`);
  const niets = gevonden.filter((g) => g.aantal === 0).map((g) => g.dimensie);
  return [wel.length ? `Gevonden: ${wel.join(", ")}` : "Niets gevonden", niets.length && wel.length ? `niets: ${niets.join(", ")}` : ""]
    .filter(Boolean).join(" · ");
}
