/** Browserregressie: de weergave wijzigt een antwoord van Lex niet, op de echte Next-UI met een gemockte BFF.
 * Start Next met AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-antwoordweergave.mjs`.
 *
 * Bewaakt:
 *  - lijstnummers staan er zoals Lex ze schreef, ook na afloop van de stroom: een lijst die bij 3 begint, een
 *    lijst met een gat en een lijst die na een alinea verdergaat;
 *  - een vermelding die een andere regeling noemt dan de bron, krijgt geen citatie-chip; de juiste wel, ook
 *    live: `parseBronnen` moet de naam van de regeling en de afkortingen doorlaten;
 *  - een sjabloon staat als blokken in de tekst, zonder kaart en zonder bronnenlijst; een ongeldig sjabloon valt terug
 *    op `tekst`;
 *  - een bron naast de wet: een tabel als tabel met kolommen (scrolt op een telefoon in haar eigen vak), een voetnoot
 *    klein met een link naar het stuk waar ze naar verwijst.
 */
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const shots = process.env.MOCK_SCREENSHOTS || "/tmp/wetsanalyse-antwoordweergave";
mkdirSync(shots, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const TEKST = ["De voorwaarden uit de bepaling:", "", "3. de ontvanger", "4. de belastingschuldige", "", "Met een gat:", "",
  "1. eerste", "3. derde", "", "Tussenzin.", "", "2. loopt door", "",
  "Zie artikel 9 van de Algemene wet bestuursrecht. Vergelijk artikel 9 Iw."].join("\n");
const IRI = "urn:bwb:BWBR0004770:artikel:9";
const BRON = { label: "Artikel 9", uri: IRI, bron_iri: IRI, bwb_id: "BWBR0004770", soort: "artikel",
  regeling: "Invorderingswet 1990", afkortingen: ["IW", "Iw 1990"] };
const stroom = [{ type: "token", content: TEKST }, { type: "sources", sources: [BRON] },
  { type: "grounding", grounded: true, cited: 1, unsupported: [], niet_letterlijk: [], niveau: "gegrond" },
  { type: "opgeslagen", run_id: "r1" }, { type: "done" }];
const K = "urn:bwb:BWBR0004770:artikel:2:lid:1:o:k";
const VINDPLAATS = { iri: K, label: "Artikel 2, lid 1, onderdeel k", jci: "jci1.3:c:BWBR0004770&artikel=2&lid=1&o=k", regeling: "Invorderingswet 1990" };
const SJABLOON = { sjabloon: "begrip", versie: 1, doelen: [VINDPLAATS], blokken: [
  { soort: "definities", door: "bron", items: [{ term: "belastingschuldige", tekst: "belastingschuldige: degene te wiens naam de belastingaanslag is gesteld;", vindplaats: VINDPLAATS, bereik: "" }] },
  { soort: "begrippen", door: "bron", items: [{ id: "b1", naam: "belastingschuldige", status: "geaccordeerd", definitie: "degene te wiens naam de belastingaanslag is gesteld", werkgebied: "Rekeningafspraak", werkgebied_id: "w1", herbeoordelen: false }] },
  { soort: "toelichting", door: "lex", kop: "Toelichting van Lex", tekst: "De tenaamstelling beslist." },
] };
// Wat de api na `opgeslagen` als bericht teruggeeft: de werkplek herlaadt het gesprek, en zonder bericht is het antwoord weg.
let bewaard = [];
const bewaar = (antwoord, niveau = "gegrond") => {
  bewaard = [{ id: 1, rol: "user", tekst: "vraag" }, { id: 2, rol: "assistant", tekst: "De tekst uit de blokken.", run_id: "r2", antwoord,
    grounding: { grounded: true, cited: 0, unsupported: [], niet_letterlijk: [], niveau } }];
};
const sjabloonStroom = (antwoord) => [{ type: "antwoord", antwoord }, { type: "token", content: "De tekst uit de blokken." },
  { type: "sources", sources: [{ label: VINDPLAATS.label, uri: K, bron_iri: K, bwb_id: "BWBR0004770", soort: "onderdeel" }] },
  { type: "grounding", grounded: true, cited: 1, unsupported: [], niet_letterlijk: [], niveau: "gegrond" },
  { type: "opgeslagen", run_id: "r2" }, { type: "done" }];
let huidige = stroom;
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");

await context.route("**/api/**", async (route) => {
  const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g9", titel: body?.titel ?? "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (/^\/api\/gesprekken\/g\d$/.test(p)) return route.fulfill({ json: { id: "g9", titel: "Test", berichten: bewaard } });
  if (p.endsWith("/berichten") && m === "POST") return route.fulfill({ status: 201, json: { id: 1 } });
  if (p === "/api/annotatie/run" && m === "POST") return route.fulfill({ status: 201, json: { run_id: "r1", conversation_id: body.conversation_id, status: "loopt" } });
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  if (/\/run\/[^/]+\/events$/.test(p)) return route.fulfill({ contentType: "text/event-stream", body: sse(huidige) });
  if (p === "/api/annotatie/v2/weergave")
    return route.fulfill({ json: { schema_versie: 2, doel: { bron_iri: K, label: VINDPLAATS.label, bwb_id: "BWBR0004770" }, snapshot_id: "s",
      segmenten: [], lagen: [], elementen: [], verwijzingen: [], dekking: {} } });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: [] });
});

