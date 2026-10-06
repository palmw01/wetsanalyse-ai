/** Browserregressie voor de 3D-samenhangsgraaf op echte Next-UI met gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * TEST_URL=http://localhost:3109 node scripts/test-samenhang.mjs   (na npx playwright install chromium)
 * Screenshots: MOCK_SCREENSHOTS (default /tmp/wetsanalyse-samenhang).
 * Gebruik `localhost`, niet `127.0.0.1`: Next 16 weigert dev-assets aan een andere origin dan de
 * server kent, en dan hydrateert de pagina niet – elke stap time-out dan zonder duidelijke fout.
 */
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const shots = process.env.MOCK_SCREENSHOTS || "/tmp/wetsanalyse-samenhang";
mkdirSync(shots, { recursive: true });
const LAW = "urn:bwb:BWBR0004770", ART = `${LAW}:artikel:9`, L1 = `${ART}:lid:1`, L2 = `${ART}:lid:2`;
const A10 = `${LAW}:artikel:10`, A10L1 = `${A10}:lid:1`, STUB = "urn:bwb:BWBR0002320:artikel:3";

const knoop = (id, soort, extra = {}) => ({ id, soort, label: id, tekst: "", klasse: "", lifecycle: "", element_id: "",
  bwb_id: "BWBR0004770", artikel: "", lid: "", rand: false, ...extra });
