/**
 * `node dist/keten-cli.js <run>`: het ketenscenario (`keten.ts`) tegen acceptatie, voor de workflow `acceptatie-keten`.
 * Leest `WETSANALYSE_ACC_URL` en `WETSANALYSE_ACC_TOKEN` uit de omgeving; beide komen uit de environment `acceptatie`.
 */
import { AcceptatieClient, controleerUrl } from "./client.js";
import { ketenScenario } from "./keten.js";
const url = process.env.WETSANALYSE_ACC_URL ?? "";
const token = (process.env.WETSANALYSE_ACC_TOKEN ?? "").trim();
const run = process.argv[2] ?? "";
if (!url || !token || !/^[\w.-]{1,60}$/.test(run)) {
    console.error("Gebruik: WETSANALYSE_ACC_URL=… WETSANALYSE_ACC_TOKEN=… node dist/keten-cli.js <run>");
    process.exit(2);
}
const uitkomst = await ketenScenario(new AcceptatieClient(controleerUrl(url), token), run);
for (const s of uitkomst.stappen)
    console.log(`${s.ok ? "ok  " : "FOUT"} ${s.stap}${s.detail ? ` (${s.detail})` : ""}`);
process.exit(uitkomst.ok ? 0 : 1);
