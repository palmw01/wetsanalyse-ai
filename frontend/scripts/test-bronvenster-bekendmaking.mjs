/** Browserregressie voor een publicatie uit het Staatsblad in het bronvenster (ADR-013, de connector Staatsblad en
 * Staatscourant). Op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-bronvenster-bekendmaking.mjs`.
 *
 * Dezelfde componenten als een Kamerstuk (de werkplek kent geen connector bij naam); deze test bewaakt dat een derde
 * connector er zonder code bij komt:
 *  - het label van de publicatie in het antwoord opent haar als tab, de kop komt uit de beschrijving (de groep
 *    "Staatsblad en Staatscourant", het soort en de datum) met de vindplaats;
 *  - de koppen van de artikelen en wijzigingsonderdelen ("Artikel I – Wijziging › A") staan bij de tekst, de citaten
 *    van Lex zijn gemarkeerd, en de gegevens tonen de velden uit de beschrijving (publicatieblad, ondertekend);
 *  - een publicatie die alleen als PDF bestaat (de Invorderingswet 1990 zelf) geeft de melding;
 *  - geen horizontale scroll op 375 en 1280 px.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const LINK = (id) => `https://zoek.officielebekendmakingen.nl/${id}`;
const KOP = "Artikel I – Wijziging › A";
const PASSAGES = [
  { nr: 5, soort: "alinea", kop: KOP, tekst: "Artikel 36 wordt als volgt gewijzigd:" },
  { nr: 6, soort: "alinea", kop: KOP, tekst: "1. In het eerste lid wordt een zin toegevoegd." },
];
const blok = (id, label, passages) => ({ soort: "extern", door: "bron", brontype: "bekendmaking", id, label, link: LINK(id),
  kop: "Uit de officiële bekendmakingen", bron_hash: "h", passages });
const antwoord = { sjabloon: "extern", versie: 1, doelen: [], blokken: [
  { soort: "toelichting", door: "lex", kop: "Toelichting van Lex", tekst: "Zo is artikel 36 gewijzigd." },
  blok("stb-2009-610", "Stb. 2009, 610", PASSAGES),
  blok("stb-1990-222", "Stb. 1990, 222", []),
] };
const bewaard = [{ id: 1, rol: "user", tekst: "Wat veranderde Stb. 2009, 610 aan artikel 36?" },
  { id: 2, rol: "assistant", tekst: "Zo is artikel 36 gewijzigd.", run_id: "r2", antwoord,
    grounding: { grounded: true, cited: 0, unsupported: [], niet_letterlijk: [], niveau: "gegrond" } }];

const BESCHRIJVING = { naam: "bekendmakingen", label: "Staatsblad en Staatscourant", groep: "Staatsblad en Staatscourant",
  brontype: "bekendmaking", id_prefixen: ["stb-", "stcrt-"],
  metadata: [{ sleutel: "publicatie", label: "publicatieblad" }, { sleutel: "soort", label: "soort" },
    { sleutel: "datum", label: "datum" }, { sleutel: "ondertekend", label: "ondertekend" }, { sleutel: "orgaan", label: "ministerie" }] };
const STUK = { id: "stb-2009-610", label: "Stb. 2009, 610", titel: "Wet van 17 december 2009 tot wijziging van de Invorderingswet 1990",
  link: LINK("stb-2009-610"), publicatie: "Staatsblad", soort: "Wet", datum: "2009-12-30", ondertekend: "2009-12-17",
  orgaan: "Ministerie van Financiën", bron_hash: "h" };
const verzoeken = [];

await context.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname;
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Wijziging", aantal_berichten: 2 }] });
  if (p === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", titel: "Wijziging", berichten: bewaard } });
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  if (p.startsWith("/api/bronnen/")) {
    verzoeken.push(p);
    const [, , , brontype, id] = p.split("/");
    assert.equal(brontype, "bekendmaking", "de werkplek vraagt de publicatie op het brontype");
    if (id === "stb-1990-222")
      return route.fulfill({ json: { connector: BESCHRIJVING, resultaat: { status: "fout", reden: "alleen_pdf", melding: "alleen pdf",
        stuk: { id, label: "Stb. 1990, 222", link: LINK(id), datum: "1990-05-31", soort: "Wet", leesbaar: false } } } });
    return route.fulfill({ json: { connector: BESCHRIJVING, resultaat: { status: "ok", volledig: true, stuk: STUK,
      resultaten: [{ nr: 1, soort: "alinea", tekst: "Wij Beatrix, bij de gratie Gods, Koningin der Nederlanden" },
        { nr: 4, soort: "alinea", kop: "Artikel I – Wijziging", tekst: "De Invorderingswet 1990 wordt als volgt gewijzigd:" },
        ...PASSAGES, { nr: 7, soort: "alinea", kop: "Artikel II", tekst: "Deze wet treedt in werking bij koninklijk besluit." }] } } });
  }
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: [] });
});

const venster = (id) => page.locator(`[data-stukvenster="${id}"]`);
const geenScroll = async (w) => assert.ok(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), `op ${w}px geen horizontale scroll`);

try {
  await page.goto(`${base}/workbench?gesprek=g1`);
  const label = page.locator("[data-stuk-link='stb-2009-610']");
  await label.waitFor();
  assert.equal(await label.getAttribute("href"), LINK("stb-2009-610"), "met Ctrl/⌘ blijft het de bron zelf");
  await label.click();

  const stuk = venster("stb-2009-610");
  await stuk.waitFor();
  await page.getByRole("heading", { name: "Stb. 2009, 610", exact: true }).waitFor();
  assert.equal(await page.locator("[data-paneel-kop] [data-herkomst-link]").innerText(), "zoek.officielebekendmakingen.nl");
  assert.match(await page.locator("[data-paneel-kop]").innerText(), /Staatsblad en Staatscourant · Wet · 30 december 2009/);

  // De tekst met de koppen van artikel en wijzigingsonderdeel, en de twee citaten van Lex gemarkeerd.
  await stuk.getByText(KOP).first().waitFor();
  await stuk.getByText("Deze wet treedt in werking bij koninklijk besluit.").waitFor();
  assert.equal(await stuk.locator("[data-geciteerd]").count(), 2, "de twee passages die Lex citeerde");
  assert.equal(await stuk.locator("[data-passage='7'][data-geciteerd]").count(), 0, "de rest is niet gemarkeerd");
  assert.match(await stuk.locator("[data-blok=gegevens]").innerText(),
    /publicatieblad\s*Staatsblad[\s\S]*ondertekend\s*17 december 2009[\s\S]*ministerie\s*Ministerie van Financiën/);
  await geenScroll(1280);

  // De Invorderingswet 1990 zelf staat bij KOOP alleen als PDF.
  await page.locator("[data-stuk-link='stb-1990-222']").click();
  await page.locator("[data-stand-melding=alleen-pdf]").waitFor();
  assert.equal(await page.locator("[data-paneel-tab]").count(), 2, "twee publicaties als twee tabs");
  assert.ok(verzoeken.every((v) => v.startsWith("/api/bronnen/bekendmaking/")), "geen connector bij naam in de route");

  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.locator("[data-stuk-link='stb-2009-610']").click();
  await venster("stb-2009-610").waitFor();
  await geenScroll(375);

  assert.deepEqual(errors, []);
  console.log("Browser OK: een publicatie uit het Staatsblad als tab (kop uit de beschrijving, artikelkoppen, citaten gemarkeerd, gegevens), alleen PDF, op 375/1280 px.");
} finally {
  await browser.close();
}
