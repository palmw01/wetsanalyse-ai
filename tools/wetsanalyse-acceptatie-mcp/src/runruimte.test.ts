import assert from "node:assert/strict";
import { test } from "node:test";
import type { BffAntwoord } from "./client.js";
import { type Bff, isVerwijderend, opruimplan, toetsVerwijderen, voerUit } from "./runruimte.js";

/** Een nep-BFF met een paar gesprekken en werkgebieden; houdt bij wat er verwijderd werd. */
function nepBff(): Bff & { verwijderd: string[] } {
  const gesprekken: Record<string, object> = {
    g1: { titel: "acc-test-run1 vraag" },
    g2: { titel: "Mijn eigen analyse" },
    g3: { titel: "Werkgebied: x", werkgebied_id: "w1" },
    g4: { titel: "deelvraag", ouder_id: "g1" },
    g5: { titel: "lex-bench-keten · gh-1-1 gesprek" },
  };
  const werkgebieden: Record<string, object> = {
    w1: { naam: "acc-test-run1 Verrekening", aangemaakt_door: "gebruiker", revisie: 3 },
    w2: { naam: "acc-test-run1 van een ander", aangemaakt_door: "jurist", revisie: 1 },
    w3: { naam: "Inning", aangemaakt_door: "gebruiker", revisie: 1 },
  };
  const verwijderd: string[] = [];
  return {
    verwijderd,
    async bff(methode: string, pad: string): Promise<BffAntwoord> {
      const [, , soort, id] = pad.split("?")[0].split("/");
      const bak = soort === "gesprekken" ? gesprekken : werkgebieden;
      if (methode === "DELETE") {
        verwijderd.push(pad);
        return { status: 204, trace_id: "", data: null };
      }
      return id in bak ? { status: 200, trace_id: "", data: bak[id] } : { status: 404, trace_id: "", data: null };
    },
  };
}

const IK = "gebruiker";

test("[R19] verwijderend: een DELETE of een route die op verwijderen eindigt; lezen niet", () => {
  assert.ok(isVerwijderend("DELETE", "/api/gesprekken/g1"));
  assert.ok(isVerwijderend("POST", "/api/gesprekken/verwijderen"));
  assert.ok(isVerwijderend("post", "/api/werkgebieden/w1/bronnen/b1/verwijder?x=1"));
  assert.ok(!isVerwijderend("GET", "/api/gesprekken"));
  assert.ok(!isVerwijderend("POST", "/api/gesprekken"));
  assert.ok(!isVerwijderend("POST", "/api/gesprekken/archiveren"));
});

test("[R19] de vangrail: alleen de eigen ruimte van een testrun", async () => {
  const c = nepBff();
  const mag = async (m: string, p: string) => (await toetsVerwijderen(c, m, p, IK)).mag;
  assert.ok(await mag("DELETE", "/api/gesprekken/g1"), "titel met voorvoegsel");
  assert.ok(await mag("DELETE", "/api/gesprekken/g5"), "het voorvoegsel van het ketenscenario");
  assert.ok(await mag("DELETE", "/api/gesprekken/g3"), "in een werkgebied van de run");
  assert.ok(await mag("DELETE", "/api/gesprekken/g4"), "onder een gesprek van de run");
  assert.ok(!(await mag("DELETE", "/api/gesprekken/g2")), "een gesprek van de gebruiker");
  assert.ok(!(await mag("DELETE", "/api/gesprekken/onbekend")), "niet te lezen = niet verwijderen");
  assert.ok(await mag("DELETE", "/api/werkgebieden/w1?verwachte_revisie=3"));
  assert.ok(!(await mag("DELETE", "/api/werkgebieden/w2?verwachte_revisie=1")), "door een ander gemaakt");
  assert.ok(!(await mag("DELETE", "/api/werkgebieden/w3?verwachte_revisie=1")), "geen voorvoegsel");
  assert.ok(!(await mag("POST", "/api/gesprekken/verwijderen")), "bulk");
  assert.ok(!(await mag("DELETE", "/api/gesprekken/groep/oud")), "bulk per groep");
  assert.ok(!(await mag("DELETE", "/api/annotatie/laag/l1")), "gedeeld");
  assert.ok(!(await mag("DELETE", "/api/begrippen/generiek/b1")), "gedeeld");
  assert.ok(!(await toetsVerwijderen(c, "DELETE", "/api/gesprekken/g1", "")).mag, "zonder account geen oordeel");
  assert.ok(await mag("GET", "/api/gesprekken/g2"), "lezen gaat niet langs de vangrail");
});

test("[R19] opruimplan: de run, met deelgesprekken vóór hun ouder, en niets van een ander", () => {
  const plan = opruimplan("acc-test-run1", IK,
    [
      { id: "w1", naam: "acc-test-run1 Verrekening", aangemaakt_door: IK, revisie: 3 },
      { id: "w2", naam: "acc-test-run1 van een ander", aangemaakt_door: "jurist", revisie: 1 },
      { id: "w9", naam: "acc-test-run2 Ander", aangemaakt_door: IK, revisie: 1 },
    ],
    [
      { id: "g1", titel: "acc-test-run1 vraag" },
      { id: "g2", titel: "Mijn eigen analyse" },
      { id: "g3", titel: "Werkgebied: x", werkgebied_id: "w1" },
      { id: "g4", titel: "deelvraag", ouder_id: "g1" },
      { id: "g5", titel: "deel van deel", ouder_id: "g4" },
      { id: "g6", titel: "in w2", werkgebied_id: "w2" },
    ]);
  assert.deepEqual(plan.werkgebieden.map((w) => w.id), ["w1"]);
  const ids = plan.gesprekken.map((g) => g.id);
  assert.deepEqual([...ids].sort(), ["g1", "g3", "g4", "g5"]);
  assert.ok(ids.indexOf("g5") < ids.indexOf("g4") && ids.indexOf("g4") < ids.indexOf("g1"));
  assert.throws(() => opruimplan("Mijn", IK, [], []), /voorvoegsel/);
  assert.throws(() => opruimplan("", IK, [], []), /voorvoegsel/);
});

test("[R19] uitvoeren: gesprekken eerst, werkgebied met zijn revisie, en de vangrail toetst elk", async () => {
  const c = nepBff();
  const plan = {
    voorvoegsel: "acc-test-run1",
    werkgebieden: [{ id: "w1", naam: "acc-test-run1 Verrekening", aangemaakt_door: IK, revisie: 3 }],
    gesprekken: [{ id: "g4", titel: "deelvraag", ouder_id: "g1" }, { id: "g1", titel: "acc-test-run1 vraag" },
      { id: "g2", titel: "Mijn eigen analyse" }],
  };
  const uit = await voerUit(c, plan, IK);
  assert.deepEqual(c.verwijderd, ["/api/gesprekken/g4", "/api/gesprekken/g1", "/api/werkgebieden/w1?verwachte_revisie=3"]);
  assert.equal(uit.geweigerd.length, 1);
  assert.match(uit.geweigerd[0], /g2/);
});
