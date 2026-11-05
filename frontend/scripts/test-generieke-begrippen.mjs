/** Browserregressie voor de generieke begrippen (ADR-006) op de echte Next-UI met een gemockte BFF: het label in het kader,
 * een wijziging bij Te doen, *Klopt nog*, geen bewerken vanuit een werkgebied, *Generiek maken*, een generiek begrip
 * gebruiken, de eigen pagina met passages per werkgebied en de keuze Kader in het overzicht. */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [], posts = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-11-05T10:00:00+00:00";
const wg = { id: "wg1", naam: "Invordering", analysevraag: "", afbakening: "", peildatum: null, status: "actief", revisie: 3,
  aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null, bronnen: [], deelvragen: [] };
const inhoud = (naam, definitie) => ({ naam, alternatieve_termen: [], context: "Toelichting.", definitie, definitie_herkomst: "geformuleerd",
  definitie_door: "analist", uitleg: "", voorbeelden: [] });
const koppeling = (id, wid, tekst) => ({ id, begrip_id: "g1", werkgebied_id: wid, element_id: `e${id}`, rol: "duiding", motivatie: "",
  bewijs: { tekst, klasse: "Rechtssubject", ankers: [], eigenaar_iri: "urn:bwb:BWBR0004770:artikel:9", laag_id: "l", snapshot_id: "s",
    lifecycle: "human_approved", vindplaats: "Artikel 9", element_hash: "h" }, beoordeling: "akkoord", beoordeeld_door: "t", beoordeeld_op: nu,
  toegevoegd_door: "t", toegevoegd: nu, actualiteit: "actueel", lifecycle_nu: "human_approved", annotatie_beoordeeld: true });
const begrip = (id, kader, status, naam, extra = {}) => ({ id, iri: `urn:wa:begrip:${id}`, werkgebied_id: kader === "generiek" ? null : "wg1", kader,
  ontstaan_in: null, kader_iri: "", status, revisie: 4, inhoud: inhoud(naam, `Definitie van ${naam}.`), aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu,
  geaccordeerd_door: "t", geaccordeerd_op: nu, geaccordeerd_revisie: 4, koppelingen: [], accorderen: { mag: true, redenen: [] }, aandachtspunten: [],
  vervangen_door: null, vervangt: [], ...extra });
const g1 = begrip("g1", "generiek", "geaccordeerd", "Belastingschuldige", { koppelingen: [koppeling("k1", "wg1", "de belastingschuldige")] });
let b1 = begrip("b1", "werkgebied", "geaccordeerd", "Uitstel");
let veranderd = true;
const veranderingen = () => veranderd ? [{ begrip_id: "g1", naam: "Belastingschuldige", revisie: 4, status: "geaccordeerd", gezien_revisie: 2,
  velden: ["definitie"], opvolger: null, toen: { definitie: "Oud." }, nu: { definitie: "Nieuw." } }] : [];
const samenvatting = (b) => ({ ...b, koppelingen: undefined, aantal_koppelingen: b.koppelingen.length, element_ids: [] });
const rij = { id: "g2", iri: "urn:wa:begrip:g2", werkgebied_id: null, werkgebied_naam: "", kader: "generiek", gebruikt_in: 2, naam: "Termijn",
  alternatieve_termen: [], status: "geaccordeerd", revisie: 1, definitie: "Een tijdvak.", definitie_herkomst: "geformuleerd", vervangen_door: null,
  aantal_dragend: 2, herbeoordelen: 0, geaccordeerd_op: nu, gewijzigd: nu };

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (m === "POST") posts.push(p);
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/begrippen" && m === "GET")
    return route.fulfill({ json: { kader_iri: "k", primair: {}, begrippen: [samenvatting(g1), samenvatting(b1)] } });
  if (p === "/api/werkgebieden/wg1/herbeoordelingen")
    return route.fulfill({ json: { werkgebied_id: "wg1", begrippen: [], generiek: veranderingen(), volledig: true, open_punten: [] } });
  if (p === "/api/werkgebieden/wg1/begrippen/gebruik/g1/bevestigen") { veranderd = false; return route.fulfill({ json: g1 }); }
  if (p === "/api/werkgebieden/wg1/begrippen/b1/generiek-maken") {
    b1 = { ...b1, kader: "generiek", werkgebied_id: null, revisie: 5 };
    return route.fulfill({ json: b1 });
  }
  if (p === "/api/werkgebieden/wg1/begrippen/gebruik" && m === "POST")
    return route.fulfill({ json: begrip("g2", "generiek", "geaccordeerd", "Termijn") });
  if (p === "/api/werkgebieden/wg1/begrippen/g2") return route.fulfill({ json: begrip("g2", "generiek", "geaccordeerd", "Termijn") });
  if (p === "/api/werkgebieden/wg1/begrippen/g1") return route.fulfill({ json: g1 });
  if (p === "/api/werkgebieden/wg1/begrippen/b1") return route.fulfill({ json: b1 });
  if (/\/begrippen\/\w+\/voorstellen$/.test(p)) return route.fulfill({ json: { voorstellen: [], runs: {}, schatting: {}, budget: null } });
  if (p === "/api/werkgebieden/wg1/relaties") return route.fulfill({ json: { relaties: [], voorstellen: [] } });
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: { run: null, groepen: [], passages: {} } });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run: null } });
  if (p === "/api/begrippen/g1")
    return route.fulfill({ json: { werkgebied: null, begrip: { ...g1, gebruik: [{ werkgebied_id: "wg1", naam: "Invordering", gezien_revisie: 4, passages: 1 }] }, relaties: [] } });
  if (p === "/api/begrippen/conformiteit") return route.fulfill({ json: { beschikbaar: true, nl_sbb_versie: "1", begrippen: {}, kader: [] } });
  if (p === "/api/begrippen") {
    const kader = url.searchParams.get("kader");
    return route.fulfill({ json: { resultaten: kader === "generiek" ? [rij] : [rij, { ...rij, id: "b9", werkgebied_id: "wg1", werkgebied_naam: "Invordering",
      kader: "werkgebied", naam: "Lokaal" }], totaal: kader === "generiek" ? 1 : 2, volgende_offset: null, per_status: { geaccordeerd: 1 } } });
  }
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ status: 404, json: { detail: "Niet in deze test." } });
});

