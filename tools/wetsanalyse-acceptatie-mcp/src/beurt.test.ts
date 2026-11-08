import assert from "node:assert/strict";
import { test } from "node:test";
import { type Bff, lexStart, vraagBericht } from "./beurt.js";

test("een getypte vraag is een gewoon user-bericht", () => {
  assert.deepEqual(vraagBericht({ question: "Wat is een belastingaanslag?", conversation_id: "g1" }),
    { rol: "user", tekst: "Wat is een belastingaanslag?" });
});

test("een klik op een suggestie (actie) is ook een gewoon user-bericht", () => {
  assert.deepEqual(vraagBericht({ question: "Stel deelvragen voor", actie: "deelvragen_opstellen", werkgebied_id: "w" }),
    { rol: "user", tekst: "Stel deelvragen voor" });
});

test("een vraagkaart-klik krijgt de velden van antwoordOp, en niet meer", () => {
  const b = vraagBericht({
    question: "Verder",
    intake_actie: { intake_id: "ab-12", stap: "bepalingen", deel: 0, actie: "klaar", deelvraag_id: "dv-1",
      keuzes: ["x"], tekst: "vrij", naar: "naam" },
  });
  assert.deepEqual(b.intake_antwoord, { intake_id: "ab-12", stap: "bepalingen", deel: 0, actie: "klaar",
    deelvraag_id: "dv-1" });
  // Zonder deel en deelvraag: die velden blijven weg.
  assert.deepEqual(vraagBericht({ question: "Ja", intake_actie: { intake_id: "c", stap: "naam", actie: "antwoord",
    deelvraag_id: "" } }).intake_antwoord, { intake_id: "c", stap: "naam", actie: "antwoord" });
});

test("een onvolledige intake_actie levert geen intake_antwoord op", () => {
  for (const k of [{ stap: "naam", actie: "antwoord" }, "tekst", ["a"], null, { intake_id: "c", stap: "naam" }]) {
    assert.equal("intake_antwoord" in vraagBericht({ question: "x", intake_actie: k }), false, JSON.stringify(k));
  }
});

test("een bevestigingsknop: bevestigd (ook 0) of een regieplan", () => {
  assert.deepEqual(vraagBericht({ question: "Annoteer", bevestigd: 0 }).bevestiging_antwoord, { keuze: "gestart" });
  assert.deepEqual(vraagBericht({ question: "Start", actie: "regie_bronnen", plan_id: "p1" }).bevestiging_antwoord,
    { keuze: "gestart" });
  assert.equal("bevestiging_antwoord" in vraagBericht({ question: "x", plan_id: "" }), false);
});

function nepBff(fout?: "status" | "gooit"): Bff & { aanroepen: { methode: string; pad: string; body: unknown }[] } {
  const aanroepen: { methode: string; pad: string; body: unknown }[] = [];
  return {
    aanroepen,
    async bff(methode, pad, body) {
      aanroepen.push({ methode, pad, body });
      if (pad.endsWith("/berichten")) {
        if (fout === "gooit") throw new Error("time-out");
        return fout === "status" ? { status: 502, trace_id: "t", data: { detail: "weg" } }
          : { status: 201, trace_id: "t", data: { id: 1 } };
      }
      return { status: 202, trace_id: "t2", data: { run_id: "r1" } };
    },
  };
}

test("lex_start bewaart eerst de vraag en start dan de run, met dezelfde body als voorheen", async () => {
  const c = nepBff();
  const r = await lexStart(c, { vraag: "Wat?", conversation_id: "g/1", werkgebied_id: "w1",
    intake_actie: { intake_id: "i", stap: "naam", actie: "antwoord" }, extra: { modus: "x" } });
  assert.deepEqual(c.aanroepen.map((x) => x.pad), ["/api/gesprekken/g%2F1/berichten", "/api/annotatie/run"]);
  assert.deepEqual(c.aanroepen[0].body, { rol: "user", tekst: "Wat?",
    intake_antwoord: { intake_id: "i", stap: "naam", actie: "antwoord" } });
  assert.deepEqual(c.aanroepen[1].body, { question: "Wat?", conversation_id: "g/1", modus: "x", werkgebied_id: "w1",
    intake_actie: { intake_id: "i", stap: "naam", actie: "antwoord" } });
  // Het antwoord van de run blijft wat het was; `vraag` komt erbij.
  assert.equal(r.status, 202);
  assert.deepEqual(r.data, { run_id: "r1" });
  assert.equal(r.trace_id, "t2");
  assert.deepEqual(r.vraag, { status: 201 });
});

test("mislukt het bewaren, dan start de run toch en staat de fout in vraag", async () => {
  for (const soort of ["status", "gooit"] as const) {
    const c = nepBff(soort);
    const r = await lexStart(c, { vraag: "Wat?", conversation_id: "g1" });
    assert.equal(c.aanroepen.length, 2);
    assert.deepEqual(r.data, { run_id: "r1" });
    assert.ok(r.vraag?.fout, soort);
  }
});

test("vraag_bewaren: false start alleen de run", async () => {
  const c = nepBff();
  const r = await lexStart(c, { vraag: "Wat?", conversation_id: "g1", vraag_bewaren: false });
  assert.deepEqual(c.aanroepen.map((x) => x.pad), ["/api/annotatie/run"]);
  assert.equal("vraag" in r, false);
});
