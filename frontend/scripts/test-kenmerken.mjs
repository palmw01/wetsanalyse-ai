/** Browserregressie voor de kenmerken van een begrip, de voorbeeldtabel van een regel en de regelbegrippen in het kader
 * (plan lessen Termijnen-bibliotheek, V2, V3, V4, V11) op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-kenmerken.mjs`. Met `KENMERKEN_SCREENSHOT=<map>` maakt hij de beelden voor de PR, op 1440
 * en op 390 px.
 *
 * Bewaakt:
 *  - het blok Kenmerken toont de klasse (afgeleid of gekozen, met reden), het waardebereik en de eigenaar, en zonder
 *    waardebereik "Nog geen waardebereik."; bewerken stuurt het waardebereik als object en een gekozen klasse met reden;
 *  - naast het gesprek staat hetzelfde blok;
 *  - de regelkaart toont de voorbeelden als tabel en het signaal van een waarde buiten het bereik;
 *  - het kader zet een regelbegrip ingeklapt onder Regelbegrippen, niet tussen de begrippen.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";
import { SCHIL, controleerOnbekend, onbekend } from "./nepApi.mjs";

/** Paden die de werkplek hier aanroept en die deze test bewust niet nabootst: ze krijgen een leeg antwoord. */
const NIET_NAGEBOOTST = [
  /^GET \/api\/werkgebieden\/wg1\/(kandidaten|herbeoordelingen|begrippen\/conformiteit|bronselectie|toestanden|dekking|annotatie-werkvoorraad)$/,
  /^GET \/api\/werkgebieden\/wg1\/(bronnen-runs\/laatste|relaties|delegaties)$/,
  /^GET \/api\/werkgebieden\/wg1\/begrippen\/b\d\/(voorstellen|revisies)$/,
  /^GET \/api\/artefact-versies$/, /^GET \/api\/delegaties$/, /^GET \/api\/werkgebieden$/, /^GET \/api\/begrippen$/,
  /^GET \/api\/gesprekken\/g1\/contextopbouw$/,
];

const base = process.env.TEST_URL || "http://localhost:3109";
const SCHERM = process.env.KENMERKEN_SCREENSHOT;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [], patches = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-11-24T10:00:00+00:00";
const wg = { id: "wg1", naam: "Termijnen", status: "in_voorbereiding", revisie: 1, peildatum: null, aangemaakt_door: "t",
  aangemaakt: nu, gewijzigd: nu, analysevraag: "Hoeveel termijnen heeft een voorlopige aanslag?", afbakening: "", aanleiding: "",
  context: "", doel: "", praktijkvoorbeeld: "", deelvragen: [], bronnen: [] };
const LEEG = { naam: "", alternatieve_termen: [], context: "", definitie: "", definitie_herkomst: null, definitie_door: "",
  uitleg: "", voorbeelden: [] };
const passage = (id, tekst, klasse) => ({ id: `k-${id}`, element_id: id, rol: "duiding", beoordeling: "akkoord", motivatie: "",
  beoordeeld_door: "t", beoordeeld_op: nu, actualiteit: "actueel", lifecycle_nu: "human_approved", annotatie_beoordeeld: true,
  bevestigingen: [], bewijs: { tekst, klasse, ankers: [], vindplaats: "Invorderingswet 1990 – Artikel 9, Lid 5", eigenaar_iri: "" } });
const begrip = (id, naam, inhoud, koppelingen, klasse, extra = {}) => ({ id, iri: `urn:wa:begrip:${id}`, werkgebied_id: "wg1",
  kader: "werkgebied", kader_iri: "urn:wa:kader:wg1", status: "concept", revisie: 1,
  inhoud: { ...LEEG, naam, ...inhoud }, koppelingen, klasse, aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu,
  geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
  accorderen: { mag: false, redenen: ["De toelichting ontbreekt."] }, aandachtspunten: [], vervangen_door: null, vervangt: [], ...extra });
