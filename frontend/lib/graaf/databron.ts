/** Waar de graaf van een bepaling zijn gegevens haalt: de samenhang, de hele kennisgraaf, wat de graaf over een knoop
 *  weet, de tekst van een gekozen bepaling en het element achter een markering.
 *
 *  Standaard is dat de api (`apiGraafBron`). De rondleiding geeft een bron in het geheugen mee (`lib/rondleidingDemo.ts`),
 *  net zoals ze het annotatiepaneel een eigen `NodeOpslag` geeft: hetzelfde paneel, dezelfde graaf, en geen verzoek de
 *  deur uit. Eén haak voor elke bron, geen uitzondering voor één geval. */
import { haalElement, type NodeDoel, type NodeElement, type NodeWeergave } from "@/lib/annotatieNode";
import { haalKennisgraaf } from "@/lib/graaf/data";
import { haalKnoopInfo, type KnoopInfo } from "@/lib/graaf/knoopinfo";
import type { KennisgraafAntwoord } from "@/lib/graaf/model";
import { haalKeten, haalSamenhang, haalSamenhangen, type Samenhang } from "@/lib/samenhang";
import { haalBepalingWeergave } from "@/lib/useBron";

export interface GraafDataBron {
  samenhang(doel: Pick<NodeDoel, "bron_iri">): Promise<Samenhang>;
  samenhangen(doelen: Pick<NodeDoel, "bron_iri">[]): Promise<{ resultaten: Samenhang[]; fouten: { bron_iri: string; reden: string }[] }>;
  keten(doelen: Pick<NodeDoel, "bron_iri">[], werkgebiedId?: string): Promise<Samenhang>;
  kennisgraaf(): Promise<KennisgraafAntwoord>;
  knoopInfo(iri: string): Promise<KnoopInfo>;
  /** De tekst van een bepaling met haar markeringen, voor de inspector. */
  bepaling(iri: string): Promise<NodeWeergave>;
  element(id: string): Promise<NodeElement>;
}

export const apiGraafBron: GraafDataBron = {
  samenhang: haalSamenhang,
  samenhangen: haalSamenhangen,
  keten: haalKeten,
  kennisgraaf: () => haalKennisgraaf(),
  knoopInfo: haalKnoopInfo,
  bepaling: haalBepalingWeergave,
  element: haalElement,
};
