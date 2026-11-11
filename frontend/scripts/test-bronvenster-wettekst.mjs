/** Browserregressie voor een wettekst buiten de kennisgraaf in het antwoord en het bronvenster (ADR-013, de connector
 * Wetgeving buiten de kennisgraaf). Op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-bronvenster-wettekst.mjs`.
 *
 * Dezelfde componenten als een Kamerstuk of een bekendmaking; deze test bewaakt wat bij deze bron anders moet:
 *  - het blok in het antwoord zegt "Wettekst van overheid.nl … niet uit de kennisgraaf", nooit "geen wettekst";
 *  - een eerdere tekst heet zo, met de periode, en de melding dat de tekst niet in de kennisgraaf staat (dus geen
 *    annotatie of werkgebied zonder import);
 *  - het venster opent het artikel op het brontype `wettekst_live`, met de leden en hun koppen en de citaten van Lex
 *    gemarkeerd, en zonder knop om op te nemen;
 *  - geen horizontale scroll op 375 en 1280 px.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";
import { readFileSync } from "node:fs";

// De vragenset van de connector (ook de adaptertoets en de meting): het id komt eruit, zodat de drie plekken hetzelfde
// artikel toetsen.
const SET = JSON.parse(readFileSync(new URL("../../tools/graph-qa/tests/data/wetgeving_live_vragenset.json", import.meta.url))).vragen;
const vraag = (id) => SET.find((v) => v.id === id) ?? assert.fail(`vraag ${id} ontbreekt in de vragenset`);
const ID = vraag("W01").verwacht.stuk.id;
assert.match(ID, /^bwbt:BWBR0015703:2026-07-01_0:artikel:31$/, "het artikel van dit scenario staat in de set");

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const LINK = "https://wetten.overheid.nl/jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.4&artikel=31&z=2026-07-01&g=2026-07-01";
const KOP = "Hoofdstuk 3 – Algemene bijstand › § 3.4 – Middelen › Artikel 31 – Middelen";
const PASSAGES = [
  { nr: 1, soort: "alinea", kop: `${KOP} › lid 1`, tekst: "Tot de middelen worden alle vermogens- en inkomensbestanddelen gerekend." },
  { nr: 2, soort: "alinea", kop: `${KOP} › lid 2`, tekst: "Tot de middelen worden niet gerekend:" },
];
const antwoord = { sjabloon: "extern", versie: 1, doelen: [], blokken: [
  { soort: "toelichting", door: "lex", kop: "Toelichting van Lex", tekst: "Artikel 31 regelt wat tot de middelen behoort." },
  { soort: "extern", door: "bron", brontype: "wettekst_live", id: ID, label: "Participatiewet, Artikel 31 (tekst geldig vanaf 2026-07-01)",
    link: LINK, kop: "Wettekst van overheid.nl (niet in de kennisgraaf)", bron_hash: "h", passages: PASSAGES,
    datum: "2026-07-01", soort_stuk: "wet", tekst_vanaf: "2015-01-01", tekst_tot: "2015-06-30", tekststand: "eerdere tekst" },
] };
const bewaard = [{ id: 1, rol: "user", tekst: "Wat staat er in artikel 31 van de Participatiewet?" },
  { id: 2, rol: "assistant", tekst: "Artikel 31 regelt wat tot de middelen behoort.", run_id: "r2", antwoord,
    grounding: { grounded: true, cited: 0, unsupported: [], niet_letterlijk: [], niveau: "gegrond" } }];

const BESCHRIJVING = { naam: "wetgeving_live", label: "Wetgeving buiten de kennisgraaf", groep: "Wetgeving buiten de kennisgraaf",
  brontype: "wettekst_live", id_prefixen: ["bwbt:"],
  metadata: [{ sleutel: "datum", label: "geldig vanaf" }, { sleutel: "soort", label: "soort" },
    { sleutel: "tekststand", label: "tekststand" }, { sleutel: "nummer", label: "BWB-id" }] };
const STUK = { id: ID, label: "Participatiewet, Artikel 31 (tekst geldig vanaf 2026-07-01)", titel: "Participatiewet",
  link: LINK, soort: "wet", datum: "2026-07-01", tekst_vanaf: "2026-07-01", tekststand: "huidige tekst", nummer: "BWBR0015703",
  bron_hash: "h", in_graaf: false, leesbaar: true };
const verzoeken = [];

await context.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname;
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Middelen", aantal_berichten: 2 }] });
  if (p === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", titel: "Middelen", berichten: bewaard } });
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  if (p.startsWith("/api/bronnen/")) {
    verzoeken.push(decodeURIComponent(p));
    return route.fulfill({ json: { connector: BESCHRIJVING, resultaat: { status: "ok", volledig: true, stuk: STUK,
      resultaten: [...PASSAGES, { nr: 3, soort: "alinea", kop: `${KOP} › lid 3`, tekst: "Lid 3 van artikel 31." }] } } });
  }
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: [] });
});

const geenScroll = async (w) => assert.ok(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), `op ${w}px geen horizontale scroll`);

try {
  await page.goto(`${base}/workbench?gesprek=g1`);
  const blok = page.locator(`[data-extern='${ID}']`);
  await blok.waitFor();
  const sectie = page.locator("section", { has: blok });
  const tekst = await sectie.innerText();
  assert.match(tekst, /Wettekst van overheid\.nl, letterlijk, maar niet uit de kennisgraaf/);
  assert.doesNotMatch(tekst, /geen wettekst/, "een wettekst buiten de graaf is wél wettekst");
  await sectie.locator("[data-stand-melding=eerdere-tekst]").waitFor();
  assert.match(await sectie.locator("[data-stand-melding=eerdere-tekst]").innerText(),
    /Dit is de tekst van 1 januari 2015 tot en met 30 juni 2015: een eerdere tekst/);
  await sectie.locator("[data-stand-melding=buiten-graaf]").waitFor();
  await geenScroll(1280);

  // Het venster: op het brontype, met de leden en hun koppen, de citaten gemarkeerd en zonder opnemen.
  await page.locator(`[data-stuk-link='${ID}']`).first().click();
  const venster = page.locator(`[data-stukvenster='${ID}']`);
  await venster.waitFor();
  await venster.getByText("Lid 3 van artikel 31.").waitFor();
  assert.equal(await venster.locator("[data-geciteerd]").count(), 2, "de twee leden die Lex citeerde");
  assert.equal(await venster.getByRole("button", { name: /opnemen/i }).count(), 0, "geen opnemen bij een wettekst buiten de graaf");
  await venster.locator("[data-stand-melding=buiten-graaf]").waitFor();
  assert.ok(verzoeken.length && verzoeken.every((v) => v.startsWith("/api/bronnen/wettekst_live/bwbt:")), verzoeken.join(", "));

  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.locator(`[data-stuk-link='${ID}']`).first().click();
  await page.locator(`[data-stukvenster='${ID}']`).waitFor();
  await geenScroll(375);

  assert.deepEqual(errors, []);
  console.log("Browser OK: een wettekst buiten de kennisgraaf in het antwoord (wél wettekst, eerdere tekst, niet in de graaf) en als tab (leden, citaten, geen opnemen), op 375/1280 px.");
} finally {
  await browser.close();
}
