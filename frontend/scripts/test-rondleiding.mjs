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
 *  - er gaat niets muterends naar de api;
 *  - de knop *Laat me de werkplek zien* staat er voor een nieuwe gebruiker en blijft na wegklikken, halverwege stoppen en
 *    afronden zonder vinkje; met het vinkje aan het eind is hij weg, ook op een andere computer (die biedt de rondleiding
 *    dan ook niet meer aan);
 *  - in de instellingen zet je de knop aan en uit, en start je de rondleiding; de werkplek volgt zonder herladen.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const errors = [];
const mutaties = [];

/** Het account in de api: dat reist mee naar elke computer. */
const nieuwAccount = () => ({ userid: "wpalm", email: "w@example.test", role: "analist", totp_enabled: false, tfa_nodig: false,
  herstelcodes_over: 0, rondleiding_aangeboden: 0, rondleiding_knop: true });

async function nieuwePagina(viewport, account = nieuwAccount(), patches = []) {
  // Elke context is een andere computer: lege `localStorage`, hetzelfde account.
  const page = await (await browser.newContext({ viewport })).newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await page.context().addCookies(await sessieCookies(base));
  await page.route("**/api/**", async (route) => {
    const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
    if (p.startsWith("/api/auth/")) return route.continue();
    if (m !== "GET" && (p.startsWith("/api/annotatie") || p.startsWith("/api/gesprekken"))) mutaties.push(`${m} ${p}`);
    if (p === "/api/account/me") return route.fulfill({ json: account });
    if (p === "/api/account/rondleiding") {
      const body = req.postDataJSON();
      patches.push(body);
      if (body.aangeboden !== undefined) account.rondleiding_aangeboden = body.aangeboden;
      if (body.knop !== undefined) account.rondleiding_knop = body.knop;
      return route.fulfill({ json: { rondleiding_aangeboden: account.rondleiding_aangeboden, rondleiding_knop: account.rondleiding_knop } });
    }
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

const knop = (page) => page.getByRole("button", { name: "Laat me de werkplek zien" });

/** Tot het slot, met *Volgende*; de stap die om een klik vraagt krijgt die. */
async function totHetSlot(page) {
  for (let i = 0; i < 30; i++) {
    if (await page.getByRole("button", { name: "Aan de slag" }).isVisible()) return;
    if ((await titel(page)) === "De annotatie openen") await page.locator('[data-tour="chip"]').click();
    else await bubbel(page).getByRole("button", { name: /Volgende|Klaar|Afronden/ }).click();
    await page.waitForTimeout(200);
  }
  throw new Error("het slot van de rondleiding komt niet in beeld");
}

/** De levensloop van de knop, over twee computers. */
async function knopVolgtDeGebruiker() {
  const account = nieuwAccount(), patches = [];
  const page = await nieuwePagina({ width: 1280, height: 860 }, account, patches);
  await page.goto(`${base}/workbench`);

  // Nu even niet: de rondleiding biedt zich niet meer aan, de knop blijft.
  await page.getByRole("button", { name: "Nu even niet" }).click();
  await knop(page).waitFor();
  assert.equal(account.rondleiding_aangeboden > 0, true, "wegklikken hoort het aanbod af te handelen");
  assert.equal(account.rondleiding_knop, true);

  // Halverwege stoppen is nog niet gezien.
  await knop(page).click();
  await page.getByRole("button", { name: "Start de rondleiding" }).click();
  await bubbel(page).waitFor();
  await bubbel(page).getByRole("button", { name: "Overslaan" }).click();
  await knop(page).waitFor();
  assert.equal(account.rondleiding_knop, true, "halverwege stoppen hoort de knop te laten staan");

  // Afronden zonder vinkje laat hem ook staan: weg gaat hij alleen op eigen keuze.
  const doorlopen = async () => {
    await knop(page).click();
    await page.getByRole("button", { name: "Start de rondleiding" }).click();
    await bubbel(page).waitFor();
    await totHetSlot(page);
  };
  await doorlopen();
  await page.getByRole("button", { name: "Aan de slag" }).click();
  await knop(page).waitFor();
  assert.equal(account.rondleiding_knop, true, "afronden zonder vinkje hoort de knop te laten staan");

  // Het vinkje: aan en weer uit verandert de voorkeur, en aan laat de knop verdwijnen.
  await doorlopen();
  const vinkje = page.getByRole("checkbox", { name: "Toon de knop op het startscherm niet meer" });
  await vinkje.check();
  await vinkje.uncheck();
  assert.equal(account.rondleiding_knop, true);
  await vinkje.check();
  await page.getByRole("button", { name: "Aan de slag" }).click();
  await knop(page).waitFor({ state: "detached" });
  assert.equal(account.rondleiding_knop, false, "het vinkje hoort de knop uit te zetten");
  assert.deepEqual(patches.at(-1), { knop: false });
  await page.close();

  // Een andere computer: geen aanbod en geen knop.
  const ander = await nieuwePagina({ width: 1280, height: 860 }, account, patches);
  const verzoek = ander.waitForResponse((r) => r.url().endsWith("/api/account/me"));
  await ander.goto(`${base}/workbench`);
  await verzoek;
  await ander.waitForTimeout(800);
  assert.equal(await ander.getByRole("button", { name: "Start de rondleiding" }).count(), 0, "de andere computer hoort niets aan te bieden");
  assert.equal(await knop(ander).count(), 0, "de andere computer hoort de knop niet te tonen");

  // De instellingen als venster over de werkplek: aanzetten werkt door zodra het venster sluit, zonder herladen.
  await ander.getByRole("button", { name: /instellingen/ }).first().click();
  await ander.getByRole("link", { name: "Account & instellingen" }).click();
  await ander.getByRole("tab", { name: "Rondleiding" }).click();
  await ander.getByRole("checkbox", { name: "Toon de knop op het startscherm" }).check();
  await ander.getByRole("button", { name: "Instellingen sluiten" }).click();
  await knop(ander).waitFor();
  await ander.close();
}

/** De tab in de instellingen: de knop aan en uit, en de rondleiding starten. */
async function instellingen(account) {
  const page = await nieuwePagina({ width: 1280, height: 860 }, account);
  await page.goto(`${base}/instellingen/rondleiding`);
  const vinkje = page.getByRole("checkbox", { name: "Toon de knop op het startscherm" });
  await vinkje.waitFor();
  assert.equal(await vinkje.isChecked(), false);
  await vinkje.check();
  await page.waitForFunction(() => document.querySelector("#rondleiding-knop")?.checked);
  assert.equal(account.rondleiding_knop, true, "het vinkje hoort in de api te landen");

  await page.getByRole("button", { name: "Start de rondleiding" }).click();
  await page.waitForURL(/\/workbench/);
  await page.getByRole("button", { name: "Start de rondleiding" }).click();
  await bubbel(page).waitFor();
  assert.ok(!page.url().includes("rondleiding="), "de vraag hoort uit de url te verdwijnen");
  await bubbel(page).getByRole("button", { name: "Overslaan" }).click();
  await knop(page).waitFor();
  await page.close();
}

try {
  // --- De knop ---
  await knopVolgtDeGebruiker();
  await instellingen({ ...nieuwAccount(), rondleiding_aangeboden: 999, rondleiding_knop: false });

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
  // Het icoon-idioom (spoor I4): de eerste Enter zet het vinkje op *Akkoord?*, de tweede beslist.
  await page.keyboard.press("Enter");
  await kaart.getByRole("button", { name: "Akkoord?" }).waitFor();
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
