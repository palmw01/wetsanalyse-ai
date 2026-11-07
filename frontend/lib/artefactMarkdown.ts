// Elk artefact als Markdown om te kopiëren of te downloaden (4 nov 2026: één knop voor kopiëren en exporteren bij
// elke soort). Kopieertekst die de jurist overneemt in een eigen document: kopjes en lijsten, geen tabellen
// (besluit gebruiker). Pure functies, zodat ze zonder DOM te testen zijn (lib/artefactMarkdown.test.ts); de vorm
// volgt `overzichtAlsMarkdown` (lib/overzicht.ts).

import { OORDEEL_LABEL, definitieAard } from "./begrippen";
import { BEWIJS_LABEL, STAND_LABEL, VOORTGANG_LABEL, zoekvraagZin, type BronselectieOverzicht, type DeelvraagSelectie } from "./bronselectie";
import { jasVolgorde, klasseLabel } from "./jas";
import type { AnnotatieDocument, Begrip, Werkgebied } from "./types";
import { DOSSIER_VELDEN, ROL_LABEL, STATUS_LABEL } from "./werkgebied";

const regels = (...xs: (string | false | null | undefined)[]) => xs.filter((x): x is string => typeof x === "string").join("\n");
const blok = (titel: string, tekst: string) => (tekst.trim() ? `**${titel}**\n\n${tekst.trim()}\n` : "");

