/** Het label van een bepaling, overal in Lex hetzelfde: de spiegel van `bepaling_label` in `packages/bronmodel`
 *  (`bronmodel/vindplaats.py`). `lib/bepalingLabel.vectoren.json` toetst beide kanten; `app/bepalingLabel.test.ts`
 *  bewaakt dat geen andere plek zelf een label van een bepaling in elkaar zet.
 *
 *  Waarom: een onderdeel zonder eigen nummer heet in de graaf "Onderdeel –" (het opsommingsstreepje is zijn nummer),
 *  een onderdeel van de Leidraad "Onderdeel c.". Los zegt dat niets – drie keer "Onderdeel –" onder elkaar, een letter
 *  zonder het artikel eromheen. Zo'n onderdeel heeft een wet-lokale `id:`-IRI met het knoop-id van wetten.overheid.nl
 *  erin, en daarin staat wél waar het staat: "Artikel 25.3a.1, 1e streepje". */
import { vindplaatsVan } from "@/lib/samenhang";

/** De tekens waarmee een ongenummerd onderdeel in de graaf "genummerd" is. */
export const OPSOMMINGSTEKENS = ["–", "—", "-", "•", "·", "●", "▪"] as const;

const KNOOPSTAP = /^(Circulaire\.divisie|Divisie|Hoofdstuk|Titeldeel|Afdeling|Paragraaf|Artikel|Lid|Onderdeel|Slottekst|Bijlage)(.*)$/;
// Een kaal label: alleen een soortwoord met een nummer of opsommingsteken ("Onderdeel –", "Onderdeel c.", "Lid 2", "–").
const KAAL = /^(?:(?:onderdeel|lid|sub|punt|slottekst)\b\.?\s*)?([^\s,]{0,4}?)\.?$/i;

/** Eén stap uit een knoop-id in woorden: "lid 2", "onderdeel c", "1e streepje", "slottekst". */
function stapTekst(soort: string, ruw: string): string {
  const waarde = ruw.trim().replace(/^\.+/, "");
  if (soort === "Onderdeel") {
    if (/^_\d+$/.test(waarde)) return `${Number(waarde.slice(1))}e streepje`;
    return waarde ? `onderdeel ${waarde}` : "onderdeel";
  }
  if (soort === "Slottekst") return "slottekst"; // het volgnummer is een telling van de importer, geen vindplaats
  if (soort === "Bijlage") return waarde ? `bijlage ${waarde}` : "bijlage";
  const woord = soort === "Artikel" || soort === "Circulaire.divisie" ? "artikel" : soort.toLowerCase();
  return waarde ? `${woord} ${waarde}` : woord;
}

function knoopStappen(knoopId: string): [string, string][] {
  return (knoopId ?? "").split("/").slice(1)
    .map((deel) => deel.match(KNOOPSTAP))
    .filter((m): m is RegExpMatchArray => m !== null)
    .map((m) => [m[1], m[2]] as [string, string]);
}

/** Waar een node staat, uit zijn knoop-id: "Artikel 25.3a.1, 1e streepje", "Bijlage 3, artikel 2, onderdeel d". Leeg
 *  als er niets herkenbaars in staat. Zelfde vorm als `vindplaatsLabel`: het structuurpad boven een artikel valt weg,
 *  behalve in een bijlage. Een divisie van een beleidsregel heet "Artikel", zoals de importer haar vindplaats schrijft. */
