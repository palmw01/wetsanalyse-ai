/** Browserregressie voor de strook "Voorstellen van Lex" (spoor D, levering 3a) en het beoordelen per term
 * (spoor H4) op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-begripvoorstellen.mjs`.
 *
 * De mock gedraagt zich als api: Lex stelt begrippen voor in het gesprek (F3e), dus de pagina toont alleen
 * wat er ligt – eerst niets, dan de laatste ronde met haar groepen; besluiten volgen de regels van
 * api/app/begrippen_run_store.py: akkoord accordeert als de poort het toelaat (definitie en door een
 * jurist beoordeelde annotaties), splitsen laat de rest van de groep open.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [], requests = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-15T10:00:00+00:00";
const wg = { id: "wg1", naam: "Invordering", analysevraag: "", afbakening: "", peildatum: null, status: "actief", revisie: 2,
  aangemaakt_door: "a", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null, bronnen: [] };
// De bron-IRI volgt de vindplaats, zodat de boom per artikel en lid groepeert (zonder /plaatsen: uit de IRI).
const iriVan = (v) => {
  const [, art, lid] = v.match(/Artikel (\w+)(?: · Lid (\w+))?/);
  return `urn:bwb:BWBR0004770:artikel:${art}${lid ? `:lid:${lid}` : ""}`;
};
const P = (id, tekst, vindplaats = "Artikel 9 · Lid 1 – IW 1990", review_status = "human_approved") =>
  ({ element_id: id, tekst, jas_klasse: "Rechtssubject", review_status, bron_iri: iriVan(vindplaats), vindplaats });
// De stand van de annotaties nú: "Annotatie akkoord" in de review zet er een op beoordeeld.
const beoordeeld = new Set(["e1", "e2", "e3", "e6", "e7", "e8", "e9", "e10"]);
const metStand = (l) => ({ ...l, lifecycle: beoordeeld.has(l.element_id) ? "human_approved" : "voorgesteld",
  annotatie_beoordeeld: beoordeeld.has(l.element_id) });
const groepen = [
  { id: "G1", aandacht: "groen", voorstel: { naam: "belastingschuldige", definitie: "degene die de belasting verschuldigd is",
      definitie_vindplaats: "Artikel 2 · Lid 1 – IW 1990" }, uitleg: ["De wet definieert de term in art. 2."], conflicten: [],
    leden: [P("e1", "belastingschuldige", "Artikel 2 · Lid 1 – IW 1990"), P("e2", "de belastingschuldige")] },
  { id: "G2", aandacht: "geel", voorstel: { naam: "aanslag" }, uitleg: ["Zelfde term"], conflicten: ["P9"],
    leden: [P("e3", "de aanslag"), P("e4", "die aanslag", "Artikel 9 · Lid 2 – IW 1990", "voorgesteld")] },
  { id: "G3", aandacht: "groen", voorstel: { naam: "aanslag" }, uitleg: [], conflicten: [],
    leden: [P("e6", "aanslag", "Artikel 10 – IW 1990"), P("e7", "de aanslag", "Artikel 11 · Lid 3 – IW 1990")] },
  { id: "G4", aandacht: "groen", voorstel: { naam: "termijn" }, uitleg: [], conflicten: [],
    leden: [P("e8", "de termijn", "Artikel 9 · Lid 3 – IW 1990"), P("e9", "deze termijn", "Artikel 9 · Lid 4 – IW 1990")] },
].map((g) => ({ ...g, besluit: "open", reden: "", begrip_id: null, besloten_door: null, lijkt_op: [], afgehandeld: [] }));
const uitkomst = {
  groep_ids: groepen.map((g) => g.id), meting: {},
  vragen: [{ kandidaat_id: "P1", van: "e3", naar: "e6", regel: "Z-ANDERS", uitleg: ["Zelfde kern, geen bron die het vastlegt."] },
    { kandidaat_id: "P2", van: "e4", naar: "e8", regel: "Z-ANDERS", uitleg: ["Staan in hetzelfde artikel."] }],
  relaties: [{ kandidaat_id: "R1", hypothese: "kwalificatie", van: "e10", naar: "e2", aandacht: "groen", uitleg: [] }],
};
const passages = { e10: P("e10", "de aansprakelijkgestelde", "Artikel 24 · Lid 1 – IW 1990"), e3: groepen[1].leden[0], e4: groepen[1].leden[1], e6: groepen[2].leden[0], e8: groepen[3].leden[0], e2: groepen[0].leden[1] };
let run = null;               // de laatste api-run
let verouderd = false;
// Wat Lex in het gesprek opleverde: de ronde die de begrippen-agent maakte.
const ronde = (over = {}) => ({ id: "r1", werkgebied_id: "wg1", manifest_id: "M1", status: "klaar", reden: "",
  aantal_formuleringen: 10, uitkomst, vragen_besluiten: {}, gestart_door: "t", gestart: nu, gewijzigd: nu,
  overgeslagen: [{ element_id: "e99", tekst: "Alfa Beta", reden: "Dit element heeft meer dan één anker; de keten werkt per passage." }],
  ...over });
const begrippen = new Map();
let teller = 0;
const alleLeden = () => groepen.flatMap((g) => g.leden);
const poortVan = (inhoud, eids) => {
  const r = [];
  if (!inhoud.definitie) r.push("Er is nog geen definitie.");
  const open = eids.filter((e) => !beoordeeld.has(e)).length;
  if (open) r.push(open === 1 ? "1 dragende annotatie is nog niet door een jurist beoordeeld."
    : `${open} dragende annotaties zijn nog niet door een jurist beoordeeld.`);
  return { mag: r.length === 0, redenen: r };
};
const begripUit = (b) => {
  const koppelingen = b.koppelingen.map((k) => ({ ...k, annotatie_beoordeeld: beoordeeld.has(k.element_id),
    lifecycle_nu: beoordeeld.has(k.element_id) ? "human_approved" : "voorgesteld" }));
  return { ...b, koppelingen, iri: `urn:wa:begrip:${b.id}`, werkgebied_id: "wg1", kader_iri: "urn:wa:kader:wg1",
    accorderen: poortVan(b.inhoud, b.koppelingen.map((k) => k.element_id)), aandachtspunten: [] };
};
function maakBegrip(naam, eids, definitie, beoordeling = "open", extra = {}) {
  const id = `b${++teller}`;
  begrippen.set(id, { id, status: "concept", revisie: 1, aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu,
    geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
    inhoud: { naam, alternatieve_termen: [], context: "", definitie: definitie ?? "",
      definitie_herkomst: definitie ? "letterlijk" : null, uitleg: "", voorbeelden: [] ,
      ...extra },
    koppelingen: eids.map((e, i) => { const p = alleLeden().find((l) => l.element_id === e) ?? passages[e]; return { id: `k${id}${i}`,
      begrip_id: id, element_id: e, rol: "duiding", motivatie: "", beoordeling, beoordeeld_door: null, beoordeeld_op: null,
      toegevoegd_door: "t", toegevoegd: nu, actualiteit: "actueel",
      bewijs: { tekst: p.tekst, klasse: p.jas_klasse, ankers: [], eigenaar_iri: "urn:x", laag_id: "l", snapshot_id: "s",
        lifecycle: "human_approved", vindplaats: p.vindplaats, element_hash: "h" } }; }) });
  return begripUit(begrippen.get(id));
}
const rest = (g) => g.leden.filter((l) => !g.afgehandeld.includes(l.element_id));
const groepUit = (g) => {
  const leden = rest(g).map(metStand);
  const open = g.besluit === "open" || g.besluit === "geparkeerd";
  const def = g.voorstel.definitie;
  return { ...g, leden, afgehandeld: g.afgehandeld.length,
    poort_vooraf: open ? poortVan({ definitie: def }, leden.map((l) => l.element_id)) : null };
};
const groepenAntwoord = () => run?.status === "klaar"
  ? { run: { ...run, uitkomst }, groepen: groepen.map(groepUit),
      passages: Object.fromEntries(Object.entries(passages).map(([k, v]) => [k, metStand(v)])) }
  : { run: null, groepen: [], passages: {} };

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  requests.push({ p, m, body });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run: run && { ...run, verouderd } } });
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: groepenAntwoord() });
  if (p === "/api/werkgebieden/wg1/groepen/akkoord") {
    const gs = groepen.filter((g) => body.groep_ids.includes(g.id));
    const klaar = gs.find((g) => ["overgenomen", "gekoppeld"].includes(g.besluit));
    if (klaar) return route.fulfill({ status: 409, json: { detail: { fout: "al_besloten", begrippen: { [klaar.id]: klaar.begrip_id },
      melding: "Een van deze groepen is al overgenomen of gekoppeld." } } });
    const leden = body.element_ids ?? gs.flatMap((g) => rest(g).map((l) => l.element_id));
    const bron = body.definitie_van ? gs.filter((g) => g.id === body.definitie_van) : gs;
    const defs = [...new Set(bron.map((g) => g.voorstel.definitie).filter(Boolean))];
    const a = body.aanpassing ?? {};
    const definitie = a.definitie ?? (defs.length === 1 ? defs[0] : undefined);
    const b = maakBegrip(body.naam, leden, definitie, "akkoord", {
      context: a.context ?? "Komt voor in Artikel 9 · Lid 1 – IW 1990.",
      ...(a.definitie !== undefined ? { definitie_herkomst: "geformuleerd" } : {}) });
    const poort = b.accorderen;
    if (poort.mag) Object.assign(begrippen.get(b.id), { status: "geaccordeerd", revisie: 2 });
    for (const g of gs) {
      g.afgehandeld = [...new Set([...g.afgehandeld, ...g.leden.map((l) => l.element_id).filter((e) => leden.includes(e))])];
      if (g.leden.every((l) => g.afgehandeld.includes(l.element_id))) Object.assign(g, { besluit: "overgenomen", begrip_id: b.id });
    }
    for (const kid of [body.kandidaat_id, ...(body.kandidaat_ids ?? [])].filter(Boolean))
      run.vragen_besluiten = { ...run.vragen_besluiten, [kid]: { antwoord: "samen", door: "browser-test", op: nu } };
    const uit = begripUit(begrippen.get(b.id));
    return route.fulfill({ status: 201, json: { begrip: uit, geaccordeerd: uit.status === "geaccordeerd", poort: uit.accorderen } });
  }
  const em = p.match(/^\/api\/annotatie\/v2\/elementen\/(e\d+)(\/beslissing)?$/);
  if (em && !em[2]) return route.fulfill({ json: { element: { id: em[1], eigenaar_iri: "urn:x:lid:2" }, laag: { revisie: 4 }, snapshot_id: "s9" } });
  if (em) {
    assert.deepEqual(body, { type: "approve", snapshot_id: "s9", verwachte_revisies: { "urn:x:lid:2": 4 } });
    beoordeeld.add(em[1]);
    return route.fulfill({ json: { status: "ok" } });
  }
  const gm = p.match(/^\/api\/werkgebieden\/wg1\/groepen\/(G\d)\/(afwijzen|parkeren|heropenen)$/);
  if (gm) {
    const g = groepen.find((x) => x.id === gm[1]);
    Object.assign(g, { besluit: { afwijzen: "afgewezen", parkeren: "geparkeerd", heropenen: "open" }[gm[2]], reden: body?.reden ?? "" });
    return route.fulfill({ json: groepenAntwoord() });
  }
  const vm = p.match(/^\/api\/werkgebieden\/wg1\/begrippen-runs\/r1\/vragen\/(P\d)$/);
  if (vm) {
    run.vragen_besluiten = { ...run.vragen_besluiten, [vm[1]]: { antwoord: body.antwoord, door: "browser-test", op: nu } };
    return route.fulfill({ json: run });
  }
  if (p === "/api/werkgebieden/wg1/begrippen") return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", primair: {},
    begrippen: [...begrippen.values()].map((b) => ({ ...begripUit(b), koppelingen: undefined, aantal_koppelingen: b.koppelingen.length,
      element_ids: b.koppelingen.map((k) => k.element_id) })) } });
  const bm = p.match(/^\/api\/werkgebieden\/wg1\/begrippen\/(b\d+)(\/accorderen)?$/);
  if (bm) {
    const b = begrippen.get(bm[1]);
    if (m === "PATCH") Object.assign(b, { inhoud: body.inhoud, revisie: b.revisie + 1 });
    if (bm[2]) {
      assert.equal(body.verwachte_revisie, b.revisie);
      if (!begripUit(b).accorderen.mag) return route.fulfill({ status: 409, json: { detail: { fout: "poort", melding: "Nog niet." } } });
      Object.assign(b, { status: "geaccordeerd", revisie: b.revisie + 1 });
    }
    return route.fulfill({ json: begripUit(b) });
  }
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ status: 404, json: { detail: "Niet in deze test." } });
});

const foto = (naam) => process.env.SCREENSHOT_DIR
  ? page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/${naam}.png`, fullPage: true }) : null;
const zie = (tekst) => page.getByText(tekst, { exact: false }).first().waitFor();
const termen = () => page.getByRole("list", { name: "Voorstellen van Lex per term" });
const laatsteBody = (pad) => requests.filter((r) => r.p.endsWith(pad) && r.m === "POST").at(-1)?.body;
const balk = () => page.locator("[data-actiebalk]");
const kader = `${base}/werkgebieden/wg1/artefacten/begrippen`;
const naarTerm = async (t) => {
  await page.goto(kader);
  await termen().locator(`[data-term="${t}"] a`).click();
  await page.locator(`[data-begripterm-pagina="${t}"] [data-bronboom]`).waitFor();
};
try {
  // 1. Zonder voorstellen: de uitleg wijst naar het gesprek; geen Lex-knoppen op de pagina (F3e).
  await page.goto(kader);
  await zie("Vraag Lex in het gesprek om begrippen voor te stellen.");
  await zie("Een voorstel is een vraag aan jou, geen begrip.");
  for (const naam of ["Stel begrippen voor", "Opnieuw voorstellen", /^Laat Lex meedenken/])
    assert.equal(await page.getByRole("button", { name: naam }).count(), 0, String(naam));
  // Lex stelde in het gesprek begrippen voor: per term één rij, de meeste passages eerst.
  run = ronde();
  await page.reload();
  await termen().waitFor();
  await zie("1 passage niet meegenomen");
  await zie("3 termen te beoordelen");
  assert.deepEqual(await page.locator("[data-term]").evaluateAll((els) => els.map((e) => e.dataset.term)),
    ["aanslag", "belastingschuldige", "termijn"]);
  await termen().locator('[data-term="aanslag"]').getByText("2 voorstellen · IW 1990 · 4 passages · 1 vraag naar een andere term").waitFor();
  // Geen reviewlijst, geen knoppen per voorstel.
  assert.equal(await page.locator("[data-review-item]").count(), 0);
  assert.equal(await termen().getByRole("button").count(), 0);
  await page.getByText("Relaties (1)").click();
  await zie("“de aansprakelijkgestelde” (Artikel 24 · Lid 1 – IW 1990) geldt als “de belastingschuldige”");
  await foto("kader-per-term");

  // 2. De term "aanslag": twee groepen op drie artikelen in één boom, alles aangevinkt.
  await naarTerm("aanslag");
  const boom = page.locator("[data-bronboom]");
  for (const kop of ["Artikel 9", "Artikel 10", "Artikel 11"])
    await boom.getByRole("button", { name: new RegExp(`^${kop}\\b`) }).first().waitFor();
  assert.equal(await page.locator("[data-passage]").count(), 4);
  assert.equal(await page.getByRole("checkbox", { name: /^Neem/ }).evaluateAll((els) => els.every((e) => e.checked)), true);
  await zie("Het begrip blijft eerst een concept");
  await zie("1 dragende annotatie is nog niet door een jurist beoordeeld.");
  await page.getByText("Waarom stelt Lex dit voor?").click();
  await zie("1 twijfelvraag tussen deze passages; met één begrip zijn ze beantwoord.");
  await page.getByRole("list", { name: "Vragen naar andere termen" }).getByText("Horen “die aanslag”").waitFor();
  // Letters doen niets: geen sneltoetsen.
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  for (const t of ["a", "j", "x", "s"]) await page.keyboard.press(t);
  assert.equal(requests.filter((r) => r.m === "POST" && /\/(groepen|vragen)\//.test(r.p)).length, 0);
  await foto("term-aanslag");
  // Eén begrip, met de vraag binnen de term in hetzelfde akkoord; daarna de begripspagina.
  await balk().getByRole("button", { name: "Eén begrip maken (4)" }).click();
  await page.waitForURL(/\/begrippen\/wg1\/b1$/);
  const een = laatsteBody("/groepen/akkoord");
  assert.deepEqual([een.groep_ids, een.naam, een.element_ids, een.kandidaat_ids, een.aanpassing],
    [["G2", "G3"], "aanslag", undefined, ["P1"], undefined]);
  assert.equal(run.vragen_besluiten.P1.antwoord, "samen");

  // 3. Het kader: aanslag is beoordeeld, de rest staat er nog.
  await page.goto(kader);
  await termen().waitFor();
  assert.deepEqual(await page.locator("[data-term]").evaluateAll((els) => els.map((e) => e.dataset.term)),
    ["belastingschuldige", "termijn"]);
  await page.getByText("Beoordeelde termen (1)").waitFor();

  // 4. belastingschuldige: één passage uitvinken (splitsen); de brondefinitie gaat mee.
  await naarTerm("belastingschuldige");
  await zie("Definitie – brondefinitie (Artikel 2 · Lid 1 – IW 1990)");
  await page.getByRole("checkbox", { name: "Neem “belastingschuldige” mee (Artikel 2 · Lid 1 – IW 1990)" }).uncheck();
  await balk().getByText("1 passage gekozen").waitFor();
  await balk().getByRole("button", { name: "Eén begrip maken (1)" }).click();
  await page.waitForURL(/\/begrippen\/wg1\/b2$/);
  const split = laatsteBody("/groepen/akkoord");
  assert.deepEqual([split.groep_ids, split.element_ids, split.kandidaat_ids], [["G1"], ["e2"], undefined]);
  assert.equal(begrippen.get("b2").status, "geaccordeerd");

  // 5. termijn: de vraag naar "aanslag" apart, en dan geen begrip – met een reden.
  await naarTerm("termijn");
  const vragen = page.getByRole("list", { name: "Vragen naar andere termen" });
  await vragen.getByRole("button", { name: /^Apart: Horen “die aanslag”/ }).click();
  await vragen.waitFor({ state: "detached" });
  assert.equal(laatsteBody("/vragen/P2").antwoord, "apart");
  await balk().getByRole("button", { name: "Geen begrip…" }).click();
  await page.keyboard.type("Verschillende termijnen");
  await page.keyboard.press("Enter");
  await page.getByText("Al besloten (1)").waitFor();
  assert.deepEqual(laatsteBody("/groepen/G4/afwijzen"), { reden: "Verschillende termijnen" });

  // 6. De rest van belastingschuldige voor later, en weer heropenen.
  await naarTerm("belastingschuldige");
  await balk().getByRole("button", { name: "Later" }).click();
  await zie("voor later bewaard");
  await balk().getByText("0 passages gekozen").waitFor();
  await page.getByRole("checkbox", { name: /^Neem “belastingschuldige” mee/ }).check();
  await balk().getByRole("button", { name: "Heropenen" }).click();
  await balk().getByText("1 passage gekozen").waitFor();
  assert.equal(groepen[0].besluit, "open");

  // 7. Verouderd na een nieuwe annotatie: de strook zegt het.
  verouderd = true;
  await page.goto(kader);
  await zie("Gebaseerd op een oudere stand van het werkgebied");

  // 8. Een mislukte ronde van Lex is zichtbaar.
  run = ronde({ status: "mislukt", reden: "De begrippenketen liep vast." });
  await page.reload();
  await zie("mislukt: De begrippenketen liep vast.");

  // 9. Smal scherm, ook op een termpagina.
  run = ronde();
  await page.setViewportSize({ width: 390, height: 844 });
  await naarTerm("belastingschuldige");
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  await foto("term-mobiel");
  assert.deepEqual(errors, []);
  console.log("Browser OK: geen Lex-knoppen, de voorstellen per term, een termpagina als boom met vinkjes, één begrip uit twee groepen met de vraag erin, splitsen met de brondefinitie, een vraag apart, geen begrip met reden, later en heropenen, geen sneltoetsen, verouderd, mislukte ronde, smal scherm.");
} catch (e) {
  await foto("voorstellen-fout");
  throw e;
} finally { await browser.close(); }
