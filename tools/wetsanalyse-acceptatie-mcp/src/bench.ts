/**
 * Lex Bench: de opdracht lezen en het formulier inleveren, buiten de context van de coördinator (pilot LB3, bevinding 1).
 *
 * In de pilot ging de opdracht van een agent (17.000 tot 30.000 tekens) letterlijk in zijn prompt, en kwam zijn formulier
 * als laatste bericht terug bij de coördinator. Die context was de grootste post van de pilot. Nu legt de coördinator de
 * opdracht in de runmap (`eval.lex_bench_team … --naar-run`), naast het logboek in `docs/acceptatie/lokaal/<run>/`
 * (gitignored), en geeft de agent alleen de runnaam mee.
 *
 * - `bench_opdracht_lezen` leest `opdracht.md`, in delen als ze groot is.
 * - `bench_inleveren` schrijft elke poging als `inlevering-<n>.json` (nooit overschreven: wat een agent inleverde, is
 *   bewijs), laat de controle van Lex Bench erop los (`eval.lex_bench_inleveren controleer`, dezelfde als
 *   `controleer`/`verwerk` bij de coördinator) en geeft de fouten terug, zodat de agent ze zelf herstelt. Een geldig
 *   formulier wordt ook `ingeleverd.json`, en daarna is er niets meer in te leveren.
 *
 * De agent heeft geen schrijftools en geen shell; dit is, naast het logboek, zijn enige schrijfweg, en die kan alleen
 * een inlevering toevoegen in een runmap met een opdracht.
 */

import { execFile } from "node:child_process";
import { readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

const RUN = /^[a-z0-9][a-z0-9-]{0,63}$/;
/** Hoeveel tekens één leesbeurt teruggeeft; de opdrachten van de pilot passen er in één keer in. */
export const DEEL = 60_000;
/** Na zoveel ongeldige pogingen is het aan de coördinator: een agent die blijft proberen, verbrandt zijn plafond. */
export const MAX_POGINGEN = 5;

export interface Uitkomst {
  geldig: boolean;
  fouten: string[];
}

/** De controle van een inlevering; in de dienst het Python-script, in de tests een nep. */
export type Controle = (run: string, bestand: string) => Promise<Uitkomst>;

function runmap(map: string, run: string): string {
  if (!RUN.test(run)) throw new Error("Een run heet bijvoorbeeld lb-10-2026-11-20-a.");
  return join(map, run);
}

async function bestaat(pad: string): Promise<boolean> {
  try {
    await readFile(pad);
    return true;
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw e;
  }
}

export async function opdrachtLezen(map: string, run: string, vanaf = 0): Promise<{
  tekst: string; vanaf: number; klaar: boolean; lengte: number;
}> {
  let tekst: string;
  try {
    tekst = await readFile(join(runmap(map, run), "opdracht.md"), "utf8");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") {
      throw new Error(`Run ${run} heeft geen opdracht. Controleer de runnaam uit je prompt.`);
    }
    throw e;
  }
  const deel = tekst.slice(vanaf, vanaf + DEEL);
  const verder = vanaf + deel.length;
  return { tekst: deel, vanaf: verder, klaar: verder >= tekst.length, lengte: tekst.length };
}

export async function inleveren(map: string, run: string, formulier: unknown, controle: Controle): Promise<{
  geldig: boolean; fouten: string[]; bestand: string; poging: number;
}> {
  const doel = runmap(map, run);
  if (!(await bestaat(join(doel, "opdracht.json")))) {
    throw new Error(`Run ${run} heeft geen opdracht: er is niets in te leveren.`);
  }
  if (await bestaat(join(doel, "ingeleverd.json"))) {
    throw new Error("Er is al een geldig formulier ingeleverd; het verandert niet meer.");
  }
  const pogingen = (await readdir(doel)).filter((n) => /^inlevering-[0-9]+\.json$/.test(n)).length;
  if (pogingen >= MAX_POGINGEN) {
    throw new Error(`Na ${MAX_POGINGEN} pogingen is het aan de coördinator. Noem in je laatste bericht wat niet lukte.`);
  }
  const poging = pogingen + 1;
  const bestand = `inlevering-${poging}.json`;
  const inhoud = JSON.stringify(formulier, null, 2) + "\n";
  await writeFile(join(doel, bestand), inhoud, { flag: "wx" });
  const uitkomst = await controle(run, bestand);
  if (uitkomst.geldig) await writeFile(join(doel, "ingeleverd.json"), inhoud, { flag: "wx" });
  return { ...uitkomst, bestand, poging };
}

/** De controle van Lex Bench zelf: `uv run python -m eval.lex_bench_inleveren controleer`, in `tools/graph-qa`. */
export function pythonControle(graphQa: string, timeoutMs = 180_000): Controle {
  return (run, bestand) =>
    new Promise((resolve, reject) => {
      execFile(
        "uv",
        ["run", "--quiet", "python", "-m", "eval.lex_bench_inleveren", "controleer", "--run", run, "--bestand", bestand],
        { cwd: graphQa, timeout: timeoutMs, maxBuffer: 4 * 1024 * 1024 },
        (fout, stdout, stderr) => {
          if (fout) {
            reject(new Error(`De controle draaide niet: ${String(stderr || fout.message).trim().slice(-500)}`));
            return;
          }
          try {
            const u = JSON.parse(stdout.trim().split("\n").at(-1) ?? "") as Uitkomst;
            resolve({ geldig: u.geldig === true, fouten: Array.isArray(u.fouten) ? u.fouten.map(String) : [] });
          } catch {
            reject(new Error("De controle gaf geen uitkomst."));
          }
        },
      );
    });
}
