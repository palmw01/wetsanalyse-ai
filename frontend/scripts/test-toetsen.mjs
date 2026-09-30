/** Browserregressie voor toetsenbord, vensters en de foutpaden van de werkplek, op echte Next-UI met
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * npm run test:browser (na npx playwright install chromium; TOUCH_ENGINE=webkit vraagt ook webkit)
 * Gebruik `localhost`, niet `127.0.0.1`: Next 16 weigert dev-assets aan een andere origin dan de
 * server kent, en dan hydrateert de pagina niet – elke stap time-out dan zonder duidelijke fout.
 *
 * Wat hier bewaakt wordt, en waarom het een browser nodig heeft:
 *  - sneltoetsen van het artefact werken alleen met de focus ín het artefact (kolomvariant: de chat
 *    staat ernaast, en een `a` op een chatknop keurde daar ongemerkt iets goed);
 *  - Escape sluit alleen het bovenste venster, en na sluiten gaat de focus terug naar de trigger;
 *  - een geslaagde beurt waarvan de wettekst niet te laden is, wordt niet eindeloos opnieuw gevolgd;
 *  - een vraag die je verstuurt terwijl het gesprek nog laadt, blijft in beeld;
 *  - zelf markeren op een aanraakscherm (iPhone-profiel) loopt via `selectionchange`. Het echte
 *    verslepen van de native selectiegrepen kan geen emulator nabootsen; dat blijft een check op
 *    een toestel.
 */
import assert from "node:assert/strict";
import { chromium, devices, webkit } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";

const doel = (lid) => ({ bron_iri: `urn:lid${lid}`, label: `Invorderingswet – artikel 9 lid ${lid}`, snapshot_id: "snapshot",
  type: "Lid", bwb_id: "BWBR0004770", artikel: "9", lid: String(lid), citeertitel: "Invorderingswet 1990" });
const view = (lid) => ({ schema_versie: 2, doel: doel(lid), snapshot_id: "snapshot",
  segmenten: [{ bron_iri: `urn:lid${lid}`, parent_iri: "urn:artikel9", type: "Lid", nummer: String(lid), label: `Lid ${lid}`,
    tekst: "De ontvanger stelt de belastingschuldige in kennis.", bron_hash: `hash${lid}`, volgorde: lid }],
  lagen: [{ id: `laag${lid}`, bron_iri: `urn:lid${lid}`, status: "in_review", revisie: 1 }],
  elementen: [{ id: `e${lid}`, eigenaar_iri: `urn:lid${lid}`, laag_id: `laag${lid}`, klasse: "Rechtssubject", tekst: "ontvanger",
    lifecycle: "voorgesteld", herkomst: "agent", ankers: [{ bron_iri: `urn:lid${lid}`, start: 3, eind: 12, tekst: "ontvanger", bron_hash: `hash${lid}` }] }],
  verwijzingen: [], dekking: {} });
