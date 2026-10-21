/** Browserregressie voor "Lex denkt mee" (spoor D, fase C) op de echte Next-UI met een gemockte BFF.
 * Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-begrippen-verdieping.mjs`.
 *
 * De mock gedraagt zich als api + graph-qa: een run met `modus: "begrippen_verdiepen"` + `bevestigd` levert
 * een stroom met een begrippenartefact (`tools/graph-qa/agent/begrippen_verdieping.py`); daarna dragen de
 * groepen een kaart en de vragen een advies. Het aanbod en de bevestiging staan sinds F3e alleen in het
 * gesprek (de suggestie *Denk mee over de begrippen*, dan de knop bij het voorstel van Lex).
 *
 * Bewaakt:
 *  - op de tab Begrippen geen aanbod en geen knop om mee te denken; `?meedenk=` start niets;
 *  - de knop bij een voorstel van Lex in het gesprek start het meedenken met het bevestigde aantal;
 *  - na het meedenken: advies bij de twijfelvraag (die blijft staan), een groep op advies van Lex, de
 *    herkomst van de definitie en de aandachtspunten;
 *  - akkoord op een groep met een definitie die Lex formuleerde (de review van fase D).
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
await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-15T10:00:00+00:00";
const wg = { id: "wg1", naam: "Invorderbaarheid", analysevraag: "", afbakening: "", peildatum: null, status: "actief", revisie: 2,
  aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null, bronnen: [] };
const P = (id, tekst, vindplaats = "Artikel 9 · Lid 1 – IW 1990") =>
  ({ element_id: id, tekst, jas_klasse: "Rechtsobject", review_status: "human_approved", bron_iri: "urn:x", vindplaats });
const vraag = (k, van, naar) => ({ kandidaat_id: k, van, naar, regel: "Z-ANDERS", uitleg: ["voor (zwak): Zelfde term"] });
const run = { id: "r1", werkgebied_id: "wg1", manifest_id: "M1", status: "klaar", reden: "", aantal_formuleringen: 8, overgeslagen: [],
  uitkomst: { groep_ids: ["G1"], meting: {}, relaties: [], vragen: [vraag("P1", "e3", "e5"), vraag("P2", "e7", "e8")] },
  vragen_besluiten: {}, gestart_door: "t", gestart: nu, gewijzigd: nu };
const passages = { e3: P("e3", "termijnen", "Artikel 9 · Lid 5 – IW 1990"), e5: P("e5", "termijnen", "Artikel 9 · Lid 10 – IW 1990"),
  e7: P("e7", "de aanslag"), e8: P("e8", "aanslag", "Artikel 4 · Lid 1 – AWR") };
const fr = { id: "F0123456789", bron_iri: "urn:x", start: 0, eind: 12, tekst: "de beschikking" };
const groep = (id, leden, over = {}) => ({ id, aandacht: "groen", voorstel: { naam: id === "G1" ? "aanslagbiljet" : "aanslag" },
  uitleg: [], conflicten: [], besluit: "open", reden: "", begrip_id: null, besloten_door: null, lijkt_op: [], leden, ...over });
let verdiept = false;
const groepen = () => verdiept
  ? [groep("G1", [P("e1", "aanslagbiljet"), P("e2", "het aanslagbiljet")], { aandacht: "geel", door: "regel",
      kaart: { groep_id: "G1", naam: "aanslagbiljet", alternatieve_termen: [], begripstype: "entiteit", begripstype_door: "regel",
        context: "Komt voor in Artikel 9 · Lid 1 – IW 1990.", definitie: "Het document waarmee de aanslag wordt bekendgemaakt.",
        herkomst: "geformuleerd", definitie_bron_iri: "", definitie_vindplaats: "", fragmenten: [fr], motivatie: "Uit lid 1.",
        aandacht: "geel", aandachtspunten: ["DOOR_LEX_GEFORMULEERD"] } }),
    groep("GM", [passages.e7, passages.e8], { aandacht: "geel", door: "model", kaart: null })]
  : [groep("G1", [P("e1", "aanslagbiljet"), P("e2", "het aanslagbiljet")])];
const groepenAntwoord = () => ({ run, groepen: groepen(), passages,
  verdieping: verdiept ? { vragen_open: ["P1"], model: "m", op: nu,
    oordelen: { P1: { kandidaat_id: "P1", oordeel: "verwant_ander_begrip", motivatie: "Lid 10 noemt alle termijnen.", reden: "" },
      P2: { kandidaat_id: "P2", oordeel: "zelfde_betekenis", motivatie: "Beide de aanslag.", reden: "" } } } : null });
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const artefact = { soort: "begrippen", titel: "Invorderbaarheid", ref: { werkgebied_id: "wg1", run_id: "r1" } };
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const gesprekken = {
  g2: [
    { rol: "user", tekst: "Stel begrippen voor", ...leeg },
    { rol: "assistant", tekst: "Ik stel **1** begrip voor. Wil je dat ik meedenk over 2 twijfelpunten?", ...leeg, run_id: "v1",
      bevestiging: { soort: "begrippen_verdiepen", werkgebied_id: "wg1", aantal: 3, schatting: 2400 } },
  ],
  g9: [],
};
const starts = [];
let overname = null;

await context.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  requests.push({ p, m, body });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: groepenAntwoord() });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run: { ...run, verouderd: false } } });
  if (p === "/api/werkgebieden/wg1/groepen/akkoord") {
    overname = body;
    return route.fulfill({ status: 409, json: { detail: { fout: "test", melding: "Overname vastgelegd door de test." } } });
  }
  if (p === "/api/werkgebieden/wg1/begrippen") return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", primair: {}, begrippen: [] } });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g9", titel: body?.titel ?? "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g2", titel: "Voorstel", aantal_berichten: 2 }] });
  const gesprek = p.match(/^\/api\/gesprekken\/(g\d)$/);
  if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: "Test", berichten: gesprekken[gesprek[1]] ?? [] } });
  if (p === "/api/annotatie/run" && m === "POST") {
    starts.push(body);
    return route.fulfill({ status: 201, json: { run_id: `w${starts.length}`, conversation_id: body.conversation_id, status: "loopt" } });
  }
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  const events = p.match(/\/run\/([^/]+)\/events$/);
  if (events) {
    if (events[1] === "w1") verdiept = true;
    return route.fulfill({ contentType: "text/event-stream", body: sse(events[1] === "w1" ? [
      { type: "status", message: "Lex · Twijfelpunten 1/1" }, { type: "status", message: "Lex · Begripskaarten 1/1" },
      { type: "token", content: "Klaar met meedenken in werkgebied *Invorderbaarheid*." },
      { type: "opgeslagen", run_id: "w1", artefact }, { type: "done" }] : [{ type: "done" }]) });
  }
  if (p.startsWith("/api/werkgebieden/wg1/")) return route.fulfill({ json: {} });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: p.endsWith("/berichten") && m === "POST" ? { id: 1 } : [] });
});

const zie = (tekst, pg = page) => pg.getByText(tekst, { exact: false }).first().waitFor();
try {
  // --- De tab Begrippen: geen aanbod en geen knop; meedenken vraag je Lex in het gesprek ---
  await page.goto(`${base}/werkgebieden/wg1?tab=begrippen`);
  await page.locator("[data-begripvoorstellen]").waitFor();
  await page.locator("[data-review-item]").first().waitFor();
  assert.equal(await page.locator("[data-meedenk-aanbod]").count(), 0);
  assert.equal(await page.getByRole("button", { name: /^Laat Lex meedenken/ }).count(), 0);

  // --- `?meedenk=` start niets meer ---
  await page.goto(`${base}/workbench?werkgebied=wg1&meedenk=3`);
  await page.getByTestId("vraag-suggesties").getByRole("button", { name: "Denk mee over de begrippen" }).waitFor();
  await page.waitForTimeout(300);
  assert.equal(starts.length, 0, "Lex begint niet vanuit de URL");

  // --- Een voorstel van Lex in het gesprek: de knop start het meedenken, met het bevestigde aantal ---
  await page.goto(`${base}/workbench?gesprek=g2`);
  await page.getByRole("button", { name: "Laat Lex meedenken (3)" }).click();
  await zie("Klaar met meedenken in werkgebied");
  assert.equal(starts.length, 1);
  assert.deepEqual({ modus: starts[0].modus, bevestigd: starts[0].bevestigd, werkgebied_id: starts[0].werkgebied_id,
    conversation_id: starts[0].conversation_id },
  { modus: "begrippen_verdiepen", bevestigd: 3, werkgebied_id: "wg1", conversation_id: "g2" });

  // --- Na het meedenken: advies, groep op advies van Lex, herkomst en aandachtspunten ---
  await page.goto(`${base}/werkgebieden/wg1?tab=begrippen`);
  await zie("Lex dacht mee");
  // De review: de twijfelvraag die open bleef, met het advies van Lex.
  assert.deepEqual(await page.locator("[data-review-item]").evaluateAll((els) => els.map((e) => e.dataset.reviewItem)),
    ["GM", "G1", "P1"], "alleen de vraag die open bleef staat in de review");
  await page.locator('[data-review-item="P1"]').click();
  await zie("Advies van Lex: verwant, maar een ander begrip");
  await zie("Lid 10 noemt alle termijnen.");
  assert.equal(await page.locator("[data-advies]").count(), 1);
  await zie("samengevoegd op advies van Lex");
  await page.locator('[data-review-item="G1"]').click();
  await zie("Definitie, geformuleerd door Lex:");
  await zie("De definitie is door Lex geformuleerd; toets haar aan de passages.");
  await page.getByText("Rust op 1 passage uit de bron").click();
  await zie("“de beschikking”");

  // --- Akkoord op de groep: de definitie van Lex gaat mee ---
  await page.getByRole("button", { name: "Akkoord: groep “aanslagbiljet”" }).click();
  await zie("Overname vastgelegd door de test.");
  assert.deepEqual([overname.groep_ids, overname.met_definitie], [["G1"], true]);

  assert.deepEqual(errors, []);
  console.log("Browser OK: geen aanbod op de tab, meedenk= start niets, de knop in het gesprek met het bevestigde aantal, advies bij de open twijfelvraag, groep op advies van Lex, herkomst en aandachtspunten van de kaart, akkoord met een geformuleerde definitie.");
} finally {
  await browser.close();
}
