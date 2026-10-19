/** Browserregressie voor de rondleiding door de werkplek. Op de echte Next-UI met een gemockte BFF.
 * Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-rondleiding.mjs`.
 *
 * Alle andere browserscripts zetten de rondleiding uit; dit script is de enige die hem doorloopt.
 *
 * Bewaakt, op een breed scherm en op een telefoon:
 *  - de rondleiding biedt zich aan bij een lege `wa_rondleiding`, en de bubbel staat in beeld;
 *  - "De annotatie openen" wacht op de gebruiker: zonder klik gebeurt er niets, en een klik op de kaart
 *    opent het paneel en gaat door naar de wettekst (eerst opende een timer het paneel vanzelf);
 *  - Enter op *Vorige* gaat terug in plaats van vooruit;
 *  - in "Jij beslist" keurt Enter op *Akkoord* goed zonder dat de rondleiding doorspringt, en de
 *    bevestiging staat er na terug- en vooruitbladeren nog;
 *  - Escape in het klassepalet sluit alleen het palet;
 *  - herladen halverwege biedt *Verder bij stap n*;
 *  - de voorbeeldannotatie staat in het bronnodepaneel, net als echt werk;
 *  - er gaat niets muterends naar de api.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const errors = [];
const mutaties = [];

async function nieuwePagina(viewport) {
  const page = await browser.newPage({ viewport });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.context().addCookies(await sessieCookies(base));
  await page.route("**/api/**", async (route) => {
    const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
    if (p.startsWith("/api/auth/")) return route.continue();
    if (m !== "GET" && (p.startsWith("/api/annotatie") || p.startsWith("/api/gesprekken"))) mutaties.push(`${m} ${p}`);
    if (p === "/api/gesprekken") return route.fulfill({ json: [] });
    if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
    if (p === "/api/annotatie/run") return route.fulfill({ json: null });
    return route.fulfill({ json: [] });
  });
  return page;
}

const bubbel = (page) => page.locator("[data-rondleiding-bubbel]");
const titel = async (page) => (await bubbel(page).locator("p").first().innerText()).trim();

/** Blader met → tot de bubbel deze titel draagt. De focus staat na elke stap op de kop van de bubbel. */
async function naarStap(page, gezocht) {
  for (let i = 0; i < 20; i++) {
    if ((await titel(page)) === gezocht) return;
    await bubbel(page).locator("p").first().focus();
    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(150);
  }
  throw new Error(`stap "${gezocht}" niet gevonden, staat op "${await titel(page)}"`);
}

async function start(page) {
  await page.goto(`${base}/workbench`);
  await page.getByRole("button", { name: "Start de rondleiding" }).click();
  await bubbel(page).waitFor();
  await binnenBeeld(page);
}

/** De bubbel staat helemaal in beeld. Een gecentreerde bubbel stond met zijn linkerbovenhoek op het
 *  midden van het scherm (de animatie overschreef de `transform`), en op een telefoon viel *Volgende*
 *  dan buiten beeld. */
async function binnenBeeld(page) {
  await page.waitForTimeout(600); // de animatie van de bubbel
  const r = await bubbel(page).boundingBox();
  const { width, height } = page.viewportSize();
  assert.ok(r && r.x >= 0 && r.y >= 0 && r.x + r.width <= width && r.y + r.height <= height,
    `de bubbel valt buiten beeld: ${JSON.stringify(r)} in ${width}×${height}`);
}

/** De openen-stap: zonder klik blijft alles staan, met een klik gaat het paneel open. */
async function openenWachtOpKlik(page) {
  await naarStap(page, "De annotatie openen");
  // De oude timer stond op 6 s.
  await page.waitForTimeout(8000);
  assert.equal(await page.locator('[data-tour="wettekst"]').count(), 0, "het paneel hoort niet vanzelf open te gaan");
  assert.equal(await titel(page), "De annotatie openen", "de rondleiding hoort niet vanzelf door te lopen");
  await page.locator('[data-tour="chip"]').click();
  await page.locator('[data-tour="wettekst"]').waitFor();
  await page.waitForFunction(() =>
    document.querySelector("[data-rondleiding-bubbel] p")?.textContent?.trim() === "De wettekst");
}

try {
  // --- Breed scherm ---
  const page = await nieuwePagina({ width: 1440, height: 1000 });
  await start(page);
  assert.match(await bubbel(page).innerText(), /Stap 1 van \d+/);

  // Enter op de kop gaat verder; Enter op *Vorige* gaat terug.
  const eerste = await titel(page);
  await bubbel(page).locator("p").first().focus();
  await page.keyboard.press("Enter");
  await page.waitForTimeout(150);
  assert.notEqual(await titel(page), eerste, "Enter op de kop hoort een stap verder te gaan");
  await bubbel(page).getByRole("button", { name: "Vorige" }).focus();
  await page.keyboard.press("Enter");
  await page.waitForTimeout(150);
  assert.equal(await titel(page), eerste, "Enter op Vorige hoort terug te gaan");

  await openenWachtOpKlik(page);
  await binnenBeeld(page);
  // De demo staat in hetzelfde paneel als echt werk (`NodeAnnotatiePaneel`): alleen dat kent Verwijderen.
  await page.locator('[data-tour="artefact-acties"]').getByRole("button", { name: /verwijderen/i }).waitFor();

  // "Jij beslist": Enter op Akkoord beslist, en de rondleiding blijft staan.
  await naarStap(page, "Jij beslist");
  const kaart = page.locator('[data-tour="review-kaart"]');
  await kaart.click({ position: { x: 24, y: 12 } });
  const akkoord = kaart.getByRole("button", { name: /^Akkoord/ }).first();
  await akkoord.waitFor();
  await akkoord.focus();
  await page.keyboard.press("Enter");
  await bubbel(page).getByText(/^Beoordeeld\./).waitFor();
  assert.equal(await titel(page), "Jij beslist", "Enter op Akkoord hoort de rondleiding niet door te zetten");

  // De bevestiging blijft bij de stap.
  await bubbel(page).getByRole("button", { name: "Vorige" }).click();
  await bubbel(page).getByRole("button", { name: "Volgende" }).click();
  await bubbel(page).getByText(/^Beoordeeld\./).waitFor();

  // Escape in het klassepalet sluit alleen het palet.
  const badge = page.locator('[data-tour="review-kaart"] button[title="Andere klasse kiezen"]').first();
  await badge.click();
  await badge.focus();
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  assert.equal(await bubbel(page).count(), 1, "Escape in het palet hoort de rondleiding open te laten");

  // Herladen halverwege: hervatten.
  const waar = await titel(page);
  await page.reload();
  const verder = page.getByRole("button", { name: /^Verder bij stap \d+$/ });
  await verder.waitFor();
  await verder.click();
  await page.waitForFunction((t) =>
    document.querySelector("[data-rondleiding-bubbel] p")?.textContent?.trim() === t, waar);
  await page.locator('[data-tour="wettekst"]').waitFor();
  await page.close();

  // --- Telefoon ---
  const mobiel = await nieuwePagina({ width: 390, height: 844 });
  await start(mobiel);
  await openenWachtOpKlik(mobiel);
  await mobiel.close();

  assert.deepEqual(mutaties, [], "de rondleiding hoort niets naar de api te sturen");
  assert.deepEqual(errors, []);
  console.log("rondleiding: alle controles geslaagd");
} finally {
  await browser.close();
}
