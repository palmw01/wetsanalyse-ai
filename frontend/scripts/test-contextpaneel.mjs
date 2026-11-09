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

// Wat de graaf verder over de bepaling weet (`GET bepaling`, ADR-008 *Detail bij een antwoord*).
const VP = (iri, label, regeling = "Invorderingswet 1990") => ({ iri, label, jci: "", regeling });
const LEEG = { aantal: 0, volledig: true, items: [] };
const BEPALING = {
  schema_versie: 1, bron_iri: LID, beschikbaar: true, vindplaats: VP(LID, "Artikel 9, lid 2"),
  plaats: [{ soort: "hoofdstuk", nummer: "II", titel: "Invordering in eerste aanleg", iri: "urn:bwb:BWBR0004770:hoofdstuk:II" }],
  status: "goed", inwerking: "2010-07-04", terugwerkend_tot: null, gewijzigd_bij: "Stb.2009-610", geldig_vanaf: "2026-10-01", geldig_tot: null,
  toestand_url: "", verwijst_naar_aantal: 2, verwijst_naar_volledig: true,
  verwijst_naar: [{ van: VP(LID, "Artikel 9, lid 2"), naar: VP("urn:bwb:BWBR0004770:artikel:8", "Artikel 8"), anker: "artikel 8", in_graaf: true, door: "bron" },
    { van: VP(LID, "Artikel 9, lid 2"), naar: VP("urn:bwb:BWBR0005291:artikel:45", "Artikel 45", ""), anker: "Artikel 45 van Boek 3 van het Burgerlijk Wetboek", in_graaf: false, door: "bron" }],
  verwezen_door: { aantal: 14, volledig: true, items: [VP("urn:bwb:BWBR0004770:artikel:56:lid:1", "Artikel 56, lid 1")] },
  grondslag_voor: LEEG, bevoegdheid_voor: { aantal: 2, volledig: true, items: [VP("urn:bwb:BWBR0004772", "Uitvoeringsbesluit Invorderingswet 1990", "Uitvoeringsbesluit Invorderingswet 1990")] },
  genoemd_in: LEEG, definieert: [],
};
let graafWeg = false;

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
  if (p === "/api/annotatie/v2/bepaling") {
    if (graafWeg) return route.fulfill({ json: { ...BEPALING, beschikbaar: false, plaats: [], verwijst_naar: [] } });
    return route.fulfill({ json: url.searchParams.get("bron_iri") === LID ? BEPALING : { ...BEPALING, bron_iri: url.searchParams.get("bron_iri"),
      vindplaats: { iri: url.searchParams.get("bron_iri"), label: "Artikel 56, lid 1", jci: "", regeling: "Invorderingswet 1990" } } });
  }
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
  // De kop noemt de herkomst (het bronvenster, PR 1): de bepaling als titel, regeling · plek · stand · bron eronder.
  await paneel("bron").getByRole("heading", { name: "Artikel 9, lid 2", exact: true }).waitFor();
  const herkomst = paneel("bron").locator("[data-paneel-kop] [data-herkomst]");
  await herkomst.waitFor();
  assert.match(await herkomst.textContent(), /^Invorderingswet 1990 · H II · stand 1 oktober 2026 · wetten\.overheid\.nl$/);

  // Onder de wettekst: wat de graaf verder weet, letterlijk uit het detail, zonder iets erbij te verzinnen.
  const feiten = paneel("bron").locator("[data-bepaling-feiten=gereed]");
  await feiten.waitFor();
  assert.equal((await feiten.locator("[data-feit=plek]").textContent()).trim(), "Invorderingswet 1990 › Hoofdstuk II – Invordering in eerste aanleg");
  await feiten.locator("[data-feit=inwerking]", { hasText: "4 juli 2010" }).waitFor();
  assert.equal(await feiten.locator("[data-feit=verwijst-naar]").count(), 2, "elke verwijzing één keer");
  assert.equal(await feiten.getByRole("button", { name: "Artikel 45" }).count(), 0, "een doel buiten de graaf is geen knop");
  await feiten.getByText("Wordt genoemd in (14)").waitFor();
  await feiten.getByText("en 13 meer").waitFor();
  await feiten.getByText("Bevoegdheid voor (2)").waitFor();
  assert.equal(await feiten.getByText("Grondslag voor").count(), 0, "een lege telling staat er niet");

  // Op een telefoon en in een half venster: geen horizontale scroll in het paneel.
  for (const width of [375, 800, 1280]) {
    await page.setViewportSize({ width, height: 800 });
    const breed = await paneel("bron").evaluate((el) => el.scrollWidth > el.clientWidth + 1);
    assert.ok(!breed, `op ${width}px loopt het paneel niet over`);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });

  // Een verwijzing in de graaf opent in hetzelfde paneel.
  await feiten.getByRole("button", { name: "Artikel 56, lid 1, Invorderingswet 1990" }).click();
  await paneel("bron").locator("[data-feit=plek]").waitFor();
  await page.getByRole("heading", { name: "Artikel 56, lid 1", exact: true }).waitFor();

  // Een haperende graaf zegt dat, en laat de wettekst staan. Een geslaagde lezing blijft per sessie bewaard, dus eerst
  // herladen.
  graafWeg = true;
  await page.reload();
  await page.getByRole("button", { name: "Artikel 9 lid 2", exact: true }).waitFor();
  await page.getByRole("button", { name: "Artikel 9 lid 2", exact: true }).click();
  await page.getByTestId("bronkaart").getByRole("button", { name: "Naast het gesprek" }).click();
  await paneel("bron").locator("[data-bepaling-feiten=niet-beschikbaar]").waitFor();
  await paneel("bron").getByText("invorderbaar op de dagtekening", { exact: false }).waitFor();
  graafWeg = false;

  // Ook in een half venster: chat en paneel staan naast elkaar, allebei leesbaar breed.
  for (const width of [800, 960, 1024, 1280]) {
    await page.setViewportSize({ width, height: 800 });
    const invoer = await page.getByRole("textbox").last().boundingBox();
    const kader = await paneel("bron").boundingBox();
    assert.ok(invoer.x + invoer.width <= kader.x + 1, `op ${width}px ligt het paneel niet over de invoer`);
    assert.ok(invoer.width >= 300 && kader.width >= 320, `op ${width}px zijn beide kolommen bruikbaar`);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });

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
  console.log("Browser OK: bron uit een antwoord naast het gesprek met markeringen en wat de graaf verder weet (plek, geldigheid, verwijzingen, tellingen; haperende graaf gemeld), element in hetzelfde paneel zonder beoordelingsknoppen, Open volledige pagina in het werkgebied, Bronnen in de chatkop, één paneel tegelijk, weg uit de werkplek is het paneel weg.");
} finally {
  await browser.close();
}
