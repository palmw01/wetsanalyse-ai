/** Browserregressie voor de strook "Voorstellen van Lex" (spoor D, levering 3a) en de begrippenreview
 * (fase D) op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-begripvoorstellen.mjs`.
 *
 * De mock gedraagt zich als api + graph-qa: een start geeft een run en een SSE-stroom (status →
 * opgeslagen → done), daarna staan de groepen er; besluiten volgen de regels van
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
const P = (id, tekst, vindplaats = "Artikel 9 · Lid 1 – IW 1990", review_status = "human_approved") =>
  ({ element_id: id, tekst, jas_klasse: "Rechtssubject", review_status, bron_iri: "urn:x", vindplaats });
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
  { id: "G3", aandacht: "groen", voorstel: { naam: "belastingaanslag" }, uitleg: [], conflicten: [],
    leden: [P("e6", "belastingaanslag"), P("e7", "de belastingaanslag")] },
  { id: "G4", aandacht: "groen", voorstel: { naam: "termijn" }, uitleg: [], conflicten: [],
    leden: [P("e8", "de termijn"), P("e9", "deze termijn")] },
].map((g) => ({ ...g, besluit: "open", reden: "", begrip_id: null, besloten_door: null, lijkt_op: [], afgehandeld: [] }));
const uitkomst = {
  groep_ids: groepen.map((g) => g.id), meting: {},
  vragen: [{ kandidaat_id: "P1", van: "e3", naar: "e6", regel: "Z-ANDERS", uitleg: ["Zelfde kern, geen bron die het vastlegt."] }],
  relaties: [{ kandidaat_id: "R1", hypothese: "kwalificatie", van: "e10", naar: "e2", aandacht: "groen", uitleg: [] }],
};
const passages = { e10: P("e10", "de aansprakelijkgestelde", "Artikel 24 · Lid 1 – IW 1990"), e3: groepen[1].leden[0], e6: groepen[2].leden[0], e2: groepen[0].leden[1] };
let run = null;               // de laatste api-run
let verouderd = false;
let agentStroom = {};          // agent-run-id → events
let actieveAgent = null;       // voor aanhaken na herladen
const begrippen = new Map();
let teller = 0;
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const alleLeden = () => groepen.flatMap((g) => g.leden);
const poortVan = (inhoud, eids) => {
  const r = [];
  if (!inhoud.definitie) r.push("Er is nog geen definitie.", "De herkomst van de definitie is niet gekozen.");
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
    inhoud: { naam, alternatieve_termen: [], context: "", jas_klasse: "", jas_subtype: "", geldigheid: "", definitie: definitie ?? "",
      definitie_herkomst: definitie ? "letterlijk" : null, uitleg: "", onderbouwing: "", voorbeelden: [], eigenschappen: {}, open_vragen: [],
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
  if (p === "/api/begrippen-run" && m === "POST") {
    if (run?.status === "klaar" && !agentStroom.volgende) return route.fulfill({ json: { run, agent_run_id: null } });
    const id = agentStroom.volgende ?? "ag1";
    delete agentStroom.volgende;
    run = { id: "r1", werkgebied_id: "wg1", manifest_id: "M1", status: "wacht", reden: "", aantal_formuleringen: 10,
      overgeslagen: [{ element_id: "e99", tekst: "Alfa Beta", reden: "Dit element heeft meer dan één anker; de keten werkt per passage." }],
      uitkomst: null, vragen_besluiten: {}, gestart_door: "t", gestart: nu, gewijzigd: nu };
    return route.fulfill({ status: 201, json: { run, agent_run_id: id } });
  }
  if (p === "/api/begrippen-run") return route.fulfill({ json: actieveAgent ? { run_id: actieveAgent, status: "loopt" } : null });
  const ev = p.match(/^\/api\/annotatie\/run\/(ag\d)\/events$/);
  if (ev) {
    const fout = ev[1] === "ag3";
    if (!fout) { run = { ...run, status: "klaar", uitkomst }; actieveAgent = null; }
    return route.fulfill({ contentType: "text/event-stream", body: sse(fout
      ? [{ type: "status", message: "Lex · Taalanalyse: 10 formuleringen (40 ms)" },
         { type: "error", message: "De begrippenketen liep vast; de voorstellen zijn niet gemaakt.", soort: "keten" }]
      : [{ type: "status", message: "Lex · 10 passages uit 4 bepalingen" }, { type: "status", message: "Lex · Groeperen: 4 groepen (12 ms)" },
         { type: "opgeslagen", begrippen_run: "r1", groepen: 4 }, { type: "done" }]) });
  }
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
    if (body.kandidaat_id) run.vragen_besluiten = { ...run.vragen_besluiten, [body.kandidaat_id]: { antwoord: "samen", door: "browser-test", op: nu } };
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
const lijst = () => page.getByRole("list", { name: "Voorstellen om te beoordelen" });
const actief = () => page.locator("[data-review-item][aria-current=true]");
const laatsteBody = (pad) => requests.filter((r) => r.p.endsWith(pad) && r.m === "POST").at(-1)?.body;
const toets = (t) => page.keyboard.press(t);
try {
  // 1. Zonder voorstellen: uitleg en de knop. Starten → stroom → de reviewlijst.
  await page.goto(`${base}/werkgebieden/wg1?tab=begrippen`);
  await zie("Een voorstel is een vraag aan jou, geen begrip.");
  // De tweede weg: met Lex in de werkplek, in de context van dit werkgebied (fase AF2).
  assert.equal(await page.getByRole("link", { name: "Bespreek met Lex" }).getAttribute("href"), "/workbench?werkgebied=wg1");
  await page.getByRole("button", { name: "Stel begrippen voor" }).click();
  await lijst().waitFor();
  assert.ok(requests.some((r) => r.p === "/api/annotatie/run/ag1/events"), "de stroom van Lex is gevolgd");
  await zie("1 passage niet meegenomen");
  await zie("Review – 0/5 beoordeeld");
  // Volgorde: geel, de twijfelvraag, dan groen (op naam bij gelijke omvang).
  assert.deepEqual(await page.locator("[data-review-item]").evaluateAll((els) => els.map((e) => e.dataset.reviewItem)),
    ["G2", "P1", "G3", "G1", "G4"]);
  await page.getByText("Relaties (1)").click();
  await zie("“de aansprakelijkgestelde” (Artikel 24 · Lid 1 – IW 1990) geldt als “de belastingschuldige”");
  await foto("review");

  // 2. Alleen het toetsenbord. j → de gele groep; de knop zegt vooraf dat het een concept blijft.
  await toets("j");
  assert.equal(await actief().getAttribute("data-review-item"), "G2");
  await zie("Akkoord als concept (3 open punten)");
  await foto("review-actief");
  await zie("vraagt een oordeel");
  // m markeert; j, j → belastingaanslag; m: de vergelijking verschijnt, met het signaal ertegen.
  await toets("m");
  await toets("j");
  assert.equal(await actief().getAttribute("data-review-item"), "P1");
  await zie("Horen “de aanslag” (Artikel 9 · Lid 1 – IW 1990) en “belastingaanslag” (Artikel 9 · Lid 1 – IW 1990) bij hetzelfde begrip?");
  await toets("j");
  await toets("m");
  const vergelijking = page.getByRole("region", { name: "Vergelijking om te combineren" });
  await vergelijking.waitFor();
  await vergelijking.getByText("aanwijzing dat passages níét hetzelfde betekenen").waitFor();
  const combiNaam = vergelijking.getByRole("textbox", { name: "Naam van het gecombineerde begrip" });
  await combiNaam.focus();
  await page.keyboard.press("Control+A");
  await page.keyboard.type("Aanslag");
  await toets("Enter");
  await zie("concept, nog te accorderen");
  const combi = laatsteBody("/groepen/akkoord");
  assert.deepEqual([combi.groep_ids, combi.naam, combi.element_ids], [["G2", "G3"], "Aanslag", undefined]);
  // Het concept zegt wat er openstaat en lost het hier op: eerst de annotatie, dan een definitie.
  const concept = page.locator("[data-concept]");
  await concept.getByText("1 dragende annotatie is nog niet door een jurist beoordeeld.").waitFor();
  await foto("review-concept");
  await concept.getByRole("button", { name: "Annotatie akkoord: die aanslag" }).click();
  await concept.getByRole("button", { name: /^Annotatie akkoord/ }).waitFor({ state: "detached" });
  await concept.getByText("Er is nog geen definitie.").waitFor();
  await concept.getByRole("button", { name: "Definitie toevoegen" }).click();
  await page.keyboard.type("de vaststelling van de verschuldigde belasting");
  await toets("Enter");
  await zie("Begrip “Aanslag” is geaccordeerd.");
  assert.equal(begrippen.get("b1").status, "geaccordeerd");
  assert.equal(begrippen.get("b1").inhoud.definitie_herkomst, "geformuleerd");

  // 3. De twijfelvraag is nu de actieve: n = apart.
  await page.evaluate(() => document.activeElement?.blur());
  assert.equal(await actief().getAttribute("data-review-item"), "P1");
  await toets("n");
  await zie("Review – 3/5 beoordeeld");
  assert.equal(laatsteBody("/vragen/P1").antwoord, "apart");

  // 4. belastingschuldige: één lid uitvinken (splitsen), e = aanpassen, context wijzigen, Ctrl+Enter.
  assert.equal(await actief().getAttribute("data-review-item"), "G1");
  await page.getByRole("checkbox", { name: "Neem “belastingschuldige” mee" }).uncheck();
  await page.evaluate(() => document.activeElement?.blur());
  await toets("e");
  const context = actief().getByRole("textbox", { name: /^Context/ });
  await context.fill("Invordering van rijksbelastingen");
  await context.press("Control+Enter");
  await zie("Begrip “belastingschuldige” is geaccordeerd.");
  const split = laatsteBody("/groepen/akkoord");
  assert.deepEqual([split.groep_ids, split.element_ids, split.aanpassing], [["G1"], ["e2"], { context: "Invordering van rijksbelastingen" }]);
  // De rest van de groep blijft als voorstel staan.
  await page.locator('[data-review-item="G1"]').getByText("1 al een begrip").waitFor();

  // 5. termijn afwijzen met x en een reden; daarna de rest van belastingschuldige met a.
  assert.equal(await actief().getAttribute("data-review-item"), "G4");
  await toets("x");
  await page.keyboard.type("Verschillende termijnen");
  await toets("Enter");
  await zie("Review – 4/5 beoordeeld");
  await page.evaluate(() => document.activeElement?.blur());
  assert.equal(await actief().getAttribute("data-review-item"), "G1");
  await toets("a");
  await zie("Review afgerond");
  await zie("Review – 5/5 beoordeeld");
  assert.deepEqual(laatsteBody("/groepen/akkoord").element_ids, undefined);

  // 6. Alles: het besluit staat er, en heropenen kan.
  await page.getByRole("button", { name: /^Alles/ }).click();
  await page.locator('[data-review-item="G4"]').click();
  await zie("afgewezen: Verschillende termijnen");
  await page.getByRole("button", { name: "Heropen groep “termijn”" }).click();
  await zie("Review – 4/5 beoordeeld");

  // 7. Opnieuw op dezelfde stand: niets te rekenen, en dat staat er.
  await page.getByRole("button", { name: "Opnieuw voorstellen" }).click();
  await zie("gelden al voor de huidige stand");

  // 8. Verouderd na een nieuwe annotatie; herladen tijdens een lopende run haakt aan.
  verouderd = true;
  actieveAgent = "ag2";
  const voor = requests.filter((r) => r.p === "/api/annotatie/run/ag2/events").length;
  await page.reload();
  await zie("Gebaseerd op een oudere stand van het werkgebied");
  assert.ok(requests.filter((r) => r.p === "/api/annotatie/run/ag2/events").length > voor, "aangehaakt op de lopende run");

  // 9. Een fout van Lex is zichtbaar.
  agentStroom.volgende = "ag3";
  await page.getByRole("button", { name: "Opnieuw voorstellen" }).click();
  await zie("De begrippenketen liep vast");

  // 10. Smal scherm.
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  await foto("voorstellen-mobiel");
  assert.deepEqual(errors, []);
  console.log("Browser OK: voorstellen starten en volgen, reviewlijst in volgorde, met alleen het toetsenbord: combineren via de vergelijking, concept → annotatie akkoord → definitie → geaccordeerd, vraag apart, splitsen + aanpassen → geaccordeerd, afwijzen, rest akkoord, review afgerond; heropenen, geen herberekening op dezelfde stand, verouderd, aanhaken na herladen, fout van Lex zichtbaar, smal scherm.");
} catch (e) {
  await foto("voorstellen-fout");
  throw e;
} finally { await browser.close(); }
