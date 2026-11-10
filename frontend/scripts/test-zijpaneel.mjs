/** Browserregressie voor het zijpaneel naast het gesprek (het bronvenster, PR 3a). Op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-zijpaneel.mjs`.
 *
 * Bewaakt:
 *  - de scheiding: slepen binnen de grenzen (320 px tot 60%, het gesprek minstens 300 px), de pijltjes als hij de
 *    focus heeft, dubbelklik terug naar de standaard;
 *  - inklappen tot een strook en weer uitklappen, met de inhoud nog op zijn plek;
 *  - vergroten over het gesprek, en Escape verkleint eerst (het paneel blijft open);
 *  - na herladen dezelfde breedte (per browser bewaard); iets anders openen klapt een ingeklapt paneel uit;
 *  - de tabs (PR 3b): elke opening een tab, met de tooltip waar hij vandaan kwam; wisselen, sluiten (de buur wordt actief),
 *    Escape verbergt in plaats van sluit, herladen herstelt de tabs van het gesprek, een nieuw gesprek begint leeg;
 *  - geen horizontale scroll op 375, 800 en 1280 px; onder 800 px geen zijpaneel maar de sheet, met de tabs boven de kop.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const LID = "urn:bwb:BWBR0004770:artikel:9:lid:2";
const TEKST = "In afwijking van het eerste lid is de aanslag invorderbaar op de dagtekening.";
const segment = { bron_iri: LID, parent_iri: "urn:bwb:BWBR0004770:artikel:9", type: "Lid", label: "Lid 2", nummer: "2",
  tekst: TEKST, bron_hash: "h1", volgorde: 1 };
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const berichten = [
  { rol: "user", tekst: "Wat regelt artikel 9 lid 2?", ...leeg },
  { rol: "assistant", tekst: "Artikel 9 lid 2 wijkt af van het eerste lid.", ...leeg,
    bronnen: [{ label: "Invorderingswet 1990, artikel 9 lid 2", uri: "jci1.3:c:BWBR0004770&artikel=9&lid=2" }] },
];
const wg = { id: "wg1", naam: "Invorderbaarheid", status: "in_voorbereiding", revisie: 1, peildatum: null, aangemaakt_door: "t",
  aangemaakt: "2026-10-26T10:00:00Z", gewijzigd: "2026-10-26T10:00:00Z", analysevraag: "Wanneer?", afbakening: "", aanleiding: "",
  context: "", doel: "", praktijkvoorbeeld: "", deelvragen: [],
  bronnen: [{ id: "s1", bron_iri: LID, rol: "analyseren", bereik: "onderliggend", reden: "De afwijking", label: "Artikel 9, lid 2",
    bwb_id: "BWBR0004770", toegevoegd_door: "t", toegevoegd: "", snapshot_id: "", bron_hash: "" }] };

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", titel: "Invordering", werkgebied_id: "wg1", berichten } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Invordering", aantal_berichten: 2, werkgebied_id: "wg1", werkgebied_naam: "Invorderbaarheid" }] });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/annotatie/run") return route.fulfill({ json: m === "GET" ? null : {} });
  if (p === "/api/annotatie/v2/weergave")
    return route.fulfill({ json: { schema_versie: 2, doel: { bron_iri: LID, label: "Artikel 9, lid 2", bwb_id: "BWBR0004770" }, snapshot_id: "snap-1",
      segmenten: [segment], lagen: [], elementen: [], verwijzingen: [], dekking: {} } });
  if (p === "/api/annotatie/v2/bepaling") return route.fulfill({ json: { beschikbaar: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ json: [] });
});

const zijpaneel = page.locator("[data-zijpaneel]");
const scheiding = page.locator("[data-paneel-scheiding]");
/** Wacht tot het zijpaneel in deze stand staat: de stand volgt een klik of toets een render later. */
const stand = async (verwacht, melding = `het zijpaneel is ${verwacht}`) => {
  try {
    await page.locator(`[data-zijpaneel="${verwacht}"]`).waitFor({ timeout: 5000 });
  } catch {
    assert.equal(await zijpaneel.getAttribute("data-zijpaneel"), verwacht, melding);
  }
};
const breedte = async () => (await zijpaneel.boundingBox()).width;
async function openBibliotheek() {
  await page.locator("[data-chatkop-bronnen]").click();
  await page.locator("[data-context-paneel=bibliotheek]").waitFor();
}
async function bronTabOpnieuw() {
  await page.locator("[data-context-bron=s1]").click();
  await page.locator("[data-context-paneel=bron]").waitFor();
}
async function geenScroll(width) {
  const breed = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  assert.ok(!breed, `op ${width}px geen horizontale scroll`);
}

