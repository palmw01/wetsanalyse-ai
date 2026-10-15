/** Browserregressie voor de strook "Voorstellen van Lex" (spoor D, levering 3a) op de echte Next-UI
 * met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-begripvoorstellen.mjs`.
 *
 * De mock gedraagt zich als api + graph-qa: een start geeft een run en een SSE-stroom (status →
 * opgeslagen → done), daarna staan de groepen er; besluiten volgen de regels van
 * api/app/begrippen_run_store.py (een besloten groep is niet nog eens over te nemen).
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
].map((g) => ({ ...g, besluit: "open", reden: "", begrip_id: null, besloten_door: null, lijkt_op: [] }));
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
const begripUit = (b) => ({ ...b, iri: `urn:wa:begrip:${b.id}`, werkgebied_id: "wg1", kader_iri: "urn:wa:kader:wg1",
  accorderen: { mag: false, redenen: ["Er is nog geen definitie."] }, aandachtspunten: [] });
function maakBegrip(naam, eids, definitie) {
  const id = `b${++teller}`;
  const alle = groepen.flatMap((g) => g.leden);
  begrippen.set(id, { id, status: "concept", revisie: 1, aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu,
    geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
    inhoud: { naam, alternatieve_termen: [], context: "", jas_klasse: "", jas_subtype: "", geldigheid: "", definitie: definitie ?? "",
      definitie_herkomst: definitie ? "letterlijk" : null, uitleg: "", onderbouwing: "", voorbeelden: [], eigenschappen: {}, open_vragen: [] },
    koppelingen: eids.map((e, i) => { const p = alle.find((l) => l.element_id === e); return { id: `k${id}${i}`, begrip_id: id, element_id: e,
      rol: "duiding", motivatie: "", beoordeling: "open", beoordeeld_door: null, beoordeeld_op: null, toegevoegd_door: "t", toegevoegd: nu,
      actualiteit: "actueel", lifecycle_nu: "human_approved", annotatie_beoordeeld: true,
      bewijs: { tekst: p.tekst, klasse: p.jas_klasse, ankers: [], eigenaar_iri: "urn:x", laag_id: "l", snapshot_id: "s",
        lifecycle: "human_approved", vindplaats: p.vindplaats, element_hash: "h" } }; }) });
  return begripUit(begrippen.get(id));
}
const groepenAntwoord = () => run?.status === "klaar"
  ? { run: { ...run, uitkomst }, groepen, passages } : { run: null, groepen: [], passages: {} };

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
  if (p === "/api/werkgebieden/wg1/groepen/overnemen") {
    const gs = groepen.filter((g) => body.groep_ids.includes(g.id));
    if (gs.some((g) => ["overgenomen", "gekoppeld"].includes(g.besluit)))
      return route.fulfill({ status: 409, json: { detail: { fout: "al_besloten", melding: "Een van deze groepen is al overgenomen of gekoppeld." } } });
    const leden = body.element_ids ?? gs.flatMap((g) => g.leden.map((l) => l.element_id));
    const defs = [...new Set(gs.map((g) => g.voorstel.definitie).filter(Boolean))];
    const b = maakBegrip(body.naam, leden, body.met_definitie && defs.length === 1 ? defs[0] : undefined);
    gs.forEach((g) => Object.assign(g, { besluit: "overgenomen", begrip_id: b.id }));
    return route.fulfill({ status: 201, json: b });
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
  const bm = p.match(/^\/api\/werkgebieden\/wg1\/begrippen\/(b\d+)$/);
  if (bm) return route.fulfill({ json: begripUit(begrippen.get(bm[1])) });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ status: 404, json: { detail: "Niet in deze test." } });
});

const foto = (naam) => process.env.SCREENSHOT_DIR
  ? page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/${naam}.png`, fullPage: true }) : null;
const zie = (tekst) => page.getByText(tekst, { exact: false }).first().waitFor();
const kaarten = () => page.getByRole("list", { name: "Voorgestelde groepen" });
const laatsteBody = (pad) => requests.filter((r) => r.p.endsWith(pad) && r.m === "POST").at(-1)?.body;
try {
  // 1. Zonder voorstellen: uitleg en de knop. Starten → stroom → groepen.
  await page.goto(`${base}/werkgebieden/wg1?tab=begrippen`);
  await zie("Een voorstel is een vraag aan jou, geen begrip.");
  // De tweede weg: met Lex in de werkplek, in de context van dit werkgebied (fase AF2).
  assert.equal(await page.getByRole("link", { name: "Bespreek met Lex" }).getAttribute("href"), "/workbench?werkgebied=wg1");
  await page.getByRole("button", { name: "Stel begrippen voor" }).click();
  await kaarten().waitFor();
  assert.equal(await kaarten().getByRole("listitem").filter({ has: page.getByRole("list") }).count(), 4);
  assert.ok(requests.some((r) => r.p === "/api/annotatie/run/ag1/events"), "de stroom van Lex is gevolgd");
  await zie("1 passage niet meegenomen");
  await zie("Brondefinitie (Artikel 2 · Lid 1 – IW 1990)");
  await zie("vraagt een oordeel");                                    // geel, met tekst
  // De twijfelvraag en de relatie letterlijk, ook met een passage buiten een groep.
  await zie("Horen “de aanslag” (Artikel 9 · Lid 1 – IW 1990) en “belastingaanslag” (Artikel 9 · Lid 1 – IW 1990) bij hetzelfde begrip?");
  await page.getByText("Relaties (1)").click();
  await zie("“de aansprakelijkgestelde” (Artikel 24 · Lid 1 – IW 1990) geldt als “de belastingschuldige”");
  await foto("voorstellen");

  // 2. Twijfelvraag "Samen" levert meteen een begrip op: beide passages plus hun open groepen.
  await page.getByRole("button", { name: /^Samen: Horen/ }).click();
  const naamVeld = page.getByRole("textbox", { name: /^Naam van het begrip uit: Horen/ });
  assert.equal(await naamVeld.inputValue(), "aanslag");                     // de naam van de groep
  await naamVeld.fill("Aanslag");
  await page.getByRole("button", { name: "Maak er één begrip van" }).click();
  await page.waitForURL(/begrip=b\d/);
  const combi = laatsteBody("/groepen/overnemen");
  assert.deepEqual([combi.groep_ids, combi.naam, combi.element_ids], [["G2", "G3"], "Aanslag", ["e3", "e4", "e6", "e7"]]);
  assert.equal(laatsteBody("/vragen/P1").antwoord, "samen");
  await page.getByRole("article", { name: "Begrip Aanslag" }).waitFor();

  // 3. Overnemen met splitsen: één lid uitvinken; de letterlijke definitie gaat mee.
  await page.getByRole("button", { name: "Neem groep “belastingschuldige” over als begrip" }).click();
  await page.getByRole("checkbox", { name: "Neem “belastingschuldige” mee" }).uncheck();
  await page.getByRole("button", { name: "Overnemen (1 van 2)" }).click();
  await page.getByRole("article", { name: "Begrip belastingschuldige" }).waitFor();
  const split = laatsteBody("/groepen/overnemen");
  assert.deepEqual([split.groep_ids, split.element_ids, split.met_definitie], [["G1"], ["e2"], true]);
  // Prefix, geen exacte naam: een label om een tekstveld neemt de inhoud van het veld op in de naam.
  assert.equal(await page.getByRole("article", { name: "Begrip belastingschuldige" }).getByRole("textbox", { name: /^Definitie/ }).inputValue(),
    "degene die de belasting verschuldigd is");

  // 4. Afwijzen met reden, en heropenen.
  await page.getByRole("button", { name: "Wijs groep “termijn” af" }).click();
  await page.getByRole("textbox", { name: /Reden om groep “termijn” af te wijzen/ }).fill("Verschillende termijnen");
  await page.getByRole("button", { name: "Afwijzen", exact: true }).click();
  await zie("afgewezen: Verschillende termijnen");
  await page.getByRole("button", { name: "Heropen groep “termijn”" }).click();
  await page.getByRole("button", { name: "Wijs groep “termijn” af" }).waitFor();

  // 5. Opnieuw op dezelfde stand: niets te rekenen, en dat staat er.
  await page.getByRole("button", { name: "Opnieuw voorstellen" }).click();
  await zie("gelden al voor de huidige stand");

  // 6. Verouderd na een nieuwe annotatie; herladen tijdens een lopende run haakt aan.
  verouderd = true;
  actieveAgent = "ag2";
  const voor = requests.filter((r) => r.p === "/api/annotatie/run/ag2/events").length;
  await page.reload();
  await zie("Gebaseerd op een oudere stand van het werkgebied");
  assert.ok(requests.filter((r) => r.p === "/api/annotatie/run/ag2/events").length > voor, "aangehaakt op de lopende run");

  // 7. Een fout van Lex is zichtbaar.
  agentStroom.volgende = "ag3";
  await page.getByRole("button", { name: "Opnieuw voorstellen" }).click();
  await zie("De begrippenketen liep vast");

  // 8. Smal scherm.
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  await foto("voorstellen-mobiel");
  assert.deepEqual(errors, []);
  console.log("Browser OK: voorstellen starten en volgen, groepen met definitie en aandacht, twijfelvraag en relatie letterlijk, samen → één begrip, splitsen met letterlijke definitie, afwijzen en heropenen, geen herberekening op dezelfde stand, verouderd, aanhaken na herladen, fout van Lex zichtbaar, smal scherm.");
} catch (e) {
  await foto("voorstellen-fout");
  throw e;
} finally { await browser.close(); }