const rel = (bron, doel, soort, groep, anker_tekst = "") => ({ bron, doel, soort, groep, anker_tekst });
function samenhang(iri) {
  if (iri.startsWith(A10)) return { schema_versie: 1, doel: { bron_iri: iri }, snapshot_id: "s10", artikel_iri: A10,
    verwijzingen_beschikbaar: true, afgekapt: false,
    knopen: [knoop(LAW, "regeling", { label: "Invorderingswet 1990" }), knoop(A10, "artikel", { label: "Artikel 10", artikel: "10" }),
      knoop(A10L1, "lid", { label: "Lid 1", artikel: "10", lid: "1", tekst: "De ontvanger kan uitstel verlenen." })],
    relaties: [rel(LAW, A10, "bevat", "structuur"), rel(A10, A10L1, "bevat", "structuur")] };
  return { schema_versie: 1, doel: { bron_iri: iri }, snapshot_id: "s9", artikel_iri: ART, verwijzingen_beschikbaar: true, afgekapt: false,
    knopen: [knoop(LAW, "regeling", { label: "Invorderingswet 1990" }), knoop(ART, "artikel", { label: "Artikel 9", artikel: "9" }),
      knoop(L1, "lid", { label: "Lid 1", artikel: "9", lid: "1", tekst: "De ontvanger vordert de belastingaanslag in." }),
      knoop(L2, "lid", { label: "Lid 2", artikel: "9", lid: "2", tekst: "In afwijking van het eerste lid geldt artikel 10." }),
      knoop("element:e1", "markering", { label: "ontvanger", tekst: "ontvanger", klasse: "Rechtssubject", lifecycle: "voorgesteld", element_id: "e1", artikel: "9", lid: "1",
        herkomst: "agent", aandacht: "" }),
      knoop("klasse:Rechtssubject", "klasse", { label: "Rechtssubject", klasse: "Rechtssubject" }),
      knoop(A10, "artikel", { label: "Artikel 10", artikel: "10", rand: true }),
      knoop(STUB, "extern", { label: "Awb, artikel 3", bwb_id: "BWBR0002320", artikel: "3", rand: true })],
    relaties: [rel(LAW, ART, "bevat", "structuur"), rel(ART, L1, "bevat", "structuur"), rel(ART, L2, "bevat", "structuur"),
      rel(L2, L1, "verwijst_naar", "verwijzingen", "het eerste lid"), rel(L2, A10, "verwijst_naar", "verwijzingen", "artikel 10"),
      rel(L1, STUB, "verwijst_naar", "verwijzingen", "artikel 3 van de Awb"),
      rel("element:e1", L1, "markeert", "annotaties"), rel("element:e1", "klasse:Rechtssubject", "heeft_klasse", "annotaties")] };
}
// Na een mutatie (afronden, markeren, …) levert de api een extra markering op lid 2: zo is te zien
// of de graaf zonder herladen meeloopt.
let bijgewerkt = false;
function samenhangNu(iri) {
  const s = samenhang(iri);
  if (!bijgewerkt || iri.startsWith(A10)) return s;
  return { ...s, knopen: [...s.knopen,
      knoop("element:e2", "markering", { label: "artikel 10", tekst: "artikel 10", klasse: "Rechtsobject", lifecycle: "voorgesteld", element_id: "e2", artikel: "9", lid: "2" }),
      knoop("klasse:Rechtsobject", "klasse", { label: "Rechtsobject", klasse: "Rechtsobject" })],
    relaties: [...s.relaties, rel("element:e2", L2, "markeert", "annotaties"), rel("element:e2", "klasse:Rechtsobject", "heeft_klasse", "annotaties")] };
}
const segment = (iri, lid, tekst) => ({ bron_iri: iri, parent_iri: ART, type: "Lid", nummer: lid, label: `Lid ${lid}`, tekst, bron_hash: `h${lid}`, volgorde: Number(lid) });
function weergave(iri) {
  const segs = [segment(L1, "1", "De ontvanger vordert de belastingaanslag in."), segment(L2, "2", "In afwijking van het eerste lid geldt artikel 10.")]
    .filter((s) => iri === ART || s.bron_iri === iri);
  return { schema_versie: 2, snapshot_id: "s9", segmenten: segs,
    doel: { bron_iri: iri, label: iri === ART ? "Artikel 9" : `Artikel 9 lid ${iri.at(-1)}`, type: iri === ART ? "Artikel" : "Lid",
      bwb_id: "BWBR0004770", artikel: "9", lid: iri === ART ? "" : iri.at(-1), citeertitel: "Invorderingswet 1990" },
    lagen: segs.map((s) => ({ id: `laag${s.nummer}`, bron_iri: s.bron_iri, status: "in_review", revisie: 1 })),
    elementen: segs.some((s) => s.bron_iri === L1) ? [{ id: "e1", eigenaar_iri: L1, laag_id: "laag1", klasse: "Rechtssubject",
      tekst: "ontvanger", toelichting: "Voert de invordering uit", lifecycle: "voorgesteld", herkomst: "agent",
      ankers: [{ bron_iri: L1, start: 3, eind: 12, tekst: "ontvanger", bron_hash: "h1" }],
      trace: { kandidaat: { bewijs: [{ detector: "rol", code: "ROL_ACTOR", regel: "jas.subject.actor" }] }, beslissing: { door: "regel" } } }] : [],
    verwijzingen: [],
    // Dekking: in lid 2 gaf "geldt artikel 10" geen enkele detectortreffer.
    dekking: segs.some((s) => s.bron_iri === L2) ? { voltooid: true, structureel: { [L2]: { dimensies: { actor: "uitgevoerd" },
      ongedekt: [{ tekst: "geldt artikel 10", start: 32, eind: 48 }] } } } : {} };
}
const berichten = [
  { rol: "user", tekst: "Wat regelt artikel 9 lid 2 van de Invorderingswet?", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" },
  { rol: "assistant", tekst: "Artikel 9 lid 2 wijkt af van het eerste lid en verwijst naar artikel 10.", denk: "",
    bronnen: [{ label: "Invorderingswet 1990, artikel 9 lid 2", uri: "jci1.3:c:BWBR0004770&artikel=9&lid=2" }],
    annotatie_slug: "", annotatie_titel: "" },
];

// Een antwoord dat twee artikelen noemt, met de bronnen in de canonieke vorm van graph-qa.
const berichtenTwee = [
  { rol: "user", tekst: "Hoe verhouden artikel 9 en 10 zich?", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" },
  { rol: "assistant", tekst: "Artikel 9 lid 2 verwijst naar artikel 10, dat uitstel regelt.", denk: "",
    bronnen: [
      { label: "Artikel 9, lid 2", uri: L2, bron_iri: L2, jci: "jci1.3:c:BWBR0004770&artikel=9&lid=2", bwb_id: "BWBR0004770", soort: "lid", regeling: "Invorderingswet 1990" },
      { label: "Artikel 10", uri: A10, bron_iri: A10, bwb_id: "BWBR0004770", soort: "artikel", regeling: "Invorderingswet 1990" },
      { label: "Invorderingswet 1990", uri: LAW, bron_iri: LAW, bwb_id: "BWBR0004770", soort: "regeling", regeling: "Invorderingswet 1990" }],
    annotatie_slug: "", annotatie_titel: "" },
];

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });

