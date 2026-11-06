/** Browserregressie: de weergave wijzigt een antwoord van Lex niet, op de echte Next-UI met een gemockte BFF.
 * Start Next met AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-antwoordweergave.mjs`.
 *
 * Bewaakt:
 *  - lijstnummers staan er zoals Lex ze schreef, ook na afloop van de stroom: een lijst die bij 3 begint, een
 *    lijst met een gat en een lijst die na een alinea verdergaat;
 *  - een vermelding die een andere regeling noemt dan de bron, krijgt geen citatie-chip; de juiste wel, ook
 *    live: `parseBronnen` moet de naam van de regeling en de afkortingen doorlaten.
 */
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const shots = process.env.MOCK_SCREENSHOTS || "/tmp/wetsanalyse-antwoordweergave";
mkdirSync(shots, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const TEKST = ["De voorwaarden uit de bepaling:", "", "3. de ontvanger", "4. de belastingschuldige", "", "Met een gat:", "",
  "1. eerste", "3. derde", "", "Tussenzin.", "", "2. loopt door", "",
  "Zie artikel 9 van de Algemene wet bestuursrecht. Vergelijk artikel 9 Iw."].join("\n");
const IRI = "urn:bwb:BWBR0004770:artikel:9";
const BRON = { label: "Artikel 9", uri: IRI, bron_iri: IRI, bwb_id: "BWBR0004770", soort: "artikel",
  regeling: "Invorderingswet 1990", afkortingen: ["IW", "Iw 1990"] };
const stroom = [{ type: "token", content: TEKST }, { type: "sources", sources: [BRON] },
  { type: "grounding", grounded: true, cited: 1, unsupported: [], niet_letterlijk: [], niveau: "gegrond" },
  { type: "opgeslagen", run_id: "r1" }, { type: "done" }];
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");

await context.route("**/api/**", async (route) => {
  const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g9", titel: body?.titel ?? "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (/^\/api\/gesprekken\/g\d$/.test(p)) return route.fulfill({ json: { id: "g9", titel: "Test", berichten: [] } });
  if (p.endsWith("/berichten") && m === "POST") return route.fulfill({ status: 201, json: { id: 1 } });
  if (p === "/api/annotatie/run" && m === "POST") return route.fulfill({ status: 201, json: { run_id: "r1", conversation_id: body.conversation_id, status: "loopt" } });
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  if (/\/run\/[^/]+\/events$/.test(p)) return route.fulfill({ contentType: "text/event-stream", body: sse(stroom) });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: [] });
});

try {
  await page.goto(`${base}/workbench`);
  const vraag = page.getByPlaceholder("Vraag of opdracht voor Lex…");
  await vraag.fill("Wat regelt artikel 9?");
  await vraag.press("Enter");

  const lijstitems = page.locator("ol > li");
  await page.getByText("loopt door").and(page.locator("li")).waitFor();
  assert.deepEqual(await lijstitems.evaluateAll((els) => els.map((li) => li.value)), [3, 4, 1, 3, 2]);

  // De chip is een knop met de vermelding erin; de vermelding van de andere wet blijft gewone tekst.
  const chips = page.locator("button[aria-haspopup=dialog]", { hasText: "artikel 9" });
  await chips.first().waitFor();
  assert.equal(await chips.count(), 1);
  await page.getByText("Zie artikel 9 van de Algemene wet bestuursrecht", { exact: false }).waitFor();
  await page.screenshot({ path: `${shots}/antwoord.png` });
  assert.deepEqual(errors, []);
  console.log("antwoordweergave: ok");
} finally {
  await browser.close();
}
