import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { type Controle, DEEL, inleveren, MAX_POGINGEN, opdrachtLezen } from "./bench.js";

async function metRun(doe: (map: string) => Promise<void>, opdracht = "# Opdracht\n"): Promise<void> {
  const map = await mkdtemp(join(tmpdir(), "bench-"));
  try {
    await mkdir(join(map, "lb-10-a"));
    await writeFile(join(map, "lb-10-a", "opdracht.md"), opdracht);
    await writeFile(join(map, "lb-10-a", "opdracht.json"), '{"soort": "analist", "casus": "LB-10"}\n');
    await doe(map);
  } finally {
    await rm(map, { recursive: true });
  }
}

const geldigAls = (ok: (f: unknown) => boolean): Controle => async (run, bestand) => {
  assert.equal(run, "lb-10-a");
  assert.match(bestand, /^inlevering-[0-9]+\.json$/);
  return ok(bestand) ? { geldig: true, fouten: [] } : { geldig: false, fouten: ["$.x: onbekend veld y"] };
};

test("de opdracht komt in delen terug als ze groot is", () =>
  metRun(async (map) => {
    const een = await opdrachtLezen(map, "lb-10-a");
    assert.equal(een.tekst.length, DEEL);
    assert.equal(een.klaar, false);
    const twee = await opdrachtLezen(map, "lb-10-a", een.vanaf);
    assert.equal(twee.klaar, true);
    assert.equal(een.tekst + twee.tekst, "x".repeat(DEEL + 10));
  }, "x".repeat(DEEL + 10)));

test("een run zonder opdracht of met een rare naam weigert", () =>
  metRun(async (map) => {
    await assert.rejects(opdrachtLezen(map, "lb-11-a"), /geen opdracht/);
    for (const run of ["../uit", "a/b", ""]) await assert.rejects(opdrachtLezen(map, run), /Een run heet/);
    await assert.rejects(inleveren(map, "lb-11-a", {}, geldigAls(() => true)), /geen opdracht/);
  }));

test("een fout gaat terug naar de agent, en elke poging blijft staan", () =>
  metRun(async (map) => {
    const fout = await inleveren(map, "lb-10-a", { y: null }, geldigAls(() => false));
    assert.deepEqual([fout.geldig, fout.poging, fout.fouten], [false, 1, ["$.x: onbekend veld y"]]);
    const goed = await inleveren(map, "lb-10-a", { y: 1 }, geldigAls(() => true));
    assert.deepEqual([goed.geldig, goed.bestand], [true, "inlevering-2.json"]);
    const namen = (await readdir(join(map, "lb-10-a"))).sort();
    assert.deepEqual(namen, ["ingeleverd.json", "inlevering-1.json", "inlevering-2.json", "opdracht.json", "opdracht.md"]);
    assert.deepEqual(JSON.parse(await readFile(join(map, "lb-10-a", "inlevering-1.json"), "utf8")), { y: null });
    assert.deepEqual(JSON.parse(await readFile(join(map, "lb-10-a", "ingeleverd.json"), "utf8")), { y: 1 });
  }));

test("een geldig formulier ligt vast", () =>
  metRun(async (map) => {
    await inleveren(map, "lb-10-a", { y: 1 }, geldigAls(() => true));
    await assert.rejects(inleveren(map, "lb-10-a", { y: 2 }, geldigAls(() => true)), /al een geldig formulier/);
  }));

test("na het maximum aantal pogingen is het aan de coördinator", () =>
  metRun(async (map) => {
    for (let i = 0; i < MAX_POGINGEN; i++) await inleveren(map, "lb-10-a", {}, geldigAls(() => false));
    await assert.rejects(inleveren(map, "lb-10-a", {}, geldigAls(() => true)), /aan de coördinator/);
  }));

test("een controle die niet draait, laat de poging staan maar levert niets in", () =>
  metRun(async (map) => {
    const stuk: Controle = async () => { throw new Error("De controle draaide niet: uv ontbreekt"); };
    await assert.rejects(inleveren(map, "lb-10-a", { y: 1 }, stuk), /draaide niet/);
    const namen = await readdir(join(map, "lb-10-a"));
    assert.ok(namen.includes("inlevering-1.json"));
    assert.ok(!namen.includes("ingeleverd.json"));
  }));
