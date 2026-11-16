import { strict as assert } from "node:assert";
import { test } from "node:test";
import { auditStaart, inventarisOverzicht, kortElement, TEKST_KORT } from "./vorm.js";

const el = (id: string, eigenaar: string, klasse: string, lifecycle = "voorgesteld", tekst = "de belastingschuldige") =>
  ({ id, eigenaar_iri: eigenaar, klasse, lifecycle, tekst, ankers: [{ bron_iri: eigenaar, start: 0, eind: 5 }],
     toelichting: "lang verhaal", aandacht: "groen" });

test("het overzicht telt de elementen en laat ze weg", () => {
  const inv = { selecties: [{ id: "s1" }], volledig: true, afgewezen: [el("x", "a", "Operator")], vervangen: [],
    elementen: [el("1", "a", "Rechtssubject"), el("2", "a", "Rechtsobject"), el("3", "b", "Rechtssubject", "edited")] };
  const uit = inventarisOverzicht(inv);
  assert.equal(uit.aantal, 3);
  assert.equal(uit.afgewezen, 1);
  assert.deepEqual(uit.per_bepaling, { a: 2, b: 1 });
  assert.deepEqual(uit.per_klasse, { Rechtssubject: 2, Rechtsobject: 1 });
  assert.deepEqual(uit.per_lifecycle, { voorgesteld: 2, edited: 1 });
  assert.equal("elementen" in uit, false);
});

test("met een bepaling de elementen daarvan in korte vorm, zonder ankers en toelichting", () => {
  const inv = { selecties: [], volledig: true, elementen: [el("1", "a", "Rechtssubject"), el("3", "b", "Operator")] };
  const uit = inventarisOverzicht(inv, "b") as { elementen: Record<string, unknown>[] };
  assert.deepEqual(uit.elementen.map((e) => e.id), ["3"]);
  assert.equal("ankers" in uit.elementen[0], false);
  assert.equal("toelichting" in uit.elementen[0], false);
});

test("een lange tekst wordt ingekort, met een ellips", () => {
  const e = kortElement(el("1", "a", "Voorwaarde", "voorgesteld", "x".repeat(TEKST_KORT + 30)));
  assert.equal((e.tekst as string).length, TEKST_KORT + 1);
  assert.ok((e.tekst as string).endsWith("…"));
});

test("de audit: de nieuwste regels eerst, zoals de api ze geeft", () => {
  const uit = auditStaart({ audit: [{ id: 30 }, { id: 29 }, { id: 28 }] }, 2);
  assert.equal(uit.gelezen, 3);
  assert.deepEqual(uit.nieuwste, [{ id: 30 }, { id: 29 }]);
  assert.deepEqual(auditStaart({ status: 500 }), { gelezen: 0, nieuwste: [] });
});