// g1: twee node-annotaties in de geschiedenis. g2: laadt traag (F2). g3: nieuw gesprek voor F1.
const gesprekken = {
  g1: [1, 2].flatMap((lid) => [
    { rol: "user", tekst: `Annoteer artikel 9 lid ${lid}`, denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" },
    { rol: "assistant", tekst: "", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "", annotatie_doel: doel(lid), run_id: `r${lid}` },
  ]),
  g2: [
    { rol: "user", tekst: "Oude vraag", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" },
    { rol: "assistant", tekst: "Oud antwoord", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "", run_id: "oud" },
  ],
};
const document1 = { slug: "doc1", bwbId: "BWBR0004770", artikel: "9", lid: "1", werkgebied: "Invorderingswet 1990",
  status: "in_review", elementen: [], runs: [] };
const stromen = {
  // F1: de beurt is vastgelegd, maar de wettekst komt niet binnen.
  f1: [{ type: "status", message: "Resultaat" }, { type: "opgeslagen", run_id: "f1", annotatie_slug: "doc1" }, { type: "done" }],
  f2: [{ type: "token", content: "Nieuw antwoord." }, { type: "done" }],
};
const sse = (events) => events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

async function nieuwePagina(browserType, opties) {
  const browser = await browserType.launch({
    executablePath: browserType === chromium ? process.env.CHROMIUM_PATH : undefined, headless: true,
  });
  const context = await browser.newContext(opties);
  await context.addCookies(await sessieCookies(base));
  await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  const page = await context.newPage();
  const errors = [], requests = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/**", async (route) => {
    const req = route.request(), url = new URL(req.url()), pad = url.pathname;
    if (pad.startsWith("/api/auth/")) return route.continue();
    requests.push({ pad, method: req.method(), body: req.method() === "GET" ? undefined : req.postDataJSON() });
    if (pad === "/api/annotatie/run") {
      if (req.method() === "GET") return route.fulfill({ json: null });
      const gesprek = req.postDataJSON().conversation_id;
      const run = gesprek === "g3" ? "f1" : gesprek === "g2" ? "f2" : "live";
      return route.fulfill({ json: { run_id: run, conversation_id: gesprek, status: "loopt" } });
    }
    const events = pad.match(/^\/api\/annotatie\/run\/([^/]+)\/events$/);
    if (events) return route.fulfill({ contentType: "text/event-stream", body: sse(stromen[events[1]] ?? [{ type: "done" }]) });
    if (pad === "/api/annotatie/artikel") return route.fulfill({ status: 502, json: { detail: "Agent onbereikbaar" } });
    if (pad === "/api/annotatie/documenten/doc1") return route.fulfill({ json: document1 });
    if (pad.endsWith("/weergave")) return route.fulfill({ json: view(url.searchParams.get("bron_iri") === "urn:lid2" ? 2 : 1) });
    if (pad.endsWith("/beslissing")) return route.fulfill({ json: {} });
    const gesprek = pad.match(/^\/api\/gesprekken\/(g\d)$/);
    if (gesprek) {
      if (gesprek[1] === "g2") await new Promise((r) => setTimeout(r, 3000));
      return route.fulfill({ json: { id: gesprek[1], titel: "Test", berichten: gesprekken[gesprek[1]] ?? [] } });
    }
    if (pad === "/api/gesprekken" && req.method() === "POST") return route.fulfill({ status: 201, json: { id: "g3", titel: "", berichten: [] } });
    if (pad === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Test", aantal_berichten: 4 }] });
    if (pad.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (pad.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
    return route.fulfill({ json: pad.endsWith("/berichten") && req.method() === "POST" ? { id: 1 } : [] });
  });
  return { browser, page, errors, requests };
}

const wettekst = (page) => page.locator('[data-tour="wettekst"]');
const inBeeld = (page) => page.getByText("in beeld", { exact: false });
const chip = (page, lid) => page.locator("button", { hasText: `Invorderingswet – artikel 9 lid ${lid}` }).last();
const beslissingen = (requests) => requests.filter((r) => r.pad.endsWith("/beslissing"));

// --- Kolomvariant: sneltoetsen en gestapelde vensters -----------------------------------------
{
  const { browser, page, errors, requests } = await nieuwePagina(chromium, { viewport: { width: 1440, height: 1000 } });
  try {
    await page.goto(`${base}/workbench?gesprek=g1`);
    await chip(page, 1).click();
    await wettekst(page).getByText("ontvanger", { exact: false }).waitFor();
    await wettekst(page).click({ position: { x: 4, y: 4 } });
    await page.keyboard.press("j");
    await inBeeld(page).waitFor();

    // Focus in de chat ernaast: de sneltoetsen van het artefact horen niets te doen.
    await chip(page, 2).focus();
    for (const toets of ["a", "x", "ArrowDown"]) await page.keyboard.press(toets);
    await page.waitForTimeout(500);
    assert.equal(beslissingen(requests).length, 0, "een toets in de chat mag niets in het artefact beslissen");
    assert.equal(await inBeeld(page).count(), 1, "de selectie in het artefact moet blijven staan");

    // Focus in het artefact: `a` keurt goed.
    await wettekst(page).click({ position: { x: 4, y: 4 } });
    await page.keyboard.press("a");
    for (let i = 0; i < 30 && !beslissingen(requests).length; i++) await page.waitForTimeout(100);
    assert.equal(beslissingen(requests)[0]?.body?.type, "approve", "`a` in het artefact hoort goed te keuren");

    // Instellingen over het artefact heen: Escape sluit alleen het bovenste venster.
    await wettekst(page).click({ position: { x: 4, y: 4 } });
    await page.keyboard.press("j");
    await inBeeld(page).waitFor();
    // Met het toetsenbord: in dev ligt de indicator van Next linksonder precies over deze knop.
    await page.getByRole("button", { name: /· instellingen/ }).focus();
    await page.keyboard.press("Enter");
    await page.getByRole("link", { name: "Account & instellingen" }).focus();
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => location.pathname.startsWith("/instellingen"));
    await page.getByRole("dialog", { name: "Instellingen" }).waitFor();
    await page.keyboard.press("Escape");
    // `router.back()` is een soft navigation; `waitForURL` ziet die niet altijd als navigatie.
    await page.waitForFunction(() => location.pathname === "/workbench");
    await page.waitForTimeout(300);
    assert.equal(await inBeeld(page).count(), 1, "Escape in het instellingenvenster mag het artefact eronder niet raken");
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
}

// --- Smal scherm: focus terug naar de trigger na sluiten --------------------------------------
{
  const { browser, page, errors } = await nieuwePagina(chromium, { viewport: { width: 800, height: 1000 } });
  try {
    await page.goto(`${base}/workbench?gesprek=g1`);
    await chip(page, 1).click();
    await wettekst(page).getByText("ontvanger", { exact: false }).waitFor();
    await page.keyboard.press("Escape");
    await wettekst(page).waitFor({ state: "detached" });
    const focus = await page.evaluate(() => document.activeElement?.textContent ?? "");
    assert.match(focus, /artikel 9 lid 1/, "na sluiten hoort de focus terug op de kaart die het paneel opende");
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
}

// --- F1: geslaagde beurt, wettekst onbereikbaar → geen herstellus -------------------------------
{
  const { browser, page, errors, requests } = await nieuwePagina(chromium, { viewport: { width: 1440, height: 1000 } });
  try {
    await page.goto(`${base}/workbench`);
    await page.getByPlaceholder("Stel een vraag of vraag een annotatie…").fill("annoteer artikel 9 lid 1");
    await page.keyboard.press("Enter");
    await page.getByText("De annotatie kon niet worden geopend", { exact: false }).waitFor();
    await page.getByText("Invorderingswet 1990 – art. 9 lid 1", { exact: false }).first().waitFor();
    // Ruim langer dan de eerste herstelpoging (1,5 s) – die mag er niet komen.
    await page.waitForTimeout(4000);
    assert.equal(requests.filter((r) => r.pad === "/api/annotatie/run/f1/events").length, 1, "de afgeronde run is opnieuw gevolgd");
    assert.equal(await page.getByText("De verbinding met Lex is weggevallen", { exact: false }).count(), 0);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
}

// --- F2: een vraag tijdens het laden van het gesprek blijft staan --------------------------------
{
  const { browser, page, errors } = await nieuwePagina(chromium, { viewport: { width: 1440, height: 1000 } });
  try {
    await page.goto(`${base}/workbench?gesprek=g2`);
    await page.getByPlaceholder("Stel een vraag of vraag een annotatie…").fill("Nieuwe vraag");
    await page.keyboard.press("Enter");
    await page.getByText("Nieuw antwoord.", { exact: true }).waitFor();
    await page.getByText("Oud antwoord", { exact: true }).waitFor({ timeout: 10_000 });
    await page.waitForTimeout(300);
    assert.equal(await page.getByText("Nieuwe vraag", { exact: true }).count(), 1, "de vraag verdween bij het laden van de geschiedenis");
    assert.equal(await page.getByText("Nieuw antwoord.", { exact: true }).count(), 1, "het antwoord verdween bij het laden van de geschiedenis");
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
}

// --- Aanraakscherm (iPhone-profiel): zelf markeren via `selectionchange` -----------------------
{
  // Standaard Chromium met het iPhone-profiel (aanraking, `pointerType: "touch"`): dat draait overal.
  // `TOUCH_ENGINE=webkit` gebruikt de Safari-engine zelf, als het systeem de bibliotheken daarvoor heeft.
  const engine = process.env.TOUCH_ENGINE === "webkit" ? webkit : chromium;
  const { defaultBrowserType: _type, ...iphone } = devices["iPhone 13"];
  const { browser, page, errors } = await nieuwePagina(engine, iphone);
  try {
    await page.goto(`${base}/annotaties/node?bron_iri=urn:lid1&snapshot_id=snapshot`);
    await wettekst(page).getByText("ontvanger", { exact: false }).waitFor();
    // Een aanraking, en daarna een selectie zonder mouseup of touchend – zoals na het verslepen van
    // de native selectiegrepen, die geen touch-events aan de pagina geven.
    await page.touchscreen.tap(20, 300);
    await page.evaluate(() => {
      const blok = document.querySelector('[data-tour="wettekst"] [data-offset]');
      const w = document.createTreeWalker(blok, NodeFilter.SHOW_TEXT);
      let knoop = w.nextNode();
      while (knoop && !knoop.data.includes("belastingschuldige")) knoop = w.nextNode();
      const start = knoop.data.indexOf("belastingschuldige");
      const r = document.createRange();
      r.setStart(knoop, start); r.setEnd(knoop, start + "belastingschuldige".length);
      getSelection().removeAllRanges(); getSelection().addRange(r);
    });
    await page.getByRole("dialog", { name: "Markering toevoegen" }).waitFor({ timeout: 5_000 });
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
}

console.log("Browser OK: sneltoetsen alleen in het artefact, Escape voor het bovenste venster, focus terug na sluiten, geen herstellus na een geslaagde beurt, vraag blijft staan tijdens laden, selectie op een aanraakscherm.");
