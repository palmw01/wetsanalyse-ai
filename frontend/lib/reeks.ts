// Een reeks: meerdere leden (of subbepalingen) van één artikel, geannoteerd in één run.
//
// De jurist vinkt op de keuzekaart onderdelen aan; graph-qa draait ze na elkaar (`agent/reeks.py`)
// en deelt de eventstroom in: `reeks` (start/eind) om het geheel, `onderdeel` (start/eind) om elk
// lid, en elk event daartussen draagt `onderdeel: <bron_iri>`. Hier wordt die stroom één
// reeksblok in de thread: per lid een regel met zijn eigen "zo is dit tot stand gekomen", zijn
// eigen annotatie om te openen, en een status.
//
// Pure functies, zodat de volgorde- en statuslogica zonder DOM te testen is (lib/reeks.test.ts).
// De events komen ruw binnen (zie `onReeksEvent` in lib/api.ts) en worden hier gevalideerd:
// een misvormd event slaat over, het breekt de reeks niet af.

import { parseHergebruik } from "./agentEvents";
import type { NodeDoel, ToolExecution } from "./annotatieNode";
import { mergeToolExecution, parseToolExecution, toolSpoorUit } from "./annotatieNode";
import type { AgentDoelInvoer, AgentHergebruik, AgentKandidaat, Bericht } from "./types";

export type OnderdeelStatus = "wacht" | "bezig" | "klaar" | "hergebruik" | "fout" | "gestopt" | "overgeslagen";

export interface ReeksOnderdeel {
  bron_iri: string;
  label: string;
  status: OnderdeelStatus;
  voorstellen: number;
  fout?: string;
  denk: string;
  tool_executions: ToolExecution[];
  /** Waar de annotatie van dit onderdeel staat; gezet zodra hij is vastgelegd. */
  annotatie_doel?: NodeDoel;
  hergebruik?: AgentHergebruik;
}

export interface Reeks {
  runId: string;
  ouder: { bron_iri: string; label: string };
  onderdelen: ReeksOnderdeel[];
  /** Het `reeks`-eind kwam binnen (of de berichten zijn uit de geschiedenis geladen). */
  afgerond: boolean;
  reden?: "gestopt" | "budget_op";
}

type Ruw = Record<string, unknown>;
const str = (v: unknown): string => (typeof v === "string" ? v : "");
const num = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) ? v : 0);

const EIND_STATUS: Record<string, OnderdeelStatus> = {
  klaar: "klaar", hergebruik: "hergebruik", fout: "fout", gestopt: "gestopt",
};

function nieuwOnderdeel(bron_iri: string, label: string): ReeksOnderdeel {
  return { bron_iri, label: label || bron_iri, status: "wacht", voorstellen: 0, denk: "", tool_executions: [] };
}

function werkBij(reeks: Reeks, iri: string, f: (o: ReeksOnderdeel) => ReeksOnderdeel): Reeks {
  if (!reeks.onderdelen.some((o) => o.bron_iri === iri)) return reeks;
  return { ...reeks, onderdelen: reeks.onderdelen.map((o) => (o.bron_iri === iri ? f(o) : o)) };
}

/** Verwerk één event van de reeksstroom. Geeft een nieuwe `Reeks` terug (of `null` zolang het
 *  `reeks`-start nog niet binnen is); de invoer wordt nooit gemuteerd. */
