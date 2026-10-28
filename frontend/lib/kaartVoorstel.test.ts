import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  AANDACHTSPUNT_LEX, aandachtTekst, definitieDoor, duidingTekst, duidingZin, herkomstLabel, onderbouwingKop, onderzoekTekst,
  openPerVeld, verouderdUit,
  voorbeeldTekst,
} from "./kaartVoorstel";
import { revisieZin } from "./begrippen";
import type { Begrip, DefinitieOnderbouwing, KaartVoorstel } from "./types";

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

describe("het betekenisonderzoek bij een voorstel (spoor M)", () => {
  it("noemt de onderzochte context, wat ontbreekt en de open vragen", () => {
    const v = voorstel({ door: { bron: "model", model: "m", promptversie: "p",
      onderzoek: { onderzocht: 7, ontbrekend: ["budget: 3"], vragen: 1 } } });
    expect(onderzoekTekst(v)).toBe("Onderzochte context: 7 bepalingen; ontbreekt: budget: 3; 1 open betekenisvraag");
    expect(onderzoekTekst(voorstel())).toBeNull();
  });
  it("toont de duiding van een definitie en de soort van een voorbeeld", () => {
    const d = voorstel({ waarde: { definitie: "d", herkomst: "geformuleerd", fragmenten: [], definitie_bron_iri: "",
      definitie_vindplaats: "", vindplaats_soort: "",
      duiding: { soort: "toepassingsgeval", bereik: "specifiek", voorkeursterm: "herziening naar een positief bedrag", ontbreekt: "" } } });
    expect(duidingTekst(d)).toBe("Lex duidt dit als een toepassingsgeval (specifiek); voorgestelde naam: herziening naar een positief bedrag");
    const vb = voorstel({ veld: "voorbeelden", actie: "voorbeelden", waarde: { tekst: "t", fragmenten: [], oordeel: "niet",
      soort_voorbeeld: "tegenvoorbeeld", toetst: "begrip", kenmerk: "een voorlopige aanslag" } });
    expect(voorbeeldTekst(vb)).toBe("Tegenvoorbeeld · toetst het begrip · kenmerk: een voorlopige aanslag");
    expect(voorbeeldTekst(d)).toBeNull();
  });
});


describe("de onderbouwing onder een overgenomen definitie (spoor M)", () => {
  const frag = (n: number) => ({ bron_iri: `urn:bwb:BWBR0002320:artikel:30fb:lid:${n}`, start: 0, eind: 4, tekst: `lid ${n}`,
    rol: "ondersteunend" });
  const o = (extra: Partial<DefinitieOnderbouwing>): DefinitieOnderbouwing => ({
    herkomst: "samengesteld", definitie_bron_iri: "", definitie_vindplaats: "", fragmenten: [frag(1)], duiding: null,
    onderzoek_id: "O1", ...extra });

  it("noemt de fragmenten en waar de definitie vandaan kwam", () => {
    expect(onderbouwingKop(o({ voorstel_id: "v1" }))).toBe("Rust op 1 fragment uit de bron – via een voorstel van Lex");
    expect(onderbouwingKop(o({ fragmenten: [frag(1), frag(2)], groep_id: "G1", run_id: "r" })))
      .toBe("Rust op 2 fragmenten uit de bron – via een betekenisgroep");
  });

  it("noemt bij een letterlijke definitie de vindplaats", () => {
    expect(onderbouwingKop(o({ herkomst: "letterlijk", fragmenten: [], definitie_vindplaats: "Artikel 2, lid 1",
      definitie_bron_iri: "urn:bwb:B:artikel:2:lid:1", groep_id: "G1" })))
      .toBe("Letterlijk uit Artikel 2, lid 1 – via een betekenisgroep");
  });

  it("zegt de duiding zoals bij het voorstel", () => {
    expect(duidingZin({ soort: "begrip", bereik: "algemeen", voorkeursterm: "", ontbreekt: "" }))
      .toBe("Lex duidt dit als een begrip (algemeen)");
  });
});