const VAR = "Variabele en variabelewaarde";
const begrippen = {
  b1: begrip("b1", "aantal termijnen", {
    definitie: "aantal betalingstermijnen van een voorlopige aanslag",
    waardebereik: { soort: "aantal", eenheid: "", decimalen: 0, minimum: "1", maximum: "12", waarden: [], toelichting: "" },
    eigenaar: "Inning" }, [passage("e1", "zoveel gelijke termijnen", VAR)],
  { klasse: VAR, afgeleid: VAR, uit_passages: { [VAR]: 1 }, gekozen: "", reden: "" }),
  b2: begrip("b2", "voorlopige aanslag in de inkomstenbelasting", {
    definitie: "situatie waarin een aanslag een voorlopige aanslag in de inkomstenbelasting is",
    klasse_keuze: { klasse: VAR, reden: "In de tekst een object, in de regels een ja/nee-kenmerk van de aanslag." } },
  [passage("e2", "een voorlopige aanslag in de inkomstenbelasting", "Rechtsobject")],
  { klasse: VAR, afgeleid: "Rechtsobject", uit_passages: { Rechtsobject: 1 }, gekozen: VAR,
    reden: "In de tekst een object, in de regels een ja/nee-kenmerk van de aanslag." }),
  b3: begrip("b3", "bepalen van het aantal termijnen", { definitie: "Afleidingsregel die het aantal termijnen bepaalt." },
    [passage("e3", "zoveel gelijke termijnen als …", "Afleidingsregel")],
    { klasse: "Afleidingsregel", afgeleid: "Afleidingsregel", uit_passages: { Afleidingsregel: 1 }, gekozen: "", reden: "" }),
  b4: begrip("b4", "maand van de dagtekening", { definitie: "kalendermaand van de dagtekening van het aanslagbiljet",
    waardebereik: { soort: "opsomming", waarden: ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
      "september", "oktober", "november", "december"] } }, [passage("e4", "de maand", VAR)],
    { klasse: VAR, afgeleid: VAR, uit_passages: { [VAR]: 1 }, gekozen: "", reden: "" }),
};
const samenvatting = (b) => { const { koppelingen, ...rest } = b;
  return { ...rest, aantal_koppelingen: koppelingen.length, regelbegrip: b.id === "b3", element_ids: koppelingen.map((k) => k.element_id) }; };

const regel = {
  id: "r1", werkgebied_id: "wg1", status: "concept", revisie: 1, herkomst: "import", opvolger_van: null, vervangen_door: null,
  opvolging: { vervangen_door: null, vervangt: [] },
  inhoud: { soort: "rekenregel", regelbegrip_id: "b3", uitvoer_begrip_id: "b1", onderwerp_begrip_id: "", lidwoord: "het",
    invoer: [{ begrip_id: "b4", rol: "invoer" }, { begrip_id: "b2", rol: "invoer" }],
    gevallen: [{ label: "", voorwaarden: null, voorrang: 0, uitkomst: [{ soort: "tekst", tekst: "twaalf min de maand" }] }],
    voorbeelden: [
      { geval: "", invoer: "april, IB", uitkomst: "8", oordeel: "juist", toelichting: "", door: "t", beoordeeld_door: "j",
        waarden: [{ begrip_id: "b4", waarde: "april" }, { begrip_id: "b2", waarde: "ja" }] },
      { geval: "", invoer: "december, IB", uitkomst: "1", oordeel: "open", toelichting: "", door: "t",
        waarden: [{ begrip_id: "b4", waarde: "december" }, { begrip_id: "b2", waarde: "ja" }] },
      { geval: "", invoer: "maand 13", uitkomst: "–", oordeel: "open", toelichting: "", door: "t",
        waarden: [{ begrip_id: "b4", waarde: "dertien" }, { begrip_id: "b2", waarde: "ja" }] },
    ],
    toelichting: "", brontype: "wet", eigenaar: "Inning" },
  naam: "bepalen van het aantal termijnen", uitvoer: "aantal termijnen",
  regeltekst: { tekst: "Het aantal termijnen moet berekend worden als twaalf min de maand van de dagtekening.",
    markdown: "Het _aantal termijnen_ moet berekend worden als twaalf min de _maand van de dagtekening_.",
    gevallen: [{ label: "", tekst: "…" }] },
  begrippen: Object.fromEntries(["b1", "b2", "b3", "b4"].map((i) => [i, { id: i, naam: begrippen[i].inhoud.naam,
    status: "concept", definitie: begrippen[i].inhoud.definitie }])),
  dragers: [{ id: "d1", element_id: "e3", rol: "grondslag", geval: "", bewijs: null, beoordeling: "akkoord", beoordeeld_door: "j",
    actualiteit: "actueel" }],
  accorderen: { mag: false, redenen: ["Voorbeeld 2 en 3 zijn nog niet beoordeeld."] },
  signalen: ['Voorbeeld 3 noemt voor maand van de dagtekening de waarde "dertien", maar dat begrip is een keuze uit een lijst (januari, februari, maart, april, mei, juni, juli, augustus, september, oktober, november, december).'],
  gaten: [], open_punten: { open: 0, totaal: 0, bij_voorganger: 0 },
  aangemaakt_door: "import", aangemaakt: nu, gewijzigd: nu, geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
};

