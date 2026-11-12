/** Browserregressie voor de testomgeving-strook bovenaan de schil. Op de echte Next-UI met een gemockte BFF. Start Next
 * met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-teststrook.mjs`.
 *
 * Bewaakt, op 375 en 1280 px:
 *  - het kruisje (*Melding testomgeving verbergen*) klikt de strook weg;
 *  - na herladen en in een tweede tab blijft hij weg, en een tab die al openstond volgt;
 *  - uitloggen via het gebruikersmenu en opnieuw inloggen brengt hem terug, net als een ander account;
 *  - *Voorwaarden testomgeving* in het gebruikersmenu opent de voorwaarden.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const errors = [];

async function mock(context) {
  await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  await context.route("**/api/**", async (route) => {
    const p = new URL(route.request().url()).pathname;
    if (p.startsWith("/api/auth/")) return route.continue();
    if (p === "/api/annotatie/run") return route.fulfill({ json: null });
    if (p === "/api/werkgebieden") return route.fulfill({ json: { werkgebieden: [] } });
    if (p === "/api/gesprekken") return route.fulfill({ json: [] });
    if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (p === "/api/disclaimer") return route.fulfill({ status: 204, body: "" });
    if (p === "/api/account/me") return route.fulfill({ json: { userid: "browser-test", email: "t@example.test", role: "analist",
      totp_enabled: false, tfa_nodig: false, rondleiding_knop: false } });
    return route.fulfill({ json: [] });
  });
}

const strook = (page) => page.locator("[data-teststrook]");
const kruisje = (page) => page.getByRole("button", { name: "Melding testomgeving verbergen" });

/** Het gebruikersmenu onderin de sidebar; op een telefoon eerst de drawer. */
async function openMenu(page, smal) {
  if (smal) await page.getByRole("button", { name: "Menu openen" }).click();
  await page.getByRole("button", { name: /· instellingen/ }).click();
}

async function ronde(breedte) {
  const smal = breedte < 1024;
  const context = await browser.newContext({ viewport: { width: breedte, height: 900 } });
  await mock(context);
  await context.addCookies(await sessieCookies(base, { loginAt: 1_000 }));
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(`${breedte}: ${e.message}`));
  // Een tab die al openstaat voordat de strook wordt weggeklikt.
  const ander = await context.newPage();
  ander.on("pageerror", (e) => errors.push(`${breedte} (andere tab): ${e.message}`));

  try {
    await page.goto(`${base}/workbench`);
    await ander.goto(`${base}/workbench`);
    await strook(page).waitFor();
    await strook(ander).waitFor();
    await strook(page).getByRole("link", { name: /Lees de voorwaarden/ }).waitFor();
    const doos = await strook(page).boundingBox();
    assert.ok(doos && doos.width <= breedte, `de strook past op ${breedte} px`);
    const knop = await kruisje(page).boundingBox();
    assert.ok(knop && knop.x + knop.width <= breedte, `het kruisje staat in beeld op ${breedte} px`);

    // --- Wegklikken ---
    await kruisje(page).click();
    await strook(page).waitFor({ state: "detached" });
    await strook(ander).waitFor({ state: "detached" }); // de open tab volgt (storage-event)

    // --- Herladen en een tweede tab ---
    await page.reload();
    await page.getByRole("button", { name: /· instellingen/ }).or(page.getByRole("button", { name: "Menu openen" })).first().waitFor();
    assert.equal(await strook(page).count(), 0, "na herladen blijft de strook weg");
    const tweede = await context.newPage();
    await tweede.goto(`${base}/workbench`);
    await tweede.getByRole("button", { name: /· instellingen/ }).or(tweede.getByRole("button", { name: "Menu openen" })).first().waitFor();
    assert.equal(await strook(tweede).count(), 0, "in een tweede tab blijft de strook weg");
    await tweede.close();

    // --- De voorwaarden blijven bereikbaar ---
    await openMenu(page, smal);
    await page.getByRole("link", { name: "Voorwaarden testomgeving" }).click();
    await page.waitForURL("**/disclaimer");
    await page.getByText("Testomgeving, geen productie").waitFor();
    if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/teststrook-voorwaarden-${breedte}.png` });
    await page.goto(`${base}/workbench`);

    // --- Uitloggen en opnieuw inloggen ---
    await openMenu(page, smal);
    await page.getByRole("button", { name: "Uitloggen" }).click();
    await page.waitForURL("**/login**");
    // Elke `GET /api/auth/session` zet het sessiecookie opnieuw (jwt-strategie). Een verzoek dat nog onderweg is,
    // kan het nieuwe cookie dus overschrijven met de oude stand: eerst moet de oude login stil zijn. De andere tab
    // vraagt na het uitloggen ook de sessie op; die is hierna niet meer nodig.
    await ander.close();
    await page.waitForLoadState("networkidle");
    // Opnieuw inloggen: een nieuwe sessie met een later inlogmoment, zoals de jwt-callback die zet.
    await context.addCookies(await sessieCookies(base, { loginAt: 2_000 }));
    await page.goto(`${base}/workbench`);
    await verwachtSessie(page, "browser-test", 2_000);
    await strook(page).waitFor();
    if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/teststrook-${breedte}.png` });

    // --- Wegklikken, dan een ander account in dezelfde browser ---
    await kruisje(page).click();
    await strook(page).waitFor({ state: "detached" });
    // Dezelfde browser = dezelfde localStorage, met de sleutel van deze login erin. Het andere account komt in een
    // context met die opslag maar zonder de cookies van de oude: dan kan geen verzoek van de vorige login zijn
    // sessiecookie nog terugzetten (zie hierboven), en dat gebeurde in de poort.
    const staat = await context.storageState();
    const opgeslagen = staat.origins.flatMap((o) => o.localStorage).find((r) => r.name === "wa-teststrook-weg");
    assert.equal(opgeslagen?.value, "browser-test:2000", "de weggeklikte sleutel van deze login staat in de opslag");
    const tweedeAccount = await browser.newContext({ viewport: { width: breedte, height: 900 },
      storageState: { cookies: [], origins: staat.origins } });
    try {
      await mock(tweedeAccount);
      await tweedeAccount.addCookies(await sessieCookies(base, { userid: "ander-account", loginAt: 2_000 }));
      const anderAccount = await tweedeAccount.newPage();
      anderAccount.on("pageerror", (e) => errors.push(`${breedte} (ander account): ${e.message}`));
      await anderAccount.goto(`${base}/workbench`);
      await verwachtSessie(anderAccount, "ander-account", 2_000);
      await strook(anderAccount).waitFor();
    } finally {
      await tweedeAccount.close();
    }
  } finally {
    await context.close();
  }
}

/** De pagina draait echt als deze login; anders zegt een ontbrekende strook niets over de strook. */
async function verwachtSessie(page, userid, loginAt) {
  const sessie = await page.evaluate(async () => (await fetch("/api/auth/session")).json());
  assert.equal(sessie?.user?.loginSleutel, `${userid}:${loginAt}`, `de pagina draait als ${userid}:${loginAt}`);
}

try {
  await ronde(375);
  await ronde(1280);
  assert.deepEqual(errors, []);
  console.log("Browser OK: teststrook wegklikbaar op 375 en 1280 px; weg na herladen, in een tweede tab en in een open tab; terug na uitloggen en inloggen en bij een ander account; voorwaarden via het gebruikersmenu.");
} finally {
  await browser.close();
}
