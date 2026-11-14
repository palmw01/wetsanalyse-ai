import { describe, expect, it } from "vitest";

import {
  delegatieSamenvatting, parseDelegaties, standVanDeelgesprek, standenPerDeelgesprek, taakMeta, teTonen,
  verwerkDelegatieEvent, voortgangUitDelegatie, weergaveUitBericht, weergaveUitStroom, type DelegatieVoortgang,
} from "./delegatie";
import { LEGE_STAND, stroomReducer } from "./beurtStroom";
import { itemsUitGesprek } from "./geschiedenis";
import { afgehandeld } from "./werkgebiedAnnoteren";
import type { Delegatie } from "./types";

// De events zoals graph-qa ze stuurt (`agent/subagent.py`): start met het plan, per kind start en eind, dan het eind.
const START = { type: "regie", fase: "start", regie_id: "d1", soort: "subagent",
  plan: { opdracht: "subagent", taken: [{ titel: "Uitspraak A", profiel: "algemeen" }, { titel: "Uitspraak B", profiel: "duiding" }] } };
const KIND_START = (index: number, gesprek: string) => ({ type: "regie_taak", fase: "start", regie_id: "d1", index,
  titel: index ? "Uitspraak B" : "Uitspraak A", gesprek_id: gesprek, profiel: index ? "duiding" : "algemeen",
  gekozen_model: "licht" });
const KIND_EIND = (index: number, gesprek: string, uitkomst: string) => ({ type: "regie_taak", fase: "eind", regie_id: "d1",
  index, gesprek_id: gesprek, uitkomst, model: "zwaar", modellen: ["licht", "zwaar"],
  rapport: { status: uitkomst, afbakening: ["alleen Hoge Raad"], periode: [2020, 2024] } });
const EIND = { type: "regie", fase: "eind", regie_id: "d1", soort: "subagent", uitkomst: "wacht", opgeleverd: 1, wacht: 1,
  kinderen: [{ gesprek_id: "g1", uitkomst: "klaar", profiel: "algemeen" },
    { gesprek_id: "g2", uitkomst: "vraag", profiel: "duiding", vragen: [{ tekst: "Welke periode?" }] }] };

function speel(...events: unknown[]): DelegatieVoortgang[] {
  return events.reduce<DelegatieVoortgang[]>((s, e) => verwerkDelegatieEvent(s, e) ?? s, []);
}

