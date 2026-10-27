import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { AANDACHTSPUNT_LEX, aandachtTekst, definitieDoor, herkomstLabel, openPerVeld, verouderdUit } from "./kaartVoorstel";
import { revisieZin } from "./begrippen";
import type { Begrip, KaartVoorstel } from "./types";

const inhoud = (over: Partial<Begrip["inhoud"]> = {}): Begrip["inhoud"] => ({
  naam: "belastingaanslag", alternatieve_termen: [], context: "",
  definitie: "", definitie_herkomst: null, uitleg: "", voorbeelden: [],
  ...over,
});
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
  const daar = Object.fromEntries([...tabel.matchAll(/"([A-Z0-9_]+)":\s*((?:"[^"]*"\s*)+),/g)]
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
