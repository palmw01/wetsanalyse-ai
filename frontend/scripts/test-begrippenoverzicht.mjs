/** Browserregressie voor het overzicht Begrippen (spoor D, fase F4) op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-begrippenoverzicht.mjs`.
 *
 * Toetst: het sidebar-item, de balk zoals bij de annotaties (één statuskeuze met tellers, *Door mij
 * bewerkt*, de werkgebiedkeuze en het zoekveld), de filters in de URL én in de query naar de BFF, kaarten
 * met status en werkgebied, verwijderen per kaart, en doorklikken naar de kaart in zijn werkgebied.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [], queries = [], verwijderd = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-19T10:00:00+00:00";
const rij = (id, naam, wg, wgNaam, status, extra = {}) => ({
  id, iri: `urn:wa:begrip:${id}`, werkgebied_id: wg, werkgebied_naam: wgNaam, naam, alternatieve_termen: [],
  status, revisie: 2, definitie: "", definitie_herkomst: null, vervangen_door: null, aantal_dragend: 1,
  geaccordeerd_op: null, gewijzigd: nu, ...extra,
});
const BEGRIPPEN = [
  rij("b1", "Termijn", "wg1", "Termijnen", "geaccordeerd", { definitie: "Een tijdvak waarbinnen betaald moet worden.",
    alternatieve_termen: ["tijdvak"], herbeoordelen: 1 }),
  rij("b2", "Uitstel van betaling", "wg1", "Termijnen", "concept"),
  rij("b3", "Belastingschuldige", "wg2", "Invordering", "vervangen", { vervangen_door: { begrip_id: "b4", naam: "Belastingschuldige (ruim)" } }),
];

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname;
  if (p.startsWith("/api/auth/")) return route.continue();
  const wis = p.match(/^\/api\/werkgebieden\/(wg\d)\/begrippen\/(b\d)$/);
  if (wis && req.method() === "DELETE") {
    verwijderd.push({ werkgebied: wis[1], begrip: wis[2], q: url.search });
    BEGRIPPEN.splice(BEGRIPPEN.findIndex((b) => b.id === wis[2]), 1);
    return route.fulfill({ json: { verwijderd: wis[2], hersteld: [] } });
  }
  if (p === "/api/begrippen") {
    queries.push(url.search);
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    const status = url.searchParams.getAll("status");
    const wg = url.searchParams.get("werkgebied_id");
    const mijn = url.searchParams.get("mijn") === "true";
    // Zoals de api: dezelfde filters, met de tellers per status zonder het statusfilter.
    const zonderStatus = BEGRIPPEN.filter((b) => (!q || b.naam.toLowerCase().includes(q) || b.definitie.toLowerCase().includes(q))
      && (!wg || b.werkgebied_id === wg) && (!mijn || b.id === "b2"));
    const res = zonderStatus.filter((b) => !status.length || status.includes(b.status));
    const per_status = {};
    for (const b of zonderStatus) per_status[b.status] = (per_status[b.status] ?? 0) + 1;
    return route.fulfill({ json: { resultaten: res, totaal: res.length, volgende_offset: null, per_status } });
  }
  if (p === "/api/werkgebieden") return route.fulfill({ json: { werkgebieden: [
    { id: "wg1", naam: "Termijnen", analysevraag: "", afbakening: "", peildatum: null, status: "in_voorbereiding", revisie: 1,
      aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null, aantal_bronnen: 1 },
    { id: "wg2", naam: "Invordering", analysevraag: "", afbakening: "", peildatum: null, status: "in_voorbereiding", revisie: 1,
      aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null, aantal_bronnen: 1 },
  ] } });
  if (p.startsWith("/api/werkgebieden/")) return route.fulfill({ status: 404, json: { detail: "niet in deze test" } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  return route.fulfill({ json: {} });
});

try {
  // Vanuit de werkgebieden via de sidebar.
  await page.goto(`${base}/werkgebieden`);
  await page.getByRole("link", { name: "Begrippen", exact: true }).click();
  await page.waitForURL(`${base}/begrippen`);
  const lijst = page.getByTestId("begrippen-overzicht");
  await lijst.waitFor();
  assert.equal(await lijst.locator("article").count(), 3);
  assert.equal(await page.getByRole("link", { name: "Begrippen", exact: true }).getAttribute("aria-current"), "page");
  const termijn = lijst.locator("article", { hasText: "Termijn" }).first();
  assert.match(await termijn.innerText(), /Geaccordeerd/);
  assert.match(await termijn.innerText(), /Termijnen · ook: tijdvak/);
  assert.match(await lijst.locator("article", { hasText: "Belastingschuldige" }).innerText(), /Vervangen door Belastingschuldige \(ruim\)/);
  // Geaccordeerd, maar een dragende passage veranderde: het overzicht zegt het.
  assert.match(await lijst.locator("article", { hasText: "Termijn" }).first().innerText(), /Herbeoordelen: 1 dragende passage veranderde/);
  assert.equal(await lijst.locator("[data-herbeoordelen]").count(), 1);

  // Zoeken: de term staat in de URL én gaat ongewijzigd naar de BFF.
  await page.getByRole("searchbox", { name: "Zoeken in begrippen" }).fill("termijn");
  await page.waitForURL(/\?q=termijn$/);
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="begrippen-overzicht"] article').length === 1);
  assert.equal(queries.at(-1), "?q=termijn");

  // Status als één keuze met teller, zoals de andere overzichten; leeg resultaat zegt dat.
  await page.getByRole("button", { name: /^Concept \(0\)$/ }).waitFor();
  await page.getByRole("button", { name: /^Alle \(1\)$/ }).waitFor();
  await page.getByRole("button", { name: /^Concept/ }).click();
  await page.waitForURL(/status=concept/);
  await page.getByText("Geen begrippen bij deze filters.").waitFor();
  await page.getByRole("searchbox", { name: "Zoeken in begrippen" }).fill("");
  await page.waitForFunction(() => !location.search.includes("q="));
  await page.getByLabel("Werkgebied").selectOption("wg1");
  await page.waitForURL(/werkgebied=wg1/);
  await lijst.waitFor();
  assert.match(queries.at(-1), /status=concept/);
  assert.match(queries.at(-1), /werkgebied_id=wg1/);
  assert.equal(await lijst.locator("article").count(), 1);

  // Na herladen staan de filters er nog.
  await page.reload();
  await lijst.waitFor();
  assert.equal(await page.getByRole("button", { name: /^Concept/ }).getAttribute("aria-pressed"), "true");
  assert.equal(await page.getByLabel("Werkgebied").inputValue(), "wg1");

  // Verwijderen per rij, zoals in het paneel en op de kaart: de rij gaat meteen weg. Een vervangen begrip
  // heeft geen knop (verwijder de opvolger).
  await page.goto(`${base}/begrippen`);
  await lijst.waitFor();
  // Door mij bewerkt: in de URL en als `mijn=true` naar de api.
  await page.getByRole("checkbox", { name: "Door mij bewerkt" }).click();
  await page.waitForURL(/mijn=1/);
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="begrippen-overzicht"] article').length === 1);
  assert.match(queries.at(-1), /mijn=true/);
  await page.getByRole("checkbox", { name: "Door mij bewerkt" }).click();
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="begrippen-overzicht"] article').length === 3);
  assert.equal(await lijst.locator("article", { hasText: "Belastingschuldige" }).getByRole("button", { name: "Begrip verwijderen" }).count(), 0);
  const termijnRij = lijst.locator("article", { hasText: "Termijn" }).first();
  await termijnRij.getByRole("button", { name: "Begrip verwijderen" }).click();
  await termijnRij.getByRole("button", { name: "Verwijderen?", exact: true }).click();
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="begrippen-overzicht"] article').length === 2);
  assert.deepEqual(verwijderd, [{ werkgebied: "wg1", begrip: "b1", q: "?verwachte_revisie=2" }]);
  await page.goto(`${base}/begrippen?status=concept&werkgebied=wg1`);
  await lijst.waitFor();

  // Doorklikken opent de kaart in zijn werkgebied.
  await lijst.getByRole("link", { name: /Uitstel van betaling/ }).click();
  await page.waitForURL(/\/begrippen\/wg1\/b2$/);

  assert.deepEqual(errors, []);
  console.log("OK test-begrippenoverzicht");
} finally {
  await browser.close();
}
