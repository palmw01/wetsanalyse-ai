/** Browserregressie voor de eigen pagina's van een bepaling en een JAS-element (spoor G3). Op de echte
 * Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-detailpaginas.mjs`.
 *
 * Bewaakt:
 *  - de bronpagina toont de letterlijke wettekst met alle markeringen in hun JAS-kleur; een klik op een
 *    markering opent het element; de elementen staan als rijen; de werkgebieden komen uit `?bron_iri=`;
 *  - met `&werkgebied=` gaat het kruimelpad via dat werkgebied, en *Bespreek met Lex* over de bronselectie;
 *  - de elementpagina toont bronvoorkomen en classificatie, en beslist tegen de laagrevisie en bronstand:
 *    accorderen, heropenen, afwijzen met een reden;
 *  - de reviewkaart en de passages linken naar de elementpagina (elders getoetst).
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [], beslissingen = [], requests = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const LID = "urn:bwb:BWBR0004770:artikel:9:lid:1";
const TEKST = "De belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.";
const segment = { bron_iri: LID, parent_iri: "urn:bwb:BWBR0004770:artikel:9", type: "Lid", label: "Artikel 9, lid 1", nummer: "1",
  tekst: TEKST, bron_hash: "h1", volgorde: 1 };
const anker = (tekst) => {
  const start = TEKST.indexOf(tekst);
  return [{ bron_iri: LID, start, eind: start + tekst.length, tekst, bron_hash: "h1" }];
};
const elementen = {
  e1: { id: "e1", eigenaar_iri: LID, laag_id: "l1", klasse: "Rechtsobject", tekst: "De belastingaanslag", toelichting: "Het object van de invordering.",
    ankers: anker("De belastingaanslag"), lifecycle: "voorgesteld", herkomst: "agent", aandacht: "geel", review_uitleg: "Twijfel tussen object en feit.",
    alternatieven: [{ klasse: "Rechtsfeit", motivatie: "" }], beslissingen: [] },
  e2: { id: "e2", eigenaar_iri: LID, laag_id: "l1", klasse: "Tijdsaanduiding", tekst: "zes weken na de dagtekening",
    toelichting: "", ankers: anker("zes weken na de dagtekening"), lifecycle: "human_approved", herkomst: "agent", beslissingen: [] },
};
const laag = { id: "l1", bron_iri: LID, revisie: 3, status: "in_review" };
const wg = { id: "wg1", naam: "Invorderbaarheid", status: "in_voorbereiding", revisie: 1, peildatum: null, aangemaakt_door: "t",
  aangemaakt: "2026-10-26T10:00:00Z", gewijzigd: "2026-10-26T10:00:00Z", analysevraag: "Wanneer is een aanslag invorderbaar?",
  afbakening: "", aanleiding: "", context: "", doel: "", praktijkvoorbeeld: "", deelvragen: [],
  bronnen: [{ id: "s1", bron_iri: LID, rol: "analyseren", bereik: "onderliggend", reden: "", label: "Artikel 9, lid 1", bwb_id: "BWBR0004770",
    toegevoegd_door: "t", toegevoegd: "", snapshot_id: "", bron_hash: "" }] };

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  requests.push({ p, q: url.search, m });
  const el = p.match(/^\/api\/annotatie\/v2\/elementen\/(e\d)$/);
  if (el) return route.fulfill({ json: { status: "ok", element: elementen[el[1]], laag, snapshot_id: "snap-1", bronnen: [segment] } });
  const besl = p.match(/^\/api\/annotatie\/v2\/elementen\/(e\d)\/beslissing$/);
  if (besl) {
    const body = req.postDataJSON();
    beslissingen.push({ id: besl[1], ...body });
    const e = elementen[besl[1]];
    e.lifecycle = body.type === "approve" ? "human_approved" : body.type === "reject" ? "rejected" : "voorgesteld";
    e.beslissingen.push({ type: body.type, actor: "browser-test", tijd: "2026-10-26T11:00:00Z", review_reason: body.review_reason ?? null, comment: "", wijziging: {} });
    laag.revisie += 1;
    return route.fulfill({ json: { status: "ok" } });
  }
  if (p === "/api/annotatie/v2/weergave")
    return route.fulfill({ json: { schema_versie: 2, doel: { bron_iri: LID, label: "Artikel 9, lid 1", bwb_id: "BWBR0004770" }, snapshot_id: "snap-1",
      segmenten: [segment], lagen: [laag], elementen: Object.values(elementen), verwijzingen: [], dekking: {} } });
  if (p === "/api/annotatie/v2/knoop")
    return route.fulfill({ json: { schema_versie: 1, bron_iri: LID, beschikbaar: true, groepen: [],
      ruw: [{ predicaat: "urn:bwb-ns:label", waarde: "Artikel 9, lid 1" }], verwijzingen: [] } });
  if (p === "/api/annotatie/v2/verklaringen") return route.fulfill({ json: {} });
  if (p === "/api/werkgebieden") return route.fulfill({ json: { werkgebieden: url.searchParams.get("bron_iri") === LID ? [wg] : [] } });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ json: [] });
});

try {
  // --- De bronpagina ---
  await page.goto(`${base}/bronnen?bron_iri=${encodeURIComponent(LID)}`);
  const bron = page.locator(`[data-bron-pagina="${LID}"]`);
  await bron.waitFor();
  await bron.getByRole("heading", { name: "Artikel 9, lid 1", level: 1 }).waitFor();
  // De wettekst letterlijk, met beide markeringen in de tekst.
  assert.equal(await bron.locator("[data-testid=graaf-knooptekst] mark").count(), 2);
  assert.ok((await bron.locator("[data-testid=graaf-knooptekst]").textContent()).includes(TEKST));
  await bron.getByText("1 van 2 elementen beoordeeld").waitFor();
  assert.equal(await bron.locator("[data-element-rij]").count(), 2);
  // In welke werkgebieden: de api krijgt de bron-IRI.
  await bron.getByRole("link", { name: /^Invorderbaarheid/ }).waitFor();
  assert.ok(requests.some((r) => r.p === "/api/werkgebieden" && r.q === `?bron_iri=${encodeURIComponent(LID)}`));
  await bron.getByText("Artikel 9, lid 1", { exact: false }).first().waitFor();
  // Zonder werkgebied: kruimelpad via de annotaties, geen *Bespreek met Lex* (er is geen bronselectie).
  assert.equal(await page.locator("[data-paginakop] [data-vraag-lex]").count(), 0);

  // Met het werkgebied als context.
  await page.goto(`${base}/bronnen?bron_iri=${encodeURIComponent(LID)}&werkgebied=wg1`);
  await bron.waitFor();
  const kruimel = page.getByRole("navigation", { name: "Kruimelpad" });
  await kruimel.getByRole("link", { name: "Invorderbaarheid" }).waitFor();
  assert.equal(await kruimel.getByRole("link", { name: "Bronnen" }).getAttribute("href"), "/werkgebieden/wg1/bronnen");
  assert.equal(await page.locator("[data-paginakop] [data-vraag-lex=bron]").getAttribute("href"),
    "/workbench?werkgebied=wg1&vraag=bron%3As1&vraag_label=Artikel+9%2C+lid+1");

  // Een klik op een markering opent het element.
  await bron.locator("[data-testid=graaf-knooptekst] mark[data-element=e1]").click();
  await page.waitForURL("**/annotaties/element/e1");

  // --- De elementpagina ---
  const elp = page.locator("[data-element-pagina=e1]");
  await elp.waitFor();
  await elp.getByText("Keuze voor jou").waitFor();
  assert.equal(await elp.locator("[data-testid=graaf-knooptekst] mark").count(), 1, "alleen dit element in het bronvoorkomen");
  await elp.getByText("Het object van de invordering.").waitFor();
  await elp.getByText("Rechtsfeit").first().waitFor();
  assert.equal(await page.getByRole("navigation", { name: "Kruimelpad" }).getByRole("link", { name: "Artikel 9, lid 1" }).getAttribute("href"),
    `/annotaties/node?bron_iri=${encodeURIComponent(LID)}&element=e1`);

  // Accorderen: tegen de laagrevisie en bronstand.
  await elp.getByRole("button", { name: "Accorderen" }).click();
  await page.getByText("Akkoord vastgelegd.").waitFor();
  assert.deepEqual(beslissingen.at(-1), { id: "e1", type: "approve", snapshot_id: "snap-1", verwachte_revisies: { [LID]: 3 } });
  await page.locator("[data-element-pagina=e1][data-lifecycle=human_approved]").waitFor();
  // Een oordeel vergrendelt: alleen heropenen.
  assert.equal(await elp.getByRole("button", { name: "Accorderen" }).count(), 0);
  await elp.getByRole("button", { name: "Opnieuw ter beoordeling" }).click();
  await page.locator("[data-element-pagina=e1][data-lifecycle=voorgesteld]").waitFor();
  assert.equal(beslissingen.at(-1).type, "heropen");
  // Afwijzen vraagt een reden.
  await elp.getByRole("button", { name: "Afwijzen…" }).click();
  await elp.getByRole("group", { name: "Reden van afwijzen" }).getByRole("button", { name: "verkeerde klasse" }).click();
  await page.locator("[data-element-pagina=e1][data-lifecycle=rejected]").waitFor();
  assert.deepEqual([beslissingen.at(-1).type, beslissingen.at(-1).review_reason], ["reject", "verkeerde_klasse"]);
  assert.equal(await elp.getByRole("list", { name: "Beslissingen" }).getByRole("listitem").count(), 3);

  // Herladen houdt de pagina; Terug gaat naar de bron.
  await page.reload();
  await page.locator("[data-element-pagina=e1]").waitFor();
  await page.goBack();
  await page.waitForURL(/\/bronnen\?bron_iri=/);

  // Smal scherm: geen horizontale scroll.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${base}/annotaties/element/e2`);
  await page.locator("[data-element-pagina=e2]").waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);

  assert.deepEqual(errors, []);
  console.log("Browser OK: bronpagina met de wettekst en alle markeringen, elementen als rijen, werkgebieden op bron-IRI, kruimelpad en Bespreek met Lex via het werkgebied, klik op een markering naar het element; elementpagina met bronvoorkomen en classificatie, accorderen, heropenen en afwijzen met reden tegen revisie en bronstand, herladen, Terug, smal scherm.");
} finally {
  await browser.close();
}
