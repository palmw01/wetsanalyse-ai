/** Browserregressie voor de stand van runs buiten het open gesprek (E6). Op de echte Next-UI met een gemockte
 * BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-runstanden.mjs`.
 *
 * Bewaakt:
 *  - een beurt die in gesprek B loopt terwijl A open is, geeft B de stip *Lex is bezig* en de tab `Bezig · …`;
 *  - wordt hij klaar terwijl de tab verborgen is, dan krijgt B *Nieuw antwoord* en de tab `Klaar · …`;
 *  - weer zichtbaar is de tabtitel gewoon; B openen telt als gezien, ook na herladen;
 *  - zonder spoor peilt de werkplek niet vanzelf door.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => {
  localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true }));
  // Een verborgen tabblad na te bootsen: Playwright houdt de pagina zichtbaar.
  window.__verborgen = false;
  Object.defineProperty(Document.prototype, "hidden", { configurable: true, get: () => window.__verborgen });
  Object.defineProperty(Document.prototype, "visibilityState", {
    configurable: true, get: () => (window.__verborgen ? "hidden" : "visible"),
  });
});

const nu = "2026-11-07T10:00:00+00:00";
const lijst = [
  { id: "gA", titel: "Gesprek A", aantal_berichten: 2, updated: nu, werkgebied_id: "", werkgebied_naam: "", gearchiveerd: null },
  { id: "gB", titel: "Gesprek B", aantal_berichten: 2, updated: nu, werkgebied_id: "", werkgebied_naam: "", gearchiveerd: null },
];
let runB = { run_id: "rB", conversation_id: "gB", status: "loopt" };
let peilingen = 0;

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/annotatie/run" && m === "GET") {
    if (url.searchParams.get("actief") === "1") {
      peilingen += 1;
      return route.fulfill({ json: runB ? [runB] : [] });
    }
    return route.fulfill({ json: null });
  }
  const gesprek = p.match(/^\/api\/gesprekken\/(g[AB])$/);
  if (gesprek) return route.fulfill({ json: { ...lijst.find((g) => g.id === gesprek[1]), user_id: "t", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: lijst });
  if (p === "/api/werkgebieden") return route.fulfill({ json: { werkgebieden: [] } });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ json: [] });
});

const rij = (id) => page.locator(`aside[data-tour=sidebar] [data-gesprek-rij=${id}]`);
const stip = (id) => rij(id).locator("[data-gesprek-status]");
async function wachtOpTitel(verwacht) {
  for (let i = 0; i < 100; i++) {
    if ((await page.title()) === verwacht) return;
    await page.waitForTimeout(100);
  }
  assert.equal(await page.title(), verwacht);
}
async function zetVerborgen(v) {
  await page.evaluate((v) => {
    window.__verborgen = v;
    document.dispatchEvent(new Event("visibilitychange"));
  }, v);
}

try {
  await page.goto(`${base}/workbench?gesprek=gA`);
  // --- B loopt terwijl A open is ---
  await rij("gB").waitFor();
  await rij("gB").locator("[data-gesprek-status=loopt]").waitFor();
  assert.equal(await stip("gB").innerText(), "Lex is bezig");
  assert.equal(await stip("gA").count(), 0);
  await wachtOpTitel("Bezig · Lex · Wetsanalyse");

  // --- B wordt klaar terwijl de tab verborgen is ---
  await zetVerborgen(true);
  runB = { ...runB, status: "klaar", afgerond_op: nu };
  await rij("gB").locator("[data-gesprek-status=nieuw]").waitFor({ timeout: 12_000 });
  assert.equal(await stip("gB").innerText(), "Nieuw antwoord");
  await wachtOpTitel("Klaar · Lex · Wetsanalyse");
  if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/runstanden-nieuw.png` });

  // --- Weer zichtbaar: de gewone titel; de stip blijft tot je B opent ---
  await zetVerborgen(false);
  await wachtOpTitel("Lex · Wetsanalyse");
  assert.equal(await stip("gB").count(), 1);

  // --- Niets loopt meer en er is geen spoor: dan peilt hij niet vanzelf door ---
  const tot = peilingen;
  await page.waitForTimeout(11_000);
  assert.equal(peilingen, tot, "zonder spoor geen peiling elke 5 s");

  // --- B openen telt als gezien, ook na herladen ---
  await rij("gB").getByRole("button", { name: /^Gesprek B/ }).click();
  await stip("gB").waitFor({ state: "detached" });
  const gezien = await page.evaluate(() => JSON.parse(localStorage.getItem("wa_runs_gezien") ?? "[]"));
  assert.deepEqual(gezien, ["rB"]);
  await rij("gA").getByRole("button", { name: /^Gesprek A/ }).click();
  await page.reload();
  await rij("gB").waitFor();
  await page.waitForTimeout(500);
  assert.equal(await stip("gB").count(), 0, "een gezien antwoord is na herladen geen nieuw antwoord");

  assert.deepEqual(errors, []);
  console.log("runstanden: ok");
} finally {
  await browser.close();
}
