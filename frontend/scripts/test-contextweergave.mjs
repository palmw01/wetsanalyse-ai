/** Browserregressie voor de contextweergave (plan contextweergave, stap 4 en 5): de contextmeter bij het invoerveld en
 * het paneel *Context van deze beurt* (`/context`). Op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-contextweergave.mjs`. Met `CONTEXT_SCREENSHOT=<map>` bewaart hij een beeld van het paneel
 * (breed en op een telefoon), voor een controle op het oog.
 *
 * Bewaakt:
 *  - de meter toont de omvang van het laatste verzoek en het deel van het venster, met een signaal bij een koud begin;
 *  - een klik opent het paneel naast het gesprek: de regel, het raster (100 vakjes = het verzoek), de legenda met ≈, hoe
 *    de beurt begon, en het verbruik van de hele beurt als een ander getal dan de context;
 *  - de boom: een gemeten deelgesprek met zijn profiel (ADR-016), context en verbruik (een klik opent dezelfde kaart), een deelgesprek
 *    zonder meting, en een totaal dat zegt dat het onvolledig is;
 *  - de beurtkiezer toont een eerdere beurt (warm), het verloop staat er bij meer dan één beurt, de details klappen uit;
 *  - `/context` opent hetzelfde paneel zonder beurt; meter en commando delen één tab;
 *  - een lopende beurt werkt de meter bij uit het `meting`-event, zonder herladen;
 *  - een gesprek zonder meting zegt "nog niet gemeten";
 *  - een regiegesprek heeft zelf geen meting (geen model), maar toont zijn deelgesprek met alle beurten;
 *  - er staat geen knop die Lex start, en op een telefoon (375 px) past alles zonder horizontale scroll.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addCookies(await sessieCookies(base));
const errors = [], runs = [], boomVerzoeken = [];
const schermafdruk = process.env.CONTEXT_SCREENSHOT;

/** Eén contextopbouw zoals graph-qa haar levert (`agent/contextopbouw.py`). */
function opbouw(run, { ouder = "", koud = true, totaal = 30890, tools = "758623c1266b", profiel = "" } = {}) {
  const begin = koud ? { lees: 0, schrijf: 27864, nieuw: 3 } : { lees: 27000, schrijf: 864, nieuw: 3 };
  const schaal = totaal / 30890;
  const delen = [["systeem", 3300], ["methode", 1081], ["graaftools", 8284], ["connectortools", 9363], ["sjablonen", 2981],
    ["beurtcontext", 2830], ["beurt", 200], ["toolresultaten", 2851]].map(([categorie, n]) => ({ categorie, omvang: Math.round(n * schaal) }));
  delen[7].omvang += totaal - delen.reduce((a, d) => a + d.omvang, 0);
  return {
    versie: 1, run_id: run, ouder_run_id: ouder, profiel_id: "", profiel_versie: "",
    agenten: [{
      rol: "antwoord", model: "claude-sonnet-4-6", venster: 1_000_000, historiegrens: 13806,
      profiel_id: profiel, profiel_versie: profiel ? "3" : "",
      venster_beurten: { in_venster: 1, gekrompen: 0, weggevallen: 0 },
      begin: { totaal: 27867, cache: begin, tools_hash: tools, system_hash: "5cc1b4215950" },
      laatste: { delen, totaal, voorvoegsel: { omvang: Math.round(25009 * schaal), exact: true }, cache: { lees: totaal - 742, schrijf: 741, nieuw: 1 } },
    }],
    verbruik: [
      { rol: "supervisor", model: "claude-sonnet-4-6", aanroepen: 1, invoer: 34, cache_lees: 2189, cache_schrijf: 0, uitvoer: 68, duur: 2747 },
      { rol: "antwoord", model: "claude-sonnet-4-6", aanroepen: 3, invoer: 5, cache_lees: 58012, cache_schrijf: 30889, uitvoer: 1815, duur: 33908 },
    ],
    som: { invoer: 39, cache_lees: 60201, cache_schrijf: 30889, uitvoer: 1883 },
    aanroepen: [
      { rol: "supervisor", totaal: 2223, cache_lees: 2189, cache_schrijf: 0, invoer: 34, uitvoer: 68, ms: 2747, tools_hash: "", system_hash: "a22ec1857baa" },
      { rol: "antwoord", totaal: 27867, cache_lees: 0, cache_schrijf: 27864, invoer: 3, uitvoer: 82, ms: 3826, tools_hash: tools, system_hash: "5cc1b4215950" },
      { rol: "antwoord", totaal, cache_lees: totaal - 742, cache_schrijf: 741, invoer: 1, uitvoer: 1635, ms: 28054, tools_hash: tools, system_hash: "5cc1b4215950" },
    ],
  };
}

