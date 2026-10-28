/** Browserregressie voor het contextpaneel naast het gesprek (spoor G4). Op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-contextpaneel.mjs`.
 *
 * Bewaakt:
 *  - de bronkaart van een citatie biedt *Naast het gesprek*: de bepaling opent rechts, met haar wettekst en
 *    markeringen; *Open volledige pagina* gaat naar de bronpagina in het werkgebied van het gesprek;
 *  - een markering of elementrij opent het element in hetzelfde paneel, met *Open volledige pagina*;
 *  - *Bronnen* in de chatkop toont de bronnen van het werkgebied; een klik opent er één;
 *  - er staat hoogstens één paneel open: een artefactchip vervangt de context;
 *  - het paneel is om te raadplegen: geen beoordelingsknoppen;
 *  - weg uit de werkplek is het paneel weg.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const LID = "urn:bwb:BWBR0004770:artikel:9:lid:2";
const TEKST = "In afwijking van het eerste lid is de aanslag invorderbaar op de dagtekening.";
const segment = { bron_iri: LID, parent_iri: "urn:bwb:BWBR0004770:artikel:9", type: "Lid", label: "Artikel 9, lid 2", nummer: "2",
  tekst: TEKST, bron_hash: "h1", volgorde: 1 };
const start = TEKST.indexOf("de aanslag");
const element = { id: "e1", eigenaar_iri: LID, laag_id: "l1", klasse: "Rechtsobject", tekst: "de aanslag", toelichting: "Wat invorderbaar wordt.",
  ankers: [{ bron_iri: LID, start, eind: start + "de aanslag".length, tekst: "de aanslag", bron_hash: "h1" }],
  lifecycle: "voorgesteld", herkomst: "agent", beslissingen: [] };
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const berichten = [
  { rol: "user", tekst: "Wat regelt artikel 9 lid 2?", ...leeg },
  { rol: "assistant", tekst: "Artikel 9 lid 2 wijkt af van het eerste lid.", ...leeg,
    bronnen: [{ label: "Invorderingswet 1990, artikel 9 lid 2", uri: "jci1.3:c:BWBR0004770&artikel=9&lid=2" }] },
  { rol: "assistant", tekst: "Het werkgebied staat er.", ...leeg, run_id: "w1",
    artefact: { soort: "werkgebied", ref: { werkgebied_id: "wg1" }, titel: "Invorderbaarheid" } },
];
const wg = { id: "wg1", naam: "Invorderbaarheid", status: "in_voorbereiding", revisie: 1, peildatum: null, aangemaakt_door: "t",
  aangemaakt: "2026-10-26T10:00:00Z", gewijzigd: "2026-10-26T10:00:00Z", analysevraag: "Wanneer?", afbakening: "", aanleiding: "",
  context: "", doel: "", praktijkvoorbeeld: "", deelvragen: [],
  bronnen: [{ id: "s1", bron_iri: LID, rol: "analyseren", bereik: "onderliggend", reden: "De afwijking", label: "Artikel 9, lid 2",
    bwb_id: "BWBR0004770", toegevoegd_door: "t", toegevoegd: "", snapshot_id: "", bron_hash: "" }] };

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", titel: "Invordering", werkgebied_id: "wg1", berichten } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Invordering", aantal_berichten: 3, werkgebied_id: "wg1", werkgebied_naam: "Invorderbaarheid" }] });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/annotatie/run") return route.fulfill({ json: m === "GET" ? null : {} });
  if (p === "/api/annotatie/v2/samenhang")
    return route.fulfill({ json: { knopen: [{ id: LID, soort: "lid", label: "Lid 2", tekst: TEKST }], relaties: [] } });
  if (p === "/api/annotatie/v2/weergave")
    return route.fulfill({ json: { schema_versie: 2, doel: { bron_iri: LID, label: "Artikel 9, lid 2", bwb_id: "BWBR0004770" }, snapshot_id: "snap-1",
      segmenten: [segment], lagen: [{ id: "l1", bron_iri: LID, revisie: 1, status: "in_review" }], elementen: [element], verwijzingen: [], dekking: {} } });
  if (p === "/api/annotatie/v2/elementen/e1")
    return route.fulfill({ json: { status: "ok", element, laag: { id: "l1", bron_iri: LID, revisie: 1, status: "in_review" }, snapshot_id: "snap-1", bronnen: [segment] } });
  if (p === "/api/annotatie/v2/verklaringen") return route.fulfill({ json: {} });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ json: [] });
});

const paneel = (soort) => page.locator(`[data-context-paneel=${soort}]`);

try {
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.locator("[data-chatkop][data-werkgebied=wg1]").waitFor();

  // --- Een bron uit het antwoord, naast het gesprek ---
  await page.getByRole("button", { name: "Artikel 9 lid 2", exact: true }).click();
  await page.getByTestId("bronkaart").getByRole("button", { name: "Naast het gesprek" }).click();
  await paneel("bron").waitFor();
  await paneel("bron").getByText("invorderbaar op de dagtekening", { exact: false }).waitFor();
  assert.equal(await paneel("bron").locator("mark[data-element=e1]").count(), 1, "de markering staat in de tekst");
  assert.equal(await paneel("bron").getByRole("link", { name: "Open volledige pagina" }).getAttribute("href"),
    `/bronnen?bron_iri=${encodeURIComponent(LID)}&werkgebied=wg1`, "de pagina in het werkgebied van het gesprek");
  // De chat blijft bruikbaar ernaast.
  assert.ok(await page.getByRole("textbox").last().isVisible());

  // --- Een markering opent het element in hetzelfde paneel; geen beoordelingsknoppen ---
  await paneel("bron").locator("mark[data-element=e1]").click();
  await paneel("element").waitFor();
  await paneel("element").getByText("Wat invorderbaar wordt.").waitFor();
  assert.equal(await paneel("element").getByRole("link", { name: "Open volledige pagina" }).getAttribute("href"), "/annotaties/element/e1");
  assert.equal(await paneel("element").getByRole("button", { name: /Accorderen|Afwijzen/ }).count(), 0, "het paneel is om te raadplegen");

  // --- Bronnen in de chatkop: de bronnen van het werkgebied ---
  await page.locator("[data-chatkop-bronnen]").click();
  await paneel("bibliotheek").waitFor();
  await paneel("bibliotheek").getByText("De afwijking").waitFor();
  assert.equal(await paneel("bibliotheek").getByRole("link", { name: "Open volledige pagina" }).getAttribute("href"), "/werkgebieden/wg1/bronnen");
  await paneel("bibliotheek").locator("[data-context-bron=s1]").click();
  await paneel("bron").waitFor();
  await paneel("bron").locator("[data-context-element=e1]").click();
  await paneel("element").waitFor();

  // --- Hoogstens één paneel: een artefactchip vervangt de context ---
  await page.locator('button[data-artefact-soort="werkgebied"]').click();
  await page.locator("[data-artefact-soort=werkgebied][data-artefact]").waitFor();
  assert.equal(await page.locator("[data-context-paneel]").count(), 0);
  // Het artefactpaneel heeft dezelfde ingang naar de pagina.
  await page.locator("[data-artefact]").getByRole("link", { name: "Open volledige pagina" }).waitFor();

  // --- Weg uit de werkplek: geen paneel ---
  await page.locator("[data-chatkop-bronnen]").click();
  await paneel("bibliotheek").waitFor();
  await paneel("bibliotheek").getByRole("link", { name: "Open volledige pagina" }).click();
  await page.waitForURL("**/werkgebieden/wg1/bronnen");
  assert.equal(await page.locator("[data-context-paneel]").count(), 0);

  assert.deepEqual(errors, []);
  console.log("Browser OK: bron uit een antwoord naast het gesprek met markeringen, element in hetzelfde paneel zonder beoordelingsknoppen, Open volledige pagina in het werkgebied, Bronnen in de chatkop, één paneel tegelijk, weg uit de werkplek is het paneel weg.");
} finally {
  await browser.close();
}
