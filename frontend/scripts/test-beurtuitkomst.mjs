/** Browserregressie voor de afloop van een beurt (verbeterplan C3). Op de echte Next-UI met een gemockte BFF.
 * Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-beurtuitkomst.mjs`.
 *
 * Bewaakt:
 *  - een mislukte beurt toont live dezelfde melding als na herladen, zonder "(geen antwoord)";
 *  - een stroom die sluit zonder `done` is geen afgeronde beurt: de werkplek haakt opnieuw aan en krijgt de uitkomst;
 *  - stoppen zegt live wat er na herladen staat;
 *  - de werkplek schrijft nooit zelf een assistent-bericht: de server is de enige schrijver.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [], geschreven = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const MELDING = "Deze beurt werd te lang en is afgebroken.";
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const scenario = {
  mislukt: [[{ type: "status", message: "Graaf bevragen" }, { type: "error", message: MELDING }, { type: "done", uitkomst: "mislukt" }]],
  // Eerst sluit de stroom halverwege; de tweede poging speelt de log af.
  verbroken: [[{ type: "status", message: "Graaf bevragen" }],
    [{ type: "token", content: "Het antwoord." }, { type: "opgeslagen", run_id: "verbroken" }, { type: "done", uitkomst: "klaar" }]],
  gestopt: [[{ type: "token", content: "Half\n\n_(gestopt)_" }, { type: "opgeslagen", run_id: "gestopt" }, { type: "done", uitkomst: "gestopt" }]],
};
const berichten = {
  mislukt: [{ rol: "user", tekst: "mislukt", ...leeg },
    { rol: "assistant", tekst: "", ...leeg, run_id: "mislukt", uitkomst: { status: "mislukt", melding: MELDING } }],
  gestopt: [{ rol: "user", tekst: "gestopt", ...leeg },
    { rol: "assistant", tekst: "Half\n\n_(gestopt)_", ...leeg, run_id: "gestopt", uitkomst: { status: "gestopt" } }],
};
let gid = "mislukt";
const pogingen = {};

await page.route("**/api/**", async (route) => {
  const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/annotatie/run") {
    if (m === "GET") return route.fulfill({ json: null });
    return route.fulfill({ json: { run_id: gid, conversation_id: gid, status: "loopt" } });
  }
  const run = p.match(/^\/api\/annotatie\/run\/(\w+)\/events$/);
  if (run) {
    const n = pogingen[run[1]] = (pogingen[run[1]] ?? 0) + 1;
    const lijst = scenario[run[1]];
    return route.fulfill({ contentType: "text/event-stream", body: sse(lijst[Math.min(n, lijst.length) - 1]) });
  }
  const gesprek = p.match(/^\/api\/gesprekken\/(\w+)$/);
  if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: gesprek[1], berichten: berichten[gesprek[1]] ?? [] } });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: gid, titel: "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.endsWith("/berichten") && m === "POST") {
    geschreven.push(req.postDataJSON());
    return route.fulfill({ status: 201, json: { id: geschreven.length } });
  }
  return route.fulfill({ json: {} });
});

async function vraag(id) {
  gid = id;
  await page.goto(`${base}/workbench`);
  const veld = page.locator("textarea").first();
  await veld.waitFor();
  await veld.fill(id);
  await veld.press("Enter");
}

// Een mislukte beurt: live.
await vraag("mislukt");
await page.locator("[data-beurt-uitkomst=mislukt]").waitFor();
assert.match(await page.locator("[data-beurt-uitkomst=mislukt]").innerText(), /te lang/);
// Na herladen hetzelfde blok.
await page.goto(`${base}/workbench?gesprek=mislukt`);
await page.locator("[data-beurt-uitkomst=mislukt]").waitFor();
assert.match(await page.locator("[data-beurt-uitkomst=mislukt]").innerText(), /te lang/);
assert.equal(await page.getByText("(geen antwoord)").count(), 0, "geen (geen antwoord) bij een fout");

// Een verbroken stroom haakt opnieuw aan en eindigt met de uitkomst van de run.
await vraag("verbroken");
await page.getByText("Het antwoord.").waitFor({ timeout: 10_000 });
assert.ok(pogingen.verbroken >= 2, "opnieuw aangehaakt");

// Stoppen: live wat er na herladen staat.
await vraag("gestopt");
await page.getByText("(gestopt)").waitFor();

assert.deepEqual(geschreven.filter((b) => b.rol === "assistant"), [], "de werkplek schrijft geen beurt weg");
assert.deepEqual(errors, []);
await browser.close();
console.log("beurtuitkomst: alles groen");
