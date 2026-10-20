/** Browserregressie voor *Vraag Lex* op een object (spoor F, F3b). Op de echte Next-UI met een gemockte
 * BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-vraaglex.mjs`.
 *
 * Bewaakt:
 *  - buiten de werkplek is *Vraag Lex* een link naar een vers gesprek met het onderwerp klaar
 *    (`?werkgebied=…&vraag=werkgebied:…`);
 *  - de werkplek leest dat één keer: de chip staat er, de parameters gaan uit de URL, het werkgebied blijft;
 *  - een suggestie met een actie stuurt `actie` + `onderwerp` + `werkgebied_id`, zonder modus, context of doel;
 *  - in de werkplek zet de knop in het werkgebiedpaneel de chip; een getypte vraag gaat als `onderwerp`, de
 *    chip verdwijnt na het versturen, en het bewaarde bericht zegt waar de vraag over ging.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [], runs = [], berichten = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-20T10:00:00+00:00";
const wg = { id: "wg1", naam: "Invordering", status: "in_voorbereiding", revisie: 1, peildatum: null, aangemaakt_door: "t",
  aangemaakt: nu, gewijzigd: nu, analysevraag: "Wanneer is een aanslag invorderbaar?", afbakening: "", aanleiding: "",
  context: "", doel: "", praktijkvoorbeeld: "", bronnen: [], deelvragen: [] };
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const gesprekken = {
  g5: [
    { rol: "user", tekst: "Kunnen we een werkgebied samenstellen?", ...leeg },
    { rol: "assistant", tekst: "Het werkgebied staat er.", ...leeg, run_id: "w1",
      artefact: { soort: "werkgebied", ref: { werkgebied_id: "wg1" }, titel: "Invordering" } },
  ],
};
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/annotatie/run") {
    if (m === "GET") return route.fulfill({ json: null });
    runs.push(req.postDataJSON());
    return route.fulfill({ json: { run_id: "live", conversation_id: req.postDataJSON().conversation_id, status: "loopt" } });
  }
  if (p === "/api/annotatie/run/live/events")
    return route.fulfill({ contentType: "text/event-stream", body: sse([{ type: "token", content: "Goed." }, { type: "done" }]) });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/kandidaten") return route.fulfill({ json: { kandidaten: [], run: null } });
  const gesprek = p.match(/^\/api\/gesprekken\/(g\d)$/);
  if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: "Test", berichten: gesprekken[gesprek[1]] ?? [] } });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g2", titel: "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.endsWith("/berichten") && m === "POST") {
    berichten.push(req.postDataJSON());
    return route.fulfill({ json: { id: berichten.length } });
  }
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: [] });
});

const chip = () => page.locator("[data-onderwerp]");
const invoer = () => page.getByRole("textbox").last();
const wachtOp = async (n, lijst = runs) => {
  for (let i = 0; i < 100 && lijst.length < n; i++) await page.waitForTimeout(50);
  assert.ok(lijst.length >= n, `verwacht ${n}, kreeg ${lijst.length}`);
};

try {
  // --- Buiten de werkplek: een link met het onderwerp ---
  await page.goto(`${base}/werkgebieden/wg1`);
  const link = page.getByRole("link", { name: "Vraag Lex over werkgebied: Invordering" });
  const href = await link.getAttribute("href");
  assert.equal(href, "/workbench?werkgebied=wg1&vraag=werkgebied%3Awg1&vraag_label=Invordering");

  // --- Binnenkomst: chip klaar, parameters weg, werkgebied blijft ---
  await link.click();
  await chip().getByText("Invordering").waitFor();
  assert.equal(await chip().getAttribute("data-onderwerp"), "werkgebied");
  for (let i = 0; i < 40 && new URL(page.url()).searchParams.get("vraag"); i++) await page.waitForTimeout(50);
  const zoek = new URL(page.url()).searchParams;
  assert.equal(zoek.get("vraag"), null, "herladen zet de chip niet opnieuw");
  assert.equal(zoek.get("vraag_label"), null);
  assert.equal(zoek.get("werkgebied"), "wg1");

  // --- Een suggestie met een actie: vaste route, geen modus, context of doel ---
  const suggesties = page.getByTestId("vraag-suggesties").getByRole("button");
  assert.equal(await suggesties.count(), 4);
  await page.getByRole("button", { name: "Zoek bepalingen die bij dit werkgebied horen" }).click();
  await wachtOp(1);
  assert.deepEqual(runs[0], {
    question: "Zoek bepalingen die bij dit werkgebied horen", conversation_id: "g2", werkgebied_id: "wg1",
    onderwerp: { soort: "werkgebied", werkgebied_id: "wg1", label: "Invordering" }, actie: "bronnen_zoeken",
  });
  await chip().waitFor({ state: "detached" });
  await wachtOp(1, berichten);
  assert.equal(berichten[0].tekst, "Bij werkgebied Invordering: Zoek bepalingen die bij dit werkgebied horen");

  // --- In de werkplek: de knop in het paneel zet de chip, een getypte vraag gaat als onderwerp ---
  await page.goto(`${base}/workbench?gesprek=g5`);
  await page.locator('button[data-artefact-soort="werkgebied"]').click();
  const knop = page.locator('[data-artefact-soort="werkgebied"][data-artefact] button[data-vraag-lex="werkgebied"]');
  await knop.click();
  await chip().getByText("Invordering").waitFor();
  await invoer().fill("Wat ontbreekt er nog?");
  await invoer().press("Enter");
  await wachtOp(2);
  assert.deepEqual(runs[1], {
    question: "Wat ontbreekt er nog?", conversation_id: "g5",
    onderwerp: { soort: "werkgebied", werkgebied_id: "wg1", label: "Invordering" },
  });
  await chip().waitFor({ state: "detached" });

  assert.deepEqual(errors, []);
  console.log("Browser OK: Vraag Lex als link buiten de werkplek, chip uit de URL (één keer), suggestie met actie, knop in het paneel, vraag met onderwerp.");
} finally {
  await browser.close();
}