export function knoopLabel(knoopId: string): string {
  let stappen = knoopStappen(knoopId);
  if (!stappen.length) return "";
  const inBijlage = stappen.some(([s]) => s === "Bijlage");
  let artikel = -1;
  stappen.forEach(([s], i) => { if (s === "Artikel" || s === "Circulaire.divisie") artikel = i; });
  if (artikel >= 0) {
    // Van geneste divisies telt de diepste: haar nummer draagt het hele pad al ("25.3a.1").
    if (stappen[artikel][0] === "Circulaire.divisie") {
      stappen = stappen.filter(([s], i) => s !== "Circulaire.divisie" || i === artikel);
      artikel = stappen.findIndex(([s]) => s === "Circulaire.divisie");
    }
    stappen = [...(inBijlage ? stappen.slice(0, artikel) : []), ...stappen.slice(artikel)];
  }
  const delen: string[] = [];
  for (const [soort, waarde] of stappen) {
    const tekst = stapTekst(soort, waarde);
    // Opeenvolgende onderdelen in één aanduiding, zoals `vindplaatsLabel`: "onderdeel e, 2".
    if (soort === "Onderdeel" && tekst.startsWith("onderdeel ") && delen.at(-1)?.startsWith("onderdeel ")) {
      delen[delen.length - 1] += `, ${tekst.slice("onderdeel ".length)}`;
    } else delen.push(tekst);
  }
  const tekst = delen.join(", ");
  return tekst.charAt(0).toUpperCase() + tekst.slice(1);
}

function knoopIdVan(iri: string): string {
  const vp = vindplaatsVan(iri);
  return vp?.soort === "node" ? vp.pad.find(([k]) => k === "id")?.[1] ?? "" : "";
}

/** Waar een bepaling staat, alleen uit haar IRI of jci: de vindplaats, of bij een `id:`-node zijn knoop-id. */
export function plekLabel(iri: string): string {
  const vp = vindplaatsVan(iri ?? "");
  if (!vp) return "";
  return vp.soort === "node" ? knoopLabel(knoopIdVan(iri)) : vp.label;
}

/** Of een label alleen een soortwoord met een nummer of streepje is ("Onderdeel –", "Onderdeel c.", "Lid 2"): het zegt
 *  dan niet waar de bepaling staat. */
export function kaalLabel(label: string): boolean {
  return KAAL.test((label ?? "").trim());
}

/** Het label van een bepaling. Een eigen naam ("Voorwaarden standaardbetalingsregeling") blijft staan; een kaal label of
 *  de staart van het pad ("Lid 2", "Onderdeel –", "Onderdeel c.") wordt de plek uit de IRI ("Artikel 9, lid 2",
 *  "Artikel 25.3a.1, 1e streepje"). Zonder plek blijft wat er gegeven is; zonder beide leeg. */
export function bepalingLabel(iri: string, gegeven = ""): string {
  const g = (gegeven ?? "").trim();
  const plek = plekLabel(iri);
  if (!plek) return g;
  if (!g || kaalLabel(g)) return plek;
  const kort = g.toLowerCase().replace(/\.$/, "");
  const lang = plek.toLowerCase();
  return lang === kort || lang.endsWith(` ${kort}`) || lang.endsWith(`, ${kort}`) ? plek : g;
}

/** Alleen de laatste stap van een bepaling, voor een rij die al onder zijn artikel staat: "1e streepje", "onderdeel c",
 *  "lid 2". Onder het artikel zegt "Onderdeel c." genoeg en blijft het staan; alleen een opsommingsteken zonder nummer
 *  ("Onderdeel –") of geen label krijgt de plaats uit de IRI. */
export function stapLabel(iri: string, gegeven = ""): string {
  const g = (gegeven ?? "").trim();
  if (g && (!kaalLabel(g) || /[\p{L}\p{N}]/u.test(g.replace(/^(?:onderdeel|lid|sub|punt|slottekst)\b/i, "")))) return g;
  const knoop = knoopStappen(knoopIdVan(iri)).at(-1);
  const vp = knoop ? undefined : vindplaatsVan(iri ?? "");
  const laatste = vp?.pad.at(-1);
  const tekst = knoop ? stapTekst(...knoop)
    : laatste && vp?.soort !== "node" ? (laatste[0] === "o" ? `onderdeel ${laatste[1]}` : `${laatste[0]} ${laatste[1]}`) : g;
  return tekst.charAt(0).toUpperCase() + tekst.slice(1);
}