export function verwerkReeksEvent(reeks: Reeks | null, ev: Ruw): Reeks | null {
  const soort = str(ev.type);
  if (soort === "reeks" && ev.fase === "start") {
    const ouder = (ev.ouder && typeof ev.ouder === "object" ? ev.ouder : {}) as Ruw;
    const onderdelen = Array.isArray(ev.onderdelen) ? ev.onderdelen : [];
    return {
      runId: str(ev.run_id),
      ouder: { bron_iri: str(ouder.bron_iri), label: str(ouder.label) },
      onderdelen: onderdelen
        .filter((o): o is Ruw => !!o && typeof o === "object" && typeof (o as Ruw).bron_iri === "string")
        .map((o) => nieuwOnderdeel(str(o.bron_iri), str(o.label))),
      afgerond: false,
    };
  }
  if (!reeks) return null;
  if (soort === "reeks" && ev.fase === "eind") {
    const overgeslagen = new Set(Array.isArray(ev.overgeslagen) ? ev.overgeslagen.map(str) : []);
    const reden = ev.reden === "gestopt" || ev.reden === "budget_op" ? ev.reden : undefined;
    return {
      ...reeks, afgerond: true, ...(reden ? { reden } : {}),
      onderdelen: reeks.onderdelen.map((o) =>
        overgeslagen.has(o.bron_iri) && (o.status === "wacht" || o.status === "bezig") ? { ...o, status: "overgeslagen" } : o),
    };
  }
  if (soort === "onderdeel") {
    const iri = str(ev.bron_iri);
    if (ev.fase === "start") return werkBij(reeks, iri, (o) => ({ ...o, status: "bezig" }));
    if (ev.fase === "eind") {
      return werkBij(reeks, iri, (o) => ({
        ...o,
        status: EIND_STATUS[str(ev.uitkomst)] ?? "klaar",
        voorstellen: num(ev.voorstellen),
        ...(str(ev.fout) ? { fout: str(ev.fout) } : {}),
      }));
    }
    return reeks;
  }
  const iri = str(ev.onderdeel);
  if (!iri) return reeks;
  switch (soort) {
    case "status":
      return werkBij(reeks, iri, (o) => ({ ...o, denk: o.denk + (o.denk ? "\n" : "") + "· " + str(ev.message) }));
    case "reason":
      return werkBij(reeks, iri, (o) => ({ ...o, denk: o.denk + str(ev.content) }));
    case "tool_execution": {
      const uitvoering = parseToolExecution(ev);
      return uitvoering ? werkBij(reeks, iri, (o) => ({ ...o, tool_executions: mergeToolExecution(o.tool_executions, uitvoering) })) : reeks;
    }
    case "hergebruik": {
      const h = parseHergebruik(ev.hergebruik);
      return h ? werkBij(reeks, iri, (o) => ({ ...o, hergebruik: h })) : reeks;
    }
    case "opgeslagen": {
      const doel = ev.annotatie_doel as Ruw | undefined;
      return doel && typeof doel.bron_iri === "string"
        ? werkBij(reeks, iri, (o) => ({ ...o, annotatie_doel: { bron_iri: str(doel.bron_iri), label: str(doel.label) || o.label,
            ...(str(doel.snapshot_id) ? { snapshot_id: str(doel.snapshot_id) } : {}) } }))
        : reeks;
    }
    case "error":
      return werkBij(reeks, iri, (o) => ({ ...o, status: "fout", fout: str(ev.message) || "Dit onderdeel is mislukt." }));
    default:
      return reeks;
  }
}

/** "3 van 5 klaar" – of, na afloop, wat er is gebeurd. */
export function reeksSamenvatting(reeks: Reeks): string {
  const totaal = reeks.onderdelen.length;
  const gedaan = reeks.onderdelen.filter((o) => o.status === "klaar" || o.status === "hergebruik").length;
  const mislukt = reeks.onderdelen.filter((o) => o.status === "fout").length;
  const niet = reeks.onderdelen.filter((o) => o.status === "overgeslagen").length;
  if (!reeks.afgerond) return `${gedaan} van ${totaal} klaar`;
  const delen = [`${gedaan} van ${totaal} geannoteerd`];
  if (mislukt) delen.push(`${mislukt} mislukt`);
  if (niet) delen.push(`${niet} niet aan bod gekomen${reeks.reden === "budget_op" ? " (tokenbudget op)" : reeks.reden === "gestopt" ? " (gestopt)" : ""}`);
  return delen.join(" · ");
}

/** Het onderdeel waar nu aan gewerkt wordt – dat staat open; de rest is ingeklapt. */
export function actiefOnderdeel(reeks: Reeks): string | undefined {
  return reeks.onderdelen.find((o) => o.status === "bezig")?.bron_iri;
}

/** De opgeslagen berichten van één reeks → het reeksblok zoals het na afloop stond.
 *
 *  Elk onderdeel is een eigen bericht met `reeks: {run_id, index, totaal, ouder}`. Een bericht dat
 *  ontbreekt (een onderdeel dat niet aan bod kwam) heeft geen bericht; dat onderdeel staat dan als
 *  "niet aan bod gekomen" – het aantal is bekend uit `totaal`. */
