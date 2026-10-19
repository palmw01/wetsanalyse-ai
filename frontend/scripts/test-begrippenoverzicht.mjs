/** Browserregressie voor het overzicht Begrippen (spoor D, fase F4) op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-begrippenoverzicht.mjs`.
 *
 * Toetst: het sidebar-item, de filters in de URL én in de query naar de BFF, de status en het
 * werkgebied per rij, en doorklikken naar de kaart in zijn werkgebied.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [], queries = [];
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
    alternatieve_termen: ["tijdvak"] }),
  rij("b2", "Uitstel van betaling", "wg1", "Termijnen", "concept"),
  rij("b3", "Belastingschuldige", "wg2", "Invordering", "vervangen", { vervangen_door: { begrip_id: "b4", naam: "Belastingschuldige (ruim)" } }),
];

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname;
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/begrippen") {
    queries.push(url.search);
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    const status = url.searchParams.getAll("status");
    const wg = url.searchParams.get("werkgebied_id");
    const res = BEGRIPPEN.filter((b) => (!q || b.naam.toLowerCase().includes(q) || b.definitie.toLowerCase().includes(q))
      && (!status.length || status.includes(b.status)) && (!wg || b.werkgebied_id === wg));
    return route.fulfill({ json: { resultaten: res, totaal: res.length, volgende_offset: null } });
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
  assert.equal(await lijst.locator("li").count(), 3);
  assert.equal(await page.getByRole("link", { name: "Begrippen", exact: true }).getAttribute("aria-current"), "page");
  const termijn = lijst.locator("li", { hasText: "Termijn" }).first();
  assert.match(await termijn.innerText(), /Geaccordeerd/);
  assert.match(await termijn.innerText(), /Termijnen · ook: tijdvak/);
  assert.match(await lijst.locator("li", { hasText: "Belastingschuldige" }).innerText(), /Vervangen door Belastingschuldige \(ruim\)/);

  // Zoeken: de term staat in de URL én gaat ongewijzigd naar de BFF.
  await page.getByRole("searchbox", { name: "Zoeken in begrippen" }).fill("termijn");
  await page.waitForURL(/\?q=termijn$/);
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="begrippen-overzicht"] li').length === 1);
  assert.equal(queries.at(-1), "?q=termijn");

  // Status en werkgebied als filter; leeg resultaat zegt dat.
  await page.getByRole("button", { name: "Concept" }).click();
  await page.waitForURL(/status=concept/);
  await page.getByText("Geen begrippen bij deze filters.").waitFor();
  await page.getByRole("searchbox", { name: "Zoeken in begrippen" }).fill("");
  await page.waitForFunction(() => !location.search.includes("q="));
  await page.getByLabel("Werkgebied").selectOption("wg1");
  await page.waitForURL(/werkgebied=wg1/);
  await lijst.waitFor();
  assert.match(queries.at(-1), /status=concept/);
  assert.match(queries.at(-1), /werkgebied_id=wg1/);
  assert.equal(await lijst.locator("li").count(), 1);

  // Na herladen staan de filters er nog.
  await page.reload();
  await lijst.waitFor();
  assert.equal(await page.getByRole("button", { name: "Concept" }).getAttribute("aria-pressed"), "true");
  assert.equal(await page.getByLabel("Werkgebied").inputValue(), "wg1");

  // Doorklikken opent de kaart in zijn werkgebied.
  await lijst.getByRole("link", { name: /Uitstel van betaling/ }).click();
  await page.waitForURL(/\/werkgebieden\/wg1\?tab=begrippen&begrip=b2$/);

  assert.deepEqual(errors, []);
  console.log("OK test-begrippenoverzicht");
} finally {
  await browser.close();
}