const gesprek = { id: "g1", titel: "Termijnen", werkgebied_id: "wg1", berichten: [
  { rol: "user", tekst: "Werk het begrip aantal termijnen uit", bronnen: [], tool_executions: [] },
  { rol: "assistant", tekst: "Het begrip staat naast het gesprek.", bronnen: [], tool_executions: [], run_id: "k1",
    artefact: { soort: "begrip", titel: "aantal termijnen", ref: { werkgebied_id: "wg1", begrip_id: "b1" } } }] };

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/begrippen" && m === "GET")
    return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", begrippen: Object.values(begrippen).map(samenvatting), primair: {} } });
  const bm = p.match(/^\/api\/werkgebieden\/wg1\/begrippen\/(b\d)$/);
  if (bm && m === "GET") return route.fulfill({ json: begrippen[bm[1]] });
  if (bm && m === "PATCH") {
    const body = req.postDataJSON(), b = begrippen[bm[1]];
    patches.push(body.inhoud);
    b.inhoud = { ...b.inhoud, ...body.inhoud };
    b.revisie += 1;
    if (body.inhoud.klasse_keuze) b.klasse = { ...b.klasse, klasse: body.inhoud.klasse_keuze.klasse, gekozen: body.inhoud.klasse_keuze.klasse,
      reden: body.inhoud.klasse_keuze.reden };
    return route.fulfill({ json: b });
  }
  if (p === "/api/werkgebieden/wg1/regels/r1" && m === "GET") return route.fulfill({ json: regel });
  if (p === "/api/werkgebieden/wg1/regels" && m === "GET") return route.fulfill({ json: { regels: [regel] } });
  if (p === "/api/werkgebieden/wg1/regels/hierarchie") return route.fulfill({ json: { regels: [], volgorde: [], pijlen: [], basisgegevens: [], signalen: [] } });
  // Wat een scherm als lege stand moet zien (anders staat er een foutmelding in het beeld).
  if (p === "/api/werkgebieden/wg1/open-punten") return route.fulfill({ json: { open_punten: [] } });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run: null } });
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: { run: null, groepen: [], passages: {} } });
  if (p === "/api/werkgebieden/wg1/regels/r1/revisies") return route.fulfill({ json: { revisies: [] } });
  if (p === "/api/gesprekken/g1") return route.fulfill({ json: gesprek });
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Termijnen", werkgebied_id: "wg1", aantal_berichten: 2 }] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return onbekend(route, { stil: [...SCHIL, ...NIET_NAGEBOOTST], leeg: {}, stilStatus: 404 });
});

/** Het venster, en met `blok` ook het blok zelf: de pagina's scrollen in een eigen kolom, dus `fullPage` helpt niet. */
const beeld = async (naam, blok) => {
  if (!SCHERM) return;
  await page.screenshot({ path: `${SCHERM}/${naam}.png` });
  if (blok) await blok.screenshot({ path: `${SCHERM}/${naam}-blok.png` });
};
let blokNu = null;
const opBeide = async (naam, toon) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  blokNu = null;
  await toon();
  await beeld(`${naam}-desktop`, blokNu);
  await page.setViewportSize({ width: 390, height: 844 });
  blokNu = null;
  await toon();
  await beeld(`${naam}-390`, blokNu);
  await page.setViewportSize({ width: 1440, height: 1000 });
};

