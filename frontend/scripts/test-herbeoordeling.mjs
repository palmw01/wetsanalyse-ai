/** Browserregressie voor herbeoordelen en dekking (spoor D, fase F1) op de echte Next-UI met een gemockte BFF.
 * Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-herbeoordeling.mjs`.
 *
 * De mock gedraagt zich als de api (`api/app/begrip_onderhoud_store.py`): herbeoordelingen per geraakte
 * koppeling, herkoppelen (de oude koppeling wordt historie, de nieuwe draagt `vervangt`), bevestigen (een
 * tweede bewijsstand) en de dekking met buiten behandeling.
 *
 * Bewaakt (de acceptatie van fase F1: een gewijzigde dragende passage verschijnt bij de geraakte
 * begrippen; de oude bewijsstand blijft):
 *  - de strook *Herbeoordelen* noemt het begrip, de lijst ook; een klik opent het begrip;
 *  - bij de passage: wat er veranderde, toen naast nu, de wettekst van nu met het fragment aangewezen,
 *    de opvolger met signalen;
 *  - herkoppelen met het toetsenbord: de nieuwe passage staat er, met de oude als "Vervangt een eerdere
 *    passage", het begrip blijft geaccordeerd, de strook verdwijnt;
 *  - bevestigen met een toelichting;
 *  - de dekking op de tab Elementen, buiten behandeling met een reden en weer terughalen.
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
const IW = "urn:bwb:BWBR0004770";
const LID1 = `${IW}:artikel:9:lid:1`, LID2 = `${IW}:artikel:9:lid:2`;
const wg = { id: "wg1", naam: "Termijnen", analysevraag: "", afbakening: "", peildatum: null, status: "actief", revisie: 2,
  aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null,
  bronnen: [{ id: "s1", bron_iri: `${IW}:artikel:9`, label: "Artikel 9", rol: "analyseren", bereik: "onderliggend", reden: "",
    bwb_id: "BWBR0004770", snapshot_id: "s", bron_hash: "h", toegevoegd_door: "t", toegevoegd: nu }] };
const LEEG = { naam: "", alternatieve_termen: [], context: "Invordering.", jas_klasse: "", jas_subtype: "", geldigheid: "",
  definitie: "Degene die de belasting verschuldigd is.", definitie_herkomst: "samengesteld", definitie_door: "analist", uitleg: "",
  onderbouwing: "", voorbeelden: [], eigenschappen: {}, open_vragen: [] };
const bewijs = (tekst, iri) => ({ tekst, klasse: "Rechtssubject", ankers: [{ bron_iri: iri, start: 0, eind: tekst.length, tekst }],
  eigenaar_iri: iri, laag_id: "l", snapshot_id: "s", lifecycle: "human_approved",
  vindplaats: iri === LID1 ? "Artikel 9 · Lid 1" : "Artikel 9 · Lid 2", element_hash: "h" });
const koppeling = (id, eid, tekst, iri, extra = {}) => ({ id, begrip_id: "b1", element_id: eid, rol: "duiding", motivatie: "",
  bewijs: bewijs(tekst, iri), beoordeling: "akkoord", beoordeeld_door: "t", beoordeeld_op: nu, toegevoegd_door: "t",
  toegevoegd: nu, actualiteit: "actueel", lifecycle_nu: "human_approved", annotatie_beoordeeld: true, bevestigingen: [], ...extra });

const b1 = { id: "b1", status: "geaccordeerd", revisie: 4, inhoud: { ...LEEG, naam: "belastingschuldige" },
  koppelingen: [
    koppeling("k1", "e1", "Beta", LID2, { actualiteit: "gewijzigd" }),
    koppeling("k2", "e3", "Alfa", LID1),
  ], revisies: [] };
const uit = (b) => ({ ...b, iri: `urn:wa:begrip:${b.id}`, werkgebied_id: "wg1", kader_iri: "urn:wa:kader:wg1",
  aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, geaccordeerd_door: "t", geaccordeerd_op: nu, geaccordeerd_revisie: 4,
  accorderen: { mag: true, redenen: [] }, aandachtspunten: [] });

// --- de herbeoordeling, zoals de api haar rekent --------------------------------------------------
const geraakt = {
  k1: { koppeling_id: "k1", element_id: "e1", rol: "duiding", actualiteit: "gewijzigd",
    redenen: ["De annotatie is verouderd: de wettekst onder het anker veranderde en de bepaling is opnieuw geannoteerd.",
      "De wettekst van Artikel 9 · Lid 2 veranderde, ook op de gemarkeerde plek."],
    toen: { tekst: "Beta", klasse: "Rechtssubject", ankers: [], vindplaats: "Artikel 9 · Lid 2", lifecycle: "human_approved", snapshot_id: "s", eigenaar_iri: LID2 },
    bevestigingen: [], nu: { tekst: "Beta", klasse: "Rechtssubject", jas_subtype: "", ankers: [], lifecycle: "human_approved", verouderd: true },
    bron: [{ bron_iri: LID2, vindplaats: "Artikel 9 · Lid 2", fragment: "Beta", stand: "gewijzigd", tekst_nu: "Other", fragment_gelijk: false }],
    opvolgers: [{ element_id: "e2", tekst: "Other", klasse: "Rechtssubject", lifecycle: "voorgesteld", annotatie_beoordeeld: false,
      signalen: [{ richting: "steun", uitleg: "Zelfde JAS-klasse (Rechtssubject)." }, { richting: "tegen", uitleg: "Andere tekst." },
        { richting: "steun", uitleg: "Op dezelfde plek in de bepaling." }] }],
    opnieuw_annoteren: [], acties: ["herkoppelen", "loskoppelen"] },
  k2: { koppeling_id: "k2", element_id: "e3", rol: "duiding", actualiteit: "actueel",
    redenen: ["De wettekst van Artikel 9 · Lid 1 veranderde; het gemarkeerde fragment staat er nog letterlijk."],
    toen: { tekst: "Alfa", klasse: "Rechtssubject", ankers: [], vindplaats: "Artikel 9 · Lid 1", lifecycle: "human_approved", snapshot_id: "s", eigenaar_iri: LID1 },
    bevestigingen: [], nu: { tekst: "Alfa", klasse: "Rechtssubject", jas_subtype: "", ankers: [], lifecycle: "human_approved", verouderd: false },
    bron: [{ bron_iri: LID1, vindplaats: "Artikel 9 · Lid 1", fragment: "Alfa", stand: "gewijzigd", tekst_nu: "Alfa en meer", fragment_gelijk: true }],
    opvolgers: [], opnieuw_annoteren: [], acties: ["bevestigen", "loskoppelen"] },
};
const herbeoordelingen = () => {
  const ks = b1.koppelingen.map((k) => geraakt[k.id]).filter(Boolean);
  return { werkgebied_id: "wg1", volledig: true, open_punten: [],
    begrippen: ks.length ? [{ begrip_id: "b1", naam: "belastingschuldige", status: b1.status, revisie: b1.revisie, koppelingen: ks }] : [] };
};

// --- de dekking ------------------------------------------------------------------------------------
const element = (id, tekst, iri) => ({ id, klasse: "Rechtssubject", tekst, lifecycle: "human_approved", eigenaar_iri: iri, laag_id: "l",
  ankers: [], verouderd: false, rol: "analyseren", selecties: ["s1"], deels_buiten: false });
const elementen = [element("e3", "Alfa", LID1), element("e2", "Other", LID2), element("e4", "Gamma", LID2)];
const buiten = {};
const dekking = () => {
  const stand = (id) => (id === "e3" || id === "e2") && b1.koppelingen.some((k) => k.element_id === id) ? "gekoppeld"
    : buiten[id] ? "buiten_behandeling" : "te_verwerken";
  const els = elementen.map((e) => ({ element_id: e.id, tekst: e.tekst, klasse: e.klasse, rol: "analyseren", stand: stand(e.id),
    begrippen: [], buiten_behandeling: buiten[e.id] ?? null, nieuw_sinds_run: e.id === "e4" }));
  const totalen = { te_verwerken: 0, voorstel: 0, gekoppeld: 0, buiten_behandeling: 0 };
  for (const e of els) totalen[e.stand] += 1;
  return { werkgebied_id: "wg1", totalen, totaal: els.length, nieuw_sinds_run: 1, laatste_run: "r1", elementen: els, volledig: true };
};

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" || m === "DELETE" ? null : req.postDataJSON();
  requests.push({ p, m, body, q: url.search });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/begrippen" && m === "GET") {
    const { koppelingen, ...r } = uit(b1);
    return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", primair: {},
      begrippen: [{ ...r, aantal_koppelingen: koppelingen.length, element_ids: koppelingen.map((k) => k.element_id) }] } });
  }
  if (p === "/api/werkgebieden/wg1/herbeoordelingen") return route.fulfill({ json: herbeoordelingen() });
  if (p === "/api/werkgebieden/wg1/begrippen/b1" && m === "GET") return route.fulfill({ json: uit(b1) });
  if (p === "/api/werkgebieden/wg1/begrippen/b1/revisies") return route.fulfill({ json: { revisies: [] } });
  const km = p.match(/^\/api\/werkgebieden\/wg1\/begrippen\/b1\/koppelingen\/(k\d)\/(herkoppelen|bevestigen)$/);
  if (km) {
    if (body.verwachte_revisie !== b1.revisie)
      return route.fulfill({ status: 412, json: { detail: { fout: "revisie_conflict", revisie: b1.revisie, melding: "Iemand anders…" } } });
    const oud = b1.koppelingen.find((k) => k.id === km[1]);
    if (km[2] === "herkoppelen") {
      const nieuw = koppeling("k9", body.element_id, "Other", LID2, { annotatie_beoordeeld: false, lifecycle_nu: "voorgesteld",
        vervangt: { koppeling_id: oud.id, element_id: oud.element_id, bewijs: oud.bewijs, vervangen_op: nu } });
      b1.koppelingen = b1.koppelingen.map((k) => (k.id === oud.id ? nieuw : k));
    } else {
      oud.bevestigingen = [{ element_hash: "h2", tekst: "Alfa", klasse: "Rechtssubject", door: "browser-test", op: nu, motivatie: body.motivatie ?? "" }];
      delete geraakt[oud.id];
    }
    b1.revisie += 1;
    return route.fulfill({ json: uit(b1) });
  }
  if (p.match(/^\/api\/werkgebieden\/wg1\/begrippen\/b1\/(voorstellen)$/))
    return route.fulfill({ json: { voorstellen: [], runs: {}, schatting: {}, budget: null } });
  if (p === "/api/werkgebieden/wg1/elementen")
    return route.fulfill({ json: { volledig: true, elementen,
      selecties: [{ id: "s1", bron_iri: `${IW}:artikel:9`, label: "Artikel 9", rol: "analyseren", bereik: "onderliggend", aantal: 3,
        afgewezen: 0, bron_gewijzigd: true, onbereikbaar: null }] } });
  if (p === "/api/werkgebieden/wg1/dekking") return route.fulfill({ json: dekking() });
  if (p === "/api/werkgebieden/wg1/dekking/buiten-behandeling" && m === "POST") {
    for (const e of body.element_ids) buiten[e] = { reden: body.reden, door: "browser-test", op: nu };
    return route.fulfill({ json: { element_ids: body.element_ids } });
  }
  const bb = p.match(/^\/api\/werkgebieden\/wg1\/dekking\/buiten-behandeling\/(e\d)$/);
  if (bb && m === "DELETE") { delete buiten[bb[1]]; return route.fulfill({ json: { element_id: bb[1] } }); }
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: { run: null, groepen: [], passages: {} } });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run: null } });
  if (p === "/api/werkgebieden/wg1/verdieping")
    return route.fulfill({ json: { run: null, aantal: 0, vragen: [], kaarten: [], batches: [], verdiept: false, schatting: null, budget: null } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ status: 404, json: { detail: "Niet in deze test." } });
});

const zie = (tekst) => page.getByText(tekst, { exact: false }).first().waitFor();
const strook = () => page.getByRole("region", { name: "Herbeoordelen" });
const passages = () => page.getByRole("list", { name: "Passages van dit begrip" });
const blok = (tekst) => passages().getByRole("listitem").filter({ hasText: tekst }).getByRole("group", { name: "Herbeoordelen" });
try {
  // 1. De strook en de lijst noemen het begrip; een klik opent het.
  await page.goto(`${base}/werkgebieden/wg1?tab=begrippen`);
  await strook().getByText("1 begrip herbeoordelen · 2 passages veranderden").waitFor();
  await page.getByRole("list", { name: "Begrippen in dit werkgebied" }).getByText("Herbeoordelen: 2 passages veranderden").waitFor();
  await strook().getByRole("button", { name: /belastingschuldige/ }).click();
  await passages().waitFor();
  await page.waitForURL(/begrip=b1/);

  // 2. Bij de passage: wat er veranderde, toen naast nu, de wettekst van nu, de opvolger met signalen.
  const k1 = blok("Beta");
  await k1.getByText("ook op de gemarkeerde plek").waitFor();
  await k1.getByText("Toen (bij koppelen)").waitFor();
  await k1.getByText("annotatie verouderd").waitFor();
  await k1.getByText("Het gemarkeerde fragment “Beta” staat er niet meer.").waitFor();
  const signalen = k1.getByRole("list", { name: "Signalen" });
  await signalen.getByText("Andere tekst.").waitFor();
  await k1.getByText("annotatie nog niet door een jurist beoordeeld").waitFor();
  assert.ok(requests.some((r) => r.p.endsWith("/herbeoordelingen") && r.q.includes("begrip_id=b1")));

  // 3. Herkoppelen met het toetsenbord: de oude passage blijft als historie, het begrip geaccordeerd.
  await k1.getByRole("button", { name: "Herkoppel aan “Other”" }).focus();
  await page.keyboard.press("Enter");
  await zie("Herkoppeld. De oude passage blijft als historie bij de nieuwe staan.");
  const nieuw = passages().getByRole("listitem").filter({ hasText: "“Other”" });
  await nieuw.getByText("Vervangt een eerdere passage").click();
  await nieuw.getByText("Toen: “Beta”", { exact: false }).waitFor();
  const herk = requests.find((r) => r.p.endsWith("/k1/herkoppelen"));
  assert.deepEqual(herk.body, { verwachte_revisie: 4, element_id: "e2" });
  assert.equal(b1.status, "geaccordeerd");

  // 4. Bevestigen met een toelichting: de strook verdwijnt.
  const k2 = blok("Alfa");
  await k2.getByText("staat er nog letterlijk").waitFor();
  await k2.getByRole("mark").filter({ hasText: "Alfa" }).waitFor();
  await k2.getByLabel(/^Toelichting bij het herbeoordelen/).fill("Alleen aangevuld.");
  await k2.getByRole("button", { name: "Begrip klopt nog" }).click();
  await zie("Bevestigd. De oude bewijsstand blijft bewaard.");
  const bev = requests.find((r) => r.p.endsWith("/k2/bevestigen"));
  assert.deepEqual(bev.body, { verwachte_revisie: 5, motivatie: "Alleen aangevuld." });
  await passages().getByText("Na een wijziging bevestigd door browser-test").waitFor();
  assert.equal(await passages().getByRole("group", { name: "Herbeoordelen" }).count(), 0);

  // 5. De dekking: buiten behandeling met een reden, en weer terughalen.
  await page.goto(`${base}/werkgebieden/wg1?tab=elementen`);
  const balk = page.getByRole("region", { name: "Dekking" });
  await balk.getByText("gekoppeld aan een geaccordeerd begrip").waitFor();
  await balk.getByText("zag de laatste begrippenronde van Lex nog niet", { exact: false }).waitFor();
  await page.getByText("Nieuw sinds de laatste begrippenronde van Lex.").waitFor();
  await page.getByRole("checkbox", { name: 'Kies "Gamma"' }).check();
  await page.getByLabel("Reden om buiten behandeling te zetten").fill("Alleen een tijdsaanduiding.");
  await page.keyboard.press("Enter");
  await page.getByText("Bewust buiten behandeling: Alleen een tijdsaanduiding.", { exact: false }).waitFor();
  assert.equal(await balk.locator("li").filter({ hasText: "bewust buiten behandeling" }).locator("span").first().textContent(), "1");
  await page.getByRole("button", { name: 'Haal "Gamma" terug in behandeling' }).click();
  await page.getByText("Bewust buiten behandeling:", { exact: false }).waitFor({ state: "detached" });

  assert.deepEqual(errors, []);
  console.log("OK test-herbeoordeling");
} catch (e) {
  if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/herbeoordeling-fout.png`, fullPage: true });
  console.error(e);
  process.exitCode = 1;
} finally {
  await browser.close();
}
