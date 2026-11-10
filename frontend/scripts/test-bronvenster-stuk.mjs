/** Browserregressie voor een stuk uit een bronconnector in het bronvenster (ADR-013, het bronvenster PR 6). Op de echte
 * Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-bronvenster-stuk.mjs`.
 *
 * Bewaakt:
 *  - het label van een stuk in het antwoord opent het als tab naast het gesprek (Ctrl/⌘ blijft de bron);
 *  - de kop uit de beschrijving van de connector en de metadata (geen connector bij naam in de code);
 *  - de inhoud, de tekst met de passages die Lex citeerde gemarkeerd, *Volgende deel laden* zolang er meer is;
 *  - de gegevens uit de beschrijving en de verwijzingen uit de voetnoten; een verwijzing opent een eigen tab;
 *  - de meldingen: een andere versie dan Lex las, alleen een PDF, en wat Lex las als de bron niet te bereiken is;
 *  - een uitspraak bij een eerdere tekst van het artikel: een label in de lijst en dezelfde melding in het venster
 *    (review ADR-013, 10 nov 2026);
 *  - geen horizontale scroll op 375, 800 en 1280 px.
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
const PASSAGES = [
  { nr: 1, soort: "alinea", kop: "I. ALGEMEEN › 1. Inleiding", tekst: "In het regeerakkoord is dit afgesproken." },
  { nr: 2, soort: "voetnoot", kop: "I. ALGEMEEN › 1. Inleiding", tekst: "Regeerakkoord, Kamerstuk 33 410, nr. 15.",
    verwijst_naar: [{ id: "kst-33410-15", label: "Kamerstukken 33410, nr. 15", link: LINK("kst-33410-15") }] },
];
const extern = { sjabloon: "extern", versie: 1, doelen: [], blokken: [
  { soort: "toelichting", door: "lex", kop: "Toelichting van Lex", tekst: "Zo staat het in de memorie." },
  { soort: "extern", door: "bron", brontype: "kamerstuk", id: "kst-33755-3", label: "Kamerstukken 33755, nr. 3", link: LINK("kst-33755-3"),
    kop: "Uit de parlementaire geschiedenis", bron_hash: "h-gelezen", gewijzigd: "2014-06-24", passages: PASSAGES }] };
const bewaard = [{ id: 1, rol: "user", tekst: "Wat zegt de memorie?" }, { id: 2, rol: "assistant", tekst: "Zo staat het in de memorie.",
  run_id: "r2", antwoord: extern, grounding: { grounded: true, cited: 0, unsupported: [], niet_letterlijk: [], niveau: "gegrond" } }];

const BESCHRIJVING = { naam: "kamerstukken", label: "Kamerstukken", groep: "Parlementaire stukken", brontype: "kamerstuk", id_prefixen: ["kst-"],
  metadata: [{ sleutel: "soort", label: "soort stuk" }, { sleutel: "datum", label: "documentdatum" }, { sleutel: "orgaan", label: "Kamer" }] };
const STUK = { id: "kst-33755-3", label: "Kamerstukken 33755, nr. 3", titel: "MEMORIE VAN TOELICHTING", link: LINK("kst-33755-3"),
  soort: "Memorie van toelichting", datum: "2013-11-12", orgaan: "Tweede Kamer", bron_hash: "h-nu" };
const ECLI = "ECLI:NL:HR:2018:2";
const uitspraken = { sjabloon: "extern", versie: 1, doelen: [], blokken: [
  { soort: "toelichting", door: "lex", kop: "Toelichting van Lex", tekst: "Twee uitspraken noemen artikel 9." },
  { soort: "stukken", door: "bron", brontype: "uitspraak", kop: "Gevonden Rechtspraak", totaal: 2,
    zoekvraag: "Gezocht bij artikel 9 van Invorderingswet 1990. Nieuwste eerst.", items: [
      { id: "ECLI:NL:HR:2024:1", label: "Hoge Raad 12 maart 2024, ECLI:NL:HR:2024:1", soort: "Uitspraak", datum: "2024-03-12",
        orgaan: "Hoge Raad", tekst_vanaf: "2023-01-01", tekststand: "huidige tekst" },
      { id: ECLI, label: "Hoge Raad 5 juni 2018, ECLI:NL:HR:2018:2", soort: "Uitspraak", datum: "2018-06-05", orgaan: "Hoge Raad",
        tekst_vanaf: "2016-05-01", tekst_tot: "2022-12-31", tekststand: "eerdere tekst" }] }] };
const RECHTSPRAAK = { naam: "rechtspraak", label: "Rechtspraak", groep: "Rechtspraak", brontype: "uitspraak", id_prefixen: ["ECLI:NL:"],
  metadata: [{ sleutel: "datum", label: "datum uitspraak" }, { sleutel: "orgaan", label: "instantie" }] };
let bronWeg = false;
const verzoeken = [];

await context.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname;
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Memorie", aantal_berichten: 2 },
    { id: "g2", titel: "Uitspraken", aantal_berichten: 2 }] });
  if (p === "/api/gesprekken/g2") return route.fulfill({ json: { id: "g2", titel: "Uitspraken", berichten: [
    { id: 1, rol: "user", tekst: "Welke uitspraken noemen artikel 9 Iw?" },
    { id: 2, rol: "assistant", tekst: "Twee uitspraken noemen artikel 9.", run_id: "r3", antwoord: uitspraken }] } });
  if (p === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", titel: "Memorie", berichten: bewaard } });
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  if (p.startsWith("/api/bronnen/")) {
    verzoeken.push(`${p}${url.search}`);
    if (bronWeg) return route.fulfill({ status: 502, json: { detail: "weg" } });
    const [, , , brontype, ruw] = p.split("/");
    const id = decodeURIComponent(ruw);
    if (brontype === "uitspraak")
      return route.fulfill({ json: { connector: RECHTSPRAAK, resultaat: { status: "ok", volledig: true,
        stuk: { id, label: "Hoge Raad 5 juni 2018, ECLI:NL:HR:2018:2", datum: "2018-06-05", orgaan: "Hoge Raad", bron_hash: "h" },
        resultaten: [{ nr: 1, soort: "alinea", kop: "Uitspraak", tekst: "Artikel 9 van de Invorderingswet 1990 bepaalt de termijn." }] } } });
    assert.equal(brontype, "kamerstuk", "de werkplek vraagt het stuk op het brontype");
    if (id === "kst-33410-15")
      return route.fulfill({ json: { connector: BESCHRIJVING, resultaat: { status: "fout", reden: "alleen_pdf", melding: "alleen pdf",
        stuk: { id, label: "Kamerstukken 33410, nr. 15", link: LINK(id), datum: "2012-10-29" } } } });
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const deel = offset === 0
      ? { status: "ok", volledig: false, stuk: STUK, inhoud: [{ kop: "1. Inleiding", offset: 0 }, { kop: "2. Doel", offset: 3 }],
          resultaten: [...PASSAGES, { nr: 3, soort: "alinea", kop: "I. ALGEMEEN › 1. Inleiding", tekst: "Context die Lex niet citeerde." }],
          vervolg: { tool: "get_kamerstuk", args: { id, offset: 3 } } }
      : { status: "ok", volledig: true, stuk: STUK, resultaten: [{ nr: 4, soort: "alinea", kop: "2. Doel", tekst: "Het doel is eenvoud." }] };
    return route.fulfill({ json: { connector: BESCHRIJVING, resultaat: deel } });
  }
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: [] });
});

const stuk = (id) => page.locator(`[data-stukvenster="${id}"]`);
const geenScroll = async (w) => assert.ok(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), `op ${w}px geen horizontale scroll`);

try {
  await page.goto(`${base}/workbench?gesprek=g1`);
  const label = page.locator("[data-stuk-link='kst-33755-3']");
  await label.waitFor();
  assert.equal(await label.getAttribute("href"), LINK("kst-33755-3"), "met Ctrl/⌘ blijft het de bron zelf");
  await label.click();

  // De kop: het label als titel, de groep · soort · datum eronder, met de vindplaats.
  const venster = stuk("kst-33755-3");
  await venster.waitFor();
  await page.getByRole("heading", { name: "Kamerstukken 33755, nr. 3", exact: true }).waitFor();
  const herkomst = page.locator("[data-paneel-kop] [data-herkomst-link]");
  assert.equal(await herkomst.innerText(), "zoek.officielebekendmakingen.nl");
  assert.match(await page.locator("[data-paneel-kop]").innerText(), /Parlementaire stukken · Memorie van toelichting · 12 november 2013/);

  // Blokken: inhoud, tekst met de citaten gemarkeerd, gegevens, verwijzingen; en de melding over de versie.
  await venster.locator("[data-blok=inhoud]").getByRole("button", { name: "2. Doel" }).waitFor();
  assert.equal(await venster.locator("[data-geciteerd]").count(), 2, "de twee passages die Lex citeerde");
  assert.equal(await venster.locator("[data-passage='3'][data-geciteerd]").count(), 0, "de context is niet gemarkeerd");
  await venster.locator("[data-stand-melding=stuk-gewijzigd]").waitFor();
  assert.match(await venster.locator("[data-blok=gegevens]").innerText(), /soort stuk\s*Memorie van toelichting[\s\S]*Kamer\s*Tweede Kamer/);
  await venster.getByRole("button", { name: "Volgende deel laden" }).click();
  await venster.getByText("Het doel is eenvoud.").waitFor();
  assert.equal(await venster.getByRole("button", { name: "Volgende deel laden" }).count(), 0, "geen knop als er niets meer is");
  assert.ok(verzoeken.some((v) => v.endsWith("?offset=3")), "het vervolg vraagt vanaf de offset");

  for (const w of [1280, 800]) { await page.setViewportSize({ width: w, height: 800 }); await geenScroll(w); }
  await page.setViewportSize({ width: 1280, height: 900 });

  // Een verwijzing in een voetnoot opent een eigen tab; dat stuk staat alleen als PDF.
  await venster.locator("[data-blok=verwijzingen]").getByRole("button", { name: "Kamerstukken 33410, nr. 15" }).click();
  await page.locator("[data-stand-melding=alleen-pdf]").waitFor();
  assert.equal(await page.locator("[data-paneel-tab]").count(), 2, "het stuk en de verwijzing als twee tabs");
  await page.getByRole("tab", { name: "Kamerstukken 33755, nr. 3" }).click();
  await stuk("kst-33755-3").waitFor();

  // De bron is niet te bereiken: dan staat er wat Lex las.
  bronWeg = true;
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.locator("[data-stand-melding=bron-onbereikbaar]").waitFor();
  await page.getByText("In het regeerakkoord is dit afgesproken.").last().waitFor();

  // Op een telefoon: de sheet, zonder horizontale scroll.
  bronWeg = false;
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.locator("[data-stuk-link='kst-33755-3']").click();
  await stuk("kst-33755-3").waitFor();
  await geenScroll(375);

  // Een uitspraak bij een eerdere tekst van het artikel: het label in de lijst, dezelfde melding in het venster.
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${base}/workbench?gesprek=g2`);
  const oud = page.locator(`[data-stuk="${ECLI}"]`);
  await oud.locator("[data-tekststand=eerdere-tekst]").waitFor();
  assert.match(await oud.innerText(), /bij de tekst van 1 mei 2016 tot en met 31 december 2022/);
  const nu = page.locator("[data-stuk='ECLI:NL:HR:2024:1']");
  assert.equal(await nu.locator("[data-tekststand]").count(), 0, "bij de huidige tekst geen label");
  assert.match(await nu.innerText(), /bij de huidige tekst \(sinds 1 januari 2023\)/);
  await oud.locator(`[data-stuk-link="${ECLI}"]`).click();
  const uitspraak = stuk(ECLI);
  await uitspraak.waitFor();
  assert.match(await uitspraak.locator("[data-stand-melding=eerdere-tekst]").innerText(), /daarna gewijzigd/);
  await page.setViewportSize({ width: 375, height: 800 });
  await geenScroll(375);

  assert.deepEqual(errors, []);
  console.log("Browser OK: een stuk uit een bronconnector als tab (kop uit de beschrijving, inhoud, citaten gemarkeerd, volgende deel, gegevens, verwijzing als eigen tab), meldingen voor een andere versie, alleen PDF en een onbereikbare bron, een uitspraak bij een eerdere tekst, op 375/800/1280 px.");
} finally {
  await browser.close();
}
