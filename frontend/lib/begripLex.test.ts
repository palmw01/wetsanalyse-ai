import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  AANDACHTSPUNT_LEX, aandachtTekst, definitieDoor, herkomstLabel, openPerVeld, runMelding, schattingTekst,
  vergelijkKandidaten, verouderdUit, waaromNiet,
} from "./begripLex";
import { revisieZin } from "./begrippen";
import type { Begrip, BegripSamenvatting, KaartRun, KaartVoorstel, Koppeling } from "./types";

const inhoud = (over: Partial<Begrip["inhoud"]> = {}): Begrip["inhoud"] => ({
  naam: "belastingaanslag", alternatieve_termen: [], context: "", jas_klasse: "", jas_subtype: "", geldigheid: "",
  definitie: "", definitie_herkomst: null, uitleg: "", onderbouwing: "", voorbeelden: [], eigenschappen: {}, open_vragen: [],
  ...over,
});
const koppeling = (over: Partial<Koppeling> = {}) =>
  ({ id: "k", element_id: "e1", rol: "duiding", beoordeling: "open", actualiteit: "actueel", ...over }) as Koppeling;
const begrip = (over: Partial<Begrip> = {}) =>
  ({ id: "b1", status: "concept", revisie: 2, inhoud: inhoud(), koppelingen: [koppeling()], ...over }) as Begrip;
const voorstel = (over: Partial<KaartVoorstel> = {}): KaartVoorstel => ({
  id: "v1", begrip_id: "b1", run_id: "r1", actie: "scherper", veld: "definitie", volgorde: 0,
  basis: { revisie: 1, definitie: "", definitie_herkomst: null },
  waarde: { definitie: "x", herkomst: "geformuleerd", fragmenten: [], definitie_bron_iri: "", definitie_vindplaats: "", vindplaats_soort: "" },
  motivatie: "", aandacht: "geel", aandachtspunten: [], door: { bron: "model", model: "m", promptversie: "p" },
  status: "open", reden: "", besloten_door: null, besloten_op: null, begrip_revisie: null, gemaakt: "2026-10-16T10:00:00Z",
  ...over,
});

