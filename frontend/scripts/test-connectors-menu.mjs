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
 *    ongewijzigd mee met de beurt, en komt de schakelaar terug zodra de stand bij het openen weer bekend is;
 *  - het menu verdwijnt nooit stil: faalt `/api/connectors`, dan staat het er met een melding en *Opnieuw proberen*;
 *    een wissel van gesprek of *Nieuw gesprek* (een remount) toont meteen de laatst bekende stand, ook als het
 *    ophalen traag is; een bron die de omgeving niet aanbiedt staat er als "niet beschikbaar", zonder schakelaar en
 *    zonder `bronnen`; en het `bronstand`-event van een beurt werkt de beschikbaarheid bij;
 *  - laden is geen oordeel: een `onbekend` (koude graph-qa) staat eerst als "wordt gecontroleerd" en herstelt vanzelf
 *    met een korte reeks herpogingen; pas daarna "onbekend" met de melding. Terugkomen in het venster en een beurt
 *    proberen het opnieuw. De herpogingen zijn hier kort (`window.__connectorHerpogingen`);
 *  - past de regel niet (een telefoon), dan staat er "Bronnen: alle 4 aan" binnen beeld, met een geel label als een bron
 *    niet beschikbaar is; een klik opent hetzelfde menu. Op een breed scherm staat de volle regel.
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

// `connectorsAntwoord(n)` (n = het hoeveelste verzoek) kan een fout of vertraging geven: `{ status, vertraging }`.
async function open({ beschikbaar = [KST], gesprekConnectors, wgStandaard = null, url = "/workbench", events = GOED,
  connectorsAntwoord = () => ({}), gesprekken = [], herpogingen = [150, 150], viewport = { width: 1280, height: 900 } } = {}) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const errors = [], runs = [], patches = [], wgPatches = [], connectorVerzoeken = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await context.addCookies(await sessieCookies(base));
  await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  await context.addInitScript((h) => { window.__connectorHerpogingen = h; }, herpogingen);
  const stand = { connectors: gesprekConnectors ?? null, wg: { id: "wg1", naam: "Invordering", status: "in_voorbereiding", revisie: 3,
    peildatum: null, aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, analysevraag: "", afbakening: "", aanleiding: "",
    context: "", doel: "", praktijkvoorbeeld: "", bronnen: [], deelvragen: [], standaard_connectors: wgStandaard } };
  await page.route("**/api/**", async (route) => {
    const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
    if (p.startsWith("/api/auth/")) return route.continue();
    if (p === "/api/connectors") {
      connectorVerzoeken.push(Date.now());
      const { status, vertraging } = connectorsAntwoord(connectorVerzoeken.length);
      if (vertraging) await new Promise((r) => setTimeout(r, vertraging));
      if (status) return route.fulfill({ status, json: { detail: "De lijst met bronnen is nu niet te lezen." } }).catch(() => {});
      const lijst = typeof beschikbaar === "function" ? beschikbaar() : beschikbaar;
      return route.fulfill({ json: { aan: lijst.map((c) => c.naam), connectors: lijst } }).catch(() => {});
    }
    if (p === "/api/annotatie/run") {
      if (m === "GET") return route.fulfill({ json: null });
      runs.push(req.postDataJSON());
      return route.fulfill({ json: { run_id: "live", conversation_id: req.postDataJSON().conversation_id, status: "loopt" } });
    }
    if (p === "/api/annotatie/run/live/events")
      return route.fulfill({ contentType: "text/event-stream", body: sse(typeof events === "function" ? events() : events) });
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
    if (p === "/api/gesprekken/g2") return route.fulfill({ json: { id: "g2", titel: "Tweede", connectors: null, berichten: [] } });
    if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g1", titel: "", berichten: [] } });
    if (p === "/api/gesprekken") return route.fulfill({ json: gesprekken });
    if (p.endsWith("/berichten") && m === "POST") return route.fulfill({ json: { id: 1 } });
    if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
    return route.fulfill({ json: [] });
  });
  await page.goto(`${base}${url}`);
  await page.getByRole("textbox").last().waitFor();
  return { page, context, errors, runs, patches, wgPatches, stand, connectorVerzoeken };
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
  await page.getByText("Wetgeving staat altijd aan. Andere bronnen zijn geen wettekst.", { exact: false }).waitFor();
  await page.getByText("Standaard: alle beschikbare bronnen staan aan.").waitFor();
  await page.getByRole("menuitemradio", { name: "Kamerstukken" }).click();
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label")?.includes("Kamerstukken uit"));
  await page.getByText("Je koos dit voor dit gesprek.").waitFor();
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
  await page.getByText("Zoals ingesteld voor dit werkgebied.").waitFor();
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


