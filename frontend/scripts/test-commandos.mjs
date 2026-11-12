/** Browserregressie voor de `/commando's` in het invoerveld (`lib/commandos.ts`). Op de echte Next-UI met een gemockte
 * BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-commandos.mjs`.
 *
 * Bewaakt:
 *  - `/` vooraan opent het menu (een combobox met een listbox); de suggestierij wijkt;
 *  - `/dee` + Enter verstuurt precies wat de suggestie *Stel deelvragen voor* verstuurt: dezelfde tekst en `actie`,
 *    zonder modus of doel – graph-qa kiest dan zonder model;
 *  - ↓ kiest een volgende regel, Tab vult de naam aan, Escape sluit het menu en laat de tekst staan;
 *  - een onbekend commando zegt dat, en Enter verstuurt de tekst gewoon als vraag (zonder actie);
 *  - bij een deelvraag als onderwerp zijn het de commando's van de deelvraag;
 *  - `/help` toont alle commando's; `/nieuw` begint een leeg gesprek, zonder beurt;
 *  - op een telefoon (375 px, touch) past het menu en zijn de regels minstens 44 px hoog.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addCookies(await sessieCookies(base));
const errors = [], runs = [];

const nu = "2026-10-20T10:00:00+00:00";
const wg = { id: "wg1", naam: "Invordering", status: "in_voorbereiding", revisie: 1, peildatum: null, aangemaakt_door: "t",
  aangemaakt: nu, gewijzigd: nu, analysevraag: "Wanneer is een aanslag invorderbaar?", afbakening: "", aanleiding: "",
  context: "", doel: "", praktijkvoorbeeld: "", bronnen: [],
  deelvragen: [{ id: "d1", vraag: "Wanneer vervalt de termijn?", volgorde: 0, status: "actief", herkomst: "analist", reden: "",
    aangemaakt_door: "t", aangemaakt: nu, bronnen: [], begrippen: [] }] };
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const gesprekken = {
  g5: [
    { rol: "user", tekst: "Kunnen we een werkgebied samenstellen?", ...leeg },
    { rol: "assistant", tekst: "Het werkgebied staat er.", ...leeg, run_id: "w1",
      artefact: { soort: "werkgebied", ref: { werkgebied_id: "wg1" }, titel: "Invordering" } },
  ],
};
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");

async function opzet(page) {
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
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
    if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: "Test", werkgebied_id: "wg1", berichten: gesprekken[gesprek[1]] ?? [] } });
    if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g2", titel: "", berichten: [] } });
    if (p === "/api/gesprekken") return route.fulfill({ json: [] });
    if (p.endsWith("/berichten") && m === "POST") return route.fulfill({ json: { id: 1 } });
    if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
    return route.fulfill({ json: [] });
  });
}

const wachtOp = async (page, n) => {
  for (let i = 0; i < 100 && runs.length < n; i++) await page.waitForTimeout(50);
  assert.ok(runs.length >= n, `verwacht ${n} runs, kreeg ${runs.length}`);
};

try {
  const page = await context.newPage();
  await opzet(page);
  const veld = page.locator('[data-tour="invoer"] textarea');
  const menu = page.locator("[data-commandomenu]");
  const regels = menu.getByRole("option");

  // --- In een werkgebied: `/` opent het menu, de suggestierij wijkt ---
  await page.goto(`${base}/workbench?werkgebied=wg1`);
  await page.getByTestId("vraag-suggesties").waitFor();
  assert.equal(await veld.getAttribute("role"), null, "zonder / een gewoon tekstveld");
  await veld.fill("/");
  await menu.waitFor();
  assert.equal(await page.getByTestId("vraag-suggesties").count(), 0, "het menu staat op de plek van de suggesties");
  assert.equal(await veld.getAttribute("role"), "combobox");
  assert.equal(await veld.getAttribute("aria-expanded"), "true");
  assert.ok((await regels.count()) > 10, "alle commando's van het werkgebied");

  // --- /dee + Enter = de suggestie *Stel deelvragen voor* ---
  await veld.fill("/dee");
  assert.deepEqual(await regels.locator("span.font-mono").allTextContents(), ["/deelvragen", "/annoteer-deelvragen"]);
  assert.equal(await veld.getAttribute("aria-activedescendant"), await regels.first().getAttribute("id"));
  await veld.press("Enter");
  await wachtOp(page, 1);
  assert.deepEqual(runs[0], { question: "Stel deelvragen voor", conversation_id: "g2", werkgebied_id: "wg1", actie: "deelvragen_voorstellen" });
  assert.equal(await veld.inputValue(), "");
  await page.getByText("Goed.").waitFor();

  // --- ↓, Tab en Escape ---
  await veld.fill("/annoteer");
  await veld.press("ArrowDown");
  assert.equal(await regels.nth(1).getAttribute("aria-selected"), "true");
  await veld.press("Tab");
  assert.equal(await veld.inputValue(), "/annoteer-deelvragen", "Tab vult aan, verstuurt niets");
  await veld.press("Escape");
  await menu.waitFor({ state: "detached" });
  assert.equal(await veld.inputValue(), "/annoteer-deelvragen", "Escape laat de tekst staan");
  assert.equal(runs.length, 1);

  // --- Onbekend: Enter verstuurt de tekst als vraag ---
  await veld.fill("/xyzq");
  await page.locator("[data-geen-commando]").waitFor();
  await veld.press("Enter");
  await wachtOp(page, 2);
  assert.equal(runs[1].question, "/xyzq");
  assert.equal(runs[1].actie, undefined, "geen commando: geen actie");
  await page.getByText("Goed.").nth(1).waitFor();

  // --- /help toont alles; /nieuw begint een leeg gesprek zonder beurt ---
  await veld.fill("/help");
  await veld.press("Enter");
  assert.equal(await veld.inputValue(), "/");
  await menu.waitFor();
  await veld.fill("/nieuw");
  await veld.press("Enter");
  // Het vorige gesprek is weg: geen antwoord van Lex meer in de thread. (De tekst "Stel deelvragen voor" blijft wel: in een
  // leeg gesprek in het werkgebied staat die weer als suggestie.)
  await page.getByText("Goed.").first().waitFor({ state: "detached" });
  assert.equal(await page.getByText("Goed.").count(), 0, "het nieuwe gesprek is leeg");
  await page.getByTestId("vraag-suggesties").locator('[data-actie="deelvragen_voorstellen"]').waitFor();
  assert.equal(runs.length, 2, "/nieuw is geen beurt");
  assert.equal(new URL(page.url()).searchParams.get("werkgebied"), "wg1", "het nieuwe gesprek blijft in het werkgebied");

  // --- Een deelvraag als onderwerp: de commando's van de deelvraag ---
  await page.goto(`${base}/workbench?werkgebied=wg1&vraag=deelvraag%3Ad1&vraag_label=${encodeURIComponent("Wanneer vervalt de termijn?")}`);
  await page.locator('[data-onderwerp="deelvraag"]').waitFor();
  await veld.fill("/s");
  assert.deepEqual(await regels.locator("span.font-mono").allTextContents(), ["/scherper", "/splits"]);
  await veld.press("Enter");
  await wachtOp(page, 3);
  assert.equal(runs[2].actie, "deelvraag_herformuleren");
  assert.equal(runs[2].question, "Formuleer scherper");
  assert.deepEqual([runs[2].onderwerp.soort, runs[2].onderwerp.id], ["deelvraag", "d1"]);
  await page.close();

  // --- Op een telefoon: het menu past en de regels zijn groot genoeg om te tikken ---
  const mobiel = await browser.newContext({ viewport: { width: 375, height: 740 }, isMobile: true, hasTouch: true });
  await mobiel.addCookies(await sessieCookies(base));
  const tel = await mobiel.newPage();
  await opzet(tel);
  await tel.goto(`${base}/workbench?werkgebied=wg1`);
  const telVeld = tel.locator('[data-tour="invoer"] textarea');
  await telVeld.fill("/");
  const telMenu = tel.locator("[data-commandomenu]");
  await telMenu.waitFor();
  const vak = await telMenu.boundingBox();
  assert.ok(vak && vak.x >= 0 && vak.x + vak.width <= 375, `het menu past op 375 px (${JSON.stringify(vak)})`);
  const regel = await telMenu.getByRole("option").first().boundingBox();
  assert.ok(regel && regel.height >= 44, `een regel is minstens 44 px hoog (${regel?.height})`);
  const breedte = await tel.evaluate(() => document.documentElement.scrollWidth);
  assert.ok(breedte <= 375, `geen horizontale scroll (${breedte})`);
  await telMenu.getByRole("option").filter({ hasText: "/deelvragen" }).tap();
  for (let i = 0; i < 100 && runs.length < 4; i++) await tel.waitForTimeout(50);
  assert.equal(runs[3]?.actie, "deelvragen_voorstellen", "een tik voert uit");
  await mobiel.close();

  assert.deepEqual(errors, []);
  console.log("Browser OK: het commandomenu bij /, /dee + Enter als de suggestie, ↓/Tab/Escape, onbekend als vraag, /help, /nieuw zonder beurt, de commando's van een deelvraag, en mobiel (375 px, 44 px, tikken).");
} finally {
  await browser.close();
}
