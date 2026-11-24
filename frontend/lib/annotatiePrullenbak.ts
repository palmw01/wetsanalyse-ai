// De prullenbak van de annotaties (api `annotatie_prullenbak.py`): verwijderen is terug te draaien. Hier de vormen en de
// zinnen; de componenten staan in `components/annotaties/Prullenbak.tsx`.
//
// - De bevestiging noemt wat er verloren gaat (`impactZinnen`, uit `POST weergave/verwijder-impact`), op elke plek waar je
//   een annotatie verwijdert: het menu van het paneel en de kaart in het overzicht.
// - De weergave draagt `prullenbak`: het nieuwste item dat deze bepaling raakt. Zonder nieuwe laag staat er
//   *Terugzetten*; met een nieuwe laag zegt het paneel wat er nu ligt en biedt het een vergelijking.
// - Een begripkoppeling of drager die naar een verwijderd element wijst, draagt `bron_verwijderd` (`bronVerwijderdZin`).

import { aantal } from "./aantal";
import { datumKort } from "./datum";

export interface VerwijzerRef { id: string; naam: string; werkgebied_id: string | null }

/** Wat verwijderen kost (`verwijder_impact` in de api). */
export interface VerwijderImpact {
  lagen: number;
  markeringen: number;
  beoordeeld: number;
  historie: number;
  relaties: number;
  begrippen: VerwijzerRef[];
  regels: VerwijzerRef[];
  bewaartermijn_dagen: number;
}

/** Een item in de prullenbak zoals de weergave het noemt (`bij_weergave`). */
export interface PrullenbakItem {
  id: string;
  weergave_iri: string;
  bron_iris: string[];
  door: string;
  op: string;
  bewaard_tot: string;
  markeringen: number;
  beoordeeld: number;
  historie?: number;
  lagen: number;
  relaties?: number;
  terugzetbaar: boolean;
  /** De bronnodes waar intussen een nieuwe laag op staat. */
  bezet: string[];
}

/** `GET prullenbak/{id}`: het item met zijn markeringen (compact), voor de vergelijking. */
export interface PrullenbakInhoud extends Omit<PrullenbakItem, "terugzetbaar" | "bezet"> {
  elementen: { id: string; klasse: string; tekst: string; lifecycle: string; eigenaar_iri: string; verouderd?: boolean }[];
}

/** Op een koppeling of drager waarvan de markering verdween omdat haar annotatie werd verwijderd. */
export interface BronVerwijderd {
  op: string;
  door: string;
  weergave: string;
  /** Nog in de prullenbak (terug te zetten), of `null`: definitief. */
  prullenbak_id: string | null;
}

export function isVerwijderImpact(x: unknown): x is VerwijderImpact {
  const v = x as Partial<VerwijderImpact> | null;
  return !!v && typeof v.markeringen === "number" && typeof v.beoordeeld === "number"
    && Array.isArray(v.begrippen) && Array.isArray(v.regels);
}

function opsomming(delen: string[]): string {
  return delen.length <= 1 ? delen.join("") : `${delen.slice(0, -1).join(", ")} en ${delen.at(-1)}`;
}

function namen(refs: VerwijzerRef[], max = 3): string {
  const getoond = refs.slice(0, max).map((r) => `“${r.naam}”`);
  return refs.length > max ? `${getoond.join(", ")} en ${refs.length - max} meer` : opsomming(getoond);
}

/** De zinnen van de bevestiging: wat er weggaat, wie ernaar verwijst, en hoe lang je het kunt terugzetten.
 *  "9 markeringen, waarvan 7 beoordeeld, en 3 relaties gaan naar de prullenbak." */
export function impactZinnen(i: VerwijderImpact): { verlies: string; verwijzers: string | null; terug: string } {
  const markeringen = `${aantal(i.markeringen, "markering", "markeringen")}, waarvan ${i.beoordeeld} beoordeeld,`;
  const delen = [markeringen, ...(i.relaties ? [aantal(i.relaties, "relatie", "relaties")] : [])];
  const verlies = `${delen.join(" en ")} ${i.markeringen === 1 && !i.relaties ? "gaat" : "gaan"} naar de prullenbak`
    + (i.historie ? `, met ${aantal(i.historie, "markering", "markeringen")} uit de historie.` : ".");
  const wie = [
    ...(i.begrippen.length ? [`${aantal(i.begrippen.length, "begrip", "begrippen")} (${namen(i.begrippen)})`] : []),
    ...(i.regels.length ? [`${aantal(i.regels.length, "afleidingsregel", "afleidingsregels")} (${namen(i.regels)})`] : []),
  ];
  const verwijzers = wie.length
    ? `${opsomming(wie)} ${i.begrippen.length + i.regels.length === 1 ? "verwijst" : "verwijzen"} ernaar; daar staat dan “bron verwijderd”.`
    : null;
  const terug = `Je kunt de annotatie ${aantal(i.bewaartermijn_dagen, "dag", "dagen")} terugzetten, zolang er geen nieuwe `
    + "annotatie op deze bepaling staat. Uit de kennisgraaf gaat hij meteen.";
  return { verlies, verwijzers, terug };
}

/** "Verwijderd op 24 nov 2026 door jurist-a." */
export function verwijderdOp(op: string, door?: string): string {
  return `verwijderd op ${datumKort(op)}${door ? ` door ${door}` : ""}`;
}

/** Wat er in de prullenbak ligt, in één regel: "9 markeringen, waarvan 7 beoordeeld". */
export function inhoudZin(p: Pick<PrullenbakItem, "markeringen" | "beoordeeld">): string {
  return `${aantal(p.markeringen, "markering", "markeringen")}, waarvan ${p.beoordeeld} beoordeeld`;
}

/** De regel bij een koppeling of drager: "bron verwijderd op 24 nov 2026 door jurist-a · terug te zetten". */
export function bronVerwijderdZin(b: BronVerwijderd): string {
  return `bron ${verwijderdOp(b.op, b.door)} · ${b.prullenbak_id ? "in de prullenbak, terug te zetten" : "definitief verwijderd"}`;
}
