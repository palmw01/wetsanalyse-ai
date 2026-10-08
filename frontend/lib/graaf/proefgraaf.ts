/** Een gegenereerde kennisgraaf met de vorm en omvang van de echte (okt 2026: 7 regelingen, ~6.500
 *  knopen, ~3.500 verwijzingen), voor de schaaltests en de browsertest. Deterministisch: een vaste
 *  lineaire congruente reeks, geen `Math.random`. */
import type { KennisgraafAntwoord } from "./model";
import type { KnoopSoort, SamenhangKnoop, SamenhangRelatie } from "@/lib/samenhang";

export interface ProefOpties {
  regelingen?: number;
  /** Artikelen per regeling (ongeveer; de leden en onderdelen komen erbij). */
  artikelen?: number;
  verwijzingen?: number;
  markeringen?: number;
}

export function proefgraaf({ regelingen = 7, artikelen = 195, verwijzingen = 3500, markeringen = 400 }: ProefOpties = {}): KennisgraafAntwoord {
  let toestand = 12345;
  const volgende = () => (toestand = (Math.imul(toestand, 1103515245) + 12345) >>> 0) / 4294967296;
  const knopen: SamenhangKnoop[] = [];
  const relaties: SamenhangRelatie[] = [];
  const knoop = (id: string, soort: KnoopSoort, label: string, bwb: string, extra: Partial<SamenhangKnoop> = {}) =>
    knopen.push({ id, soort, label, tekst: "", klasse: "", lifecycle: "", element_id: "", bwb_id: bwb, artikel: "", lid: "", rand: false, ...extra });
  const bevat = (bron: string, doel: string) => relaties.push({ bron, doel, soort: "bevat", groep: "structuur", anker_tekst: "" });
  const bepalingen: string[] = [];
  const perRegeling: string[][] = [];

  for (let r = 0; r < regelingen; r++) {
    const bwb = `BWBR${String(4770 + r).padStart(7, "0")}`;
    const wortel = `urn:bwb:${bwb}`;
    const eigen: string[] = [];
    perRegeling.push(eigen);
    knoop(wortel, "regeling", `Regeling ${r + 1}`, bwb);
    const aantal = Math.round(artikelen * (0.4 + 1.2 * volgende()));
    const hoofdstukken = 4 + Math.floor(volgende() * 6);
    for (let h = 1; h <= hoofdstukken; h++) {
      const hid = `${wortel}:hoofdstuk:${h}`;
      knoop(hid, "deel", `Hoofdstuk ${h}`, bwb);
      bevat(wortel, hid);
      for (let a = 1; a <= Math.ceil(aantal / hoofdstukken); a++) {
        const nr = `${h}.${a}`;
        const aid = `${wortel}:artikel:${nr}`;
        knoop(aid, "artikel", `Artikel ${nr}`, bwb, { artikel: nr });
        bevat(hid, aid);
        bepalingen.push(aid);
        eigen.push(aid);
        const leden = Math.floor(volgende() * 4);
        for (let l = 1; l <= leden; l++) {
          const lid = `${aid}:lid:${l}`;
          knoop(lid, "lid", `Lid ${l}`, bwb, { artikel: nr, lid: String(l) });
          bevat(aid, lid);
          bepalingen.push(lid);
          eigen.push(lid);
          const onderdelen = volgende() < 0.4 ? 1 + Math.floor(volgende() * 5) : 0;
          for (let o = 0; o < onderdelen; o++) {
            const oid = `${lid}:o:${String.fromCharCode(97 + o)}`;
            knoop(oid, "onderdeel", `Onderdeel ${String.fromCharCode(97 + o)}`, bwb, { artikel: nr, lid: String(l) });
            bevat(lid, oid);
          }
        }
      }
    }
  }
  const gezien = new Set<string>();
  for (let i = 0; i < verwijzingen; i++) {
    // Zoals in de echte graaf: de meeste verwijzingen blijven binnen de eigen regeling.
    const eigen = perRegeling[Math.floor(volgende() * perRegeling.length)];
    const bron = eigen[Math.floor(volgende() * eigen.length)];
    const binnen = volgende() < 0.75 ? eigen : bepalingen;
    const doel = binnen[Math.floor(volgende() * binnen.length)];
    if (bron === doel || gezien.has(bron + doel)) continue;
    gezien.add(bron + doel);
    relaties.push({ bron, doel, soort: "verwijst_naar", groep: "verwijzingen", anker_tekst: "artikel" });
  }
  const klassen = ["Rechtssubject", "Rechtsobject", "Rechtsfeit", "Voorwaarde", "Tijdsaanduiding"];
  for (const k of klassen) knoop(`klasse:${k}`, "klasse", k, "", { klasse: k });
  for (let i = 0; i < markeringen; i++) {
    const anker = bepalingen[Math.floor(volgende() * bepalingen.length)];
    const klasse = klassen[i % klassen.length];
    const id = `element:${i}`;
    knoop(id, "markering", `fragment ${i}`, "", { klasse, lifecycle: "voorgesteld", element_id: String(i) });
    relaties.push({ bron: id, doel: anker, soort: "markeert", groep: "annotaties", anker_tekst: "" });
    relaties.push({ bron: id, doel: `klasse:${klasse}`, soort: "heeft_klasse", groep: "annotaties", anker_tekst: "" });
  }
  return {
    schema_versie: 1, versie: "proef", knopen, relaties,
    regelingen: Array.from({ length: regelingen }, (_, r) => ({ bwb_id: `BWBR${String(4770 + r).padStart(7, "0")}`, citeertitel: `Regeling ${r + 1}`, toestand: "" })),
  };
}