describe("verwerkDelegatieEvent", () => {
  it("bouwt het plan en de stand per kind op", () => {
    const [d] = speel(START, KIND_START(0, "g1"));
    expect(d.soort).toBe("subagent");
    expect(d.taken.map((t) => t.stand)).toEqual(["loopt", "gepland"]);
    expect(d.taken[0]).toMatchObject({ gesprek_id: "g1", profiel: "algemeen", model: "licht" });
  });

  it("neemt het echte model, de afbakening en de periode van het eind over", () => {
    const [d] = speel(START, KIND_START(0, "g1"), KIND_EIND(0, "g1", "klaar"));
    expect(d.taken[0]).toMatchObject({ stand: "klaar", model: "zwaar", afbakening: ["alleen Hoge Raad"], periode: [2020, 2024] });
    expect(taakMeta(d.taken[0])).toBe("subagent algemeen · zwaar · afbakening: alleen Hoge Raad · periode 2020–2024");
  });

  it("zet bij het eind elk kind op zijn uitkomst, ook een vraag", () => {
    const [d] = speel(START, KIND_START(0, "g1"), KIND_EIND(0, "g1", "klaar"), KIND_START(1, "g2"), EIND);
    expect(d.afgerond).toBe(true);
    expect(d.status).toBe("wacht");
    expect(d.taken.map((t) => t.stand)).toEqual(["klaar", "vraag"]);
    expect(delegatieSamenvatting(d)).toBe("2 subagents · 1 klaar · 1 wacht op antwoord");
  });

  it("een kind dat niet aan bod kwam, heet zo", () => {
    const [d] = speel(START, KIND_START(0, "g1"), { ...EIND, uitkomst: "gestopt", kinderen: [{ gesprek_id: "g1", uitkomst: "gestopt" }] });
    expect(d.taken.map((t) => t.stand)).toEqual(["gestopt", "overgeslagen"]);
  });

  it("bij het hervatten koppelt het eind op het deelgesprek, niet op de plek", () => {
    const hervat = { ...START, hervat: true, plan: { opdracht: "subagent", taken: [{ titel: "Uitspraak B", profiel: "duiding" }] } };
    const [d] = speel(hervat, KIND_START(0, "g2"), { ...EIND, uitkomst: "klaar",
      kinderen: [{ gesprek_id: "g1", uitkomst: "klaar" }, { gesprek_id: "g2", uitkomst: "klaar" }] });
    expect(d.hervat).toBe(true);
    expect(d.taken).toHaveLength(1);
    expect(d.taken[0]).toMatchObject({ gesprek_id: "g2", stand: "klaar" });
  });

  it("een kind dat niet startte (niet_gestart) kwam niet aan bod, het mislukte niet", () => {
    const [d] = speel(START, KIND_START(0, "g1"), KIND_EIND(0, "g1", "klaar"), { ...EIND, uitkomst: "klaar",
      kinderen: [{ gesprek_id: "g1", uitkomst: "klaar" }, { gesprek_id: "", uitkomst: "niet_gestart" }] });
    expect(d.taken.map((t) => t.stand)).toEqual(["klaar", "overgeslagen"]);
    expect(voortgangUitDelegatie({ ...API, status: "klaar",
      uitkomst: { kinderen: [{ gesprek_id: "g1", uitkomst: "klaar" }, { uitkomst: "niet_gestart" }] } }).taken[1].stand)
      .toBe("overgeslagen");
  });

  it("een onbekende uitkomst is mislukt; een ongeldig event laat de stand staan", () => {
    const voor = speel(START, KIND_START(0, "g1"));
    expect(verwerkDelegatieEvent(voor, { type: "regie_taak", fase: "eind" })).toBeUndefined();
    expect(verwerkDelegatieEvent(voor, { type: "regie", fase: "eind", regie_id: "onbekend" })).toBeUndefined();
    expect(verwerkDelegatieEvent(voor, "onzin")).toBeUndefined();
    const [d] = speel(START, KIND_EIND(0, "g1", "raar"));
    expect(d.taken[0].stand).toBe("mislukt");
  });

  it("de stroom opnieuw afspelen geeft dezelfde stand", () => {
    const events = [START, KIND_START(0, "g1"), KIND_EIND(0, "g1", "klaar")];
    expect(speel(...events, START, ...events.slice(1))).toEqual(speel(...events));
  });

  it("de regie van ADR-012 werkt op dezelfde manier, zonder profiel", () => {
    const [d] = speel({ type: "regie", fase: "start", regie_id: "r1", plan: { taken: [{ titel: "Deelvraag 1" }] } },
      { type: "regie_taak", fase: "start", regie_id: "r1", index: 0, titel: "Deelvraag 1", gesprek_id: "g9" },
      { type: "regie_taak", fase: "eind", regie_id: "r1", index: 0, gesprek_id: "g9", uitkomst: "klaar" },
      { type: "regie", fase: "eind", regie_id: "r1", uitkomst: "klaar", opgeleverd: 1, mislukt: 0 });
    expect(d.soort).toBe("regie");
    expect(d.taken).toEqual([{ titel: "Deelvraag 1", profiel: "", gesprek_id: "g9", stand: "klaar" }]);
    expect(delegatieSamenvatting(d)).toBe("1 deelgesprek · 1 klaar");
    // Sinds graph-qa #1521 draagt de start van een regiekind `profiel: retrieval`: dat is geen subagent.
    const [r] = speel({ type: "regie", fase: "start", regie_id: "r2", plan: { taken: [{ titel: "Deelvraag 1" }] } },
      { type: "regie_taak", fase: "start", regie_id: "r2", index: 0, titel: "Deelvraag 1", gesprek_id: "g9", profiel: "retrieval" });
    expect(taakMeta(r.taken[0], r.soort)).toBe("profiel retrieval");
  });

  it("de stroomstand houdt de delegaties bij", () => {
    const s = [START, KIND_START(0, "g1")].reduce((st, event) =>
      stroomReducer(st, { type: "delegatie", event: event as Record<string, unknown> }), LEGE_STAND);
    expect(s.delegaties[0].taken[0].stand).toBe("loopt");
    expect(weergaveUitStroom(s.delegaties)?.ids).toEqual(["d1"]);
  });
});

const API: Delegatie = {
  id: "d1", soort: "subagent", werkgebied_id: "", gesprek_id: "ouder", opdracht: "subagent", status: "wacht",
  plan: { taken: [{ titel: "Uitspraak A", profiel: "algemeen" }, { titel: "Uitspraak B", profiel: "duiding" }] },
  uitkomst: { kinderen: [{ gesprek_id: "g1", uitkomst: "klaar", modellen: ["zwaar"] }, { gesprek_id: "g2", uitkomst: "vraag" }] },
  later_gewijzigd: false,
};