const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const gesprekken = {
  // Twee gemeten beurten: de eerste warm, de laatste koud (het signaal).
  g1: [
    { rol: "user", tekst: "Wat regelt artikel 9?", ...leeg },
    { rol: "assistant", tekst: "Artikel 9 regelt de betalingstermijn.", ...leeg, run_id: "r1", contextopbouw: opbouw("r1", { koud: false, totaal: 24000 }) },
    { rol: "user", tekst: "En lid 2?", ...leeg },
    { rol: "assistant", tekst: "Lid 2 gaat over navorderingsaanslagen.", ...leeg, run_id: "r2", contextopbouw: opbouw("r2") },
  ],
  // Een gesprek van vóór de meting.
  g3: [
    { rol: "user", tekst: "Een oude vraag", ...leeg },
    { rol: "assistant", tekst: "Een oud antwoord.", ...leeg, run_id: "oud" },
  ],
};
const boom = { gesprek_id: "g1", kinderen: [
  { gesprek_id: "k1", titel: "Deelvraag 1: de termijn", updated: null,
    berichten: [{ bericht_id: 9, run_id: "k1r", created: null, contextopbouw: opbouw("k1r", { ouder: "r2", koud: false, totaal: 18000, profiel: "bronnenzoeker" }) }] },
  { gesprek_id: "k2", titel: "Deelvraag 2: loopt nog", updated: null, berichten: [] },
] };
/** Een regie (ADR-012): het gesprek zelf gebruikt geen model, het deelgesprek is een reeks van drie beurten zonder
 *  toollus en zonder ouder op de beurt – zoals op acceptatie gemeten. */
const zonderLus = (run) => ({ ...opbouw(run), agenten: [], som: { invoer: 6334, cache_lees: 0, cache_schrijf: 0, uitvoer: 1213 },
  verbruik: [{ rol: "jas_classifier", model: "claude-sonnet-4-6", aanroepen: 4, invoer: 6334, cache_lees: 0, cache_schrijf: 0, uitvoer: 1213, duur: 36646 }] });
gesprekken.g4 = [
  { rol: "user", tekst: "Start de regie", ...leeg },
  { rol: "assistant", tekst: "Opgeleverd: annoteren.", ...leeg, run_id: "regie" },
];
const regieBoom = { gesprek_id: "g4", kinderen: [{ gesprek_id: "k9", titel: "Annoteren · analysevraag (3 bepalingen)", updated: null,
  berichten: ["c.1", "c.2", "c.3"].map((run, i) => ({ bericht_id: 20 + i, run_id: run, created: null, contextopbouw: zonderLus(run) })) }] };
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");

async function opzet(page) {
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  await page.route("**/api/**", async (route) => {
    const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
    if (p.startsWith("/api/auth/")) return route.continue();
    if (p === "/api/annotatie/run") {
      if (m === "GET") return route.fulfill({ json: null });
      runs.push(req.postDataJSON());
      return route.fulfill({ json: { run_id: "live", conversation_id: req.postDataJSON().conversation_id, status: "loopt" } });
    }
    if (p === "/api/annotatie/run/live/events")
      return route.fulfill({ contentType: "text/event-stream", body: sse([
        { type: "token", content: "Lid 3 gaat over boetes." },
        { type: "meting", route: "duiding", contextopbouw: opbouw("live", { koud: false, totaal: 45200 }) },
        { type: "done" }]) });
    const boomPad = p.match(/^\/api\/gesprekken\/(\w+)\/contextopbouw$/);
    if (boomPad) {
      boomVerzoeken.push(boomPad[1]);
      return route.fulfill({ json: boomPad[1] === "g1" ? boom : boomPad[1] === "g4" ? regieBoom : { gesprek_id: boomPad[1], kinderen: [] } });
    }
    const gesprek = p.match(/^\/api\/gesprekken\/(g\d)$/);
    if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: "Test", werkgebied_id: "", berichten: gesprekken[gesprek[1]] ?? [] } });
    if (p === "/api/gesprekken") return route.fulfill({ json: [] });
    if (p.endsWith("/berichten") && m === "POST") return route.fulfill({ json: { id: 1 } });
    if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
    return route.fulfill({ json: [] });
  });
}

