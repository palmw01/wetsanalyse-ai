/** Browserregressie voor de tab *Diagram* van het annotatiepaneel (deelactiviteit 2c, Handleiding §3.4c; vraag gebruiker
 * 24 nov 2026: het diagram ook in de UI tonen bij het accorderen, en daar relaties kunnen toevoegen). Op de echte Next-UI
 * met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-diagram-tab.mjs`.
 *
 * De data is art. 9 lid 1 Invorderingswet 1990 zoals in het werkgebied Termijnen op acceptatie; de diagrammen in
 * `diagram-art9.json` zijn uitgerekend door de api-code zelf (`diagram.diagrammen`, `annotatie_v2._diagram_json`), vóór en
 * na het leggen van de voorwerp-relatie. Bewaakt:
 *  - *Annotatie afronden* opent eerst de tab Diagram (zonder af te ronden); daarna rondt dezelfde knop wél af;
 *  - het diagram rond de rechtsbetrekking met wat nog ontbreekt (rechthebbende, plichthebbende, voorwerp);
 *  - een lijn kiezen toont de relatie bovenaan in het blok *Relaties* van haar kant in deze bepaling;
 *  - *+ voorwerp* opent *Verbind met…* met alleen de markeringen die die rol kunnen hebben, het type voorgekozen; verbinden
 *    stuurt de relatie en het diagram toont haar daarna;
 *  - de bediening van de graaf: knoppen rechtsonder, zoomen met het muiswiel, slepen, Alles in beeld;
 *  - toegankelijk (axe) en geen horizontale scroll.
 * Met `SCHERMAFBEELDINGEN=<map>` bewaart hij de standen (voor de PR).
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { chromium } from "playwright";
import { toetsToegankelijkheid } from "./axe.mjs";
import { SCHIL, controleerOnbekend, onbekend } from "./nepApi.mjs";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const map = process.env.SCHERMAFBEELDINGEN;
const F = JSON.parse(readFileSync(new URL("./diagram-art9.json", import.meta.url), "utf8"));
const L1 = "urn:bwb:BWBR0004770:artikel:9:lid:1";

const stand = { revisie: 3, gelegd: false, afgerond: false, diagramVerzoeken: 0 };
const view = () => ({
  schema_versie: 2, snapshot_id: "snapshot",
  doel: { bron_iri: L1, label: "Invorderingswet 1990 – Artikel 9, Lid 1", type: "Lid", bwb_id: "BWBR0004770", artikel: "9", lid: "1",
    citeertitel: "Invorderingswet 1990", snapshot_id: "snapshot" },
  segmenten: [{ bron_iri: L1, parent_iri: "urn:bwb:BWBR0004770:artikel:9", type: "Lid", nummer: "1", label: "Lid 1", tekst: F.tekst,
    bron_hash: "h1", volgorde: 1 }],
  lagen: [{ id: "laag1", bron_iri: L1, status: stand.afgerond ? "geaccordeerd" : "in_review", revisie: stand.revisie }],
  elementen: F.elementen, verwijzingen: [], dekking: {}, impliciet: [],
  relaties: stand.gelegd ? [...F.relaties, F.relatie_na] : F.relaties,
});

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true })).newPage();
const errors = [], verzoeken = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname;
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p.includes("/v2/") && req.method() !== "GET") verzoeken.push({ p, body: req.postDataJSON() });
  if (p.endsWith("/v2/weergave")) return route.fulfill({ json: view() });
  if (p.endsWith("/v2/diagrammen")) {
    assert.equal(url.searchParams.get("bron_iri"), L1);
    stand.diagramVerzoeken += 1;
    return route.fulfill({ json: stand.gelegd ? F.diagrammen_na : F.diagrammen });
  }
  if (p.endsWith("/v2/relaties") && req.method() === "POST") {
    stand.gelegd = true;
    stand.revisie += 1;
    return route.fulfill({ status: 201, json: { relatie: F.relatie_na } });
  }
  if (p.endsWith("/v2/lagen/laag1/status")) {
    stand.afgerond = true;
    stand.revisie += 1;
    return route.fulfill({ json: {} });
  }
  // *Exporteren* in *Groot bekijken*: de SVG van de api (`GET /v1/annotatie/diagram?vorm=svg`).
  if (p.endsWith("/v2/diagram") && new URL(req.url()).searchParams.get("vorm") === "svg")
    return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect x="10" y="10" width="180" height="80" fill="#90a2d0"/></svg>' });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  if (p.endsWith("/v2/bepaling")) return route.fulfill({ json: { beschikbaar: false } });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return onbekend(route, { stil: [...SCHIL, /^GET \/api\//], leeg: [] });
});

try {
  await page.goto(`${base}/annotaties/node?bron_iri=${encodeURIComponent(L1)}&snapshot_id=snapshot`);
  await page.locator('[data-review-kaart="rb"]').waitFor();
  const tabs = page.locator("[data-weergave-tab]");
  assert.deepEqual(await tabs.allInnerTexts(), ["Tekst", "Diagram"], "zonder kennisgraaf: Tekst en Diagram");

  // Afronden opent eerst het diagram, en rondt nog niet af.
  await page.getByRole("button", { name: "Annotatie afronden" }).click();
  const kaart = page.locator('[data-diagram-kaart="rb"]');
  await kaart.waitFor();
  assert.equal(verzoeken.filter((v) => v.p.endsWith("/status")).length, 0, "afronden wacht op het diagram");
  await page.locator("[data-diagram-tab]").getByText("Bekijk eerst de samenhang:").waitFor();
  assert.equal(await page.locator("[data-diagram-kaart]").count(), 1, "één diagram: de afleidingsregel hangt in dat van de rechtsbetrekking");
  const svg = kaart.locator("[data-diagram-2c]");
  for (const k of ["element:rb", "element:ta", "element:ar"]) {
    assert.equal(await svg.locator(`[data-diagram-knoop="${k}"]`).count(), 1, `knoop ${k} staat in het diagram`);
  }
  // De uitzonderingen uit lid 5–7 zijn een tekstuele relatie: in de lijst Relaties, niet in het diagram (Handleiding §3.4c).
  assert.equal(await svg.locator('[data-diagram-knoop="element:u5"]').count(), 0, "geen tekstuele relatie in het diagram");
  assert.deepEqual(await kaart.locator("[data-ontbreekt] button").allInnerTexts(), ["+ rechthebbende", "+ plichthebbende", "+ voorwerp"]);
  if (map) await page.screenshot({ path: `${map}/diagram-tab.png` });

  // De bediening van de graaf: knoppen rechtsonder, het muiswiel zoomt, slepen verschuift, Alles in beeld zet terug.
  const zoomStand = async () => Number(await kaart.locator("[data-diagram-zoom]").getAttribute("data-diagram-zoom"));
  const viewBox = async () => (await svg.getAttribute("viewBox")).split(" ").map(Number);
  assert.equal(await zoomStand(), 1, "alles in beeld");
  // Geen knoppen voor in- en uitzoomen (melding gebruiker 24 nov 2026): dat gaat met het muiswiel en twee vingers.
  assert.equal(await kaart.getByRole("button", { name: "Inzoomen" }).count(), 0, "geen knop Inzoomen");
  assert.equal(await kaart.getByTestId("graaf-hint").count(), 0, "geen uitleg in het diagram");
  const s = await svg.boundingBox();
  await page.mouse.move(s.x + s.width / 2, s.y + s.height / 2);
  await page.mouse.wheel(0, -400);
  await page.waitForFunction(() => Number(document.querySelector("[data-diagram-zoom]").getAttribute("data-diagram-zoom")) > 1.3);
  if (map) await page.screenshot({ path: `${map}/diagram-ingezoomd.png` });
  await page.mouse.move(s.x + s.width / 2, s.y + s.height / 2);
  const voorWiel = await zoomStand();
  await page.mouse.wheel(0, -400);
  await page.waitForFunction((v) => Number(document.querySelector("[data-diagram-zoom]").getAttribute("data-diagram-zoom")) > v, voorWiel);
  const [x0] = await viewBox();
  await page.mouse.down();
  await page.mouse.move(s.x + s.width / 2 - 120, s.y + s.height / 2 + 40, { steps: 6 });
  await page.mouse.up();
  assert.ok((await viewBox())[0] > x0 + 10, "slepen verschuift het beeld");
  assert.equal(await page.locator("[data-diagram-gekozen]").count(), 0, "slepen kiest niets");
  await kaart.getByRole("button", { name: "Alles in beeld" }).click();
  assert.equal(await zoomStand(), 1, "Alles in beeld zet terug");

  // *Groot bekijken*: alleen dit diagram in een venster boven de pagina, met *Exporteren* (SVG en PNG) en een kruisje.
  await kaart.getByRole("button", { name: "Groot bekijken" }).click();
  const grootVenster = page.locator("[data-tekening-venster]");
  await grootVenster.locator("[data-diagram-2c]").waitFor();
  assert.equal(await grootVenster.getByRole("button", { name: "Groot bekijken" }).count(), 0, "in het venster geen tweede Groot bekijken");
  if (map) await page.screenshot({ path: `${map}/diagram-groot.png` });
  for (const [formaat, ext] of [["SVG", ".svg"], ["PNG", ".png"]]) {
    await grootVenster.getByRole("button", { name: "Exporteren" }).click();
    const [dl] = await Promise.all([page.waitForEvent("download"), page.locator(`[data-export="${formaat.toLowerCase()}"]`).click()]);
    assert.ok(dl.suggestedFilename().endsWith(ext), `download ${dl.suggestedFilename()}`);
    assert.ok(dl.suggestedFilename().startsWith("diagram-rechtsbetrekking-"), dl.suggestedFilename());
    const inhoud = await import("node:fs").then((fs) => dl.path().then((p) => fs.readFileSync(p)));
    if (ext === ".png") assert.equal(inhoud.subarray(1, 4).toString(), "PNG", "een echte PNG");
    else assert.match(inhoud.toString(), /<svg/, "een echte SVG");
  }
  if (map) await page.screenshot({ path: `${map}/diagram-groot-export.png` });
  await page.keyboard.press("Escape");
  await grootVenster.waitFor({ state: "detached" });

  // Twee vingers knijpen, zoals in de graaf (melding gebruiker 24 nov 2026: op mobiel zoomde het diagram niet). Echte
  // touch-events via het DevTools-protocol: de browser maakt er pointer-events van, zoals op een telefoon.
  const cdp = await page.context().newCDPSession(page);
  const mx = s.x + s.width / 2, my = s.y + s.height / 2;
  const vingers = (d) => [{ x: mx - d, y: my, id: 1 }, { x: mx + d, y: my, id: 2 }];
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: vingers(20) });
  for (const d of [30, 45, 60, 80]) await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: vingers(d) });
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  assert.ok(await zoomStand() > 2.5, `knijpen zoomt in (zoom ${await zoomStand()})`);
  assert.equal(await page.locator("[data-diagram-gekozen]").count(), 0, "knijpen kiest niets");
  await kaart.getByRole("button", { name: "Alles in beeld" }).click();
  assert.equal(await zoomStand(), 1);

  // Een lijn kiezen: de relatie staat bovenaan in het blok van haar kant in deze bepaling, met nadruk.
  await svg.locator('[data-diagram-lijn="R-tijd"]').click();
  const gekozen = page.locator('[data-diagram-gekozen="element:rb"]');
  await gekozen.waitFor();
  const eerste = gekozen.locator("[data-relatie]").first();
  assert.equal(await eerste.getAttribute("data-relatie"), "R-tijd");
  assert.equal(await eerste.getAttribute("data-nadruk"), "true");
  assert.equal(await gekozen.locator("[data-diagram]").count(), 0, "geen tweede diagram in het blok");
  if (map) await page.screenshot({ path: `${map}/diagram-lijn-gekozen.png` });
  // Dezelfde knoppen als de graaf: bij een keuze staat *Terug* bij de beeldknoppen, en de achtergrond is ook terug.
  const knoppen = await kaart.getByRole("group", { name: "Beeld" }).boundingBox();
  const venster = await svg.boundingBox();
  assert.ok(knoppen.x + knoppen.width > venster.x + venster.width - 30, "de knoppen staan rechtsonder, zoals in de graaf");
  await kaart.getByRole("button", { name: "Naar het hele diagram" }).click();
  await gekozen.waitFor({ state: "detached" });
  assert.equal(await kaart.getByRole("button", { name: "Naar het hele diagram" }).count(), 0, "zonder keuze geen Terug");
  await svg.locator('[data-diagram-lijn="R-tijd"]').click();
  await gekozen.waitFor();
  const vlak = await svg.boundingBox();
  await page.mouse.click(vlak.x + 4, vlak.y + 4);
  await gekozen.waitFor({ state: "detached" });
  await svg.locator('[data-diagram-lijn="R-tijd"]').click();
  await gekozen.waitFor();

  // + voorwerp: Verbind met… opent, alleen met wat een voorwerp kan zijn, en het type voorgekozen.
  await kaart.getByRole("button", { name: "+ voorwerp" }).click();
  const andere = gekozen.getByLabel("Andere kant");
  const opties = (await andere.locator("option").allInnerTexts()).slice(1);
  assert.deepEqual(opties, ["Rechtsobject: “Een belastingaanslag”", "Rechtsobject: “het aanslagbiljet”"]);
  await andere.selectOption({ label: "Rechtsobject: “Een belastingaanslag”" });
  assert.equal(await gekozen.getByLabel("Soort relatie").inputValue(), "uit:voorwerp");
  await gekozen.locator("[data-verbind-zin]").waitFor();
  if (map) await page.screenshot({ path: `${map}/diagram-verbinden.png` });
  const verzoekenVoor = stand.diagramVerzoeken;
  await gekozen.getByRole("button", { name: "Verbinden", exact: true }).click();
  await page.waitForFunction(() => document.querySelectorAll('[data-diagram-lijn="R-nieuw"]').length === 1);
  // In sync: na elke wijziging (nieuwe revisie van de laag) haalt het diagram zich opnieuw op, uit de api.
  assert.ok(stand.diagramVerzoeken > verzoekenVoor, "het diagram is na de wijziging opnieuw opgehaald");
  const gelegd = verzoeken.find((v) => v.p.endsWith("/v2/relaties"));
  assert.deepEqual({ van: gelegd.body.van, naar: gelegd.body.naar, type: gelegd.body.type },
    { van: { soort: "element", id: "rb" }, naar: { soort: "element", id: "ro" }, type: "voorwerp" });
  assert.deepEqual(gelegd.body.verwachte_revisies, { [L1]: 3 });
  assert.deepEqual(await kaart.locator("[data-ontbreekt] button").allInnerTexts(), ["+ rechthebbende", "+ plichthebbende"]);
  await kaart.locator('[data-diagram-knoop="element:ro"]').waitFor();
  assert.equal(await page.getByText("Leg de relatie voorwerp").count(), 0, "een vastgelegde rol is geen opdracht meer");
  if (map) await page.screenshot({ path: `${map}/diagram-na-verbinden.png` });

  await toetsToegankelijkheid(page, "tab Diagram");
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), "geen horizontale scroll");

  // Nu rondt dezelfde knop af.
  await Promise.all([page.waitForResponse((r) => r.url().endsWith("/v2/lagen/laag1/status")),
    page.getByRole("button", { name: "Annotatie afronden" }).click()]);
  // Afgerond: alleen te lezen, geen aanvulknoppen meer (wel nog wat ontbreekt).
  await page.waitForFunction(() => !document.querySelector("[data-ontbreekt] button"));
  assert.equal(await kaart.locator("[data-ontbreekt]").count(), 1);

  // Smal: het diagram schaalt mee, geen horizontale scroll, en doorlopend: de keuze direct onder het diagram, zonder dat
  // het diagram in een venster van 45% gevangen zit (melding gebruiker: veel witruimte onder het diagram).
  await page.setViewportSize({ width: 420, height: 900 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), "smal: geen horizontale scroll");
  const [tk, lk] = await page.evaluate(() => ["[data-tekst-kolom]", "[data-lijst-kolom]"].map((q) => {
    const el = document.querySelector(`[data-diagram-tab]`).closest(".tekst-en-lijst").querySelector(`:scope > ${q}`);
    const r = el.getBoundingClientRect();
    return { top: r.top, bottom: r.bottom, binnen: el.scrollHeight - el.clientHeight };
  }));
  assert.ok(tk.binnen <= 1, "smal: het diagram heeft geen eigen scroll");
  assert.ok(Math.abs(lk.top - tk.bottom) <= 2, "smal: de keuze staat direct onder het diagram");
  if (map) await page.screenshot({ path: `${map}/diagram-smal.png`, fullPage: false });

  assert.deepEqual(errors, []);
  controleerOnbekend();
  console.log("Browser OK: tab Diagram (afronden vraagt eerst het diagram, ontbrekende rollen, lijn kiezen, verbinden met voorgekozen type, afronden, smal).");
} finally {
  await browser.close();
}
