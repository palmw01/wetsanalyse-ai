/** Browserregressie voor begrippen in de graaf en de NL-SBB-export (spoor D, fase F3) op de echte Next-UI
 * met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-begrippengraaf.mjs`.
 *
 * Bewaakt:
 *  - op de tab Samenhang staan de begrippen van het werkgebied als knopen (`GET …/begrippen/samenhang`),
 *    met hun dragende passage en hun relaties als zin, voorstel en akkoord apart;
 *  - de laag Begrippen staat in het lagenpaneel en verbergt ze;
 *  - *Open de begripskaart* gaat naar de tab Begrippen op dat begrip, en de kaart zegt of het begrip
 *    NL-SBB-conform is (diagnostisch, accorderen blijft zoals de poort zegt);
 *  - de export biedt Turtle (geaccordeerd) en Turtle met alle begrippen.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
const page = await context.newPage();
const errors = [], requests = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-16T10:00:00+00:00";
const IRI9 = "urn:bwb:BWBR0004770:artikel9", LID1 = `${IRI9}:lid1`;
const wg = { id: "wg1", naam: "Termijnen", analysevraag: "", afbakening: "", peildatum: null, status: "actief", revisie: 2,
  aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null,
  bronnen: [{ id: "s1", bron_iri: IRI9, bereik: "onderliggend", rol: "analyseren", reden: "", label: "Invorderingswet 1990 – artikel 9",
    bwb_id: "BWBR0004770", snapshot_id: "snap", bron_hash: "", toegevoegd_door: "t", toegevoegd: nu, verwijderd: null }] };
const knoop = (id, soort, label, over = {}) => ({ id, soort, label, tekst: "", klasse: "", lifecycle: "", element_id: "",
  bwb_id: "BWBR0004770", artikel: "", lid: "", rand: false, ...over });
const samenhang = () => ({
  schema_versie: 1, doel: { bron_iri: IRI9 }, snapshot_id: "snap", artikel_iri: IRI9, verwijzingen_beschikbaar: true, afgekapt: false,
  knopen: [knoop("urn:bwb:BWBR0004770", "regeling", "Invorderingswet 1990"), knoop(IRI9, "artikel", "Artikel 9", { artikel: "9" }),
    knoop(LID1, "lid", "Lid 1", { artikel: "9", lid: "1" }),
    knoop("element:e1", "markering", "belastingaanslag", { klasse: "Rechtsbetrekking", lifecycle: "human_approved", element_id: "e1", bwb_id: "" })],
  relaties: [{ bron: "urn:bwb:BWBR0004770", doel: IRI9, soort: "bevat", groep: "structuur", anker_tekst: "" },
    { bron: IRI9, doel: LID1, soort: "bevat", groep: "structuur", anker_tekst: "" },
    { bron: "element:e1", doel: LID1, soort: "markeert", groep: "annotaties", anker_tekst: "" },
    { bron: "element:e1", doel: "klasse:Rechtsbetrekking", soort: "heeft_klasse", groep: "annotaties", anker_tekst: "" }],
});
const relatie = (id, van, naar, type, beoordeling, herkomst) => ({ id, van_begrip: van, naar_begrip: naar, van_naam: "", naar_naam: "",
  type, herkomst, beoordeling, toelichting: "", bewijs: {} });
const begripSamenhang = {
  begrippen: [{ id: "b1", iri: "urn:wa:begrip:b1", naam: "belastingaanslag", status: "geaccordeerd", definitie: "De aanslag die de inspecteur vaststelt." },
    { id: "b2", iri: "urn:wa:begrip:b2", naam: "navorderingsaanslag", status: "concept", definitie: "" }],
  koppelingen: [{ begrip_id: "b1", element_id: "e1", rol: "duiding", beoordeling: "akkoord", actualiteit: "actueel" }],
  relaties: [relatie("r1", "b1", "b2", "hierarchie", "akkoord", "analist")],
  voorstellen: [relatie("R2", "b2", "b1", "kwalificatie", "voorgesteld", "lex")],
};
const LEEG = { naam: "", alternatieve_termen: [], context: "", jas_klasse: "", jas_subtype: "", geldigheid: "", definitie: "",
  definitie_herkomst: null, definitie_door: "", uitleg: "", onderbouwing: "", voorbeelden: [], eigenschappen: {}, open_vragen: [] };
const begrip = (id, naam, status, definitie) => ({ id, iri: `urn:wa:begrip:${id}`, werkgebied_id: "wg1", kader_iri: "urn:wa:kader:wg1",
  status, revisie: 3, inhoud: { ...LEEG, naam, definitie, definitie_herkomst: definitie ? "letterlijk" : null },
  aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, geaccordeerd_door: status === "geaccordeerd" ? "jurist-a" : null,
  geaccordeerd_op: status === "geaccordeerd" ? nu : null, geaccordeerd_revisie: null, koppelingen: [],
  accorderen: { mag: false, redenen: ["De context ontbreekt."] }, aandachtspunten: [], vervangen_door: null, vervangt: [] });
const begrippen = { b1: begrip("b1", "belastingaanslag", "geaccordeerd", "De aanslag die de inspecteur vaststelt."),
  b2: begrip("b2", "navorderingsaanslag", "concept", "") };
const DEF = "http://www.w3.org/2004/02/skos/core#definition";
const conformiteit = { beschikbaar: true, nl_sbb_versie: "1.0.0", kader: [], begrippen: {
  b1: { conform: true, meldingen: [{ laag: "nl_sbb", ernst: "waarschuwing", pad: "http://www.w3.org/2004/02/skos/core#example", melding: "Geen voorbeeld." }] },
  b2: { conform: false, meldingen: [{ laag: "nl_sbb", ernst: "fout", pad: DEF, melding: "Less than 1 values on skos:definition" }] } } };

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  requests.push({ p, m, q: url.search });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/annotatie/v2/capabilities") return route.fulfill({ json: { schema_versie: 2, samenhang: true, werkgebieden: true, begrippen: true } });
  if (p === "/api/annotatie/v2/samenhang") return route.fulfill({ json: samenhang() });
  if (p === "/api/annotatie/v2/samenhang/meer") return route.fulfill({ json: { resultaten: [samenhang()], fouten: [] } });
  if (p === "/api/werkgebieden/wg1/begrippen/samenhang") return route.fulfill({ json: begripSamenhang });
  if (p === "/api/werkgebieden/wg1/begrippen/conformiteit") return route.fulfill({ json: conformiteit });
  if (p === "/api/werkgebieden/wg1/begrippen/export")
    return route.fulfill({ body: "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n", headers: {
      "Content-Type": "text/turtle; charset=utf-8", "Content-Disposition": 'attachment; filename="begrippen.ttl"' } });
  if (p === "/api/werkgebieden/wg1/begrippen" && m === "GET")
    return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", primair: {},
      begrippen: Object.values(begrippen).map((b) => { const { koppelingen, ...r } = b; return { ...r, aantal_koppelingen: 0, element_ids: [] }; }) } });
  const bm = p.match(/^\/api\/werkgebieden\/wg1\/begrippen\/(b\d)(?:\/(.+))?$/);
  if (bm) {
    const rest = bm[2] ?? "";
    if (!rest) return route.fulfill({ json: begrippen[bm[1]] });
    if (rest === "revisies") return route.fulfill({ json: { revisies: [] } });
    if (rest === "voorstellen") return route.fulfill({ json: { voorstellen: [], runs: {}, schatting: {}, budget: null } });
  }
  if (p === "/api/werkgebieden/wg1/relaties") return route.fulfill({ json: { relaties: [], voorstellen: [] } });
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: { run: null, groepen: [], passages: {} } });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run: null } });
  if (p === "/api/werkgebieden/wg1/verdieping")
    return route.fulfill({ json: { run: null, aantal: 0, vragen: [], kaarten: [], batches: [], verdiept: false, schatting: null, budget: null } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ status: 404, json: { detail: "Niet in deze test." } });
});

const zijbalk = () => page.getByTestId("graaf-zijbalk");
try {
  await page.goto(`${base}/werkgebieden/wg1?tab=samenhang`);
  await page.locator('[data-testid="samenhang-graaf"][data-gereed="true"]').waitFor({ timeout: 30000 });

  // Een begrip staat als knoop in de graaf, te vinden met zoeken; de inspector noemt status en definitie.
  const zoek = page.getByRole("combobox", { name: "Zoek in de graaf" });
  await zoek.fill("belastingaanslag");
  await page.locator('[role="option"][data-knoop-id="begrip:b1"]').click();
  await zijbalk().getByTestId("graaf-begrip").getByText("Geaccordeerd · een analyse-uitkomst", { exact: false }).waitFor();
  await zijbalk().getByText("De aanslag die de inspecteur vaststelt.").waitFor();
  // Zijn passage en zijn relaties, als zin; voorstel en akkoord apart.
  await zijbalk().getByText("Dragende passages").waitFor();
  await zijbalk().getByText("“duidt het begrip aan”").waitFor();
  await zijbalk().getByText("Relaties met begrippen").waitFor();
  await zijbalk().getByText("“navorderingsaanslag is een soort belastingaanslag”").waitFor();
  await zijbalk().getByText("Voorgestelde relaties").waitFor();
  await zijbalk().getByText("“voorstel van Lex: navorderingsaanslag geldt als belastingaanslag”").waitFor();
  // Geen "Vraag Lex" op een begrip (dat is een vraag over wettekst).
  assert.equal(await zijbalk().getByRole("button", { name: "Vraag Lex" }).count(), 0);

  // De laag Begrippen: staat er, en verbergt de begrippen (de zoeklijst zegt het).
  await page.getByRole("button", { name: /^Lagen/ }).click();
  const laag = page.getByRole("checkbox", { name: /Begrippen/ });
  assert.equal(await laag.isChecked(), true);
  await page.getByTestId("graaf-legenda").getByText("Relatie voorgesteld door Lex").waitFor();
  await laag.uncheck();
  await zoek.fill("navorderingsaanslag");
  await page.locator('[role="option"][data-knoop-id="begrip:b2"]').getByText("laag staat uit", { exact: false }).waitFor();
  await page.locator('[role="option"][data-knoop-id="begrip:b2"]').click();
  // Kiezen zet de laag weer aan.
  assert.equal(await laag.isChecked(), true);
  await zijbalk().getByText("Er is nog geen definitie.", { exact: false }).waitFor();

  // Naar de begripskaart: NL-SBB-conform staat erbij, met de meldingen; accorderen volgt de poort.
  await zijbalk().getByRole("button", { name: "Open de begripskaart" }).click();
  await page.waitForURL(/\/begrippen\/wg1\/b2$/);
  const stand = page.getByTestId("nl-sbb-stand");
  await stand.getByText("Niet NL-SBB-conform (profiel 1.0.0): definitie ontbreekt of klopt niet").waitFor();
  await stand.getByText("Meldingen (1)").click();
  await stand.getByText("NL-SBB · fout · definitie", { exact: false }).waitFor();
  // Een ander begrip: zijn eigen pagina.
  await page.goto(`${base}/begrippen/wg1/b1`);
  await page.getByTestId("nl-sbb-stand").getByText("NL-SBB-conform (profiel 1.0.0)").waitFor();

  // De export: Turtle (geaccordeerd) en Turtle met alles.
  await page.goto(`${base}/werkgebieden/wg1/artefacten/begrippen`);
  for (const [label, verwacht] of [["Turtle (NL-SBB)", "?formaat=ttl"], ["Turtle, alle begrippen", "?formaat=ttl&inclusief=alle"]]) {
    await page.getByRole("button", { name: "Exporteren" }).click();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: new RegExp(`^${label.replace(/[()]/g, "\\$&")}`) }).click();
    assert.equal((await download).suggestedFilename(), "begrippen.ttl");
    assert.equal(requests.filter((r) => r.p.endsWith("/begrippen/export")).at(-1).q, verwacht);
  }

  assert.deepEqual(errors, []);
  console.log("Browser OK: begrippen als knopen in de samenhangsgraaf (passage, relatie als zin, voorstel apart), laag Begrippen, naar de begripskaart, NL-SBB-conform met meldingen, Turtle-export geaccordeerd en alles.");
} catch (e) {
  await page.screenshot({ path: "/tmp/test-begrippengraaf.png", fullPage: true }).catch(() => {});
  console.error(e);
  process.exitCode = 1;
} finally {
  await browser.close();
}
