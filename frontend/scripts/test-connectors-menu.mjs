/** Browserregressie voor het menu *Bronnen en tools* boven het invoerveld (ADR-013), op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-connectors-menu.mjs`.
 *
 * Bewaakt:
 *  - zonder connector bij de beheerder is er geen menu en gaat er geen `bronnen` mee;
 *  - met een connector staat *Wetgeving · Kamerstukken* boven het invoerveld, en een beurt draagt `bronnen`;
 *  - uitzetten in een nieuw gesprek gaat mee met de beurt en wordt na het aanmaken op het gesprek bewaard;
 *  - na herladen komt de stand van het gesprek terug (`Gesprek.connectors`);
 *  - in een werkgebied geldt zijn standaard, en *Maak dit de standaard* zet `standaard_connectors` met de revisie;
 *  - een beurt draagt de herkomst van de stand (`bronnen_herkomst`), en na een `bron_uit` zet *Zet … aan* de bron aan in
 *    het gesprek; een bron die de beheerder uitzette krijgt geen knop;
 *  - was graph-qa niet te lezen (beschikbaarheid `onbekend`), dan staat de bron er zonder schakelaar, gaat de keuze
 *    ongewijzigd mee met de beurt, en komt de schakelaar terug zodra de stand bij het openen weer bekend is.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const nu = "2026-11-08T10:00:00+00:00";
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const KST = { naam: "kamerstukken", label: "Kamerstukken", brontype: "kamerstuk" };

const GOED = [{ type: "token", content: "Goed." }, { type: "done" }];

async function open({ beschikbaar = [KST], gesprekConnectors, wgStandaard = null, url = "/workbench", events = GOED } = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const errors = [], runs = [], patches = [], wgPatches = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await context.addCookies(await sessieCookies(base));
  await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  const stand = { connectors: gesprekConnectors ?? null, wg: { id: "wg1", naam: "Invordering", status: "in_voorbereiding", revisie: 3,
    peildatum: null, aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, analysevraag: "", afbakening: "", aanleiding: "",
    context: "", doel: "", praktijkvoorbeeld: "", bronnen: [], deelvragen: [], standaard_connectors: wgStandaard } };
  await page.route("**/api/**", async (route) => {
    const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
    if (p.startsWith("/api/auth/")) return route.continue();
    if (p === "/api/connectors") {
      const lijst = typeof beschikbaar === "function" ? beschikbaar() : beschikbaar;
      return route.fulfill({ json: { aan: lijst.map((c) => c.naam), connectors: lijst } });
    }
    if (p === "/api/annotatie/run") {
      if (m === "GET") return route.fulfill({ json: null });
      runs.push(req.postDataJSON());
      return route.fulfill({ json: { run_id: "live", conversation_id: req.postDataJSON().conversation_id, status: "loopt" } });
    }
    if (p === "/api/annotatie/run/live/events")
      return route.fulfill({ contentType: "text/event-stream", body: sse(events) });
    if (p === "/api/werkgebieden/wg1" && m === "PATCH") {
      const body = req.postDataJSON();
      wgPatches.push(body);
      stand.wg = { ...stand.wg, ...body, revisie: stand.wg.revisie + 1 };
      return route.fulfill({ json: stand.wg });
    }
    if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: stand.wg });
    if (p === "/api/gesprekken/g1" && m === "PATCH") {
      const body = req.postDataJSON();
      patches.push(body);
      if ("connectors" in body) stand.connectors = body.connectors;
      return route.fulfill({ json: { id: "g1", titel: "Test", connectors: stand.connectors, berichten: [] } });
    }
    if (p === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", titel: "Test", connectors: stand.connectors, berichten: [] } });
    if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g1", titel: "", berichten: [] } });
    if (p === "/api/gesprekken") return route.fulfill({ json: [] });
    if (p.endsWith("/berichten") && m === "POST") return route.fulfill({ json: { id: 1 } });
    if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
    return route.fulfill({ json: [] });
  });
  await page.goto(`${base}${url}`);
  await page.getByRole("textbox").last().waitFor();
  return { page, context, errors, runs, patches, wgPatches, stand };
}

const wachtOp = async (page, lijst, n) => {
  for (let i = 0; i < 200 && lijst.length < n; i++) await page.waitForTimeout(50);
  assert.ok(lijst.length >= n, `verwacht ${n}, kreeg ${lijst.length}`);
};
const vraag = async (page, tekst) => {
  await page.getByRole("textbox").last().fill(tekst);
  await page.keyboard.press("Enter");
};
const menu = (page) => page.locator("[data-connectors-menu]");

// 1. Zonder connector: geen menu, geen `bronnen`.
{
  const { page, context, errors, runs } = await open({ beschikbaar: [] });
  await page.waitForTimeout(500);
  assert.equal(await menu(page).count(), 0, "geen menu zonder connector");
  await vraag(page, "Wat zegt artikel 9 Iw?");
  await wachtOp(page, runs, 1);
  assert.equal("bronnen" in runs[0], false);
  assert.deepEqual(errors, []);
  await context.close();
}

// 2. Met een connector: aan als standaard, uitzetten gaat mee en wordt bewaard; herladen houdt het.
{
  const { page, context, errors, runs, patches, stand } = await open();
  await menu(page).waitFor();
  assert.equal(await menu(page).getAttribute("aria-label"), "Bronnen: Wetgeving aan, Kamerstukken aan");
  await vraag(page, "Eerste vraag");
  await wachtOp(page, runs, 1);
  assert.deepEqual(runs[0].bronnen, ["kamerstukken"]);

  await menu(page).click();
  await page.getByRole("menuitemradio", { name: "Kamerstukken" }).click();
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label")?.includes("Kamerstukken uit"));
  await wachtOp(page, patches, 1);
  assert.deepEqual(patches.at(-1), { connectors: [] });
  await page.keyboard.press("Escape");
  await vraag(page, "Tweede vraag");
  await wachtOp(page, runs, 2);
  assert.deepEqual(runs[1].bronnen, []);
  assert.deepEqual(stand.connectors, []);

  await page.goto(`${base}/workbench?gesprek=g1`);
  await menu(page).waitFor();
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label")?.includes("Kamerstukken uit"));
  assert.deepEqual(errors, []);
  await context.close();
}

// 3. In een nieuw gesprek gekozen vóór er een gesprek was: na het aanmaken bewaard.
{
  const { page, context, errors, runs, patches } = await open();
  await menu(page).click();
  await page.getByRole("menuitemradio", { name: "Kamerstukken" }).click();
  await page.keyboard.press("Escape");
  assert.equal(patches.length, 0, "nog geen gesprek, dus nog niets bewaard");
  await vraag(page, "Een vraag");
  await wachtOp(page, runs, 1);
  assert.deepEqual(runs[0].bronnen, []);
  await wachtOp(page, patches, 1);
  assert.deepEqual(patches[0], { connectors: [] });
  assert.deepEqual(errors, []);
  await context.close();
}

// 4. In een werkgebied: zijn standaard geldt, en *Maak dit de standaard* zet hem met de revisie.
{
  const { page, context, errors, runs, wgPatches } = await open({ wgStandaard: [], url: "/workbench?werkgebied=wg1" });
  await menu(page).waitFor();
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label")?.includes("Kamerstukken uit"));
  await vraag(page, "Vraag in het werkgebied");
  await wachtOp(page, runs, 1);
  assert.deepEqual(runs[0].bronnen, []);
  await menu(page).click();
  await page.getByText("De standaard van dit werkgebied.").waitFor();
  await page.getByRole("menuitemradio", { name: "Kamerstukken" }).click();
  await page.getByRole("menuitem", { name: "Maak dit de standaard van het werkgebied" }).click();
  await wachtOp(page, wgPatches, 1);
  assert.deepEqual(wgPatches[0], { verwachte_revisie: 3, standaard_connectors: ["kamerstukken"] });
  assert.deepEqual(errors, []);
  await context.close();
}

// 5. Een vraag naar een bron die uit staat: de herkomst gaat mee, en *Zet Kamerstukken aan* zet hem aan in het gesprek.
{
  const uit = (reden) => [{ type: "bron_uit", bronnen: [{ naam: "kamerstukken", label: "Kamerstukken", reden }] },
    { type: "token", content: "Kamerstukken staat uit in dit gesprek." }, { type: "done" }];
  const { page, context, errors, runs, patches } = await open({ gesprekConnectors: [], url: "/workbench?gesprek=g1", events: uit("gesprek") });
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label")?.includes("Kamerstukken uit"));
  await vraag(page, "Wat staat er in de memorie van toelichting?");
  await wachtOp(page, runs, 1);
  assert.equal(runs[0].bronnen_herkomst, "gesprek");
  await page.getByRole("button", { name: "Zet Kamerstukken aan" }).click();
  await wachtOp(page, patches, 1);
  assert.deepEqual(patches.at(-1), { connectors: ["kamerstukken"] });
  await page.waitForFunction(() => !document.querySelector("[data-bron-uit]"));
  assert.deepEqual(errors, []);
  await context.close();

  const b = await open({ events: uit("beheerder") });
  await vraag(b.page, "Wat staat er in de memorie van toelichting?");
  await wachtOp(b.page, b.runs, 1);
  await b.page.getByText("Kamerstukken staat uit in dit gesprek.").waitFor();
  assert.equal(await b.page.locator("[data-bron-uit]").count(), 0, "de beheerder zet je niet aan vanuit het gesprek");
  await b.context.close();
}

// 6. graph-qa niet te lezen: geen schakelaar die niets doet (review ADR-013, punt 2), en terug zodra de stand bekend is.
{
  let bekend = false;
  const beschikbaar = () => [{ ...KST, beschikbaarheid: bekend ? "aan" : "onbekend" }];
  const { page, context, errors, runs, patches } = await open({ beschikbaar, gesprekConnectors: ["kamerstukken"],
    url: "/workbench?gesprek=g1" });
  await menu(page).waitFor();
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label")?.includes("Kamerstukken onbekend"));
  await menu(page).click();
  await page.locator("[data-connector-onbekend=kamerstukken]").waitFor();
  assert.equal(await page.getByRole("menuitemradio", { name: "Kamerstukken" }).count(), 0, "geen schakelaar bij een onbekende stand");
  await page.locator("[data-connector-onbekend=kamerstukken]").click();
  await page.waitForTimeout(300);
  assert.equal(patches.length, 0, "een klik op een onbekende bron verandert niets");
  await page.keyboard.press("Escape");
  await vraag(page, "Wat staat er in de memorie van toelichting?");
  await wachtOp(page, runs, 1);
  assert.deepEqual(runs[0].bronnen, ["kamerstukken"], "de beurt houdt de opgeslagen keuze");

  bekend = true;
  await menu(page).click();
  await page.getByRole("menuitemradio", { name: "Kamerstukken" }).waitFor();
  assert.deepEqual(errors, []);
  await context.close();
}

console.log("ok - Bronnen en tools");
await browser.close();
