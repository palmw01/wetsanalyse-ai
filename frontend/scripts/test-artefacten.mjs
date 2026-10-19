/** Browserregressie voor het artefactmodel van de werkplek (spoor D, fase AF): één `artefact` per
 * beurt, met een chip en een paneel per soort. Op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-artefacten.mjs`.
 *
 * Bewaakt:
 *  - een bewaard begrippenartefact komt na herladen terug als chip en opent de voorstellen van Lex
 *    in het artefactpaneel (kolom naast de chat), met de link naar het werkgebied;
 *  - een annotatie-artefact in de nieuwe vorm (alleen `artefact`, geen `annotatie_doel`) opent de
 *    annotatie, en het sluit het begrippenpaneel – er staat er één open;
 *  - afleidingsregels zijn gereserveerd: de kaart staat er, maar is geen knop;
 *  - de balk boven de chat brengt het laatste artefact terug, ook als dat begrippen zijn;
 *  - een live beurt waarvan het `opgeslagen`-event een begrippenartefact draagt, opent dat paneel;
 *  - vanuit een werkgebied (`?werkgebied=`): de balk noemt het werkgebied, *Stel begrippen voor* stuurt
 *    een beurt mét `werkgebied_id`, en na *Verlaten* draagt een beurt het niet meer (fase AF2).
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [], runs = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-15T10:00:00+00:00";
const doel = { bron_iri: "urn:lid1", label: "Invorderingswet – artikel 9 lid 1", snapshot_id: "snapshot" };
const view = { schema_versie: 2, doel: { ...doel, type: "Lid", bwb_id: "BWBR0004770", artikel: "9", lid: "1", citeertitel: "Invorderingswet 1990" },
  snapshot_id: "snapshot",
  segmenten: [{ bron_iri: "urn:lid1", parent_iri: "urn:artikel9", type: "Lid", nummer: "1", label: "Lid 1",
    tekst: "De ontvanger stelt de belastingschuldige in kennis.", bron_hash: "hash1", volgorde: 1 }],
  lagen: [{ id: "laag1", bron_iri: "urn:lid1", status: "in_review", revisie: 1 }],
  elementen: [], verwijzingen: [], dekking: {} };
const begrippenArtefact = { soort: "begrippen", ref: { werkgebied_id: "wg1", run_id: "r1" }, titel: "Invordering" };
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const gesprekken = {
  g1: [
    { rol: "user", tekst: "Annoteer artikel 9 lid 1", ...leeg },
    { rol: "assistant", tekst: "", ...leeg, run_id: "a1",
      artefact: { soort: "annotatie", ref: doel, titel: "Invorderingswet – artikel 9 lid 1" } },
    { rol: "user", tekst: "Stel begrippen voor", ...leeg },
    { rol: "assistant", tekst: "Ik stel 1 begrip voor.", ...leeg, run_id: "b1", artefact: begrippenArtefact },
    { rol: "assistant", tekst: "", ...leeg, run_id: "c1", artefact: { soort: "regels", ref: {}, titel: "Regels bij invordering" } },
  ],
  // Een kaartactie vanuit het gesprek (fase F4): het artefact wijst naar één begrip.
  g3: [
    { rol: "user", tekst: "Geef voorbeelden van termijn", ...leeg },
    { rol: "assistant", tekst: "Voorbeelden voor *Termijn*: 2 voorstellen staan bij de voorbeelden op de begripskaart.", ...leeg,
      run_id: "k1", artefact: { soort: "begrippen", titel: "Termijn",
        ref: { werkgebied_id: "wg1", begrip_id: "b9", kaart_run_id: "kr1", actie: "voorbeelden" } } },
  ],
};
const LEEG = { naam: "", alternatieve_termen: [], context: "", jas_klasse: "", jas_subtype: "", geldigheid: "", definitie: "",
  definitie_herkomst: null, definitie_door: "", uitleg: "", onderbouwing: "", voorbeelden: [], eigenschappen: {}, open_vragen: [] };
const termijn = { id: "b9", iri: "urn:wa:begrip:b9", werkgebied_id: "wg1", kader_iri: "urn:wa:kader:wg1", status: "concept", revisie: 1,
  inhoud: { ...LEEG, naam: "Termijn", definitie: "Een tijdvak." }, koppelingen: [], aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu,
  geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
  accorderen: { mag: false, redenen: ["De context ontbreekt."] }, aandachtspunten: [], vervangen_door: null, vervangt: [] };
const P = (id, tekst) => ({ element_id: id, tekst, jas_klasse: "Rechtssubject", review_status: "human_approved", bron_iri: "urn:x",
  vindplaats: "Artikel 9 · Lid 1 – IW 1990" });
const groep = { id: "G1", aandacht: "groen", voorstel: { naam: "belastingschuldige" }, uitleg: [], conflicten: [],
  leden: [P("e1", "belastingschuldige"), P("e2", "de belastingschuldige")], besluit: "open", reden: "", begrip_id: null,
  besloten_door: null, lijkt_op: [] };
const run = { id: "r1", werkgebied_id: "wg1", manifest_id: "M1", status: "klaar", reden: "", aantal_formuleringen: 2, overgeslagen: [],
  uitkomst: { groep_ids: ["G1"], meting: {}, vragen: [], relaties: [] }, vragen_besluiten: {}, gestart_door: "t", gestart: nu, gewijzigd: nu };
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/annotatie/run") {
    if (m === "GET") return route.fulfill({ json: null });
    runs.push(req.postDataJSON());
    return route.fulfill({ json: { run_id: "live", conversation_id: req.postDataJSON().conversation_id, status: "loopt" } });
  }
  if (p === "/api/annotatie/run/live/events") {
    return route.fulfill({ contentType: "text/event-stream", body: sse([
      { type: "token", content: "Ik stel 1 begrip voor." },
      { type: "opgeslagen", run_id: "live", artefact: { ...begrippenArtefact, titel: "Live voorstellen" } },
      { type: "done" }]) });
  }
  if (p.endsWith("/weergave")) return route.fulfill({ json: view });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: { id: "wg1", naam: "Invordering", revisie: 1, bronnen: [] } });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run } });
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: { run, groepen: [groep], passages: {} } });
  if (p === "/api/begrippen-run") return route.fulfill({ json: null });
  if (p === "/api/werkgebieden/wg1/begrippen" && m === "GET")
    return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", begrippen: [], primair: {} } });
  if (p === "/api/werkgebieden/wg1/begrippen/b9") return route.fulfill({ json: termijn });
  if (p === "/api/werkgebieden/wg1/begrippen/b9/voorstellen")
    return route.fulfill({ json: { voorstellen: [], runs: {}, schatting: {}, budget: null } });
  if (p === "/api/kaart-run") return route.fulfill({ json: null });
  const gesprek = p.match(/^\/api\/gesprekken\/(g\d)$/);
  if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: "Test", berichten: gesprekken[gesprek[1]] ?? [] } });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g2", titel: "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Test", aantal_berichten: 5 }] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: p.endsWith("/berichten") && m === "POST" ? { id: 1 } : [] });
});

// In de kolomvariant is het paneel een `section` met een naam (niet modaal), dus de rol `region`.
const begrippenPaneel = () => page.getByRole("region", { name: /^Begripsvoorstellen:/ });
const begrippenChip = () => page.locator('button[data-artefact-soort="begrippen"]');

try {
  // --- Na herladen: drie soorten, elk met zijn eigen kaart ---
  await page.goto(`${base}/workbench?gesprek=g1`);
  await begrippenChip().waitFor();
  assert.match(await begrippenChip().innerText(), /Invordering[\s\S]*Begripsvoorstellen/);
  const regels = page.locator('[data-artefact-soort="regels"]');
  assert.equal(await regels.count(), 1, "de kaart van de afleidingsregels hoort er te staan");
  assert.equal(await regels.evaluate((el) => el.tagName), "DIV", "afleidingsregels zijn nog niet te openen: geen knop");
  assert.match(await regels.innerText(), /nog niet te openen/);

  // --- Begrippen openen: de voorstellen van Lex in het paneel ---
  await begrippenChip().click();
  await begrippenPaneel().waitFor();
  await begrippenPaneel().getByText("belastingschuldige", { exact: true }).first().waitFor();
  assert.equal(await begrippenPaneel().getByText("eerdere ronde van Lex", { exact: false }).count(), 0,
    "de chip wijst naar de laatste ronde: geen melding");
  assert.equal(await begrippenPaneel().getByRole("link", { name: "Open het werkgebied" }).getAttribute("href"),
    "/werkgebieden/wg1?tab=begrippen");
  assert.equal(await begrippenPaneel().locator('button[aria-expanded]').filter({ hasText: "Voorstellen van Lex" }).count(), 0,
    "in het paneel is de strook niet in te klappen");
  // De review werkt in het paneel met het toetsenbord (fase D) – maar niet zolang de focus in het gesprek
  // staat (op de chip): pas met de focus in het paneel kiest j het eerste voorstel en klapt het uit.
  await page.keyboard.press("j");
  assert.equal(await begrippenPaneel().locator("[data-review-item][aria-current=true]").count(), 0,
    "een toets vanuit het gesprek doet niets in het paneel");
  await begrippenPaneel().getByText(/^Review – /).click();
  await page.keyboard.press("j");
  await begrippenPaneel().locator('[data-review-item="G1"][aria-current=true]').waitFor();
  await begrippenPaneel().getByRole("button", { name: /^Akkoord.*groep “belastingschuldige”/ }).waitFor();

  // --- Een annotatie openen sluit de begrippen: er staat één artefact open ---
  await page.locator("button", { hasText: "Invorderingswet – artikel 9 lid 1" }).first().click();
  await page.locator('[data-tour="wettekst"]').waitFor();
  assert.equal(await begrippenPaneel().count(), 0, "het begrippenpaneel hoort dicht te gaan");

  // --- Dicht: de balk brengt het laatste artefact terug (de begrippen staan het laatst) ---
  await page.getByRole("button", { name: "Sluiten" }).first().click();
  const balk = page.locator("button", { hasText: "· begripsvoorstellen" });
  await balk.waitFor();
  // Intussen deed Lex een nieuwe ronde: het paneel toont die, en zegt dat de chip ouder is.
  run.id = "r2";
  await balk.click();
  await begrippenPaneel().waitFor();
  await begrippenPaneel().getByText("Dit gesprek wijst naar een eerdere ronde van Lex", { exact: false }).waitFor();
  run.id = "r1";
  await begrippenPaneel().getByRole("button", { name: "Sluiten" }).click();
  await balk.waitFor();

  // --- Eén begrip (fase F4): de chip heet "Begrip" en opent de kaart in het paneel ---
  await page.goto(`${base}/workbench?gesprek=g3`);
  const begripChip = page.locator('button[data-artefact-soort="begrippen"]', { hasText: "Termijn" });
  await begripChip.waitFor();
  assert.match(await begripChip.innerText(), /Termijn[\s\S]*Begrip · beoordelen/);
  await begripChip.click();
  const begripPaneel = page.getByRole("region", { name: "Begrip: Termijn" });
  await begripPaneel.waitFor();
  await begripPaneel.getByRole("button", { name: /Bedenk voorbeelden/ }).waitFor();
  assert.equal(await begripPaneel.getByRole("link", { name: "Open het werkgebied" }).getAttribute("href"),
    "/werkgebieden/wg1?tab=begrippen&begrip=b9");
  // Onbewaarde wijzigingen op de kaart: sluiten vraagt eerst, net als een tabwissel in het werkgebied.
  await begripPaneel.getByLabel(/^Uitleg/).fill("Nog niet bewaard");
  await begripPaneel.getByRole("button", { name: "Sluiten" }).first().click();
  await begripPaneel.getByRole("button", { name: "Blijf hier" }).click();
  assert.equal(await begripPaneel.getByLabel(/^Uitleg/).inputValue(), "Nog niet bewaard");
  await begripPaneel.getByRole("button", { name: "Sluiten" }).first().click();
  await begripPaneel.getByRole("button", { name: "Toch sluiten" }).click();
  await page.locator("button", { hasText: "· begrip" }).waitFor();

  // --- Live: een beurt die begrippen oplevert, opent het paneel ---
  await page.goto(`${base}/workbench`);
  const invoer = page.getByRole("textbox").last();
  await invoer.fill("Stel begrippen voor");
  await invoer.press("Enter");
  await page.getByRole("region", { name: "Begripsvoorstellen: Live voorstellen" }).waitFor();
  await page.locator('button[data-artefact-soort="begrippen"]', { hasText: "Live voorstellen" }).waitFor();

  // --- Vanuit een werkgebied: de context reist mee met elke beurt ---
  runs.length = 0;
  await page.goto(`${base}/workbench?werkgebied=wg1`);
  const balk2 = page.locator("[data-werkgebied=wg1]");
  await balk2.getByRole("link", { name: "Invordering" }).waitFor();
  await balk2.getByRole("button", { name: "Stel begrippen voor" }).click();
  await page.getByRole("region", { name: "Begripsvoorstellen: Live voorstellen" }).waitFor();
  assert.equal(runs[0]?.werkgebied_id, "wg1", "de beurt hoort het werkgebied te dragen");
  assert.equal(runs[0]?.question, "Stel begrippen voor");
  await balk2.getByRole("button", { name: /Uit de context/ }).click();
  await balk2.waitFor({ state: "detached" });
  assert.ok(!new URL(page.url()).searchParams.has("werkgebied"), "verlaten haalt het werkgebied uit de URL");
  const invoer2 = page.getByRole("textbox").last();
  await invoer2.fill("Stel begrippen voor");
  await invoer2.press("Enter");
  for (let i = 0; i < 50 && runs.length < 2; i++) await page.waitForTimeout(100);
  assert.equal(runs[1]?.werkgebied_id, undefined, "na verlaten draagt een beurt geen werkgebied meer");

  assert.deepEqual(errors, []);
  console.log("Browser OK: begrippenartefact na herladen en live, één artefact tegelijk, laatste-artefactbalk, regels gereserveerd, werkgebiedcontext in de werkplek.");
} finally {
  await browser.close();
}