try {
  await page.goto(`${base}/workbench`);
  const vraag = page.getByPlaceholder("Vraag of opdracht voor Lex…");
  await vraag.fill("Wat regelt artikel 9?");
  await vraag.press("Enter");

  const lijstitems = page.locator("ol > li");
  await page.getByText("loopt door").and(page.locator("li")).waitFor();
  assert.deepEqual(await lijstitems.evaluateAll((els) => els.map((li) => li.value)), [3, 4, 1, 3, 2]);

  // De chip is een knop met de vermelding erin; de vermelding van de andere wet blijft gewone tekst.
  const chips = page.locator("button[aria-haspopup=dialog]", { hasText: "artikel 9" });
  await chips.first().waitFor();
  assert.equal(await chips.count(), 1);
  await page.getByText("Zie artikel 9 van de Algemene wet bestuursrecht", { exact: false }).waitFor();
  await page.screenshot({ path: `${shots}/antwoord.png` });

  // Een sjabloon: blokken in de tekst, de definitie uit de bron, wat Lex schreef onder een eigen kop.
  huidige = sjabloonStroom(SJABLOON);
  bewaar(SJABLOON);
  await page.goto(`${base}/workbench`);
  await vraag.fill("Wat betekent belastingschuldige?");
  await vraag.press("Enter");
  const blokken = page.getByTestId("antwoord-sjabloon");
  await blokken.waitFor();
  const inhoud = await blokken.innerText();
  assert.match(inhoud, /Wettelijke definitie\s+belastingschuldige: degene te wiens naam/);
  assert.match(inhoud, /Artikel 2, lid 1, onderdeel k, Invorderingswet 1990/);
  assert.match(inhoud, /Vastgelegd begrip/);
  assert.match(inhoud, /Toelichting van Lex\s+De tenaamstelling beslist\./);
  assert.equal(await page.getByRole("button", { name: /^Bronnen \(/ }).count(), 0, "de blokken noemen de vindplaats al");
  const stijl = await blokken.evaluate((el) => { const s = getComputedStyle(el); return [s.backgroundColor, s.borderTopWidth]; });
  assert.deepEqual(stijl, ["rgba(0, 0, 0, 0)", "0px"], "een sjabloon staat in de tekst");
  await page.screenshot({ path: `${shots}/sjabloon.png` });
  await page.setViewportSize({ width: 375, height: 800 });
  await page.screenshot({ path: `${shots}/sjabloon-mobiel.png` });
  await page.setViewportSize({ width: 1280, height: 900 });

  // De chip onder het antwoord opent de bepaling naast het gesprek (ADR-008, *Detail bij een antwoord*).
  await page.waitForURL(/gesprek=g9/);
  await page.locator(`[data-bepaling-chip="${K}"]`).click();
  await page.locator("[data-context-paneel=bron]").waitFor();
  await page.keyboard.press("Escape");

  // Een bepaling met leden: één kop voor het artikel, "lid N" bij elke tekst.
  const lid = (n, tekst) => ({ tekst, vindplaats: { iri: `${IRI}:lid:${n}`, label: `Artikel 9, lid ${n}`,
    jci: `jci1.3:c:BWBR0004770&hoofdstuk=II&artikel=9&lid=${n}&z=2026-10-01&g=2026-10-01`, regeling: "Invorderingswet 1990" }, nog_niet_in_werking: false });
  const bepaling = { sjabloon: "bepaling", versie: 1, doelen: [{ iri: IRI, label: "Artikel 9", jci: "", regeling: "Invorderingswet 1990" }], blokken: [
    { soort: "wettekst", door: "bron", items: [lid(1, "Een belastingaanslag is invorderbaar zes weken na de dagtekening."), lid(2, "In afwijking van het eerste lid is een navorderingsaanslag invorderbaar na één maand.")] }] };
  huidige = sjabloonStroom(bepaling);
  bewaar(bepaling);
  await page.goto(`${base}/workbench`);
  await vraag.fill("Wat staat er in artikel 9?");
  await vraag.press("Enter");
  await page.locator(`[data-wettekst-artikel="${IRI}"]`).waitFor();
  assert.equal(await page.locator("[data-wettekst-artikel]").count(), 1, "de leden staan onder één artikelkop");
  assert.equal(await page.getByRole("link", { name: "Artikel 9, Invorderingswet 1990" }).count(), 1);
  assert.equal(await page.getByRole("link", { name: "lid 2" }).getAttribute("href"),
    "https://wetten.overheid.nl/jci1.3:c:BWBR0004770&hoofdstuk=II&artikel=9&lid=2&z=2026-10-01&g=2026-10-01", "de link opent de gelezen toestand");
  for (const width of [375, 800, 1280]) {
    await page.setViewportSize({ width, height: 800 });
    assert.ok(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), `geen horizontale scroll op ${width}px`);
  }
  await page.setViewportSize({ width: 1280, height: 900 });

  // Annotaties: een chip naar de bepaling van de markeringen; een leemte van de code krijgt geen "niets te controleren".
  const metAnnotaties = (blokken, niveau = "gegrond") => {
    bewaar({ sjabloon: "annotaties", versie: 1, doelen: [], blokken }, niveau);
    return sjabloonStroom({ sjabloon: "annotaties", versie: 1, doelen: [], blokken }).map((e) => e.type === "grounding" ? { ...e, niveau, cited: 0 } : e);
  };
  huidige = metAnnotaties([{ soort: "annotaties", door: "bron", totaal: 1, volledig: true,
    items: [{ id: "e1", klasse: "Tijdsaanduiding", tekst: "zes weken", vindplaats: "Invorderingswet 1990 art. 9 lid 1", bron_iri: `${IRI}:lid:1` }] }]);
  await page.goto(`${base}/workbench`);
  await vraag.fill("Welke annotaties zijn er bij artikel 9 lid 1?");
  await vraag.press("Enter");
  await page.locator(`[data-bepaling-chip="${IRI}:lid:1"]`).waitFor();
  huidige = metAnnotaties([{ soort: "leemte", door: "bron", tekst: "Geen annotaties gevonden met deze zoekopdracht (Artikel 36)." }], "onbepaald");
  await page.goto(`${base}/workbench`);
  await vraag.fill("Welke annotaties zijn er bij artikel 36?");
  await vraag.press("Enter");
  await page.locator("[data-leemte]").waitFor();
  assert.equal(await page.getByText("er valt niets te controleren", { exact: false }).count(), 0, "een leemte van de code is geen controlemelding");

  // Een Kamerstuk met een tabel en een voetnoot (ADR-013): de tabel als tabel met kolommen, de voetnoot klein met een link.
  const extern = { sjabloon: "extern", versie: 1, doelen: [], blokken: [
    { soort: "toelichting", door: "lex", kop: "Toelichting van Lex", tekst: "De opbrengst staat in tabel 1." },
    { soort: "extern", door: "bron", brontype: "kamerstuk", id: "kst-33755-3", label: "Kamerstukken 33755, nr. 3",
      link: "https://zoek.officielebekendmakingen.nl/kst-33755-3", kop: "Uit de parlementaire geschiedenis", bron_hash: "h", gewijzigd: "2014-06-24",
      passages: [
        { nr: 1, soort: "alinea", kop: "I. ALGEMEEN › 1. Inleiding", tekst: "In het regeerakkoord is dit afgesproken." },
        { nr: 2, soort: "voetnoot", kop: "I. ALGEMEEN › 1. Inleiding", tekst: "Regeerakkoord, Kamerstuk 33 410, nr. 15, bijlage B.",
          verwijst_naar: [{ id: "kst-33410-15", label: "Kamerstukken 33410, nr. 15", link: "https://zoek.officielebekendmakingen.nl/kst-33410-15" }] },
        { nr: 13, soort: "tabel", kop: "I. ALGEMEEN › 5. Budgettaire aspecten", tekst: "Tabel 1 Gevolgen voor uitgavenkader (€ miljoenen)",
          cellen: ["", "2014", "2015", "2016", "2017", "struc"] },
        { nr: 14, soort: "tabelrij", kop: "", tekst: "Totaal | 12 | 106 | 155 | 193 | 267",
          cellen: ["Totaal Wet wijziging percentages belasting- en invorderingsrente", "12", "106", "155", "193", "267"] },
      ] }] };
  huidige = sjabloonStroom(extern);
  bewaar(extern);
  await page.goto(`${base}/workbench`);
  await vraag.fill("Wat is de budgettaire opbrengst volgens de MvT?");
  await vraag.press("Enter");
  const tabel = page.locator("[data-extern-tabel] table");
  await tabel.waitFor();
  assert.deepEqual(await tabel.locator("th").allInnerTexts(), ["", "2014", "2015", "2016", "2017", "struc"]);
  assert.deepEqual((await tabel.locator("td").allInnerTexts()).slice(0, 2), ["Totaal Wet wijziging percentages belasting- en invorderingsrente", "12"]);
  assert.match(await tabel.locator("caption").innerText(), /^Tabel 1 Gevolgen voor uitgavenkader/);
  const noot = page.locator("[data-extern-voetnoot]");
  assert.match(await noot.innerText(), /Voetnoot: Regeerakkoord, Kamerstuk 33 410, nr\. 15/);
  assert.equal(await noot.getByRole("link", { name: "Kamerstukken 33410, nr. 15" }).getAttribute("href"),
    "https://zoek.officielebekendmakingen.nl/kst-33410-15");
  await page.screenshot({ path: `${shots}/extern-tabel.png` });
  await page.setViewportSize({ width: 375, height: 800 });
  assert.ok(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), "een brede tabel scrolt in zijn eigen vak");
  await page.screenshot({ path: `${shots}/extern-tabel-mobiel.png` });
  await page.setViewportSize({ width: 1280, height: 900 });

  // Een lijst gevonden Kamerstukken (gesprek e906567a): elk feit uit de zoekrijen, met de zoekvraag en het totaal, en een
  // onopgemaakt stuk met alleen een PDF zichtbaar als zodanig. De datum van een gelezen stuk staat in de kop van `extern`.
  const lijst = { sjabloon: "extern", versie: 1, doelen: [], blokken: [
    { soort: "toelichting", door: "lex", kop: "Toelichting van Lex", tekst: "Het nieuwste stuk is een brief." },
    { soort: "stukken", door: "bron", brontype: "kamerstuk", kop: "Gevonden Kamerstukken", totaal: 405,
      zoekvraag: "Gezocht op dossier 32140, nieuwste eerst.", items: [
        { id: "kst-1278484", label: "Kamerstukken 32140, nr. 342", link: "https://zoek.officielebekendmakingen.nl/kst-1278484",
          soort: "Brief regering", titel: "Informatie implementatie FASTER richtlijn", datum: "2026-10-16",
          gepubliceerd: "2026-11-05", orgaan: "Tweede Kamer", indieners: ["E. Eerenberg"], status: "Onopgemaakt", leesbaar: false,
          zonder_tekst: "onopgemaakt, alleen PDF" },
        { id: "kst-32140-AR", label: "Kamerstukken 32140, nr. AR", link: "https://zoek.officielebekendmakingen.nl/kst-32140-AR",
          soort: "Brief", datum: "2026-07-01", orgaan: "Eerste Kamer" }] },
    { soort: "extern", door: "bron", brontype: "kamerstuk", id: "kst-32140-AR", label: "Kamerstukken 32140, nr. AR",
      link: "https://zoek.officielebekendmakingen.nl/kst-32140-AR", kop: "Uit de parlementaire geschiedenis",
      datum: "2026-07-01", soort_stuk: "Brief", passages: [{ nr: 1, soort: "alinea", kop: "", tekst: "Hierbij informeer ik u." }] }] };
  huidige = sjabloonStroom(lijst);
  bewaar(lijst);
  await page.goto(`${base}/workbench`);
  await vraag.fill("Wat is het laatste stuk van dossier 32140?");
  await vraag.press("Enter");
  const stukken = page.locator("[data-stukken=kamerstuk]");
  await stukken.waitFor();
  const eerste = stukken.locator("[data-stuk=kst-1278484]");
  assert.equal(await eerste.getByRole("link", { name: "Kamerstukken 32140, nr. 342" }).getAttribute("href"),
    "https://zoek.officielebekendmakingen.nl/kst-1278484");
  // De tekst bij een stuk zonder tekst komt van de connector (`zonder_tekst`, #1190), niet vast uit de werkplek.
  assert.match(await eerste.innerText(), /onopgemaakt, alleen PDF/);
  assert.match(await eerste.innerText(), /Brief regering · 16 oktober 2026 · Tweede Kamer · gepubliceerd 5 november 2026/);
  assert.match(await eerste.innerText(), /Ingediend door E\. Eerenberg/);
  assert.equal(await page.locator("[data-stukken-zoekvraag]").innerText(), "Gezocht op dossier 32140, nieuwste eerst. 2 van de 405 stukken.");
  assert.equal(await page.locator("[data-extern-meta]").innerText(), " · Brief, 1 juli 2026");
  await page.screenshot({ path: `${shots}/stukken.png` });
  await page.setViewportSize({ width: 375, height: 800 });
  assert.ok(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), "de lijst past op een telefoon");
  await page.screenshot({ path: `${shots}/stukken-mobiel.png` });
  await page.setViewportSize({ width: 1280, height: 900 });

  // Klopt het sjabloon niet, dan is `tekst` het antwoord.
  huidige = sjabloonStroom({ sjabloon: "begrip", blokken: [{ soort: "onbekend" }] });
  bewaar({ sjabloon: "begrip", blokken: [{ soort: "onbekend" }] });
  await page.goto(`${base}/workbench`);
  await vraag.fill("Nog eens");
  await vraag.press("Enter");
  await page.getByText("De tekst uit de blokken.").waitFor();
  assert.equal(await page.getByTestId("antwoord-sjabloon").count(), 0);
  assert.deepEqual(errors, []);
  console.log("antwoordweergave: ok");
} finally {
  await browser.close();
}