// 7. `/api/connectors` faalt: het menu staat er met de melding, en *Opnieuw proberen* haalt de stand terug.
{
  let stuk = true;
  const { page, context, errors, connectorVerzoeken } = await open({ connectorsAntwoord: () => (stuk ? { status: 503 } : {}) });
  await menu(page).waitFor();
  assert.equal(await menu(page).getAttribute("data-laden"), "mislukt");
  assert.equal(await menu(page).getAttribute("aria-label"), "Bronnen: Wetgeving aan (nu niet te controleren)");
  await menu(page).click();
  await page.locator("[data-connectors-melding]").getByText("Lex kan de bronnen nu niet controleren.").waitFor();
  stuk = false;
  const voor = connectorVerzoeken.length;
  await page.getByRole("menuitem", { name: "Opnieuw proberen" }).click();
  await page.getByRole("menuitemradio", { name: "Kamerstukken" }).waitFor();
  assert.ok(connectorVerzoeken.length > voor);
  assert.equal(await page.locator("[data-connectors-melding]").count(), 0, "de melding is weg zodra de stand bekend is");
  assert.equal(await menu(page).getAttribute("data-laden"), null);
  // Een 503 telt in de console als netwerkfout, niet als paginafout.
  assert.deepEqual(errors, []);
  await context.close();
}

// 8. Traag laden: na een wissel van gesprek (remount) staat het menu er meteen, met de laatst bekende stand.
// 9. *Nieuw gesprek* (ook een remount): het menu blijft staan. Faalt het verversen daarna, dan blijft de lijst staan.
{
  const gesprekken = [
    { id: "g1", titel: "Test", aantal_berichten: 0, updated: nu },
    { id: "g2", titel: "Tweede", aantal_berichten: 0, updated: nu },
  ];
  let traag = false, stuk = false;
  const { page, context, errors } = await open({ gesprekken, url: "/workbench?gesprek=g1",
    connectorsAntwoord: () => (stuk ? { status: 504 } : traag ? { vertraging: 4000 } : {}) });
  await menu(page).waitFor();
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label") === "Bronnen: Wetgeving aan, Kamerstukken aan");
  traag = true;
  await page.locator("aside[data-tour=sidebar] [data-gesprek-rij=g2]").getByRole("button", { name: /^Tweede/ }).click();
  await page.waitForFunction(() => new URL(location.href).searchParams.get("gesprek") === "g2");
  // Binnen de vertraging van 4 s: het menu moet er al staan.
  await page.waitForTimeout(300);
  assert.equal(await menu(page).count(), 1, "het menu staat er direct na de wissel");
  assert.equal(await menu(page).getAttribute("aria-label"), "Bronnen: Wetgeving aan, Kamerstukken aan");

  // Het trage verzoek loopt nog; een nieuwe mount sluit daarop aan (één verzoek tegelijk). Wacht het af.
  traag = false;
  await page.waitForTimeout(4200);
  stuk = true;
  await page.getByRole("button", { name: "Nieuw gesprek" }).first().click();
  await page.waitForTimeout(300);
  assert.equal(await menu(page).count(), 1, "het menu staat er direct na Nieuw gesprek");
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("data-laden") === "mislukt");
  assert.equal(await menu(page).getAttribute("aria-label"), "Bronnen: Wetgeving aan, Kamerstukken aan (nu niet te controleren)");
  await menu(page).click();
  await page.getByText("Je ziet de laatst bekende stand.").waitFor();
  assert.deepEqual(errors, []);
  await context.close();
}

