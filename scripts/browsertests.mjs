/** Draait één deel (shard) van de browserregressie, voor de parallelle jobs in `poort.yml`.
 *
 *   node ../scripts/browsertests.mjs 2/4      (vanuit frontend/, Next draait al, zie test-annotatie-nodes.mjs)
 *   node ../scripts/browsertests.mjs --lijst  (de indeling tonen, zonder iets te draaien)
 *
 * Het staat bij het gereedschap van de poort (naast `kruistests.sh` en `pytest_shard.py`); een wijziging eraan
 * draait de browserregressie (zie de detectie in `poort.yml`). De lijst komt uit `test:browser` in frontend/package.json – die blijft de enige bron, dus een nieuwe browsertest
 * hoeft niet hier bij te worden gezet en kan in de poort niet wegvallen. Lokaal draait `npm run test:browser`
 * gewoon alles na elkaar.
 *
 * Verdeling: grootste eerst naar de lichtste shard, op de duur in GEWICHT (seconden, gemeten in de poort van
 * 12 nov 2026, inclusief het compileren van een route door `next dev`). Die tijden sturen alleen de balans; een
 * test die er niet in staat telt als ONBEKEND. Bijhouden is dus nooit nodig voor de juistheid.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

const GEWICHT = {
  "test-annotatie-nodes": 20, "test-samenhang": 80, "test-reeks": 6, "test-toetsen": 17, "test-werkgebieden": 22,
  "test-begrippen": 18, "test-begripvoorstellen": 13, "test-artefacten": 21, "test-bronkandidaten": 7,
  "test-werkgebied-annoteren": 9, "test-begrippen-verdieping": 6, "test-herbeoordeling": 4, "test-begriprelaties": 7,
  "test-begrippengraaf": 4, "test-begrippenoverzicht": 5, "test-generieke-begrippen": 6, "test-deelvragen": 6,
  "test-werkgebied-intake": 5, "test-dossier-aanvullen": 2, "test-bronselectie": 5, "test-bronselectie-paneel": 4,
  "test-vraaglex": 5, "test-beurtuitkomst": 5, "test-sidebar-groepen": 4, "test-gesprekken-opruimen": 4,
  "test-teststrook": 10, "test-runstanden": 19, "test-detailpaginas": 5, "test-contextpaneel": 5, "test-zijpaneel": 5,
  "test-bronvenster-stuk": 6, "test-bronvenster-bekendmaking": 4, "test-bronvenster-wettekst": 4,
  "test-rondleiding": 50, "test-api-tokens": 3, "test-connectors": 3, "test-connectors-menu": 24,
  "test-instellingen": 17, "test-instellingen-breedte": 61, "test-antwoordweergave": 11,
};
const ONBEKEND = 8;
const FRONTEND = fileURLToPath(new URL("../frontend/", import.meta.url));

export function lijst() {
  const pakket = JSON.parse(readFileSync(new URL("../frontend/package.json", import.meta.url), "utf8"));
  const tests = [...pakket.scripts["test:browser"].matchAll(/node (scripts\/[\w-]+\.mjs)/g)].map((m) => m[1]);
  if (!tests.length) throw new Error("geen browsertests gevonden in scripts.test:browser");
  return tests;
}

export function verdeel(tests, totaal) {
  const naam = (t) => t.replace(/^scripts\//, "").replace(/\.mjs$/, "");
  const duur = (t) => GEWICHT[naam(t)] ?? ONBEKEND;
  const shards = Array.from({ length: totaal }, () => ({ tests: [], duur: 0 }));
  const opDuur = tests.map((t, i) => [t, i]).sort((a, b) => duur(b[0]) - duur(a[0]) || a[1] - b[1]);
  for (const [t] of opDuur) {
    const doel = shards.reduce((min, s) => (s.duur < min.duur ? s : min), shards[0]);
    doel.tests.push(t);
    doel.duur += duur(t);
  }
  // Binnen een shard in de volgorde van package.json, zodat een shard leest als een stuk van de lijst.
  for (const s of shards) s.tests.sort((a, b) => tests.indexOf(a) - tests.indexOf(b));
  return shards;
}

const arg = process.argv[2] ?? "";
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const tests = lijst();
  if (arg === "--lijst") {
    const n = Number(process.argv[3] ?? 4);
    verdeel(tests, n).forEach((s, i) => console.log(`shard ${i + 1}/${n} (~${s.duur} s): ${s.tests.join(" ")}`));
    process.exit(0);
  }
  const m = /^(\d+)\/(\d+)$/.exec(arg);
  if (!m || +m[1] < 1 || +m[1] > +m[2]) {
    console.error("gebruik: node scripts/browsertests.mjs i/n   (1 <= i <= n)");
    process.exit(2);
  }
  const shard = verdeel(tests, +m[2])[+m[1] - 1];
  console.log(`browsertests shard ${arg}: ${shard.tests.length} van ${tests.length} (~${shard.duur} s)`);
  for (const t of shard.tests) {
    const begin = Date.now();
    console.log(`─── ${t}`);
    const r = spawnSync(process.execPath, [t], { stdio: "inherit", cwd: FRONTEND });
    console.log(`    ${t}: ${((Date.now() - begin) / 1000).toFixed(1)} s`);
    // Net als de `&&`-keten van test:browser: de eerste fout stopt de shard.
    if (r.status !== 0) process.exit(r.status ?? 1);
  }
}