async function nieuwePagina({ width = 1440, height = 1000, webgl = true } = {}) {
  const page = await browser.newPage({ viewport: { width, height } });
  const log = { errors: [], console: [], samenhang: [], mutaties: [] };
  page.on("pageerror", (e) => log.errors.push(e.message));
  // React meldt in dev dat de CSP geen eval toestaat; in productie gebruikt React geen eval.
  page.on("console", (m) => { if (m.type() === "error" && !/React will never use eval\(\) in production/.test(m.text())) log.console.push(m.text()); });
  await page.context().addCookies(await sessieCookies(base));
  await page.addInitScript((webgl) => {
    localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true }));
    if (!webgl) {
      const orig = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (type, ...rest) { return /webgl/.test(type) ? null : orig.call(this, type, ...rest); };
    }
  }, webgl);
  await page.route("**/api/**", async (route) => {
    const req = route.request(), url = new URL(req.url());
    if (url.pathname.startsWith("/api/auth/")) return route.continue();
    if (req.method() !== "GET") { log.mutaties.push(`${req.method()} ${url.pathname}`); bijgewerkt = true; }
    if (url.pathname.endsWith("/v2/capabilities")) return route.fulfill({ json: { schema_versie: 2, bronnodes_actief: true, samenhang: true } });
    if (url.pathname.endsWith("/v2/samenhang")) { log.samenhang.push(url.searchParams.get("bron_iri")); return route.fulfill({ json: samenhangNu(url.searchParams.get("bron_iri")) }); }
    if (url.pathname.endsWith("/v2/weergave")) return route.fulfill({ json: weergave(url.searchParams.get("bron_iri")) });
    if (url.pathname.endsWith("/v2/elementen/e1")) return route.fulfill({ json: { element: weergave(ART).elementen[0] } });
    if (url.pathname.endsWith("/v2/elementen/e1/graaf")) return route.fulfill({ json: { element_id: "e1", laag_id: "laag1",
      turtle: "<urn:jas:element:e1> a <urn:jas-ns:Markering> .",
      graafcontrole: { laag_id: "laag1", revisie: 1, status: "achterstand", afwijkingen: [], shacl: null } } });
    if (url.pathname === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", user_id: "browser-test", titel: "Samenhang", berichten } });
    if (url.pathname === "/api/gesprekken/g2") return route.fulfill({ json: { id: "g2", user_id: "browser-test", titel: "Twee artikelen", berichten: berichtenTwee } });
    if (url.pathname === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Samenhang", aantal_berichten: 2 }] });
    if (url.pathname.includes("/actief")) return route.fulfill({ status: 404, json: {} });
    if (url.pathname.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (url.pathname.includes("/verklaringen")) return route.fulfill({ json: {
      besluit: { regel: { naam: "vaste regel", uitleg: "" } }, regels: { "jas.subject.actor": { naam: "Handelende partij", uitleg: "" } } } });
    return route.fulfill({ status: 200, json: [] });
  });
  return { page, log };
}

const detail = (page) => page.getByTestId("graaf-detail");
const zoekveld = (page) => page.getByRole("combobox", { name: "Knoop zoeken" });
/** Kies een knoop via het zoekveld (ook als hij verborgen is). */
async function zoekEnKies(page, vraag, id) {
  await zoekveld(page).fill(vraag);
  const optie = page.locator(`[role="option"][data-knoop-id="${id}"]`);
  // De camera- en lijstupdates na een vorige keuze kunnen de lijst kort hertekenen: dan opnieuw openen.
  for (let i = 0; i < 3; i++) {
    try { await optie.click({ timeout: 5000 }); return; } catch { await zoekveld(page).click(); }
  }
  await optie.click();
}
/** De knopen die nu in beeld staan: de lijst bij een lege zoekfocus. */
async function inBeeld(page) {
  await zoekveld(page).fill("");
  // Klikken, niet focussen: na een keuze heeft het veld de focus al, dan vuurt geen focus-event.
  await zoekveld(page).click();
  await page.getByRole("listbox", { name: "Knopen" }).waitFor();
  const ids = await page.locator('[role="option"][data-knoop-id]').evaluateAll((els) => els.map((e) => e.getAttribute("data-knoop-id")));
  await page.keyboard.press("Escape");
  return ids;
}
async function detailsOpen(page) {
  const knop = page.getByRole("button", { name: "Details tonen" });
  if (await knop.count()) await knop.click();
}

// 1. Breed scherm: chatknop opent het paneel direct op de graaf; hint, tooltip, rustige bediening.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina();
  await page.goto(`${base}/workbench?gesprek=g1`);
  // Citatie-chip: "Artikel 9 lid 2" hoort bij de bron van de beurt en opent een bronkaart;
  // "artikel 10" heeft geen bron en blijft gewone tekst.
  await page.getByRole("button", { name: "Artikel 9 lid 2", exact: true }).click();
  await page.getByTestId("bronkaart").getByText("Artikel 9, lid 2", { exact: true }).waitFor();
  await page.screenshot({ path: `${shots}/0-bronkaart.png` });
  assert.equal(await page.getByRole("button", { name: "artikel 10", exact: true }).count(), 0);
  await page.keyboard.press("Escape");
  await page.getByTestId("bronkaart").waitFor({ state: "detached" });
  await page.getByRole("button", { name: /^Bekijk samenhang van/ }).first().click();
  await page.getByTestId("samenhang-graaf").waitFor();
  // StrictMode draait effecten in dev twee keer; tel daarom unieke aanvragen.
  assert.deepEqual([...new Set(log.samenhang)], [L2], "de graaf vraagt de samenhang van de geciteerde bepaling");
  assert.equal(await page.getByRole("button", { name: "3D-graaf" }).getAttribute("aria-pressed"), "true");
  await page.locator('[data-graaf-status="gereed"]').waitFor({ timeout: 20000 });
  await page.getByTestId("graaf-hint").waitFor();
  await page.screenshot({ path: `${shots}/1-graaf.png` });
  // Namen staan als tooltip op de knopen (alleen selectie en buren hebben een vast label).
  const doek = await page.locator('[data-testid="graaf-canvas"] canvas').boundingBox();
  let tooltip = "";
  // Een fijn raster over het hele doek: waar de knopen landen hangt af van wat er in beeld staat.
  for (let i = 0; i < 16 * 14 && !tooltip; i++) {
    await page.mouse.move(doek.x + doek.width * (0.1 + (i % 16) * 0.05), doek.y + doek.height * (0.15 + Math.floor(i / 16) * 0.05));
    await page.waitForTimeout(40);
    // Niet wachten: zonder tooltip op deze plek meteen door naar de volgende.
    const tips = page.locator(".samenhang-tip");
    tooltip = (await tips.count()) ? (await tips.first().textContent()) || "" : "";
  }
  assert.ok(tooltip.length > 0, "een knoop of verbinding toont een tooltip bij hover");
  // Met de laag Annotaties aan staan markeringen en hun JAS-klasse meteen in beeld.
  const begin = await inBeeld(page);
  assert.ok(begin.includes("element:e1") && begin.includes("klasse:Rechtssubject"), "annotaties staan er vanaf het begin");

  // 2. Zoeken kiest een knoop; de inspector toont zijn relaties per soort; de hint verdwijnt.
  await zoekEnKies(page, "lid 2", L2);
  await page.getByTestId("graaf-hint").waitFor({ state: "detached" });
  await detailsOpen(page);
  assert.match(await detail(page).innerText(), /Artikel 9 · lid 2[\s\S]*Verwijst naar/);

  // 3. Een randknoop kies je vanuit de inspector; de hoofdactie opent het artikel (één keer).
  await detail(page).getByRole("button", { name: /^Artikel 10\b/ }).click();
  await page.getByRole("button", { name: "Artikel openen" }).click();
  for (let i = 0; i < 40 && !(await inBeeld(page)).includes(A10L1); i++) await page.waitForTimeout(150);
  assert.ok((await inBeeld(page)).includes(A10L1), "het geopende artikel staat in beeld");
  assert.deepEqual([...new Set(log.samenhang)], [L2, A10], "openen laadt het doelartikel");
  assert.equal(log.samenhang.filter((i) => i === A10).length, 1, "één keer bijladen per klik");

  // 4. Een verborgen, niet-geïmporteerde bepaling: vindbaar via zoeken, zonder hoofdactie.
  await zoekEnKies(page, "awb", STUB);
  assert.match(await detail(page).innerText(), /niet in de kennisgraaf/);
  assert.equal(await page.getByRole("button", { name: "Artikel openen" }).count(), 0, "extern is niet te openen");

  // 5. De schakelaar klapt verbindingen in en uit (dezelfde handeling als dubbelklik).
  await zoekEnKies(page, "lid 1", L1);
  const schakelaar = page.getByRole("switch", { name: /Verbindingen tonen/ });
  const aan = await schakelaar.getAttribute("aria-checked");
  await schakelaar.click();
  assert.notEqual(await schakelaar.getAttribute("aria-checked"), aan);
  // De Awb-bepaling hangt alleen aan lid 1 (in stap 4 stond ze maar tijdelijk in beeld).
  const naKlik = (await inBeeld(page)).includes(STUB);
  await schakelaar.click();
  assert.notEqual((await inBeeld(page)).includes(STUB), naKlik, "de schakelaar verandert wat er in beeld staat");

  // 6. Markering: "Toon in tekst" wisselt naar de tekst met dezelfde keuze.
  await zoekEnKies(page, "ontvanger", "element:e1");
  assert.match(await detail(page).innerText(), /Rechtssubject/);
  // De inspector vertelt hetzelfde als de reviewkaart: één Waarom-uitklap.
  await detail(page).getByText("Waarom?", { exact: true }).click();
  await detail(page).getByText("Handelende partij", { exact: true }).waitFor();
  await detail(page).getByText("vaste regel", { exact: true }).waitFor();
  await detail(page).getByText("Technisch detail", { exact: true }).click();
  await detail(page).getByText("Nog niet in de graaf bijgewerkt", { exact: false }).waitFor();
  await page.getByRole("button", { name: "Toon in tekst" }).click();
  assert.equal(await page.getByRole("button", { name: "Tekst", exact: true }).getAttribute("aria-pressed"), "true");
  await page.locator("[data-artefact]").waitFor();
  await page.getByRole("button", { name: "3D-graaf" }).click();
  assert.match(await detail(page).innerText(), /ontvanger/, "selectie blijft na terugkeren");

  // 6b. Een JAS-klasse kiezen: klasse en markering staan er al (laag Annotaties), en blijven staan.
  await detailsOpen(page);
  await detail(page).getByRole("button", { name: "Rechtssubject", exact: true }).click();
  assert.match(await detail(page).innerText(), /JAS-klasse[\s\S]*Rechtssubject[\s\S]*Markeringen[\s\S]*ontvanger/i);
  const naKlasse = await inBeeld(page);
  assert.ok(naKlasse.includes("klasse:Rechtssubject") && naKlasse.includes("element:e1"), "klasse en markering blijven in beeld");

  // 6c. Een via zoeken getoonde, verborgen knoop staat er alleen zolang hij gekozen is.
  await zoekEnKies(page, "awb", STUB);
  assert.ok((await inBeeld(page)).includes(STUB));
  await zoekEnKies(page, "artikel 9", ART);
  assert.ok(!(await inBeeld(page)).includes(STUB), "een eerder gekozen verborgen knoop blijft niet hangen");

  // 7. Centreren, en ✕ heft de selectie op: de inspector toont de stand van zaken.
  await page.getByRole("button", { name: "Centreren" }).click();
  await page.getByRole("button", { name: "Selectie opheffen" }).click();
  assert.match(await detail(page).innerText(), /Kies een knoop/);

  // 8. Vergroten; Escape van binnen naar buiten: selectie op, dan verkleinen.
  await zoekEnKies(page, "lid 1", L1);
  await page.getByRole("button", { name: "Vergroten" }).click();
  assert.equal(await page.getByTestId("samenhang-graaf").getAttribute("data-vergroot"), "true");
  await page.screenshot({ path: `${shots}/2-vergroot.png` });
  await page.keyboard.press("Escape");
  assert.match(await detail(page).innerText(), /Kies een knoop/, "eerste Escape heft de selectie op");
  assert.equal(await page.getByTestId("samenhang-graaf").getAttribute("data-vergroot"), "true");
  await page.keyboard.press("Escape");
  assert.equal(await page.getByTestId("samenhang-graaf").getAttribute("data-vergroot"), "false");

  // 8b. Laag Dekking: het lid met een zinsdeel zonder detectortreffer toont dat in de inspector;
  // de laag uitzetten haalt het weg (de halo zelf zit in WebGL – zie de screenshot).
  await zoekEnKies(page, "lid 2", L2);
  await detailsOpen(page);
  await detail(page).getByTestId("graaf-dekking").getByText("“geldt artikel 10”").waitFor();
  await page.screenshot({ path: `${shots}/8b-dekking.png` });
  await page.getByRole("button", { name: "Lagen" }).click();
  const dekkingLaag = page.getByRole("group", { name: "Lagen" }).getByRole("checkbox", { name: /Dekking/ });
  assert.ok(await dekkingLaag.isChecked(), "de laag Dekking staat standaard aan");
  await dekkingLaag.uncheck();
  assert.equal(await detail(page).getByTestId("graaf-dekking").count(), 0, "laag uit haalt de dekking uit de inspector");
  await dekkingLaag.check();
  await page.keyboard.press("Escape");

  // 9. Lagen: filters en legenda in één; Escape sluit eerst het lagenpaneel.
  await zoekEnKies(page, "lid 1", L1);
  await page.getByRole("button", { name: "Lagen" }).click();
  const lagen = page.getByRole("group", { name: "Lagen" });
  await lagen.getByRole("checkbox", { name: /Annotaties/ }).uncheck();
  assert.ok(!(await inBeeld(page)).includes("element:e1"), "annotaties uit verbergt markeringen");
  if (!(await lagen.count())) await page.getByRole("button", { name: "Lagen" }).click();
  await lagen.getByRole("checkbox", { name: /Annotaties/ }).check();
  // Markeringsfilter: "keuze voor de jurist" verbergt e1 (geen aandacht), "alle" brengt hem terug.
  await lagen.getByLabel("Markeringen", { exact: true }).selectOption("aandacht");
  for (let i = 0; i < 20 && (await inBeeld(page)).includes("element:e1"); i++) await page.waitForTimeout(150);
  assert.ok(!(await inBeeld(page)).includes("element:e1"), "het markeringsfilter verbergt e1");
  assert.ok((await inBeeld(page)).includes(L1), "structuur blijft staan");
  await lagen.getByLabel("Markeringen", { exact: true }).selectOption("alle");
  for (let i = 0; i < 20 && !(await inBeeld(page)).includes("element:e1"); i++) await page.waitForTimeout(150);
  assert.ok((await inBeeld(page)).includes("element:e1"), "alle brengt e1 terug");
  await page.keyboard.press("Escape");
  assert.equal(await lagen.count(), 0, "Escape sluit het lagenpaneel");

  // 10. Weergave Omgeving ⇄ Alles keert terug naar de eerdere stand.
  const omgeving = (await inBeeld(page)).length;
  await page.getByRole("button", { name: "Alles", exact: true }).click();
  assert.equal(await page.getByRole("button", { name: "Alles", exact: true }).getAttribute("aria-pressed"), "true");
  assert.ok((await inBeeld(page)).length >= omgeving);
  await page.getByRole("button", { name: "Omgeving" }).click();
  assert.equal((await inBeeld(page)).length, omgeving, "Omgeving keert terug naar de eerdere stand");

  // 11. Beeldknoppen.
  for (const naam of ["Inzoomen", "Uitzoomen", "Alles in beeld"]) await page.getByRole("button", { name: naam }).click();

  // 12. Vraag Lex over een bron zet de vraag klaar, zonder iets te versturen.
  await zoekEnKies(page, "artikel 10", A10L1);
  await page.getByRole("button", { name: "Vraag Lex" }).click();
  assert.match(await page.locator("textarea").inputValue(), /Hoe hangt .*BWBR0004770, artikel 10, lid 1/);
  assert.deepEqual(log.mutaties, [], "de graaf muteert niets");

  // 13. Een annotatiewijziging werkt de graaf bij zonder herladen.
  const voor = log.samenhang.filter((i) => i === L2).length;
  await page.getByRole("button", { name: "Tekst", exact: true }).click();
  await page.getByRole("button", { name: /afronden/i }).first().click();
  await page.getByRole("button", { name: "3D-graaf" }).click();
  for (let i = 0; i < 40 && !(await inBeeld(page)).includes("element:e2"); i++) await page.waitForTimeout(250);
  assert.ok((await inBeeld(page)).includes("element:e2"), "de nieuwe markering staat in beeld");
  assert.ok(log.samenhang.filter((i) => i === L2).length > voor, "de graaf haalt de samenhang opnieuw op");
  assert.ok((await inBeeld(page)).includes(A10L1), "het geopende artikel blijft in beeld");
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 13b. Een antwoord dat twee artikelen noemt: de knop zegt het, de graaf opent beide als cluster,
// de bronnenlijst staat per regeling, en een knoop uit het tweede artikel opent dát in het paneel.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina();
  await page.goto(`${base}/workbench?gesprek=g2`);
  await page.getByRole("button", { name: /^Bronnen \(3\)/ }).click();
  assert.match(await page.locator('[data-tour="bronnen"]').innerText(), /Invorderingswet 1990 – Artikel 9, lid 2, Artikel 10/);
  await page.getByRole("button", { name: "Bekijk samenhang van de 2 genoemde artikelen in 3D" }).click();
  await page.getByTestId("samenhang-graaf").waitFor();
  await page.getByText("Samenhang van 2 artikelen").waitFor();
  assert.deepEqual([...new Set(log.samenhang)].sort(), [A10, L2].sort(), "beide genoemde artikelen geladen");
  await zoekEnKies(page, "Artikel 10", A10);
  await page.getByRole("button", { name: "Open in het paneel" }).waitFor();
  await page.screenshot({ path: `${shots}/2b-twee-artikelen.png` });
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 14. Mobiel: inspector onder de graaf, in te klappen; zoeken werkt met het toetsenbord.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina({ width: 390, height: 844 });
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByRole("button", { name: /^Bekijk samenhang van/ }).click();
  await page.getByTestId("samenhang-graaf").waitFor();
  await zoekveld(page).fill("lid 1");
  await page.keyboard.press("Enter");
  assert.match(await detail(page).innerText(), /Artikel 9 · lid 1/);
  await page.getByRole("button", { name: "Details tonen" }).click();
  assert.match(await detail(page).innerText(), /Onderdeel van/);
  await page.getByRole("button", { name: "Details inklappen" }).click();
  const hoogte = (await page.locator('[data-testid="graaf-canvas"]').boundingBox()).height;
  assert.ok(hoogte >= 200, `het canvas houdt hoogte (${hoogte}px)`);
  await page.screenshot({ path: `${shots}/3-mobiel.png` });
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 15. Zonder WebGL blijven zoeken, lagen en de inspector bruikbaar.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina({ webgl: false });
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByRole("button", { name: /^Bekijk samenhang van/ }).click();
  await page.getByText("Deze browser kan de 3D-weergave niet openen.").waitFor();
  await zoekEnKies(page, "lid 1", L1);
  assert.match(await detail(page).innerText(), /Artikel 9 · lid 1/);
  await page.getByRole("button", { name: "Lagen" }).click();
  await page.getByRole("group", { name: "Lagen" }).waitFor();
  await page.screenshot({ path: `${shots}/4-zonder-webgl.png` });
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

await browser.close();
console.log(`samenhang: alle controles geslaagd; screenshots in ${shots}`);