// 10. De omgeving biedt een aangezette bron niet aan: hij staat er als niet beschikbaar, zonder schakelaar en zonder `bronnen`.
{
  const ECLI = { naam: "rechtspraak", label: "Rechtspraak", brontype: "uitspraak", beschikbaarheid: "aan" };
  const { page, context, errors, runs } = await open({ beschikbaar: [{ ...KST, beschikbaarheid: "niet_aangeboden" }, ECLI] });
  await menu(page).waitFor();
  assert.equal(await menu(page).getAttribute("aria-label"), "Bronnen: Wetgeving aan, Kamerstukken niet beschikbaar, Rechtspraak aan");
  assert.equal(await page.locator("[data-bron=Kamerstukken]").getAttribute("data-stand"), "niet_aangeboden");
  await menu(page).click();
  await page.locator("[data-connector-niet-aangeboden=kamerstukken]").waitFor();
  await page.getByText("Kamerstukken staat aan, maar is hier niet beschikbaar. Lex gebruikt deze bron dan niet.").waitFor();
  assert.equal(await page.getByRole("menuitemradio", { name: "Kamerstukken" }).count(), 0, "geen schakelaar");
  await page.keyboard.press("Escape");
  await vraag(page, "Een vraag");
  await wachtOp(page, runs, 1);
  assert.deepEqual(runs[0].bronnen, ["rechtspraak"]);
  assert.deepEqual(errors, []);
  await context.close();
}

// 11. De bronstand van een beurt: de straat biedt hem niet (meer) aan → niet beschikbaar; de volgende beurt zegt aan →
// hersteld. (Bij `register_onleesbaar` haalt de werkplek na de beurt meteen de stand opnieuw op, en die wint.)
{
  let reden = "straat";
  const events = () => [{ type: "bronstand", bronnen: [{ naam: "kamerstukken", label: "Kamerstukken", aan: reden === "aan", reden }] },
    ...GOED];
  const { page, context, errors, runs } = await open({ events });
  await menu(page).waitFor();
  await vraag(page, "Eerste vraag");
  await wachtOp(page, runs, 1);
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label")?.includes("Kamerstukken niet beschikbaar"));
  reden = "aan";
  await vraag(page, "Tweede vraag");
  await wachtOp(page, runs, 2);
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label") === "Bronnen: Wetgeving aan, Kamerstukken aan");
  assert.deepEqual(errors, []);
  await context.close();
}

// 12. Een koude graph-qa: de eerste twee antwoorden zijn onbekend, het derde aan. Er staat nooit "onbekend" op de knop:
// eerst "wordt gecontroleerd", daarna het vinkje, zonder klik.
{
  const KOUD = [KST, { ...KST, naam: "rechtspraak", label: "Rechtspraak", brontype: "uitspraak" }];
  let n = 0;
  const beschikbaar = () => KOUD.map((c) => ({ ...c, beschikbaarheid: n > 2 ? "aan" : "onbekend" }));
  const { page, context, errors } = await open({ beschikbaar, herpogingen: [400, 400],
    connectorsAntwoord: () => { n++; return {}; } });
  // Leg elke naam van de knop vast, ook de kortstondige.
  await page.evaluate(() => {
    window.__namen = [];
    const kijk = () => { const n = document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label"); if (n) window.__namen.push(n); };
    new MutationObserver(kijk).observe(document.body, { subtree: true, childList: true, attributes: true });
    kijk();
  });
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label") ===
    "Bronnen: Wetgeving aan, Kamerstukken aan, Rechtspraak aan");
  const namen = await page.evaluate(() => window.__namen);
  assert.ok(namen.some((x) => x.includes("Kamerstukken wordt gecontroleerd")), "eerst wordt gecontroleerd");
  assert.ok(!namen.some((x) => x.includes("onbekend")), `nooit onbekend: ${namen.join(" | ")}`);
  assert.equal(await page.locator("[data-connectors-menu] [data-stand=laden]").count(), 0);
  assert.deepEqual(errors, []);
  await context.close();
}

