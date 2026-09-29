/** Browserregressie voor de 3D-samenhangsgraaf op echte Next-UI met gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * TEST_URL=http://127.0.0.1:3109 node scripts/test-samenhang.mjs   (na npx playwright install chromium)
 * Screenshots: MOCK_SCREENSHOTS (default /tmp/wetsanalyse-samenhang).
 */
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
import { encode } from "../node_modules/next-auth/jwt.js";

const base = process.env.TEST_URL || "http://127.0.0.1:3109";
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
      knoop("element:e1", "markering", { label: "ontvanger", tekst: "ontvanger", klasse: "Rechtssubject", lifecycle: "voorgesteld", element_id: "e1", artikel: "9", lid: "1" }),
      knoop("klasse:Rechtssubject", "klasse", { label: "Rechtssubject", klasse: "Rechtssubject" }),
      knoop(A10, "artikel", { label: "Artikel 10", artikel: "10", rand: true }),
      knoop(STUB, "extern", { label: "Awb, artikel 3", bwb_id: "BWBR0002320", artikel: "3", rand: true })],
    relaties: [rel(LAW, ART, "bevat", "structuur"), rel(ART, L1, "bevat", "structuur"), rel(ART, L2, "bevat", "structuur"),
      rel(L2, L1, "verwijst_naar", "verwijzingen", "het eerste lid"), rel(L2, A10, "verwijst_naar", "verwijzingen", "artikel 10"),
      rel(L1, STUB, "verwijst_naar", "verwijzingen", "artikel 3 van de Awb"),
      rel("element:e1", L1, "markeert", "annotaties"), rel("element:e1", "klasse:Rechtssubject", "heeft_klasse", "annotaties")] };
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
      ankers: [{ bron_iri: L1, start: 3, eind: 12, tekst: "ontvanger", bron_hash: "h1" }] }] : [],
    verwijzingen: [], dekking: {} };
}
const berichten = [
  { rol: "user", tekst: "Wat regelt artikel 9 lid 2 van de Invorderingswet?", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" },
  { rol: "assistant", tekst: "Lid 2 wijkt af van het eerste lid en verwijst naar artikel 10.", denk: "",
    bronnen: [{ label: "Invorderingswet 1990, artikel 9 lid 2", uri: "jci1.3:c:BWBR0004770&artikel=9&lid=2" }],
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
  const token = await encode({ secret: process.env.AUTH_SECRET || "annotatie-browser-test-only-secret", salt: "authjs.session-token",
    token: { userid: "browser-test", role: "analist", email: "test@example.test", verifiedAt: Date.now(), loginAt: Date.now() } });
  await page.context().addCookies([
    { name: "authjs.session-token", value: token, url: base }, { name: "wa-disclaimer", value: "1", url: base },
  ]);
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
    if (req.method() !== "GET") log.mutaties.push(`${req.method()} ${url.pathname}`);
    if (url.pathname.endsWith("/v2/capabilities")) return route.fulfill({ json: { schema_versie: 2, bronnodes_actief: true, samenhang: true } });
    if (url.pathname.endsWith("/v2/samenhang")) { log.samenhang.push(url.searchParams.get("bron_iri")); return route.fulfill({ json: samenhang(url.searchParams.get("bron_iri")) }); }
    if (url.pathname.endsWith("/v2/weergave")) return route.fulfill({ json: weergave(url.searchParams.get("bron_iri")) });
    if (url.pathname === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", user_id: "browser-test", titel: "Samenhang", berichten } });
    if (url.pathname === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Samenhang", aantal_berichten: 2 }] });
    if (url.pathname.includes("/actief")) return route.fulfill({ status: 404, json: {} });
    if (url.pathname.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (url.pathname.includes("/verklaringen")) return route.fulfill({ json: {} });
    return route.fulfill({ status: 200, json: [] });
  });
  return { page, log };
}

const knopInLijst = (page, id) => page.locator(`[data-knoop-id="${id}"]`);
async function openLijst(page) {
  const knop = page.getByRole("button", { name: "Knopenlijst" });
  if ((await knop.getAttribute("aria-expanded")) !== "true") await knop.click();
}

// 1. Breed scherm: chatknop opent het paneel direct op de graaf.
{
  const { page, log } = await nieuwePagina();
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByRole("button", { name: /Bekijk samenhang in 3D/ }).click();
  const graaf = page.getByTestId("samenhang-graaf");
  await graaf.waitFor();
  // StrictMode draait effecten in dev twee keer; tel daarom unieke aanvragen.
  assert.deepEqual([...new Set(log.samenhang)], [L2], "de graaf vraagt de samenhang van de geciteerde bepaling");
  assert.equal(await page.getByRole("button", { name: "3D-graaf" }).getAttribute("aria-pressed"), "true");
  await page.locator('[data-graaf-status="gereed"]').waitFor({ timeout: 20000 });
  await page.screenshot({ path: `${shots}/1-graaf.png` });
  // Namen staan als tooltip op de knopen (alleen selectie en buren hebben een vast label).
  const doek = await page.locator('[data-testid="graaf-canvas"] canvas').boundingBox();
  let tooltip = "";
  for (let i = 0; i < 40 && !tooltip; i++) {
    await page.mouse.move(doek.x + doek.width * (0.2 + (i % 8) * 0.08), doek.y + doek.height * (0.25 + Math.floor(i / 8) * 0.12));
    await page.waitForTimeout(60);
    // Niet wachten: zonder tooltip op deze plek meteen door naar de volgende.
    const tips = page.locator(".samenhang-tip");
    tooltip = (await tips.count()) ? (await tips.first().textContent()) || "" : "";
  }
  assert.ok(tooltip.length > 0, "een knoop of verbinding toont een tooltip bij hover");

  // 2. Knoop kiezen via de lijst; het lid toont zijn verwijzingen en uitklappen toont de randknoop.
  await openLijst(page);
  await knopInLijst(page, L2).click();
  assert.match(await page.getByTestId("graaf-detail").innerText(), /verwijst naar/);
  await knopInLijst(page, A10).click();
  await page.getByRole("button", { name: "Artikel bijladen" }).click();
  await knopInLijst(page, A10L1).waitFor();
  assert.deepEqual([...new Set(log.samenhang)], [L2, A10], "uitklappen laadt het doelartikel");
  assert.equal(log.samenhang.filter((i) => i === A10).length, 1, "één keer bijladen per klik");
  assert.equal(await knopInLijst(page, STUB).count(), 0, "een niet-uitgeklapt lid toont zijn externe verwijzing nog niet");
  await knopInLijst(page, L1).click();
  await page.getByRole("button", { name: /Toon verbindingen/ }).click();
  await knopInLijst(page, STUB).click();
  assert.match(await page.getByTestId("graaf-detail").innerText(), /niet in de kennisgraaf/);
  assert.equal(await page.getByRole("button", { name: "Artikel bijladen" }).count(), 0, "extern is niet uitklapbaar");

  // 3. Markering: de keuze is in tekst en graaf dezelfde.
  await knopInLijst(page, "element:e1").click();
  assert.match(await page.getByTestId("graaf-detail").innerText(), /Rechtssubject/);
  await page.getByRole("button", { name: "Open brontekst" }).click();
  assert.equal(await page.getByRole("button", { name: "Tekst" }).getAttribute("aria-pressed"), "true");
  await page.locator("[data-artefact]").waitFor();
  await page.getByRole("button", { name: "3D-graaf" }).click();
  assert.equal(await knopInLijst(page, "element:e1").getAttribute("aria-pressed"), "true", "selectie blijft na terugkeren");

  // 4. Vergroten en met Escape terug; de camera en selectie blijven.
  await page.getByRole("button", { name: "Vergroten" }).click();
  assert.equal(await page.getByTestId("samenhang-graaf").getAttribute("data-vergroot"), "true");
  await page.screenshot({ path: `${shots}/2-vergroot.png` });
  await page.keyboard.press("Escape");
  assert.equal(await page.getByTestId("samenhang-graaf").getAttribute("data-vergroot"), "false");

  // 5. Vraag Lex over een bron zet de vraag klaar, zonder iets te versturen.
  await knopInLijst(page, A10L1).click();
  await page.getByRole("button", { name: "Vraag Lex hierover" }).click();
  assert.match(await page.locator("textarea").inputValue(), /Hoe hangt .*BWBR0004770, artikel 10, lid 1/);
  assert.deepEqual(log.mutaties, [], "de graaf muteert niets");
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 6. Mobiel: het paneel ligt over de chat; de lijst werkt met het toetsenbord.
{
  const { page, log } = await nieuwePagina({ width: 390, height: 844 });
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByRole("button", { name: /Bekijk samenhang in 3D/ }).click();
  await page.getByTestId("samenhang-graaf").waitFor();
  await openLijst(page);
  await knopInLijst(page, L1).focus();
  await page.keyboard.press("Enter");
  assert.equal(await knopInLijst(page, L1).getAttribute("aria-pressed"), "true");
  await page.screenshot({ path: `${shots}/3-mobiel.png` });
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 7. Zonder WebGL blijven lijst, detail en brontekst bruikbaar.
{
  const { page, log } = await nieuwePagina({ webgl: false });
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByRole("button", { name: /Bekijk samenhang in 3D/ }).click();
  await page.getByText("Deze browser kan de 3D-weergave niet openen.").waitFor();
  await openLijst(page);
  await knopInLijst(page, "element:e1").waitFor({ state: "detached" }).catch(() => {});
  await knopInLijst(page, L1).click();
  assert.match(await page.getByTestId("graaf-detail").innerText(), /Artikel 9 · lid 1/);
  await page.screenshot({ path: `${shots}/4-zonder-webgl.png` });
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

await browser.close();
console.log(`samenhang: alle controles geslaagd; screenshots in ${shots}`);
