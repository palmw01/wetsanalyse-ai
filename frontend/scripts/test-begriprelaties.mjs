/** Browserregressie voor begripsrelaties en opvolging (spoor D, fase F2) op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-begriprelaties.mjs`.
 *
 * De mock gedraagt zich als de api (`api/app/begrip_relatie_store.py`): voorstellen van Lex, vastleggen,
 * afwijzen (komt niet terug), nieuwe betekenis (oud → vervangen, opvolger met de kaart) en combineren.
 *
 * Bewaakt:
 *  - een voorstel van Lex staat als zin met zijn passages; akkoord met het toetsenbord legt het vast;
 *  - zelf een relatie toevoegen in de juiste richting ("is een soort": het andere begrip is `van`), en
 *    "verwant" alleen met een toelichting;
 *  - afwijzen vraagt een reden en het voorstel verdwijnt;
 *  - nieuwe betekenis: de opvolger opent, "Vervangt …", het oude staat ingeklapt onder Vervangen en is
 *    alleen-lezen (geen Lex naast de kaart);
 *  - combineren met een vergelijking vooraf; de keuze welk begrip blijft bepaalt de route.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [], requests = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-16T10:00:00+00:00";
const wg = { id: "wg1", naam: "Termijnen", analysevraag: "", afbakening: "", peildatum: null, status: "actief", revisie: 2,
  aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null, bronnen: [] };
const LEEG = { naam: "", alternatieve_termen: [], context: "", jas_klasse: "", jas_subtype: "", geldigheid: "", definitie: "",
  definitie_herkomst: null, definitie_door: "", uitleg: "", onderbouwing: "", voorbeelden: [], eigenschappen: {}, open_vragen: [] };
const begrip = (id, naam, status = "concept", definitie = "") => ({ id, status, revisie: 1, inhoud: { ...LEEG, naam, definitie },
  koppelingen: [], vervangen_door: null, vervangt: [] });
const begrippen = {
  b1: begrip("b1", "belastingaanslag", "geaccordeerd", "de aanslag die de inspecteur vaststelt"),
  b2: begrip("b2", "navorderingsaanslag", "concept", "een aanslag achteraf"),
  b3: begrip("b3", "aanslag", "concept", "een beschikking over verschuldigde belasting"),
};
const uit = (b) => ({ ...b, iri: `urn:wa:begrip:${b.id}`, werkgebied_id: "wg1", kader_iri: "urn:wa:kader:wg1", aangemaakt_door: "t",
  aangemaakt: nu, gewijzigd: nu, geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
  accorderen: { mag: false, redenen: ["De context ontbreekt."] }, aandachtspunten: [] });

const passage = (tekst) => ({ element_id: `e-${tekst}`, tekst, vindplaats: "Artikel 2 · Lid 1", jas_klasse: "", review_status: "", bron_iri: "" });
let voorstellen = [
  { id: "R1", van_begrip: "b1", naar_begrip: "b2", van_naam: "belastingaanslag", naar_naam: "navorderingsaanslag", type: "inclusie",
    herkomst: "lex", beoordeling: "voorgesteld", toelichting: "",
    bewijs: { aandacht: "geel", uitleg: ["onder X wordt mede verstaan Y"], van: passage("belastingaanslag"), naar: passage("navorderingsaanslag") } },
  { id: "R2", van_begrip: "b1", naar_begrip: "b3", van_naam: "belastingaanslag", naar_naam: "aanslag", type: "kwalificatie",
    herkomst: "lex", beoordeling: "voorgesteld", toelichting: "", bewijs: { aandacht: "geel", uitleg: [] } },
];
const relaties = [];
let teller = 0;
const naam = (id) => begrippen[id].inhoud.naam;
const rel = (van, naar, type, herkomst, toelichting = "", beoordeling = "akkoord") =>
  ({ id: `r${++teller}`, van_begrip: van, naar_begrip: naar, van_naam: naam(van), naar_naam: naam(naar), type, herkomst,
    beoordeling, toelichting, bewijs: {}, door: "browser-test", op: nu, veranderd: false });
const relatieStand = (bid) => {
  const raakt = (x) => !bid || x.van_begrip === bid || x.naar_begrip === bid;
  return { relaties: relaties.filter(raakt), voorstellen: voorstellen.filter(raakt) };
};
function vervang(oud, nieuw, reden) {
  begrippen[oud].status = "vervangen";
  begrippen[oud].revisie += 1;
  begrippen[oud].vervangen_door = { begrip_id: nieuw, naam: naam(nieuw), reden };
  begrippen[nieuw].vervangt = [...begrippen[nieuw].vervangt, { begrip_id: oud, naam: naam(oud), reden }];
  relaties.push(rel(oud, nieuw, "opvolging", "systeem", reden));
}

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" || m === "DELETE" ? null : req.postDataJSON();
  requests.push({ p, m, body });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/begrippen" && m === "GET")
    return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", primair: {},
      begrippen: Object.values(begrippen).map((b) => { const { koppelingen, ...r } = uit(b);
        return { ...r, aantal_koppelingen: koppelingen.length, element_ids: [] }; }) } });
  if (p === "/api/werkgebieden/wg1/relaties" && m === "GET") return route.fulfill({ json: relatieStand(url.searchParams.get("begrip_id")) });
  if (p === "/api/werkgebieden/wg1/relaties" && m === "POST") {
    if (body.voorstel_id) {
      const v = voorstellen.find((x) => x.id === body.voorstel_id);
      voorstellen = voorstellen.filter((x) => x !== v);
      relaties.push(rel(v.van_begrip, v.naar_begrip, v.type, "lex"));
    } else {
      if (body.type === "verwant" && !body.toelichting) return route.fulfill({ status: 422, json: { detail: "toelichting" } });
      relaties.push(rel(body.van_begrip, body.naar_begrip, body.type, "analist", body.toelichting ?? ""));
    }
    return route.fulfill({ status: 201, json: relatieStand() });
  }
  const af = p.match(/^\/api\/werkgebieden\/wg1\/relaties\/voorstellen\/(R\d)\/afwijzen$/);
  if (af) {
    const v = voorstellen.find((x) => x.id === af[1]);
    voorstellen = voorstellen.filter((x) => x !== v);
    relaties.push({ ...rel(v.van_begrip, v.naar_begrip, v.type, "lex", body.reden, "afgewezen") });
    return route.fulfill({ json: relatieStand() });
  }
  const bm = p.match(/^\/api\/werkgebieden\/wg1\/begrippen\/(b\d)(?:\/(.+))?$/);
  if (bm) {
    const b = begrippen[bm[1]], rest = bm[2] ?? "";
    if (!rest && m === "GET") return route.fulfill({ json: uit(b) });
    if (rest === "revisies") return route.fulfill({ json: { revisies: [] } });
    if (rest === "voorstellen") return route.fulfill({ json: { voorstellen: [], runs: {}, schatting: {}, budget: null } });
    if (rest === "nieuwe-betekenis") {
      const id = "b4";
      begrippen[id] = { ...begrip(id, b.inhoud.naam), inhoud: { ...b.inhoud } };
      vervang(b.id, id, body.reden);
      return route.fulfill({ status: 201, json: uit(begrippen[id]) });
    }
    if (rest === "combineren") {
      const ander = begrippen[body.ander_begrip_id];
      if (body.verwachte_revisie !== b.revisie || body.ander_revisie !== ander.revisie)
        return route.fulfill({ status: 412, json: { detail: { fout: "revisie_conflict", revisie: b.revisie } } });
      b.inhoud.alternatieve_termen = [...b.inhoud.alternatieve_termen, ander.inhoud.naam];
      b.revisie += 1;
      vervang(ander.id, b.id, body.reden);
      return route.fulfill({ json: uit(b) });
    }
  }
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: { run: null, groepen: [], passages: {} } });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run: null } });
  if (p === "/api/werkgebieden/wg1/verdieping")
    return route.fulfill({ json: { run: null, aantal: 0, vragen: [], kaarten: [], batches: [], verdiept: false, schatting: null, budget: null } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ status: 404, json: { detail: "Niet in deze test." } });
});

const sectie = () => page.getByRole("region", { name: "Relaties en opvolging" });
const zie = (tekst) => sectie().getByText(tekst, { exact: false }).first().waitFor();
try {
  await page.goto(`${base}/werkgebieden/wg1?tab=begrippen&begrip=b1&weergave=kaart`);
  const voorgesteld = sectie().getByRole("list", { name: "Voorgestelde relaties" });
  await voorgesteld.getByText("voorgesteld door Lex · inclusie").waitFor();
  await voorgesteld.getByText("onder X wordt mede verstaan Y", { exact: false }).waitFor();

  // 1. Akkoord met het toetsenbord.
  await voorgesteld.getByRole("button", { name: "Leg vast: belastingaanslag omvat ook navorderingsaanslag" }).focus();
  await page.keyboard.press("Enter");
  await zie("Relatie vastgelegd.");
  const vast = sectie().getByRole("list", { name: "Vastgelegde relaties" });
  await vast.getByText("inclusie · voorgesteld door Lex", { exact: false }).waitFor();

  // 2. Afwijzen vraagt een reden; het voorstel verdwijnt.
  await voorgesteld.getByRole("button", { name: "Wijs af: belastingaanslag geldt als aanslag" }).click();
  const reden = sectie().getByLabel("Reden om “belastingaanslag geldt als aanslag” af te wijzen");
  await reden.fill("Geen fictie.");
  await page.keyboard.press("Enter");
  await zie("Voorstel afgewezen");
  assert.equal(await voorgesteld.count(), 0);
  await sectie().getByText("Afgewezen voorstellen (1)").waitFor();

  // 3. Zelf: "is een soort" zet het andere begrip links (van); verwant alleen met toelichting.
  const form = sectie().getByRole("form", { name: "Relatie toevoegen" });
  await form.getByLabel("Soort relatie").selectOption("verwant");
  await form.getByLabel("Ander begrip").selectOption("b3");
  assert.equal(await form.getByRole("button", { name: "Vastleggen" }).isDisabled(), true);
  await form.getByLabel("Soort relatie").selectOption("soort-van");
  await form.getByRole("button", { name: "Vastleggen" }).click();
  await zie("Relatie vastgelegd.");
  const post = requests.filter((r) => r.p.endsWith("/relaties") && r.m === "POST").at(-1);
  assert.deepEqual(post.body, { van_begrip: "b3", naar_begrip: "b1", type: "hierarchie" });
  await vast.getByText("soort van · door de analist", { exact: false }).waitFor();
  assert.equal((await vast.getByRole("listitem").nth(1).textContent()).startsWith("belastingaanslag is een soort aanslag"), true);

  // 4. Nieuwe betekenis: de opvolger opent, het oude is vervangen en alleen-lezen.
  await sectie().getByRole("button", { name: "Nieuwe betekenis" }).click();
  await sectie().getByLabel("Reden voor de nieuwe betekenis").fill("Ruimer na de wetswijziging.");
  await sectie().getByRole("button", { name: "Maak opvolger" }).click();
  await page.waitForURL(/(begrip=|\/begrippen\/wg1\/)b4/);
  await zie("Vervangt");
  await sectie().getByRole("button", { name: "belastingaanslag" }).waitFor();
  // Het vervangen begrip staat in het begrippenkader, ingeklapt; zijn kaart is zijn eigen pagina.
  await page.goto(`${base}/werkgebieden/wg1/artefacten/begrippen`);
  await page.getByText("Vervangen (1)").click();
  await page.getByRole("list", { name: "Vervangen begrippen" }).getByRole("button").click();
  await page.waitForURL(/begrip=b1/);
  await page.getByRole("button", { name: "Begripskaart" }).click();
  await page.waitForURL(/\/begrippen\/wg1\/b1$/);
  await zie("Dit begrip is alleen nog te lezen.");
  assert.equal(await page.locator("[data-begrip-lex]").count(), 0);
  assert.equal(await sectie().getByRole("button", { name: "Nieuwe betekenis" }).count(), 0);

  // 5. Combineren met een vergelijking vooraf; "aanslag blijft" combineert op b3.
  await page.goto(`${base}/werkgebieden/wg1?tab=begrippen&begrip=b2&weergave=kaart`);
  await sectie().getByRole("button", { name: "Combineren met…" }).click();
  const comb = sectie().getByRole("form", { name: "Combineren" });
  await comb.getByLabel("Combineren met").selectOption("b3");
  await comb.getByText("een beschikking over verschuldigde belasting").waitFor();
  await comb.getByText("een aanslag achteraf").waitFor();
  await comb.getByRole("radio").nth(1).check();
  await comb.getByLabel("Reden om te combineren").fill("Zelfde begrip.");
  await comb.getByRole("button", { name: "Combineren" }).click();
  await page.waitForURL(/(begrip=|\/begrippen\/wg1\/)b3/);
  const c = requests.find((r) => r.p.endsWith("/combineren"));
  assert.equal(c.p, "/api/werkgebieden/wg1/begrippen/b3/combineren");
  assert.deepEqual(c.body, { verwachte_revisie: 1, ander_begrip_id: "b2", ander_revisie: 1, reden: "Zelfde begrip." });
  await zie("Vervangt");

  assert.deepEqual(errors, []);
  console.log("OK test-begriprelaties");
} catch (e) {
  if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/begriprelaties-fout.png`, fullPage: true });
  console.error(e);
  process.exitCode = 1;
} finally {
  await browser.close();
}