const foto = (naam) => process.env.SCREENSHOT_DIR
  ? page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/${naam}.png`, fullPage: true }) : null;
try {
  // 1. Het kader: het label, en de wijziging bij Te doen.
  await page.goto(`${base}/werkgebieden/wg1/artefacten/begrippen`);
  await page.locator("[data-begrip-rij=g1]").getByText("Generiek").waitFor();
  assert.equal(await page.locator("[data-begrip-rij=b1]").getByText("Generiek").count(), 0);
  await page.locator("[data-herbeoordelen=g1]").getByText("Het generieke begrip veranderde").waitFor();
  await foto("generiek-kader");

  // 2. In het werkgebied: toen en nu, geen bewerken, en *Klopt nog*.
  await page.locator("[data-herbeoordelen=g1] a").click();
  await page.waitForURL(/\/werkgebieden\/wg1\/begrippen\/g1$/);
  const blok = page.locator("[data-generiek-veranderd]");
  await blok.getByText("Toen: Oud.").waitFor();
  assert.equal(await page.getByRole("button", { name: "Betekenis bewerken" }).count(), 0, "niet bewerken vanuit een werkgebied");
  assert.equal(await page.getByRole("link", { name: "Bewerk generiek begrip" }).getAttribute("href"), "/begrippen/g1");
  await foto("generiek-in-werkgebied");
  await blok.getByRole("button", { name: "Klopt nog voor dit werkgebied" }).click();
  await blok.waitFor({ state: "detached" });
  assert.ok(posts.includes("/api/werkgebieden/wg1/begrippen/gebruik/g1/bevestigen"));
  await page.getByRole("button", { name: "Meer voor dit begrip" }).click();
  await page.getByRole("menuitem", { name: "Dit begrip niet meer gebruiken" }).waitFor();
  await page.keyboard.press("Escape");

  // 3. Een geaccordeerd lokaal begrip generiek maken.
  await page.goto(`${base}/werkgebieden/wg1/begrippen/b1`);
  await page.getByRole("button", { name: "Meer voor dit begrip" }).click();
  await page.getByRole("menuitem", { name: "Generiek maken" }).click();
  await page.getByText("Dit begrip is nu generiek.").waitFor();
  assert.ok(posts.includes("/api/werkgebieden/wg1/begrippen/b1/generiek-maken"));

  // 4. Een generiek begrip gebruiken: wat er al is, staat er niet bij.
  await page.goto(`${base}/werkgebieden/wg1/artefacten/begrippen`);
  await page.getByRole("button", { name: "Generiek begrip gebruiken" }).click();
  const venster = page.locator("[data-generiek-gebruiken]");
  await venster.getByRole("button", { name: "Gebruik Termijn" }).click();
  await page.waitForURL(/\/werkgebieden\/wg1\/begrippen\/g2$/);

  // 5. De eigen pagina: wel bewerken, passages per werkgebied, en waar het gebruikt wordt.
  await page.goto(`${base}/begrippen/g1`);
  await page.getByRole("button", { name: "Betekenis bewerken" }).waitFor();
  await page.locator("[data-passages-werkgebied=wg1]").getByText("“de belastingschuldige”").waitFor();
  await page.getByRole("list", { name: "Werkgebieden die dit begrip gebruiken" }).getByText("Invordering").waitFor();
  await foto("generiek-pagina");

  // 6. Het overzicht: de keuze Kader.
  await page.goto(`${base}/begrippen`);
  await page.getByText("Lokaal").first().waitFor();
  await page.getByLabel("Kader").selectOption({ label: "Generiek" });
  await page.waitForURL(/kader=generiek/);
  await page.waitForFunction(() => document.querySelectorAll("[data-begrip-kaart]").length === 1);
  await page.getByText("Generiek · gebruikt in 2 werkgebieden").waitFor();
  assert.equal(await page.locator("[data-begrip-kaart=g2] h3 a").getAttribute("href"), "/begrippen/g2");

  assert.deepEqual(errors, []);
  console.log("OK test-generieke-begrippen");
} catch (e) {
  await foto("generiek-fout");
  console.error(e);
  process.exitCode = 1;
} finally {
  await browser.close();
}
