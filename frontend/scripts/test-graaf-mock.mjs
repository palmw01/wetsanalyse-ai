/** Echte 3D-browsercontrole. Start eerst `npm run mock:graaf`. */
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const base = process.env.TEST_URL || "http://127.0.0.1:3110";
const artifacts = process.env.MOCK_SCREENSHOTS || "/tmp/wetsanalyse-graaf-mock";
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true, args: ["--enable-unsafe-swiftshader"] });
const errors = [], apiCalls = [];
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, reducedMotion: "reduce" });
page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
page.on("request", (request) => { if (new URL(request.url()).pathname.startsWith("/api/")) apiCalls.push({ method: request.method(), url: request.url() }); });
page.setDefaultTimeout(15000);
const klaar = () => page.locator('[data-graaf-status="gereed"] canvas').waitFor({ state: "visible" });
const detail = () => page.getByTestId("graaf-detail");
async function knoop(id) {
  if (await page.getByRole("button", { name: "Knopenlijst", exact: true }).getAttribute("aria-expanded") !== "true")
    await page.getByRole("button", { name: "Knopenlijst", exact: true }).click();
  await page.locator(`[data-knoop-id="${id}"]`).click();
}
try {
  await page.goto(`${base}/mock/graaf`, { waitUntil: "networkidle", timeout: 90000 });
  await klaar();
  assert.equal(await page.title(), "3D-workbench · Interactieve mock");
  assert.equal(await page.locator("canvas").count(), 1);
  await page.screenshot({ path: `${artifacts}/01-chat-en-graaf.png` });
  console.log("Chat en 3D geladen.");

  const canvas = page.locator("canvas");
  // Klik de donkerblauwe regeling in de werkelijk gerenderde canvas aan.
  // Beeldherkenning voorkomt een testhaak naar de interne Three.js-selectie.
  const png = await canvas.screenshot();
  assert.ok(png.length > 4500, "De gereedmelding mag geen lege canvas opleveren");
  const bronPixel = await page.evaluate(async (encoded) => {
    const img = new Image(); img.src = `data:image/png;base64,${encoded}`; await img.decode();
    const c = document.createElement("canvas"); c.width = img.width; c.height = img.height;
    const ctx = c.getContext("2d"); ctx.drawImage(img, 0, 0);
    const { data } = ctx.getImageData(0, 0, c.width, c.height);
    const mask = new Uint8Array(c.width * c.height);
    for (let i = 0; i < data.length; i += 4) {
      const [r, g, b] = data.subarray(i, i + 3);
      if (b > r * 1.7 && b > 35 && b < 130 && g < 100) mask[i / 4] = 1;
    }
    const groepen = [];
    for (let i = 0; i < mask.length; i++) {
      if (!mask[i]) continue;
      const todo = [i]; mask[i] = 0;
      let x = 0, y = 0, aantal = 0;
      while (todo.length) {
        const p = todo.pop(), px = p % c.width, py = Math.floor(p / c.width);
        x += px; y += py; aantal++;
        for (const [nx, ny] of [[px-1,py], [px+1,py], [px,py-1], [px,py+1]]) {
          const n = ny * c.width + nx;
          if (nx >= 0 && nx < c.width && ny >= 0 && ny < c.height && mask[n]) { mask[n] = 0; todo.push(n); }
        }
      }
      if (aantal > 20) groepen.push({ x: x / aantal, y: y / aantal, aantal });
    }
    return groepen.sort((a, b) => a.x - b.x)[0];
  }, png.toString("base64"));
  assert.ok(bronPixel.aantal > 20, "De bronknoop is zichtbaar");
  const klikBox = await canvas.boundingBox();
  await page.mouse.move(klikBox.x + bronPixel.x, klikBox.y + bronPixel.y);
  await page.waitForTimeout(100);
  await canvas.click({ position: { x: bronPixel.x, y: bronPixel.y }, delay: 80 });
  await detail().getByRole("heading", { name: "Invorderingswet 1990", exact: true }).waitFor();
  assert.match(await detail().innerText(), /REGELING\s+Invorderingswet 1990/);
  const voor = await canvas.screenshot();
  const box = await canvas.boundingBox();
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.45);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.55 + 100, box.y + box.height * 0.45 + 55, { steps: 12 });
  await page.mouse.up();
  await page.waitForTimeout(300);
  assert.notEqual(Buffer.compare(voor, await canvas.screenshot()), 0, "Draaien verandert de echte canvasweergave");

  await knoop("urn:bwb:BWBR0004770:artikel:9:lid:2");
  assert.match(await detail().innerText(), /In afwijking van het eerste lid/);
  await detail().getByRole("button", { name: /Toon verbindingen \(\+/ }).click();
  assert.ok(await page.locator("[data-knoop-id]").count() > 7, "Uitklappen toont extra markeringen");
  await knoop("demo-el-3");
  assert.match(await detail().innerText(), /Tijdsaanduiding/);
  await page.getByRole("button", { name: "Knopenlijst", exact: true }).click();
  await detail().getByRole("button", { name: "Open brontekst", exact: true }).click();
  assert.match(await page.locator("[data-artefact] mark").first().innerText(), /zes weken/);
  await page.screenshot({ path: `${artifacts}/02-annotatie-en-tekst.png` });
  await page.getByRole("button", { name: "3D-graaf", exact: true }).click();
  assert.match(await detail().innerText(), /zes weken/);
  console.log("Uitklappen en selectie tussen graaf en tekst gecontroleerd.");

  await page.getByRole("button", { name: "Vergroten", exact: true }).click();
  await klaar();
  assert.equal(await page.getByTestId("graaf-paneel").getAttribute("data-vergroot"), "true");
  await page.getByRole("button", { name: "Hele voorbeeld tonen", exact: true }).click();
  await page.getByRole("button", { name: "Alles in beeld", exact: true }).click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${artifacts}/03-vergrote-graaf.png` });
  await page.getByRole("button", { name: "Verkleinen", exact: true }).click();
  await klaar();
  assert.match(await detail().innerText(), /zes weken/);
  await detail().getByRole("button", { name: "Vraag Lex hierover", exact: true }).click();
  assert.match(await page.locator("textarea").inputValue(), /Waarom is dit een Tijdsaanduiding/);
  await page.getByRole("button", { name: "Versturen", exact: true }).click();
  await page.getByText("Voorbeeldantwoord bij", { exact: false }).waitFor();
  console.log("Vergroten, terugkeren en de lokale voorbeeldchat gecontroleerd.");

  await page.getByLabel("Annotaties", { exact: true }).uncheck();
  assert.match(await detail().innerText(), /Selecteer een zichtbare knoop/);
  await page.getByLabel("Annotaties", { exact: true }).check();
  assert.match(await detail().innerText(), /Tijdsaanduiding/);
  await page.getByRole("button", { name: "Paneel sluiten", exact: true }).click();
  await page.getByRole("button", { name: /Bekijk samenhang in 3D/ }).first().click();
  await klaar();
  await page.getByRole("button", { name: /JAS-annotaties verkennen/ }).click();
  await page.getByRole("button", { name: "3D-graaf", exact: true }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Tekst", exact: true }).getAttribute("aria-pressed"), "true");
  await page.getByRole("button", { name: "3D-graaf", exact: true }).click();
  await klaar();
  await knoop("demo-el-3");
  await page.getByRole("button", { name: "Knopenlijst", exact: true }).click();
  await detail().getByRole("button", { name: "Open brontekst", exact: true }).click();
  await page.keyboard.press("a");
  await page.getByRole("button", { name: "3D-graaf", exact: true }).click();
  // De bestaande review springt na akkoord naar de volgende markering.
  await knoop("demo-el-3");
  assert.match(await detail().innerText(), /akkoord/, "Lokaal beoordelen werkt door naar het graafdetail");
  await page.getByRole("textbox", { name: "Knopen zoeken" }).fill("bestaat niet");
  await page.getByText("Geen knopen gevonden.", { exact: true }).waitFor();
  await page.getByRole("textbox", { name: "Knopen zoeken" }).fill("");
  await knoop("urn:bwb:BWBR0004770:artikel:9");
  await page.getByRole("button", { name: "Knopenlijst", exact: true }).click();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "3D-graaf", exact: true }).click();
  await klaar();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "Geen horizontale overflow op mobiel");
  await page.screenshot({ path: `${artifacts}/04-mobiel.png` });
  await detail().getByRole("button", { name: "Vraag Lex hierover", exact: true }).click();
  await page.getByTestId("graaf-paneel").waitFor({ state: "detached" });
  assert.ok((await page.locator("textarea").inputValue()).length > 0, "Vraag wordt zichtbaar in de mobiele chat klaargezet");
  console.log("Mobiele overlay, filters en wisselen van voorbeeld gecontroleerd.");

  const fallback = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await fallback.addInitScript(() => {
    const origineel = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (soort, ...args) {
      if (soort === "webgl2") return null;
      return origineel.call(this, soort, ...args);
    };
  });
  await fallback.goto(`${base}/mock/graaf`, { waitUntil: "networkidle" });
  await fallback.getByText("Deze browser kan de 3D-weergave niet openen.", { exact: false }).waitFor();
  await fallback.getByRole("button", { name: "Knopenlijst", exact: true }).click();
  assert.ok(await fallback.locator("[data-knoop-id]").count() > 0);
  await fallback.close();

  const beschermd = await page.request.get(`${base}/workbench`, { maxRedirects: 0 });
  assert.ok([302, 303, 307, 308].includes(beschermd.status()), "De echte workbench blijft achter login");
  assert.equal(apiCalls.filter((r) => !r.url.endsWith("/api/auth/session")).length, 0, JSON.stringify(apiCalls));
  assert.equal(apiCalls.filter((r) => r.method !== "GET").length, 0, "Geen backendmutaties");
  assert.deepEqual(errors, [], "Geen browserfouten");
  console.log(`Geslaagd. Screenshots: ${artifacts}`);
} catch (error) {
  await page.screenshot({ path: `${artifacts}/fout.png` }).catch(() => {});
  console.error("Browserfouten:", errors);
  throw error;
} finally { await browser.close(); }