/** Het dossier van een werkgebied: de velden in de volgorde van de methode, het zoekbereik en de deelvragen. */
export function dossierAlsMarkdown(wg: Werkgebied, selectie?: BronselectieOverzicht): string {
  const stand = new Map((selectie?.deelvragen ?? []).map((d) => [d.id, d]));
  const deelvragen = (wg.deelvragen ?? []).filter((d) => d.status === "actief");
  return regels(
    `# ${wg.naam}`, "",
    `Status: ${STATUS_LABEL[wg.status]}${wg.peildatum ? ` · peildatum ${wg.peildatum}` : ""}`, "",
    ...DOSSIER_VELDEN.map(({ veld, label }) => blok(label, wg[veld] ?? "")),
    (wg.regelingen ?? []).length ? `**Regelingen**\n\n${(wg.regelingen ?? []).map((r) => `- ${r.label || r.bwb_id}`).join("\n")}\n` : "",
    deelvragen.length ? `**Deelvragen**\n\n${deelvragen.map((d, i) => {
      const s = stand.get(d.id);
      return `${i + 1}. ${d.vraag}${s ? ` (${VOORTGANG_LABEL[s.status].toLowerCase()})` : ""}`;
    }).join("\n")}\n` : "",
  ).replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

/** Eén deelvraag met haar stand, bronnen per rol en open voorstellen. */
export function deelvraagAlsMarkdown(d: DeelvraagSelectie, titel = `Deelvraag ${d.nr}`): string {
  const bronnen = (rol: "analyseren" | "context") => d.bronnen.filter((b) => b.rol === rol);
  const open = d.kandidaten.filter((k) => k.stand === "voorgesteld");
  return regels(
    `## ${titel}`, "", d.vraag, "",
    `Stand: ${VOORTGANG_LABEL[d.status]}`, "",
    ...(["analyseren", "context"] as const).map((rol) => bronnen(rol).length
      ? `**${ROL_LABEL[rol]}**\n\n${bronnen(rol).map((b) => `- ${b.label || b.bron_iri}`).join("\n")}\n` : ""),
    open.length ? `**Ter beoordeling**\n\n${open.map((k) => `- ${k.label || k.bron_iri}${
      [...k.zoekvragen.map(zoekvraagZin), ...k.bewijs_soorten.map((s) => BEWIJS_LABEL[s])].length
        ? ` (${[...k.zoekvragen.map(zoekvraagZin), ...k.bewijs_soorten.map((s) => BEWIJS_LABEL[s])].join(", ")})` : ""}`).join("\n")}\n` : "",
    d.open_punten.length ? `**Onderzoekspunten**\n\n${d.open_punten.map((p) => `- ${p.tekst}`).join("\n")}\n` : "",
  ).replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

/** De bronselectie per deelvraag: per deelvraag haar bronnen en voorstellen. */
export function bronselectieAlsMarkdown(o: BronselectieOverzicht): string {
  const kop = `# Bronselectie – ${o.naam}`;
  const delen = o.deelvragen.map((d) => deelvraagAlsMarkdown(d, o.modus === "analysevraag" ? "Analysevraag" : `Deelvraag ${d.nr}`));
  const niet = o.deelvragen.flatMap((d) => d.kandidaten.filter((k) => k.stand === "uitgesloten").map((k) => `- ${k.label || k.bron_iri} (${STAND_LABEL[k.stand]}, deelvraag ${d.nr})`));
  return [kop, ...delen, niet.length ? `## Uitgesloten\n\n${niet.join("\n")}\n` : ""].filter(Boolean).join("\n").trim() + "\n";
}

/** Eén begrip: termen, definitie met haar aard, uitleg, toelichting en voorbeelden. */
export function begripAlsMarkdown(b: Pick<Begrip, "inhoud">): string {
  const i = b.inhoud;
  const aard = i.definitie ? definitieAard(i).titel : "";
  return regels(
    `# ${i.naam}`, "",
    i.alternatieve_termen.length ? `Ook: ${i.alternatieve_termen.join(", ")}\n` : "",
    i.definitie ? `**Definitie**\n\n${i.definitie}${aard ? `\n\n_${aard}_` : ""}\n` : "",
    blok("Uitleg", i.uitleg), blok("Toelichting", i.context),
    i.voorbeelden.length ? `**Voorbeelden**\n\n${i.voorbeelden.map((v) => `- ${v.tekst} (${OORDEEL_LABEL[v.oordeel]})`).join("\n")}\n` : "",
  ).replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

const LIFECYCLE: Record<string, string> = {
  voorgesteld: "voorstel van Lex", human_approved: "akkoord", edited: "door de jurist aangepast", rejected: "verworpen",
  published: "gepubliceerd", reused: "hergebruikt",
};

/** Een annotatie: de markeringen per JAS-klasse (in de volgorde van de tabel) met hun fragment en stand. Verworpen
 *  markeringen gaan niet mee: ze zijn er niet. */
export function annotatieAlsMarkdown(doc: AnnotatieDocument, titel: string): string {
  const per = new Map<string, AnnotatieDocument["elementen"]>();
  for (const el of doc.elementen.filter((e) => e.lifecycle !== "rejected" && !e.verouderd)) {
    per.set(el.klasse, [...(per.get(el.klasse) ?? []), el]);
  }
  const klassen = [...per.keys()].sort((a, b) => jasVolgorde(a) - jasVolgorde(b));
  return [`# ${titel}`, "", ...klassen.map((k) => `## ${klasseLabel(k)}\n\n${per.get(k)!.map((el) =>
    `- “${el.tekst}”${el.lid ? ` (lid ${el.lid})` : ""} – ${LIFECYCLE[el.lifecycle] ?? el.lifecycle}${el.toelichting ? `: ${el.toelichting}` : ""}`).join("\n")}\n`)]
    .join("\n").trim() + "\n";
}

/** Alle begrippen van een werkgebied, na elkaar. */
export function begrippenAlsMarkdown(naam: string, begrippen: Pick<Begrip, "inhoud">[]): string {
  return [`# Begrippen – ${naam}`, "", ...begrippen.map((b) => begripAlsMarkdown(b).replace(/^# /, "## "))].join("\n").trim() + "\n";
}

/** Een bestandsnaam uit een titel: kleine letters, streepjes, zonder tekens die een bestandssysteem weigert. Met datum en
 *  tijd, zodat elke download een eigen bestand is; dezelfde vorm als de exports van de api (`app/bestandsnaam.py`). */
export function bestandsnaam(titel: string, extensie = "md", nu = new Date()): string {
  const stam = titel.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80) || "artefact";
  const twee = (n: number) => String(n).padStart(2, "0");
  const dag = `${nu.getFullYear()}${twee(nu.getMonth() + 1)}${twee(nu.getDate())}`;
  return `${stam}-${dag}-${twee(nu.getHours())}${twee(nu.getMinutes())}${twee(nu.getSeconds())}.${extensie}`;
}

/** De voorstellen van Lex per term, voor een oude versie van het artefact: wat er toen lag, zonder de passages. */
export function voorstellenAlsMarkdown(titel: string, termen: readonly { naam: string; passages: number; open: readonly unknown[] }[]): string {
  const regels = [`# ${titel}`, ""];
  if (!termen.length) regels.push("Geen voorstellen.");
  for (const t of termen)
    regels.push(`- ${t.naam} (${t.passages === 1 ? "1 passage" : `${t.passages} passages`}${t.open.length ? ", te beoordelen" : ", beoordeeld"})`);
  return `${regels.join("\n")}\n`;
}
