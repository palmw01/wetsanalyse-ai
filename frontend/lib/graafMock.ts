import { DEMO_ARTIKEL, DEMO_SLUG, maakDemoDocument, type DemoScene } from "./rondleidingDemo";
import { jasStyle } from "./jas";
import type { AnnotatieDocument, AnnotatieElement } from "./types";

export const REGELING = "urn:bwb:BWBR0004770";
export const ARTIKEL = `${REGELING}:artikel:9`;
export const LID1 = `${ARTIKEL}:lid:1`;
export const LID2 = `${ARTIKEL}:lid:2`;
export type GraafSoort = "regeling" | "artikel" | "lid" | "markering" | "klasse";
export type RelatieGroep = "structuur" | "verwijzingen" | "annotaties";
export type GraafScenario = "bronnen" | "annotaties" | "nieuw";
export interface GraafKnoop {
  id: string; label: string; kort: string; soort: GraafSoort; kleur: string;
  tekst?: string; elementId?: string; klasse?: string; lid?: string;
  x: number; y: number; z: number; fx: number; fy: number; fz: number;
}
export interface GraafRelatie {
  id: string; source: string; target: string; label: string; groep: RelatieGroep;
}
export interface GraafData { nodes: GraafKnoop[]; links: GraafRelatie[] }

export const SOORT_LABEL: Record<GraafSoort, string> = {
  regeling: "Regeling", artikel: "Artikel", lid: "Lid", markering: "Markering", klasse: "JAS-klasse",
};

