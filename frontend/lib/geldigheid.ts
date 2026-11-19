// Waar een wettelijke definitie geldt, in woorden: de spiegel van `GELDT_VOOR` in
// `packages/bronmodel/bronmodel/definities.py` (`geldigheid.test.ts` leest die bron). Eén vertaling voor het antwoord
// van Lex (`components/antwoord/Antwoord.tsx`) en de graaf (`components/graaf/GraafInspector.tsx`): "geldt voor
// “Deze wet”" zei een jurist weinig (acceptatie 19 nov 2026).

/** Per soort van de geldingsformule (`bronmodel.definities.Geldigheid.soort`). `{regeling}` is de naam van de regeling
 *  ("regeling" als die onbekend is), `{waarde}` het artikelnummer of het woord ("hoofdstuk"). */
export const GELDT_VOOR: Readonly<Record<string, string>> = {
  regeling: "geldt in de hele {regeling}",
  artikel: "geldt alleen in dit artikel",
  artikel_n: "geldt voor artikel {waarde}",
  lid: "geldt alleen in dit lid",
  structuur: "geldt alleen in dit deel ({waarde})",
};

/** Waar een definitie geldt, in woorden; leeg zonder (bekende) soort. */
export function geldtVoor(soort: string | undefined, { waarde = "", regeling = "" }: { waarde?: string; regeling?: string } = {}): string {
  const sjabloon = soort ? GELDT_VOOR[soort] : undefined;
  return sjabloon ? sjabloon.replace("{waarde}", waarde).replace("{regeling}", regeling || "regeling") : "";
}

/** Het artikelnummer of het woord uit de formule zelf ("voor de toepassing van artikel 7", "in dit hoofdstuk"), voor wie
 *  alleen soort en formule heeft (de graaf, `samenhang_antwoord`): zo zegt "artikel_n" nooit "geldt voor artikel ". */
export function waardeUitFormule(soort: string | undefined, formule: string | undefined): string {
  if (!formule) return "";
  if (soort === "artikel_n") return /artikel\s+([0-9]+[a-z]*)/i.exec(formule)?.[1] ?? "";
  if (soort === "structuur") return /(hoofdstuk|afdeling|paragraaf|titeldeel|titel|onderdeel)\b/i.exec(formule)?.[1]?.toLowerCase() ?? "";
  return "";
}
