// Het overzicht van een onderwerp, zoals graph-qa het uit de graaf opbouwt
// (`tools/graph-qa/agent/overzicht.py`): de rekenkern achter `OverzichtBlok`, de 3D-knop en de
// kopieerknop.
//
// Alles hier leest het overzicht, niet de tekst van Lex. Dat is de reden van bestaan: de doelen van de
// 3D-graaf en de nummers in het blok hingen eerst af van hoe het model formuleerde, en dezelfde vraag
// gaf zo een andere kaart. Nu geeft hetzelfde overzicht dezelfde kaart.

import type { NodeDoel } from "./annotatieNode";
import type { Overzicht, OverzichtBepaling, OverzichtDeel } from "./types";

/** Hoeveel delen de 3D-graaf van een overzicht hoogstens opent. Ruimer dan voor losse artikelen
 *  (`MAX_SAMENHANG_DOELEN`): de delen vormen één compacte boom en komen in één verzoek, met één
 *  bronboom per regeling. Gelijk aan de grens van `/samenhang/meer` in de api. */
export const MAX_OVERZICHT_DOELEN = 30;

/** De doelen voor de 3D-graaf: de delen van het overzicht in zijn eigen volgorde (rang, dan
 *  documentvolgorde), het eerste opent in het paneel. Zonder delen: de bepalingen die het onderwerp
 *  noemen. Geen tekst nodig – dus elke formulering van Lex geeft dezelfde kaart. */
export function overzichtDoelen(ov: Overzicht, max = MAX_OVERZICHT_DOELEN): { doelen: NodeDoel[]; totaal: number } {
  const delen = ov.regelingen.flatMap((r) => r.delen.map((d): NodeDoel => ({
    bron_iri: d.iri, bwb_id: r.bwb_id, label: d.label, citeertitel: r.citeertitel,
  })));
  const alle = delen.length ? delen : ov.regelingen.flatMap((r) => r.ook_genoemd.map((b): NodeDoel => ({
    bron_iri: b.iri, bwb_id: r.bwb_id, label: b.label, citeertitel: r.citeertitel,
  })));
  return { doelen: alle.slice(0, max), totaal: alle.length };
}

/** "Bekijk samenhang van de 8 delen (6 getoond)" – zegt wat de knop opent. */
export function overzichtKnopTekst({ doelen, totaal }: { doelen: NodeDoel[]; totaal: number }, ov: Overzicht): string {
  const zijnDelen = ov.regelingen.some((r) => r.delen.length);
  const soort = zijnDelen ? (totaal === 1 ? "deel" : "delen") : (totaal === 1 ? "bepaling" : "bepalingen");
  const getoond = totaal > doelen.length ? ` (${doelen.length} getoond)` : "";
  return totaal === 1 ? `Bekijk samenhang van ${doelen[0]?.label ?? "het deel"}` : `Bekijk samenhang van de ${totaal} ${soort}${getoond}`;
}

/** Een bepaling zoals de jurist haar leest: "art. 9" voor een artikel, "28.3a" voor een divisie. graph-qa
 *  zet de naam; een ouder bericht heeft hem niet, en dan dezelfde regel: op het nummer (een punt is een
 *  divisie), niet op de IRI-vorm – een deel van de Leidraad-divisies heeft een `:artikel:`-IRI. */
export function bepalingNaam(b: OverzichtBepaling): string {
  if (b.naam) return b.naam;
  return b.nummer.includes(".") || b.iri.includes(":id:") ? b.nummer : `art. ${b.nummer}`;
}

/** De kop van een deel: "Hoofdstuk II – Invordering in eerste aanleg", "28 – Invorderingsrente". graph-qa
 *  zet hem; een ouder bericht valt terug op het label, met het nummer uit de IRI waar dat kan. */
export function deelKop(d: OverzichtDeel): string {
  if (d.kop) return d.kop;
  if (d.label.includes(" – ") || !/:artikel:/.test(d.iri)) return d.label;
  const nummer = decodeURIComponent(d.iri.split(":artikel:")[1] ?? "");
  return nummer ? `${nummer} – ${d.label}` : d.label;
}

export interface OverzichtTelling { regelingen: number; delen: number; bepalingen: number; ookGenoemd: number }

export function telling(ov: Overzicht): OverzichtTelling {
  return {
    regelingen: ov.regelingen.length,
    delen: ov.regelingen.reduce((n, r) => n + r.delen.length, 0),
    bepalingen: ov.regelingen.reduce((n, r) => n + r.delen.reduce((m, d) => m + d.bepalingen.length, 0), 0),
    ookGenoemd: ov.regelingen.reduce((n, r) => n + r.ook_genoemd.length, 0),
  };
}

/** Wat er gezocht is, in één zin – ook als het onderwerp is ingekort of afgebakend. Zo ziet de jurist
 *  waaróp het overzicht berust, en niet alleen wat eruit kwam. */
export function zoekverantwoording(ov: Overzicht): string {
  const delen = [`Gezocht op „${ov.onderwerp_opbouw}” in de opschriften`];
  delen.push(ov.onderwerp_tekst === ov.onderwerp_opbouw ? "en in de wettekst" : `en op „${ov.onderwerp_tekst}” in de wettekst`);
  let zin = delen.join(" ");
  if (ov.gevraagd !== ov.onderwerp_opbouw || ov.gevraagd !== ov.onderwerp_tekst) zin += ` (gevraagd: „${ov.gevraagd}”)`;
  if (ov.scope.length) zin += `, binnen ${ov.regelingen.map((r) => r.citeertitel).join(", ") || ov.scope.join(", ")}`;
  return `${zin}.`;
}

/** Het overzicht als Markdown, voor de kopieerknop: dezelfde inhoud als het blok, in dezelfde volgorde. */
export function overzichtAlsMarkdown(ov: Overzicht): string {
  const regels: string[] = [];
  for (const d of ov.definities) {
    regels.push(`Definitie: ${d.begrip} – ${d.citeertitel}, ${d.vindplaats || d.label}`);
  }
  if (ov.definities.length) regels.push("");
  for (const r of ov.regelingen) {
    regels.push(`**${r.citeertitel}**`);
    for (const d of r.delen) {
      regels.push(`- ${deelKop(d)}: ${d.bepalingen.map(bepalingNaam).join(", ")}`);
      for (const s of d.subdelen) regels.push(`  - waarin ${s.label}`);
    }
    if (r.ook_genoemd.length) {
      regels.push(`- Ook genoemd: ${r.ook_genoemd.map((b) =>
        b.in_deel ? `${bepalingNaam(b)} (${b.in_deel.label})` : bepalingNaam(b)).join("; ")}`);
    }
    regels.push("");
  }
  for (const t of ov.trefwoorden) {
    regels.push(`Trefwoord „${t.trefwoord}” bij: ${t.regelingen.map((r) => r.citeertitel).join(", ")}`);
  }
  regels.push(zoekverantwoording(ov));
  return regels.join("\n").trim();
}