try {
  await page.goto(`${base}/workbench?gesprek=g1`);
  await openBibliotheek();
  await stand("open");
  const standaard = await breedte();
  const ouder = await zijpaneel.evaluate((el) => el.parentElement.clientWidth);
  assert.ok(Math.abs(standaard - Math.min(544, ouder * 0.46)) <= 2, `standaardbreedte ${standaard} (werkplek ${ouder})`);

  // --- Slepen: binnen de grenzen ---
  const s = await scheiding.boundingBox();
  await page.mouse.move(s.x + s.width / 2, s.y + 200);
  await page.mouse.down();
  await page.mouse.move(100, s.y + 200, { steps: 8 });
  await page.mouse.up();
  const max = Math.min(Math.floor(ouder * 0.6), ouder - 300);
  assert.ok(Math.abs((await breedte()) - max) <= 1, `slepen stopt bij de bovengrens (${max})`);
  const t = await page.getByRole("textbox").last().boundingBox();
  assert.ok(t.width >= 300, "het gesprek houdt minstens 300 px");
  const s2 = await scheiding.boundingBox();
  await page.mouse.move(s2.x + s2.width / 2, s2.y + 200);
  await page.mouse.down();
  await page.mouse.move(1270, s2.y + 200, { steps: 8 });
  await page.mouse.up();
  assert.ok(Math.abs((await breedte()) - 320) <= 1, "slepen stopt bij 320 px");

  // --- De pijltjes op de scheiding, als die de focus heeft ---
  await scheiding.focus();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  assert.ok(Math.abs((await breedte()) - 352) <= 1, "← maakt het paneel 16 px breder");
  assert.equal(await scheiding.getAttribute("aria-valuenow"), "352");
  await page.keyboard.press("ArrowRight");
  assert.ok(Math.abs((await breedte()) - 336) <= 1, "→ maakt het smaller");

  // --- Herladen: de breedte blijft ---
  await page.reload();
  await openBibliotheek();
  assert.ok(Math.abs((await breedte()) - 336) <= 1, "na herladen dezelfde breedte");
  await scheiding.dblclick();
  assert.ok(Math.abs((await breedte()) - standaard) <= 2, "dubbelklik zet de standaard terug");

  // --- Inklappen tot een strook, en weer uitklappen ---
  await page.getByRole("button", { name: "Paneel inklappen" }).click();
  await stand("ingeklapt");
  assert.ok((await breedte()) <= 44, "ingeklapt is een strook");
  assert.equal(await page.locator("[data-context-paneel=bibliotheek]").count(), 1, "de inhoud blijft staan");
  await page.getByRole("button", { name: "Paneel uitklappen" }).click();
  await stand("open");
  await page.locator("[data-context-paneel=bibliotheek]").getByText("De afwijking").waitFor();
  // Iets anders openen terwijl het paneel ingeklapt is: het klapt uit (een klik op een ingang doet altijd iets zichtbaars).
  await page.getByRole("button", { name: "Paneel inklappen" }).click();
  await page.locator("[data-context-bron=s1]").evaluate((el) => el.click());
  await page.locator("[data-context-paneel=bron]").waitFor();
  await stand("open", "een nieuwe inhoud klapt het paneel uit");

  // --- Vergroten over het gesprek; Escape verkleint eerst ---
  await page.getByRole("button", { name: "Vergroten", exact: true }).click();
  await stand("vergroot");
  assert.ok((await breedte()) >= ouder - 2, "vergroot ligt het paneel over het gesprek");
  await page.keyboard.press("Escape");
  await stand("open", "Escape verkleint");
  assert.equal(await page.locator("[data-context-paneel=bron]").count(), 1, "en sluit het paneel niet");

  // --- Tabs (PR 3b): wat er open was staat als tab ernaast; wisselen, sluiten, en Escape verbergt ---
  const tabs = page.locator("[data-paneel-tab]");
  await page.locator("[data-chatkop-bronnen]").click();
  await page.locator("[data-context-paneel=bibliotheek]").waitFor();
  assert.deepEqual(await tabs.evaluateAll((els) => els.map((e) => e.getAttribute("data-paneel-tab"))),
    ["bibliotheek:wg1", `bron:${LID}:wg1`], "de bronnen en de bron staan als twee tabs");
  assert.equal(await page.getByRole("tab", { name: "Bronnen", exact: true }).getAttribute("aria-selected"), "true");
  const bronTab = page.getByRole("tab", { name: "Artikel 9, lid 2" });
  assert.match(await bronTab.getAttribute("title"), /geopend vanuit het paneel$/, "de tooltip zegt waar de tab geopend werd");
  await bronTab.click();
  await page.locator("[data-context-paneel=bron]").getByText("invorderbaar op de dagtekening", { exact: false }).waitFor();
  // Escape verbergt: het paneel klapt in, de tabs blijven.
  // De focus op de kop: een klik midden in het paneel kan op een markering landen, die een element als nieuwe tab
  // opent – en een nieuwe opening klapt het paneel juist uit (CI, bundel 28).
  await page.locator("[data-context-paneel=bron] [data-paneel-kop] h2").click();
  await page.keyboard.press("Escape");
  await stand("ingeklapt", "Escape klapt het paneel in");
  await page.getByRole("button", { name: "Paneel uitklappen" }).click();
  assert.equal(await tabs.count(), 2, "de tabs staan er nog");
  // Een tab sluiten: de buur wordt actief.
  await page.getByRole("button", { name: "Sluit tab Artikel 9, lid 2" }).click();
  await page.locator("[data-context-paneel=bibliotheek]").waitFor();
  assert.equal(await tabs.count(), 1);
  // Herladen: de tabs van dit gesprek komen terug, de actieve open.
  await bronTabOpnieuw();
  await page.reload();
  await page.locator("[data-context-paneel=bron]").waitFor();
  assert.equal(await tabs.count(), 2, "na herladen dezelfde tabs");
  // Een nieuw gesprek begint leeg.
  await page.goto(`${base}/workbench`);
  await page.getByRole("textbox").last().waitFor();
  assert.equal(await tabs.count(), 0, "een nieuw gesprek heeft geen tabs");
  assert.equal(await zijpaneel.count(), 0);
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.locator("[data-context-paneel=bron]").waitFor();

  // --- Breedtes: geen horizontale scroll; onder 800 px de sheet ---
  for (const width of [1280, 800]) {
    await page.setViewportSize({ width, height: 800 });
    await geenScroll(width);
    assert.equal(await zijpaneel.count(), 1, `op ${width}px een zijpaneel`);
  }
  await page.setViewportSize({ width: 375, height: 800 });
  await geenScroll(375);
  assert.equal(await zijpaneel.count(), 0, "op een telefoon geen zijpaneel");
  // Op een telefoon: de tabs boven de kop van de sheet; Escape verbergt de sheet, *Paneel · Openen* haalt hem terug.
  await page.locator("[data-paneel-tabs] [data-paneel-tab]").first().waitFor();
  await page.keyboard.press("Escape");
  await page.locator("[data-paneel-terug]").waitFor();
  assert.equal(await page.locator("[data-context-paneel]").count(), 0, "de sheet is weg");
  await page.locator("[data-paneel-terug]").click();
  await page.locator("[data-context-paneel=bron]").waitFor();
  await geenScroll(375);

  assert.deepEqual(errors, []);
  console.log("Browser OK: zijpaneel met scheiding (slepen binnen 320 px–60%, pijltjes, dubbelklik), inklappen tot een strook, vergroten met Escape terug, breedte bewaard na herladen, een nieuwe inhoud klapt uit, geen horizontale scroll op 375/800/1280, op een telefoon de sheet; tabs openen, wisselen, sluiten, herstellen per gesprek, Escape verbergt.");
} finally {
  await browser.close();
}