export function reeksUitBerichten(berichten: Bericht[]): Reeks | null {
  const eerste = berichten.find((b) => b.reeks);
  if (!eerste?.reeks) return null;
  const totaal = eerste.reeks.totaal;
  const perIndex = new Map(berichten.filter((b) => b.reeks).map((b) => [b.reeks!.index, b]));
  const onderdelen: ReeksOnderdeel[] = [];
  for (let i = 0; i < totaal; i++) {
    const b = perIndex.get(i);
    if (!b) {
      onderdelen.push({ ...nieuwOnderdeel(`onbekend:${i}`, `Onderdeel ${i + 1}`), status: "overgeslagen" });
      continue;
    }
    const doel = b.annotatie_doel;
    const hergebruik = b.hergebruik ? parseHergebruik(b.hergebruik) : undefined;
    onderdelen.push({
      bron_iri: doel?.bron_iri ?? `onbekend:${i}`,
      label: doel?.label || b.annotatie_titel || `Onderdeel ${i + 1}`,
      status: doel ? (hergebruik?.volledig ? "hergebruik" : "klaar") : "fout",
      voorstellen: 0,
      ...(doel ? {} : { fout: b.tekst || "Niet vastgelegd." }),
      denk: b.denk ?? "",
      tool_executions: toolSpoorUit(b.tool_executions),
      ...(doel ? { annotatie_doel: doel } : {}),
      ...(hergebruik ? { hergebruik } : {}),
    });
  }
  return { runId: eerste.reeks.run_id, ouder: { bron_iri: "", label: eerste.reeks.ouder }, onderdelen, afgerond: true };
}

/** De gekozen opties van de keuzekaart als doelen voor één reeks-run. Alleen opties met een
 *  `bron_iri` – zonder is het geen onderdeel van de kaart maar een onderwerpkandidaat. */
export function doelenVanKandidaten(kandidaten: AgentKandidaat[]): AgentDoelInvoer[] {
  return kandidaten
    .filter((k) => k.bron_iri)
    .map((k) => ({
      bron_iri: k.bron_iri, bwbId: k.bwbId, artikel: k.artikel,
      ...(k.lid ? { lid: k.lid } : {}),
      ...(k.label ? { label: k.label } : {}),
      ...(k.citeertitel ? { citeertitel: k.citeertitel } : {}),
    }));
}

/** De leesbare opdracht in de thread voor een keuze van meerdere onderdelen. */
export function reeksPrompt(ouder: string, kandidaten: AgentKandidaat[]): string {
  const namen = kandidaten.map((k) => k.label || (k.lid ? `lid ${k.lid}` : k.artikel));
  const opsomming = namen.length > 1 ? `${namen.slice(0, -1).join(", ")} en ${namen[namen.length - 1]}` : namen[0] ?? "";
  return `Annoteer ${ouder ? `${ouder}: ` : ""}${opsomming}`;
}

/** De leden van een reeks in het annotatiepaneel: welke staat er open, en waar ga je heen met
 *  vorige/volgende. Alleen onderdelen met een vastgelegde annotatie tellen mee – een mislukt of
 *  overgeslagen lid heeft niets om te openen. `null` als het paneel iets anders toont. */
export interface ReeksNavigatie {
  ouder: string;
  index: number;
  totaal: number;
  vorige?: NodeDoel;
  volgende?: NodeDoel;
}

export function reeksNavigatie(reeks: Reeks, bronIri: string): ReeksNavigatie | null {
  const leden = reeks.onderdelen.flatMap((o) => (o.annotatie_doel ? [o.annotatie_doel] : []));
  const index = leden.findIndex((d) => d.bron_iri === bronIri);
  if (index < 0 || leden.length < 2) return null;
  return {
    ouder: reeks.ouder.label,
    index,
    totaal: leden.length,
    ...(index > 0 ? { vorige: leden[index - 1] } : {}),
    ...(index < leden.length - 1 ? { volgende: leden[index + 1] } : {}),
  };
}