export function klasseKleur(klasse: string): string {
  return jasStyle(klasse).match(/bg-\[(#[a-f0-9]+)\]/)?.[1] ?? "#cbd5e1";
}

/** Dezelfde brontekst en ankers als de rondleiding; alle annotaties zijn voorbeelden. */
export function maakGraafScene(scenario: GraafScenario): DemoScene {
  const doc = maakDemoDocument();
  doc.citeertitel = "Invorderingswet 1990";
  doc.elementen = doc.elementen.map((el) => el.id === "demo-el-8"
    ? { ...el, klasse: "Rechtsbetrekking", aandacht: "geel", toelichting: "Een voorgestelde markering van de juridische toestand.", critic: "Controleer de gekozen klasse in de context van dit lid." }
    : el);
  const antwoord = {
    id: "graaf-antwoord", type: "antwoord" as const,
    tekst: "Artikel 9 bestaat uit verschillende leden. In dit voorbeeld bekijken we **lid 1 en lid 2**.\n\n" +
      "Lid 2 verwijst met ‘In afwijking van het eerste lid’ naar lid 1. In de graaf kun je deze verwijzing volgen en de bijbehorende tekst openen.\n\n" +
      "Je kunt ook de **voorbeeldmarkeringen en hun JAS-klassen** zichtbaar maken. Zo bekijk je hetzelfde fragment vanuit de tekst en vanuit zijn samenhang.",
    denk: "Voorbeeld · brontekst en relaties uit de lokale voorbeeldscène",
    bronnen: [{ label: "Invorderingswet 1990, artikel 9", uri: "jci1.3:c:BWBR0004770&artikel=9" }],
  };
  return {
    docs: { [DEMO_SLUG]: doc }, infos: { [DEMO_SLUG]: DEMO_ARTIKEL },
    gesprekken: [
      { id: "bronnen", titel: "Samenhang van artikel 9", aantal_berichten: 2, updated: "2026-09-29T09:30:00Z" },
      { id: "annotaties", titel: "JAS-annotaties verkennen", aantal_berichten: 4, updated: "2026-09-29T09:00:00Z" },
    ],
    items: scenario === "nieuw" ? [] : [
      { id: "graaf-vraag", type: "user", tekst: "Hoe hangen de leden en annotaties van artikel 9 met elkaar samen?" },
      antwoord,
      ...(scenario === "annotaties" ? [
        { id: "graaf-annotatie-vraag", type: "user" as const, tekst: "Laat me de annotaties van artikel 9 bekijken." },
        { id: "graaf-annotatie", type: "annotatie" as const, slug: DEMO_SLUG,
          titel: "Invorderingswet 1990 – artikel 9", denk: "Voorbeeld · 11 markeringen · klaar om te bekijken" },
      ] : []),
    ],
  };
}

export function bouwVoorbeeldGraaf(doc: AnnotatieDocument): GraafData {
  const nodes: GraafKnoop[] = [];
  const links: GraafRelatie[] = [];
  function node(data: Omit<GraafKnoop, "fx" | "fy" | "fz">) {
    nodes.push({ ...data, fx: data.x, fy: data.y, fz: data.z });
  }
  function link(source: string, target: string, label: string, groep: RelatieGroep) {
    links.push({ id: `${source}|${label}|${target}`, source, target, label, groep });
  }
  node({ id: REGELING, label: "Invorderingswet 1990", kort: "Invorderingswet 1990", soort: "regeling", kleur: "#154273", x: -100, y: 60, z: -35 });
  node({ id: ARTIKEL, label: "Artikel 9", kort: "Artikel 9", soort: "artikel", kleur: "#007bc7", x: -32, y: 20, z: 25 });
  link(REGELING, ARTIKEL, "bevat", "structuur");
  for (const [index, lid] of DEMO_ARTIKEL.leden_teksten.entries()) {
    const id = `${ARTIKEL}:lid:${lid.lid}`;
    node({ id, label: `Artikel 9 · lid ${lid.lid}`, kort: `Lid ${lid.lid}`, soort: "lid", kleur: "#398ab8",
      tekst: lid.tekst, lid: lid.lid, x: 26, y: index === 0 ? 86 : -61, z: index === 0 ? -28 : 36 });
    link(ARTIKEL, id, "bevat", "structuur");
  }
  // Deze expliciete verwijzing staat letterlijk in lid 2. Geen afgeleide juridische afhankelijkheid.
  link(LID2, LID1, "verwijst naar", "verwijzingen");
  const actueel = doc.elementen.filter((el) => !el.verouderd && el.lifecycle !== "rejected");
  for (const [index, el] of actueel.entries()) {
    const groep = actueel.filter((e) => e.lid === el.lid);
    const positie = groep.findIndex((e) => e.id === el.id);
    const hoek = (positie / groep.length) * Math.PI * 2;
    node({ id: el.id, elementId: el.id, label: el.tekst, kort: el.tekst.length > 27 ? el.tekst.slice(0, 25) + "…" : el.tekst,
      soort: "markering", kleur: klasseKleur(el.klasse), klasse: el.klasse, lid: el.lid, tekst: el.tekst,
      x: 92 + Math.cos(hoek) * 40, y: (el.lid === "1" ? 91 : -69) + Math.sin(hoek) * 53,
      z: ((index % 3) - 1) * 53 });
    link(el.id, `${ARTIKEL}:lid:${el.lid || "1"}`, "markeert", "annotaties");
    link(el.id, `klasse:${el.klasse}`, "heeft klasse", "annotaties");
  }
  const klassen = [...new Set(actueel.map((e) => e.klasse))];
  klassen.forEach((klasse, i) => node({ id: `klasse:${klasse}`, label: klasse, kort: klasse, klasse,
    soort: "klasse", kleur: klasseKleur(klasse), x: 211, y: 105 - i * 51, z: i % 2 ? -35 : 40 }));
  return { nodes, links };
}

/** Filters veranderen alleen zichtbaarheid; vaste 3D-posities houden de kaart herkenbaar. */
export function zichtbareGraaf(data: GraafData, uitgebreid: string[], filters: Record<RelatieGroep, boolean>): GraafData {
  const zichtbaar = new Set([REGELING, ARTIKEL, LID1, LID2, ...uitgebreid]);
  for (const id of uitgebreid) {
    for (const edge of data.links) {
      if (edge.source === id) zichtbaar.add(edge.target);
      if (edge.target === id) zichtbaar.add(edge.source);
    }
  }
  const nodes = data.nodes.filter((n) => zichtbaar.has(n.id) && (filters.annotaties || !["klasse", "markering"].includes(n.soort)));
  const ids = new Set(nodes.map((n) => n.id));
  return { nodes, links: data.links.filter((e) => filters[e.groep] && ids.has(e.source) && ids.has(e.target)) };
}

export function voorbeeldAntwoord(prompt: string, element?: AnnotatieElement): string {
  if (element) return `**Voorbeeldantwoord bij “${element.tekst}”**\n\n${element.toelichting || "Deze markering heeft nog geen toelichting."}` +
    `\n\nDe voorgestelde klasse is **${element.klasse}**. Je vindt het fragment in artikel 9, lid ${element.lid}.` +
    (element.alternatieven?.length ? ` Als andere lezing is **${element.alternatieven[0].klasse}** vastgelegd: ${element.alternatieven[0].motivatie}` : "") +
    "\n\n_Dit is een lokaal voorbeeldantwoord; er is geen model aangeroepen._";
  if (/samenhang|verbinding|lid|artikel 9|graaf|bron/i.test(prompt)) return "**Samenhang in dit voorbeeld**\n\nArtikel 9 bevat lid 1 en lid 2. Lid 2 verwijst expliciet naar lid 1. Open de 3D-graaf en kies **Toon verbindingen** bij een lid om de voorbeeldmarkeringen te bekijken.\n\n_Dit is een vooraf opgesteld voorbeeldantwoord._";
  return "Deze interactieve mock heeft voorbeeldantwoorden over **artikel 9, de verbindingen en geselecteerde markeringen**. Probeer een van die onderwerpen of kies **Vraag Lex hierover** in de graaf. Er wordt geen echte AI-aanroep uitgevoerd.";
}