try {
  // --- Kenmerken op de pagina, met waardebereik en eigenaar ---
  await opBeide("kenmerken-pagina", async () => {
    await page.goto(`${base}/werkgebieden/wg1/begrippen/b1`);
    const blok = page.locator('[data-blok="kenmerken"]');
    await blok.waitFor();
    const lees = blok.locator("[data-begrip-kenmerken]");
    await lees.getByText(VAR).first().waitFor();
    await lees.getByText("uit 1 passage").waitFor();
    await lees.getByText("aantal, 0 decimalen, van 1 tot en met 12").waitFor();
    await lees.getByText("Inning").waitFor();
    await blok.scrollIntoViewIfNeeded();
    blokNu = blok;
  });

  // --- Zonder waardebereik, met een gekozen klasse en reden ---
  await opBeide("kenmerken-zonder-waardebereik", async () => {
    await page.goto(`${base}/werkgebieden/wg1/begrippen/b2`);
    const lees = page.locator('[data-blok="kenmerken"] [data-begrip-kenmerken]');
    await lees.waitFor();
    await lees.getByText("Nog geen waardebereik.").waitFor();
    await lees.getByText("gekozen; de passages zeggen Rechtsobject").waitFor();
    await lees.getByText("In de tekst een object", { exact: false }).waitFor();
    blokNu = page.locator('[data-blok="kenmerken"]');
    await blokNu.scrollIntoViewIfNeeded();
  });

  // --- Bewerken: een waardebereik zetten ---
  await page.goto(`${base}/werkgebieden/wg1/begrippen/b2`);
  const blok = page.locator('[data-blok="kenmerken"]');
  await blok.getByRole("button", { name: "Kenmerken bewerken" }).click();
  await blok.getByLabel("Soort waarde").selectOption("ja_nee");
  await blok.getByLabel("Toelichting bij de waarde").fill("waar als de aanslag dit soort is");
  await beeld("kenmerken-bewerken-desktop");
  await blok.getByRole("button", { name: "Opslaan" }).click();
  await blok.locator("[data-begrip-kenmerken]").getByText("ja of nee (waar als de aanslag dit soort is)").waitFor();
  const laatst = patches.at(-1);
  assert.equal(laatst.waardebereik.soort, "ja_nee");
  assert.deepEqual(laatst.klasse_keuze, { klasse: VAR, reden: "In de tekst een object, in de regels een ja/nee-kenmerk van de aanslag." });

  // --- Naast het gesprek ---
  await opBeide("kenmerken-paneel", async () => {
    await page.goto(`${base}/workbench?gesprek=g1`);
    const chip = page.locator('button[data-artefact-soort="begrip"]', { hasText: "aantal termijnen" });
    await chip.waitFor();
    await chip.click();
    const paneel = page.locator("[data-begrip-paneel=b1]");
    await paneel.waitFor();
    const lees = paneel.locator('[data-blok="kenmerken"] [data-begrip-kenmerken]');
    await lees.getByText("aantal, 0 decimalen, van 1 tot en met 12").waitFor();
    blokNu = paneel.locator('[data-blok="kenmerken"]');
    await blokNu.scrollIntoViewIfNeeded();
  });

  // --- De voorbeeldtabel en het signaal op de regelkaart ---
  await opBeide("voorbeeldtabel", async () => {
    await page.goto(`${base}/werkgebieden/wg1/regels/r1`);
    const tabel = page.locator("[data-voorbeeld-tabel]");
    await tabel.waitFor();
    const kop = await tabel.locator("thead th").allInnerTexts();
    assert.deepEqual(kop.map((t) => t.trim()), ["Voorbeeld", "1", "2", "3"]);
    await tabel.getByRole("rowheader", { name: "maand van de dagtekening" }).waitFor();
    await tabel.getByRole("cell", { name: "dertien" }).waitFor();
    await page.locator("[data-regel-signalen]").getByText('de waarde "dertien"', { exact: false }).waitFor();
    await page.getByText("eigenaar Inning", { exact: false }).waitFor();
    blokNu = page.locator("[data-regel-geval]").first();
    await blokNu.scrollIntoViewIfNeeded();
  });

  // --- De regelbegrippen in het kader ---
  await opBeide("regelbegrippen", async () => {
    await page.goto(`${base}/werkgebieden/wg1/artefacten/begrippen`);
    const lijst = page.getByRole("list", { name: "Begrippen in dit werkgebied" });
    await lijst.locator("[data-begrip-rij=b1]").waitFor();
    assert.equal(await lijst.locator("[data-begrip-rij=b3]").count(), 0, "het regelbegrip staat niet tussen de begrippen");
    const uitklap = page.locator("[data-regelbegrippen]");
    await uitklap.getByText("Regelbegrippen (1)").waitFor();
    assert.equal(await uitklap.getAttribute("open"), null, "ingeklapt");
    await uitklap.locator("summary").click();
    await uitklap.locator("[data-begrip-rij=b3]").waitFor();
    blokNu = uitklap;
    await uitklap.scrollIntoViewIfNeeded();
  });

  assert.deepEqual(errors, []);
  controleerOnbekend();
  console.log("test-kenmerken: alles in orde");
} finally {
  await browser.close();
}