try {
  const page = await context.newPage();
  await opzet(page);
  const veld = page.locator('[data-tour="invoer"] textarea');
  const meter = page.locator("[data-contextmeter]");
  const paneel = page.locator('[data-context-paneel="contextopbouw"]');

  // --- De meter: omvang en deel van het venster, met het signaal van een koud begin ---
  await page.goto(`${base}/workbench?gesprek=g1`);
  await meter.waitFor();
  assert.match(await meter.innerText(), /31k · 3,1%/);
  assert.equal(await meter.getAttribute("data-signaal"), "koud_pauze");
  assert.equal(await meter.locator("[data-contextsignaal]").count(), 1, "een stip bij het signaal");
  const tooltip = await meter.getAttribute("title");
  assert.match(tooltip, /Grootste delen: Bronnen naast de wet 9,4k · Wettools 8,3k · Vaste instructies 3,3k\./);
  assert.match(tooltip, /Verbruik van deze beurt: 93k\./);
  assert.match(await meter.getAttribute("aria-label"), /opnieuw geschreven/, "het signaal staat ook in de naam voor een schermlezer");
  assert.equal(await meter.getByRole("progressbar").getAttribute("aria-valuenow"), "3");

  // --- Een klik opent het paneel: context en verbruik zijn twee getallen ---
  await meter.click();
  await paneel.waitFor();
  assert.match(await page.getByRole("heading", { name: "Context van deze beurt" }).first().innerText(), /Context van deze beurt/);
  assert.match(await paneel.locator("[data-context-regel]").innerText(), /31k · 3,1% van het venster \(1M\)/);
  assert.equal(await paneel.locator("[data-context-raster] [data-vakje]").count(), 100, "het raster is 100% van het verzoek");
  assert.equal(await paneel.locator('[data-context-raster] [data-vakje="connectortools"]').count(), 30);
  assert.match(await paneel.locator("[data-context-raster]").getAttribute("aria-label"), /Bronnen naast de wet 30%/);
  const legenda = paneel.locator("[data-context-legenda]").first();
  assert.deepEqual(await legenda.locator("[data-categorie]").evaluateAll((r) => r.map((x) => x.dataset.categorie)),
    ["systeem", "methode", "graaftools", "connectortools", "sjablonen", "beurtcontext", "beurt", "toolresultaten"]);
  assert.match(await legenda.locator('[data-categorie="graaftools"]').innerText(), /Wettools\s*≈ 8,3k\s*27%/);
  assert.equal(await paneel.locator("[data-context-begin]").first().getAttribute("data-context-begin"), "koud");
  assert.match(await paneel.innerText(), /het vaste deel \(instructies, methode en tools\) is samen exact 25k/);
  assert.equal(await paneel.locator("[data-verbruik-totaal]").first().innerText(), "93k");
  assert.equal(await paneel.locator("[data-verbruik-rollen] li").count(), 2, "per rol een rij, ook de losse stap");
  assert.deepEqual(await paneel.locator("[data-context-adviezen] [data-advies]").evaluateAll((r) => r.map((x) => x.dataset.advies)),
    ["koud_pauze", "veel_connectortools"]);

  // --- De boom: een gemeten deelgesprek, een zonder meting, en een onvolledig totaal ---
  const kinderen = paneel.locator("[data-context-kind]");
  await kinderen.first().waitFor();
  // In dev draait StrictMode een effect twee keer: het gaat om welk gesprek, niet om hoe vaak.
  assert.deepEqual([...new Set(boomVerzoeken)], ["g1"], "de boom komt van de leesroute van dit gesprek");
  assert.equal(await kinderen.count(), 2);
  assert.match(await kinderen.nth(0).innerText(), /Deelvraag 1: de termijn\s*bronnenzoeker, versie 3 ·\s*context 18k · 1,8% · verbruik 93k/);
  assert.equal(await paneel.locator("[data-context-profiel]").count(), 0, "de vaste agent heeft geen profiel");
  assert.match(await kinderen.nth(1).innerText(), /loopt nog, of niet gemeten/);
  assert.equal(await kinderen.nth(1).getByRole("button").isDisabled(), true);
  assert.match(await paneel.locator("[data-boom-totaal]").innerText(), /minstens 186k.*onvolledig/s);
  await kinderen.nth(0).getByRole("button").click();
  assert.equal(await kinderen.nth(0).locator("[data-context-raster] [data-vakje]").count(), 100, "dezelfde kaart voor het kind");
  assert.equal(await kinderen.nth(0).locator("[data-context-adviezen]").count(), 0, "adviezen horen bij de eigen beurt");
  assert.equal(await kinderen.nth(0).locator("[data-context-profiel]").innerText(), "Profiel: bronnenzoeker, versie 3");
  await kinderen.nth(0).getByRole("button").first().click();

  if (schermafdruk) await page.screenshot({ path: `${schermafdruk}/contextweergave-breed.png` });

  // --- De beurtkiezer, het verloop en de details ---
  await paneel.locator("[data-context-verloop] svg").waitFor();
  assert.match(await paneel.locator("[data-context-verloop] svg").getAttribute("aria-label"), /Verloop over 2 beurten\. Context: van 24k naar 31k/);
  const kiezer = paneel.locator("[data-context-beurtkiezer]");
  await kiezer.selectOption({ index: 0 });
  assert.match(await paneel.locator("[data-context-regel]").innerText(), /24k · 2,4%/);
  assert.equal(await paneel.locator("[data-context-begin]").first().getAttribute("data-context-begin"), "warm");
  assert.equal(await paneel.locator("[data-context-kind]").count(), 0, "de deelgesprekken horen bij de beurt die ze startte");
  await kiezer.selectOption({ index: 1 });
  const details = paneel.locator("[data-context-details]").first();
  await details.locator("summary").click();
  assert.equal(await details.locator("ol > li").count(), 3);
  assert.match(await details.innerText(), /tools 758623c1266b · instructies 5cc1b4215950/);

  // --- Een weergave, geen artefact: geen knop die Lex start, geen besluit ---
  const knoppen = await paneel.getByRole("button").allInnerTexts();
  assert.ok(!knoppen.some((t) => /Vraag Lex|Bespreek|Beoordelen|Akkoord|Opslaan|Start/.test(t)), `geen handeling in het paneel (${knoppen.join(" | ")})`);
  assert.equal(await paneel.locator('a[href*="/werkgebieden"], [data-naar-pagina]').count(), 0, "geen volledige pagina: de weergave bestaat alleen naast het gesprek");

  // --- /context: hetzelfde paneel, dezelfde tab, zonder beurt ---
  await page.getByRole("button", { name: /^Sluit tab/ }).first().click();
  await paneel.waitFor({ state: "detached" });
  await veld.fill("/con");
  await page.locator("[data-commandomenu]").getByRole("option").filter({ hasText: "/context" }).waitFor();
  await veld.press("Enter");
  await paneel.waitFor();
  assert.equal(await veld.inputValue(), "");
  assert.equal(runs.length, 0, "/context is geen beurt");
  await meter.click();
  assert.equal(await page.getByRole("tab", { name: "Context" }).count(), 1, "de meter en het commando delen één tab");

  // --- Een lopende beurt werkt de meter bij uit het meting-event, zonder herladen ---
  await veld.fill("En lid 3?");
  await veld.press("Enter");
  await page.getByText("Lid 3 gaat over boetes.").waitFor();
  await page.waitForFunction(() => /45k · 4,5%/.test(document.querySelector("[data-contextmeter]")?.textContent ?? ""));
  assert.equal(await meter.getAttribute("data-signaal"), null, "een warme beurt zonder bijzonderheden: geen signaal");
  assert.match(await paneel.locator("[data-context-regel]").innerText(), /45k · 4,5%/, "het open paneel volgt de laatste beurt");
  assert.equal(await paneel.locator("[data-context-beurtkiezer] option").count(), 3);
  await page.close();

  // --- Een gesprek van vóór de meting ---
  const oud = await context.newPage();
  await opzet(oud);
  await oud.goto(`${base}/workbench?gesprek=g3`);
  const oudeMeter = oud.locator("[data-contextmeter]");
  await oudeMeter.waitFor();
  assert.match(await oudeMeter.innerText(), /nog niet gemeten/);
  await oudeMeter.click();
  await oud.locator("[data-context-leeg]").waitFor();
  assert.equal(await oud.locator("[data-context-boom]").count(), 0, "zonder deelgesprekken geen boom");

  // --- Een regiegesprek: zelf geen meting, wel het deelgesprek met al zijn beurten ---
  await oud.goto(`${base}/workbench?gesprek=g4`);
  await oud.locator("[data-contextmeter]").click();
  const regieKind = oud.locator('[data-context-paneel="contextopbouw"] [data-context-kind]');
  await regieKind.waitFor();
  assert.match(await regieKind.innerText(), /Annoteren · analysevraag \(3 bepalingen\)\s*3 beurten · verbruik 23k/);
  assert.match(await oud.locator("[data-boom-totaal]").innerText(), /De deelgesprekken samen: 23k\./);
  await regieKind.getByRole("button").click();
  assert.equal(await regieKind.locator("[data-kind-beurt]").count(), 3, "de kaart toont elke beurt van het deelgesprek");
  assert.equal(await regieKind.locator("[data-context-raster]").count(), 0, "losse stappen hebben geen raster, wel verbruik");
  assert.equal(await regieKind.locator("[data-verbruik-totaal]").first().innerText(), "7,5k");
  await oud.close();

  // --- Op een telefoon: de meter past, het paneel is een sheet zonder horizontale scroll ---
  const mobiel = await browser.newContext({ viewport: { width: 375, height: 740 }, isMobile: true, hasTouch: true });
  await mobiel.addCookies(await sessieCookies(base));
  const tel = await mobiel.newPage();
  await opzet(tel);
  await tel.goto(`${base}/workbench?gesprek=g1`);
  const telMeter = tel.locator("[data-contextmeter]");
  await telMeter.waitFor();
  const vak = await telMeter.boundingBox();
  assert.ok(vak && vak.x >= 0 && vak.x + vak.width <= 375, `de meter past op 375 px (${JSON.stringify(vak)})`);
  assert.ok(vak.height >= 44, `de meter is groot genoeg om te tikken (${vak.height})`);
  await telMeter.tap();
  const telPaneel = tel.locator('[data-context-paneel="contextopbouw"]');
  await telPaneel.waitFor();
  await telPaneel.locator("[data-context-kind]").first().waitFor();
  if (schermafdruk) await tel.screenshot({ path: `${schermafdruk}/contextweergave-telefoon.png` });
  const breedte = await tel.evaluate(() => document.documentElement.scrollWidth);
  assert.ok(breedte <= 375, `geen horizontale scroll (${breedte})`);
  const buiten = await telPaneel.evaluate((el) => {
    const rand = el.getBoundingClientRect();
    return [...el.querySelectorAll("*")].filter((x) => {
      const r = x.getBoundingClientRect();
      return r.width > 0 && (r.right > rand.right + 1 || r.left < rand.left - 1);
    }).map((x) => x.tagName + (x.className?.baseVal ?? x.className ?? "").toString().slice(0, 40));
  });
  assert.deepEqual(buiten, [], "niets steekt buiten het paneel");
  const raster = await telPaneel.locator("[data-context-raster]").first().boundingBox();
  assert.ok(raster && raster.width <= 375 && raster.height < 120, `het raster past (${JSON.stringify(raster)})`);
  const rij = await telPaneel.locator("[data-context-kind] button").first().boundingBox();
  assert.ok(rij && rij.height >= 44, `een rij van de boom is groot genoeg om te tikken (${rij?.height})`);
  await mobiel.close();

  assert.deepEqual(errors, []);
  console.log("Browser OK: de contextmeter met signaal, het paneel (regel, raster, legenda, begin, verbruik), de boom met een onvolledig totaal, de beurtkiezer, het verloop, de details, /context zonder beurt, de meter live uit het meting-event, nog niet gemeten, en mobiel (375 px).");
} finally {
  await browser.close();
}
