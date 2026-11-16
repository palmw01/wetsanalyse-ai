/** Browserregressie voor de afloop van een beurt (verbeterplan C3). Op de echte Next-UI met een gemockte BFF.
 * Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-beurtuitkomst.mjs`.
 *
 * Bewaakt:
 *  - een mislukte beurt toont live dezelfde melding als na herladen, zonder "(geen antwoord)";
 *  - een stroom die sluit zonder `done` is geen afgeronde beurt: de werkplek haakt opnieuw aan en krijgt de uitkomst;
 *  - stoppen zegt live wat er na herladen staat;
 *  - het oordeel van de controle en de melding bij een afgekapt antwoord blijven na herladen staan (C4);
 *  - de werkplek schrijft nooit zelf een assistent-bericht: de server is de enige schrijver;
 *  - een stroom in de echte vorm (`\r\n`, keep-alive-commentaar) die halverwege breekt, hervat zonder dat er tekst
 *    dubbel staat: de werkplek speelt de log opnieuw af, de server geeft hem vanaf het gevraagde volgnummer;
 *  - een 409 bij de start haakt aan bij de lopende run en geeft de nieuwe vraag terug in het invoerveld;
 *  - een run die bij terugkomst verdwenen is (geen run en geen bericht), krijgt de waarschuwing.
 *
 * risico: R08, R21
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";
import { SCHIL, controleerOnbekend, onbekend, sse, stroomInDelen } from "./nepApi.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [], geschreven = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const MELDING = "Deze beurt werd te lang en is afgebroken.";
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
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
berichten.oordeel = [{ rol: "user", tekst: "oordeel", ...leeg }, { rol: "assistant", tekst: "Er staat “verzonnen tekst” in de wet.", ...leeg,
  run_id: "oordeel", grounding: { niveau: "ongegrond", grounded: false, cited: 0, unsupported: [], niet_letterlijk: ["verzonnen tekst"], afgekapt: true, onbevestigd: ["artikel 999"] } }];
let gid = "mislukt";
const pogingen = {};
// Eén log, zoals de runstore hem bewaart; de eerste verbinding breekt na twee events af (zonder `done`).
const hervat = stroomInDelen([
  { type: "status", message: "Graaf bevragen" }, { type: "token", content: "Eerste deel. " },
  { type: "token", content: "Tweede deel." }, { type: "opgeslagen", run_id: "hervat" }, { type: "done", uitkomst: "klaar" },
], { breek: 2, ping: true });

await page.route("**/api/**", async (route) => {
  const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/annotatie/run") {
    if (m === "GET") return route.fulfill({ json: null });
    // Er loopt al een beurt op dit gesprek (een ander tabblad): de agent weigert en wijst die run aan.
    if (gid === "botst") return route.fulfill({ status: 409, json: { detail: { reden: "run_loopt_al", run_id: "lopend" } } });
    return route.fulfill({ json: { run_id: gid, conversation_id: gid, status: "loopt" } });
  }
  if (p === "/api/annotatie/run/hervat/events") return hervat.handler(route);
  if (p === "/api/annotatie/run/lopend/events") {
    return route.fulfill({ contentType: "text/event-stream",
      body: sse([{ type: "token", content: "Antwoord op de lopende vraag." }, { type: "done", uitkomst: "klaar" }]) });
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
  return onbekend(route, { stil: SCHIL, leeg: {} });
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

// Een stroom in de echte vorm breekt halverwege af: de werkplek haakt opnieuw aan en niets staat dubbel.
await vraag("hervat");
await page.getByText("Eerste deel. Tweede deel.").waitFor({ timeout: 10_000 });
assert.equal(hervat.aangehaakt.length, 2, "na de breuk één keer opnieuw aangehaakt");
assert.equal((await page.locator("body").innerText()).split("Eerste deel.").length - 1, 1, "geen tekst dubbel na het hervatten");

// Een 409 bij de start: aanhaken bij de lopende run, en de nieuwe vraag terug in het invoerveld.
await vraag("botst");
await page.getByText("Antwoord op de lopende vraag.").waitFor({ timeout: 10_000 });
assert.equal(await page.locator("textarea").first().inputValue(), "botst", "de vraag die niet werd aangenomen, staat terug");

// Stoppen: live wat er na herladen staat.
await vraag("gestopt");
await page.getByText("(gestopt)").waitFor();

// Het oordeel na herladen: het blok, de aanwijzing in de tekst en de afkapping.
await page.goto(`${base}/workbench?gesprek=oordeel`);
await page.locator("[data-afgekapt]").waitFor();
assert.match(await page.locator("[data-onbevestigd]").innerText(), /artikel 999/);
await page.locator("mark", { hasText: "verzonnen tekst" }).waitFor();

// Een run die bij terugkomst verdwenen is: er stond er een open, maar er is geen run en geen bericht met dat id.
await page.evaluate(() => localStorage.setItem("wa_lopende_run", JSON.stringify({ weg: "run-weg" })));
await page.goto(`${base}/workbench?gesprek=weg`);
await page.getByText("De vorige vraag is afgebroken", { exact: false }).waitFor({ timeout: 10_000 });

assert.deepEqual(geschreven.filter((b) => b.rol === "assistant"), [], "de werkplek schrijft geen beurt weg");
controleerOnbekend();
assert.deepEqual(errors, []);
await browser.close();
console.log("beurtuitkomst: alles groen");