describe("de stand bij de api", () => {
  it("leest per kind de afloop, in de volgorde van het plan", () => {
    const d = voortgangUitDelegatie(API);
    expect(d.taken.map((t) => [t.gesprek_id, t.stand, t.model])).toEqual([["g1", "klaar", "zwaar"], ["g2", "vraag", undefined]]);
    expect(d.afgerond).toBe(true);
  });

  it("noemt de vragen die Lex zelf uit het dossier beantwoordde", () => {
    const d = voortgangUitDelegatie({ ...API, uitkomst: { kinderen: [
      { gesprek_id: "g1", uitkomst: "klaar", zelf_beantwoord: [{ vraag: "Welke periode?", antwoord: "2024" }] }] } });
    expect(d.taken[0].zelfBeantwoord).toBe(1);
    expect(taakMeta(d.taken[0])).toBe("subagent algemeen · 1 vraag door Lex beantwoord uit het dossier");
  });

  it("een plan dat op de bevestiging wacht, is gepland; een lopende delegatie loopt", () => {
    expect(voortgangUitDelegatie({ ...API, uitkomst: {} }).taken.map((t) => t.stand)).toEqual(["gepland", "gepland"]);
    expect(voortgangUitDelegatie({ ...API, status: "loopt", uitkomst: {} }).taken.map((t) => t.stand)).toEqual(["loopt", "gepland"]);
  });

  it("toont zolang de beurt loopt de stroom, daarna de api, en anders de stroom als terugval", () => {
    const live = speel(START, KIND_START(0, "g1"));
    const w = weergaveUitStroom(live)!;
    expect(teTonen(w, [API], true)[0].taken[0].stand).toBe("loopt");
    expect(teTonen(w, [API], false)[0].taken[1].stand).toBe("vraag");
    expect(teTonen(w, [], false)[0].taken[0].stand).toBe("loopt");
    expect(teTonen({ ids: ["d1"] }, null, false)).toEqual([]);
  });

  it("geeft de sidebar per deelgesprek de stand, de nieuwste delegatie eerst", () => {
    const nieuwer: Delegatie = { ...API, id: "d2", status: "klaar",
      uitkomst: { kinderen: [{ gesprek_id: "g1", uitkomst: "klaar" }, { gesprek_id: "g2", uitkomst: "klaar" }] } };
    const per = standenPerDeelgesprek([nieuwer, API]);
    expect(per).toEqual({ g1: "klaar", g2: "klaar" });
    const regie: Delegatie = { ...API, id: "r1", soort: "regie", status: "loopt", uitkomst: {} };
    expect(standVanDeelgesprek({ id: "g7", delegatie_id: "r1" }, per, [regie])).toBe("loopt");
    expect(standVanDeelgesprek({ id: "g8" }, per, [regie])).toBeUndefined();
  });

  it("laat een rij die niet klopt weg", () => {
    expect(parseDelegaties([API, { id: 3 }, { ...API, status: "raar" }, null])).toHaveLength(1);
    expect(parseDelegaties({ fout: "x" })).toEqual([]);
  });
});

describe("het bewaarde bericht", () => {
  it("draagt de id's, en het blok staat er na herladen", () => {
    expect(weergaveUitBericht(["d1", 3, ""])).toEqual({ ids: ["d1"] });
    expect(weergaveUitBericht(undefined)).toBeUndefined();
    let n = 0;
    const { items } = itemsUitGesprek([
      { rol: "assistant", tekst: "De bundel.", denk: "", bronnen: [], run_id: "r", delegaties: ["d1"] },
      { rol: "assistant", tekst: "Gewoon.", denk: "", bronnen: [], run_id: "r2" },
    ], () => `i${n++}`);
    expect(items[0]).toMatchObject({ type: "antwoord", delegatie: { ids: ["d1"] } });
    expect(items[1]).not.toHaveProperty("delegatie");
  });

  it("de bundel van een regie houdt de knop voor de volgende fase, ook na herladen, tot hij gekozen is", () => {
    let n = 0;
    const bevestiging = { soort: "regie", werkgebied_id: "wg1", opdracht: "annoteren", plan_id: "0".repeat(16), aantal: 2, schatting: null };
    const bericht = { rol: "assistant" as const, tekst: "Klaar.", denk: "", bronnen: [], run_id: "r", delegaties: ["r5"],
      artefact: { soort: "regie" as const, ref: { werkgebied_id: "wg1", regie_id: "r5" }, titel: "Regie" }, bevestiging };
    const { items } = itemsUitGesprek([bericht as never], () => `i${n++}`);
    expect(items[0]).toMatchObject({ type: "artefact", bevestiging: { plan_id: "0".repeat(16), opdracht: "annoteren" } });
    const gekozen = itemsUitGesprek([bericht as never,
      { rol: "user", tekst: "Annoteer", denk: "", bronnen: [], run_id: "", bevestiging_antwoord: { keuze: "gestart" } }], () => `j${n++}`);
    expect(afgehandeld(gekozen.items).get(gekozen.items[0].id)).toBe("gestart");
  });

  it("een bericht dat de code in een deelgesprek doorgaf, is geen bericht van de jurist", () => {
    let n = 0;
    const { items } = itemsUitGesprek([
      { rol: "user", tekst: "OPDRACHT …", denk: "", bronnen: [], run_id: "", doorgegeven: "opdracht" },
      { rol: "user", tekst: "Mijn vraag", denk: "", bronnen: [], run_id: "" },
      { rol: "user", tekst: "ANTWOORD OP JE VRAGEN …", denk: "", bronnen: [], run_id: "", doorgegeven: "antwoorden" },
    ], () => `i${n++}`);
    expect(items.map((i) => (i.type === "user" ? i.doorgegeven ?? "jurist" : i.type))).toEqual(["opdracht", "jurist", "antwoorden"]);
  });
});