it("de aandachtspunten volgen graph-qa kaartacties.TEKST, code voor code en woord voor woord", () => {
  const bron = readFileSync(resolve(__dirname, "../../tools/graph-qa/agent/begrippen_pipeline/kaartacties.py"), "utf8");
  const tabel = bron.slice(bron.indexOf("TEKST: dict"), bron.indexOf("}\n", bron.indexOf("TEKST: dict")));
  // Een Python-string mag over regels doorlopen ("…" "…"): de stukken samen zijn de tekst.
  const daar = Object.fromEntries([...tabel.matchAll(/"([A-Z_]+)":\s*((?:"[^"]*"\s*)+),/g)]
    .map((m) => [m[1], [...m[2].matchAll(/"([^"]*)"/g)].map((x) => x[1]).join("")]));
  expect(AANDACHTSPUNT_LEX).toEqual(daar);
  expect(aandachtTekst("DOOR_LEX_GEFORMULEERD")).toMatch(/door Lex geformuleerd/);
  expect(aandachtTekst("ONBEKEND")).toBe("ONBEKEND");
});

describe("herkomstLabel", () => {
  it("noemt de vindplaats en waar die staat", () => {
    const v = voorstel({ actie: "brondefinitie", waarde: { definitie: "d", herkomst: "letterlijk", fragmenten: [],
      definitie_bron_iri: "urn:x", definitie_vindplaats: "Artikel 2 – AWR", vindplaats_soort: "definitieverwijzing" } });
    expect(herkomstLabel(v)).toBe("Letterlijk uit Artikel 2 – AWR (in een regeling waarnaar het werkgebied verwijst)");
    expect(herkomstLabel(voorstel())).toBe("Geformuleerd door Lex");
    expect(herkomstLabel(voorstel({ veld: "voorbeelden", waarde: { tekst: "t", fragmenten: [], oordeel: "wel" } }))).toBe("Bedacht door Lex");
  });
});

it("openPerVeld laat besloten voorstellen weg", () => {
  const p = openPerVeld([voorstel(), voorstel({ id: "v2", status: "afgewezen" }), voorstel({ id: "v3", veld: "uitleg" })]);
  expect([p.definitie.map((v) => v.id), p.uitleg.map((v) => v.id), p.voorbeelden]).toEqual([["v1"], ["v3"], []]);
});

describe("waaromNiet", () => {
  it("niets met onbewaarde wijzigingen, budget op alleen voor het model", () => {
    expect(waaromNiet("brondefinitie", begrip(), { onbewaard: true })).toMatch(/Sla eerst/);
    expect(waaromNiet("brondefinitie", begrip(), { onbewaard: false, budgetOp: true })).toBeNull();
    expect(waaromNiet("scherper", begrip(), { onbewaard: false, budgetOp: true })).toMatch(/tokenbudget/);
  });
  it("voorbeelden vragen een definitie, scherper een actuele passage, verschil een ander begrip", () => {
    expect(waaromNiet("voorbeelden", begrip(), { onbewaard: false })).toMatch(/definitie/);
    expect(waaromNiet("voorbeelden", begrip({ inhoud: inhoud({ definitie: "d" }) }), { onbewaard: false })).toBeNull();
    const weg = begrip({ koppelingen: [koppeling({ actualiteit: "verdwenen" }), koppeling({ rol: "context" })] });
    expect(waaromNiet("scherper", weg, { onbewaard: false })).toMatch(/passage/);
    expect(waaromNiet("betekenisverschil", begrip(), { onbewaard: false })).toMatch(/Kies/);
    expect(waaromNiet("betekenisverschil", begrip(), { onbewaard: false, ander: "b2" })).toBeNull();
  });
});

it("schattingTekst alleen voor een model-actie met een schatting", () => {
  const data = { voorstellen: [], runs: {}, schatting: { scherper: { tokens: 1234, basis: 3 } } };
  expect(schattingTekst("scherper", data)).toBe("~1.234 tokens");
  expect(schattingTekst("voorbeelden", data)).toBe("");
  expect(schattingTekst("brondefinitie", data)).toBe("");
});

it("runMelding: waarom er niets kwam, of waarom het mislukte", () => {
  const run = (over: Partial<KaartRun>) => ({ status: "klaar", melding: "", reden: "", ...over }) as KaartRun;
  expect(runMelding(run({ melding: "Geen wettelijke definitie gevonden." }))).toEqual({ soort: "uitleg", tekst: "Geen wettelijke definitie gevonden." });
  expect(runMelding(run({ status: "mislukt", reden: "model weg" }))).toEqual({ soort: "fout", tekst: "model weg" });
  expect(runMelding(run({}))).toBeNull();
  expect(runMelding(undefined)).toBeNull();
});

it("vergelijkKandidaten: gedeelde passages en gelijke woorden eerst, zichzelf niet", () => {
  const s = (id: string, naam: string, element_ids: string[] = []) =>
    ({ id, inhoud: inhoud({ naam }), element_ids }) as unknown as BegripSamenvatting;
  const uit = vergelijkKandidaten(begrip(), [s("b1", "zelf"), s("b2", "aanslag"), s("b3", "belastingaanslag voorlopig"), s("b4", "x", ["e1"])]);
  expect(uit.map((b) => b.id)).toEqual(["b4", "b3", "b2"]);
});

it("definitieDoor zegt wie de definitie voorstelde", () => {
  expect(definitieDoor(inhoud({ definitie: "d", definitie_door: "lex" }))).toBe("Van Lex overgenomen");
  expect(definitieDoor(inhoud({ definitie: "d", definitie_door: "analist" }))).toBe("Door de analist");
  expect(definitieDoor(inhoud({ definitie: "d" }))).toBe("");
  expect(definitieDoor(inhoud({ definitie_door: "lex" }))).toBe("");
});

it("verouderdUit leest de 409 met toen, nu en voorstel", () => {
  const e = { status: 409, detail: "x", data: { fout: "voorstel_verouderd", toen: { definitie: "" }, nu: { definitie: "eigen" },
    voorstel: { definitie: "van Lex" } } };
  expect(verouderdUit(e, "v1")).toEqual({ voorstelId: "v1", toen: "", nu: "eigen", voorstel: "van Lex" });
  expect(verouderdUit({ status: 409, data: { fout: "al_besloten" } }, "v1")).toBeNull();
});

it("de historie noemt een overgenomen voorstel van Lex", () => {
  expect(revisieZin({ actie: "voorstel-overgenomen", detail: { veld: "definitie", aangepast: false } })).toBe("Overgenomen van Lex: definitie");
  expect(revisieZin({ actie: "voorstel-overgenomen", detail: { veld: "voorbeelden", aangepast: true } })).toBe("Aangepast overgenomen van Lex: voorbeelden");
});