// 13. Blijft het onbekend, dan pas na de reeks "onbekend" met de melding; terugkomen in het venster probeert opnieuw.
{
  let bekend = false;
  const beschikbaar = () => [{ ...KST, beschikbaarheid: bekend ? "aan" : "onbekend" }];
  const { page, context, errors, connectorVerzoeken } = await open({ beschikbaar });
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label") ===
    "Bronnen: Wetgeving aan, Kamerstukken onbekend");
  const na = connectorVerzoeken.length;
  assert.ok(na >= 3, "één verzoek en twee herpogingen");
  // Geen timer meer: zonder handeling komt er geen verzoek bij.
  await page.waitForTimeout(800);
  assert.equal(connectorVerzoeken.length, na, "geen polling na de reeks");
  // Het menu openen probeert het opnieuw (een nieuwe reeks); daarna staat de melding er.
  await menu(page).click();
  await page.getByText("Lex kan nu niet nagaan of Kamerstukken bereikbaar is.").waitFor();
  assert.ok(connectorVerzoeken.length > na, "openen van het menu probeert opnieuw");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(800);
  bekend = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label") ===
    "Bronnen: Wetgeving aan, Kamerstukken aan");
  assert.deepEqual(errors, []);
  await context.close();
}

// 14. Vóór een beurt: was de stand niet vast te stellen, dan gaat er een verversverzoek uit, en de beurt wacht er niet op.
{
  const { page, context, errors, runs, connectorVerzoeken } = await open({
    beschikbaar: () => [{ ...KST, beschikbaarheid: "onbekend" }] });
  await page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.getAttribute("aria-label")?.includes("Kamerstukken onbekend"));
  const voor = connectorVerzoeken.length;
  await vraag(page, "Een vraag");
  await wachtOp(page, runs, 1);
  assert.ok(connectorVerzoeken.length > voor, "verversen vóór de beurt");
  assert.deepEqual(runs[0].bronnen, ["kamerstukken"], "de beurt houdt de opgeslagen keuze");
  assert.deepEqual(errors, []);
  await context.close();
}

console.log("ok - Bronnen en tools");
// Smal scherm: de korte vorm, binnen beeld, en hetzelfde menu.
{
  const VIER = [KST, { naam: "bekendmakingen", label: "Staatsblad en Staatscourant", brontype: "bekendmaking" },
    { naam: "rechtspraak", label: "Rechtspraak", brontype: "uitspraak" }];
  const smal = await open({ beschikbaar: VIER, viewport: { width: 375, height: 812 } });
  await menu(smal.page).waitFor();
  await smal.page.waitForFunction(() => document.querySelector("[data-connectors-menu]")?.hasAttribute("data-kort"));
  assert.equal((await smal.page.locator("[data-connectors-kort]").innerText()).trim(), "Bronnen: alle 4 aan");
  const vak = await menu(smal.page).boundingBox();
  assert.ok(vak && vak.x >= 0 && vak.x + vak.width <= 375, `de knop past op 375 px (${JSON.stringify(vak)})`);
  assert.equal(await smal.page.evaluate(() => document.documentElement.scrollWidth <= 375), true, "geen horizontale scroll");
  assert.equal(await menu(smal.page).getAttribute("aria-label"),
    "Bronnen: Wetgeving aan, Kamerstukken aan, Staatsblad en Staatscourant aan, Rechtspraak aan");
  await menu(smal.page).click();
  await smal.page.getByRole("menuitemradio", { name: /Staatsblad en Staatscourant/ }).waitFor();
  assert.deepEqual(smal.errors, []);
  await smal.context.close();

  const zorg = await open({ beschikbaar: [KST, { ...VIER[1], beschikbaarheid: "niet_aangeboden" }, VIER[2]],
    viewport: { width: 375, height: 812 } });
  await zorg.page.waitForFunction(() => document.querySelector("[data-connectors-kort]"));
  assert.match(await zorg.page.locator("[data-connectors-kort]").innerText(), /niet beschikbaar/);
  await zorg.context.close();

  const breed = await open({ beschikbaar: VIER });
  await menu(breed.page).waitFor();
  await breed.page.waitForTimeout(300);
  assert.equal(await menu(breed.page).getAttribute("data-kort"), null, "op 1280 px de volle regel");
  assert.equal(await breed.page.locator("[data-connectors-kort]").count(), 0);
  await breed.context.close();
}

await browser.close();
