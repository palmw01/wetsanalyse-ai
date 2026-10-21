/** Browserregressie voor het artefactmodel van de werkplek (spoor D, fase AF): één `artefact` per
 * beurt, met een chip en een paneel per soort. Op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-artefacten.mjs`.
 *
 * Bewaakt:
 *  - een bewaard begrippenartefact komt na herladen terug als chip en opent de voorstellen van Lex
 *    in het artefactpaneel (kolom naast de chat), met de link naar het werkgebied en zonder Lex-knoppen;
 *  - een annotatie-artefact in de nieuwe vorm (alleen `artefact`, geen `annotatie_doel`) opent de
 *    annotatie, en het sluit het begrippenpaneel – er staat er één open;
 *  - afleidingsregels zijn gereserveerd: de kaart staat er, maar is geen knop;
 *  - de balk boven de chat brengt het laatste artefact terug, ook als dat begrippen zijn;
 *  - een live beurt waarvan het `opgeslagen`-event een begrippenartefact draagt, opent dat paneel;
 *  - één begrip (F3d): de chip heet *Begrip*, het paneel is de leesweergave zonder Lex-knoppen, een open
 *    voorstel van Lex wordt er overgenomen, en een eigen bewerking vraagt bevestiging bij sluiten;
 *  - vanuit een werkgebied (`?werkgebied=`): de balk noemt het werkgebied en heeft geen actieknoppen meer;
 *    de suggestie *Stel begrippen voor* boven het invoerveld stuurt een beurt mét `werkgebied_id` en de
 *    actie `begrippen_voorstellen`, en na *Verlaten* draagt een beurt het niet meer (fase AF2, F3c, F3d);
 *  - één deelvraag (F3d): *Vraag Lex* bij de deelvraag → *Formuleer scherper* stuurt de actie met het
 *    onderwerp → het deelvraagpaneel opent met het voorstel dat haar vervangt → *Overnemen* → na herladen
 *    zegt het paneel dat ze vervangen is en opent het de opvolger; de kandidaat bij de deelvraag staat erin.
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
  // Een werkgebied dat Lex samenstelde (activiteit 1): verwijderen kan in het paneel.
  g5: [
    { rol: "assistant", tekst: "Werkgebied *Invordering* is aangemaakt.", ...leeg, run_id: "w1",
      artefact: { soort: "werkgebied", titel: "Invordering", ref: { werkgebied_id: "wg1" } } },
  ],
  // Een kaartactie vanuit het gesprek (fase F4): het artefact wijst naar één begrip.
  g3: [
    { rol: "user", tekst: "Geef voorbeelden van termijn", ...leeg },
    { rol: "assistant", tekst: "Voorbeelden voor *Termijn*: 2 voorstellen staan bij de voorbeelden op de begripskaart.", ...leeg,
      run_id: "k1", artefact: { soort: "begrip", titel: "Termijn",
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
// Eén open voorstel van Lex op de definitie van termijn; overnemen zet het in het begrip.
const kaartVoorstellen = [{ id: "v1", begrip_id: "b9", run_id: "kr1", actie: "scherper", veld: "definitie", volgorde: 0,
  basis: { definitie: "Een tijdvak." }, waarde: { definitie: "Het tijdvak waarbinnen betaald moet zijn.", herkomst: "geformuleerd",
    fragmenten: [], toelichting: "" }, aandacht: "geel", aandachtspunten: [], status: "open", reden: "", besloten_door: null,
  besloten_op: null, verouderd: false }];
// Het werkgebied met een deelvraag; *Formuleer scherper* laat Lex een verbetering voorstellen (d2 vervangt d1).
const dv = (id, vraag, status, extra = {}) => ({ id, vraag, volgorde: id === "d1" ? 0 : 1, status, herkomst: status === "voorgesteld" ? "lex" : "analist",
  reden: "", vervangt: "", aangemaakt_door: "t", aangemaakt: nu, bronnen: [], begrippen: [], ...extra });
const wg1 = { id: "wg1", naam: "Invordering", revisie: 1, analysevraag: "Wanneer is een aanslag invorderbaar?",
  bronnen: [{ id: "s1", bron_iri: "urn:lid1", label: "art. 9 lid 1 Iw", rol: "analyseren", bereik: "precies" }],
  deelvragen: [dv("d1", "Wie betaalt?", "actief", { bronnen: ["s1"] })] };
const alleDv = {};
const dvDetail = (id) => {
  const d = alleDv[id] ?? wg1.deelvragen.find((x) => x.id === id);
  const verwant = wg1.deelvragen.filter((x) => x.vervangt === id);
  return { ...d, opvolgers: verwant.filter((x) => x.status === "actief").map((x) => ({ id: x.id, vraag: x.vraag })),
    voorstellen: verwant.filter((x) => x.status === "voorgesteld") };
};
const kandidaat = { id: "k1", bron_iri: "urn:art10", label: "art. 10 Iw", bwb_id: "BWBR0004770", rol: "kern",
  bewijs: [{ methode: "deelvraag", vanuit: "", detail: { deelvraag_id: "d1", vraag: "Wie betaalt?" } }], status: "voorgesteld",
  reden: "", run_id: "br1", in_laatste_run: true, in_selectie: false, besloten_door: null, besloten_op: null };
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
    const laatste = runs[runs.length - 1];
    if (laatste?.actie === "deelvraag_herformuleren") {
      // graph-qa: de verbetering landt als voorstel dat d1 vervangt, en het bericht draagt het deelvraagartefact.
      if (!wg1.deelvragen.some((d) => d.id === "d2"))
        wg1.deelvragen.push(dv("d2", "Wie is de belastingschuldige?", "voorgesteld", { vervangt: "d1" }));
      const artefact = { soort: "deelvraag", ref: { werkgebied_id: "wg1", deelvraag_id: "d1" }, titel: "Wie betaalt?" };
      (gesprekken.g2 ??= []).push({ rol: "assistant", tekst: "Ik stel een scherpere formulering voor.", ...leeg, run_id: "dv", artefact });
      return route.fulfill({ contentType: "text/event-stream", body: sse([
        { type: "token", content: "Ik stel een scherpere formulering voor." },
        { type: "opgeslagen", run_id: "live", artefact }, { type: "done" }]) });
    }
    return route.fulfill({ contentType: "text/event-stream", body: sse([
      { type: "token", content: "Ik stel 1 begrip voor." },
      { type: "opgeslagen", run_id: "live", artefact: { ...begrippenArtefact, titel: "Live voorstellen" } },
      { type: "done" }]) });
  }
  if (p.endsWith("/weergave")) return route.fulfill({ json: view });
  // Verwijderd: een 404 met wanneer en door wie, zoals de api (`werkgebied_store.niet_gevonden`).
  const weg = (soort) => route.fulfill({ status: 404, json: { detail: { fout: "verwijderd", soort, op: nu, door: "t",
    melding: "Is verwijderd." } } });
  if (p === "/api/werkgebieden/wg1" && m === "DELETE") {
    assert.equal(url.searchParams.get("verwachte_revisie"), String(wg1.revisie));
    wg1.verwijderd = true;
    return route.fulfill({ json: { verwijderd: "wg1" } });
  }
  if (p === "/api/werkgebieden/wg1") return wg1.verwijderd ? weg("werkgebied") : route.fulfill({ json: wg1 });
  if (p === "/api/werkgebieden/wg1/begrippen/b9" && m === "DELETE") {
    assert.equal(url.searchParams.get("verwachte_revisie"), String(termijn.revisie));
    termijn.verwijderd = true;
    return route.fulfill({ json: { verwijderd: "b9", hersteld: [] } });
  }
  if (p === "/api/werkgebieden/wg1/begrippen/b9" && termijn.verwijderd) return weg("begrip");
  if (p === "/api/werkgebieden/wg1/deelvragen/dekking") {
    const actief = wg1.deelvragen.filter((d) => d.status === "actief");
    return route.fulfill({ json: { deelvragen: actief.map((d) => ({ id: d.id, vraag: d.vraag, stand: d.bronnen.length ? "geen_begrip" : "geen_bron",
      bronnen: d.bronnen.map((b) => ({ id: b, label: "art. 9 lid 1 Iw" })), begrippen: [] })),
      telling: { gedekt: 0, geen_begrip: 1, geen_bron: 0 }, totaal: actief.length } });
  }
  const deelvraag = p.match(/^\/api\/werkgebieden\/wg1\/deelvragen\/(d\d)$/);
  if (deelvraag && m === "GET") return route.fulfill({ json: dvDetail(deelvraag[1]) });
  if (deelvraag && m === "PATCH") {
    // De api: overnemen van een verbetering vervangt de oude, op haar plek en met haar koppelingen.
    const body = req.postDataJSON(), d = wg1.deelvragen.find((x) => x.id === deelvraag[1]);
    assert.equal(body.verwachte_revisie, wg1.revisie);
    const oud = wg1.deelvragen.find((x) => x.id === d.vervangt);
    Object.assign(d, { status: body.status, volgorde: oud.volgorde, bronnen: [...oud.bronnen] });
    alleDv[oud.id] = { ...oud, status: "vervangen" };
    wg1.deelvragen = wg1.deelvragen.filter((x) => x !== oud);
    wg1.revisie += 1;
    return route.fulfill({ json: wg1 });
  }
  if (p === "/api/werkgebieden/wg1/kandidaten") return route.fulfill({ json: { kandidaten: [kandidaat], run: null } });
  if (p === "/api/werkgebieden/wg1/bronnen-runs/laatste") return route.fulfill({ json: { run: null } });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run } });
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: { run, groepen: [groep], passages: {} } });
  if (p === "/api/werkgebieden/wg1/begrippen" && m === "GET")
    return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", begrippen: [], primair: {} } });
  if (p === "/api/werkgebieden/wg1/begrippen/b9") return route.fulfill({ json: termijn });
  if (p === "/api/werkgebieden/wg1/begrippen/b9/voorstellen")
    return route.fulfill({ json: { voorstellen: kaartVoorstellen, runs: {}, schatting: {}, budget: null } });
  if (p === "/api/werkgebieden/wg1/begrippen/b9/voorstellen/v1/overnemen" && m === "POST") {
    assert.equal(req.postDataJSON().verwachte_revisie, termijn.revisie);
    kaartVoorstellen[0].status = "overgenomen";
    Object.assign(termijn, { revisie: termijn.revisie + 1,
      inhoud: { ...termijn.inhoud, definitie: kaartVoorstellen[0].waarde.definitie, definitie_herkomst: "geformuleerd", definitie_door: "lex" } });
    return route.fulfill({ json: termijn });
  }
  if (p === "/api/werkgebieden/wg1/relaties") return route.fulfill({ json: { relaties: [], voorstellen: [] } });
  const gesprek = p.match(/^\/api\/gesprekken\/(g\d)$/);
  if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: "Test", berichten: gesprekken[gesprek[1]] ?? [] } });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g2", titel: "", berichten: [] } });
  if (p === "/api/gesprekken/g2/berichten" && m === "POST") {
    (gesprekken.g2 ??= []).push({ ...leeg, ...req.postDataJSON() });
    return route.fulfill({ json: { id: gesprekken.g2.length } });
  }
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
  // Wachten op de tekst, niet alleen op de knop: op een koude server staat de chip er even leeg.
  await begrippenChip().filter({ hasText: /Invordering[\s\S]*Begripsvoorstellen/ }).waitFor();
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
  // F3e: geen Lex-knoppen in het paneel; starten en meedenken vraag je in het gesprek.
  for (const naam of ["Stel begrippen voor", "Opnieuw voorstellen", /^Laat Lex meedenken/])
    assert.equal(await begrippenPaneel().getByRole("button", { name: naam }).count(), 0, String(naam));
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

  // --- Eén begrip (F3d): de chip heet "Begrip" en opent de leesweergave, zonder Lex-knoppen ---
  await page.goto(`${base}/workbench?gesprek=g3`);
  const begripChip = page.locator('button[data-artefact-soort="begrip"]', { hasText: "Termijn" });
  await begripChip.waitFor();
  assert.match(await begripChip.innerText(), /Termijn[\s\S]*Begrip · beoordelen/);
  await begripChip.click();
  const begripPaneel = page.getByRole("region", { name: "Begrip: Termijn" });
  await begripPaneel.locator("[data-begrip-paneel=b9]").waitFor();
  assert.equal(await begripPaneel.getByRole("button", { name: /Bedenk voorbeelden|Zoek de brondefinitie/ }).count(), 0,
    "het paneel is voor beoordelen: geen Lex-knoppen");
  assert.equal(await begripPaneel.getByRole("link", { name: "Open het werkgebied" }).getAttribute("href"),
    "/werkgebieden/wg1?tab=begrippen&begrip=b9");
  // Het open voorstel van Lex staat erin en wordt overgenomen: een nieuwe revisie.
  await begripPaneel.locator('[data-voorstel="v1"]').waitFor();
  await begripPaneel.locator('[data-voorstel="v1"]').getByRole("button", { name: /^Overnemen/ }).click();
  await begripPaneel.getByText("Overgenomen van Lex", { exact: false }).waitFor();
  await begripPaneel.locator("[data-begrip-lees]").getByText("Het tijdvak waarbinnen betaald moet zijn.").waitFor();
  assert.equal(await begripPaneel.locator('[data-voorstel="v1"]').count(), 0, "een overgenomen voorstel is niet meer open");
  // Een eigen bewerking: sluiten vraagt eerst, net als een tabwissel in het werkgebied.
  await begripPaneel.getByRole("button", { name: "Definitie en uitleg bewerken" }).click();
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
  assert.equal(await balk2.getByRole("button").count(), 1, "de balk heeft alleen *Verlaten* nog (F3d)");
  // De handelingen op het werkgebied staan als suggesties boven het invoerveld, zonder chip.
  const suggesties = page.locator('[data-testid="vraag-suggesties"][data-suggesties-van="werkgebied"]');
  await suggesties.getByRole("button", { name: "Stel begrippen voor" }).click();
  await page.getByRole("region", { name: "Begripsvoorstellen: Live voorstellen" }).waitFor();
  assert.equal(runs[0]?.werkgebied_id, "wg1", "de beurt hoort het werkgebied te dragen");
  assert.equal(runs[0]?.question, "Stel begrippen voor");
  assert.equal(runs[0]?.actie, "begrippen_voorstellen", "de suggestie is een vaste handeling, geen tekstpatroon (F3c)");
  // Typen laat de suggesties wijken.
  await page.getByRole("textbox").last().fill("Een eigen vraag");
  await suggesties.waitFor({ state: "detached" });
  await page.getByRole("textbox").last().fill("");

  // --- Eén deelvraag (F3d): Vraag Lex → suggestie → paneel → overnemen → herladen ---
  // *Vraag Lex* bij een deelvraag (buiten de werkplek een link: `vraagUrl`) zet haar als onderwerp.
  await page.goto(`${base}/workbench?werkgebied=wg1&vraag=deelvraag:d1&vraag_label=${encodeURIComponent("Wie betaalt?")}`);
  await page.locator('[data-onderwerp="deelvraag"]').waitFor();
  const dvSuggesties = page.locator('[data-testid="vraag-suggesties"][data-suggesties-van="deelvraag"]');
  assert.deepEqual(await dvSuggesties.locator("button").evaluateAll((bs) => bs.map((b) => b.dataset.actie)),
    ["bronnen_zoeken", "deelvragen_annoteren", "dekking", "deelvraag_herformuleren", "deelvraag_splitsen"]);
  runs.length = 0;
  await dvSuggesties.getByRole("button", { name: "Formuleer scherper" }).click();
  const dvPaneel = page.getByRole("region", { name: "Deelvraag: Wie betaalt?" });
  await dvPaneel.locator("[data-deelvraag-paneel=d1]").waitFor();
  assert.equal(runs[0]?.actie, "deelvraag_herformuleren");
  assert.deepEqual(runs[0]?.onderwerp, { soort: "deelvraag", werkgebied_id: "wg1", id: "d1", label: "Wie betaalt?" });
  // De kandidaat die Lex bij deze deelvraag vond, en de bron die er al bij hoort.
  await dvPaneel.getByText("art. 10 Iw").first().waitFor();
  await dvPaneel.locator("[data-bron=s1]").waitFor();
  const voorstel = dvPaneel.locator('[data-voorstel-deelvraag="d2"]');
  await voorstel.getByText("Vervangt “Wie betaalt?”").waitFor();
  await voorstel.getByRole("button", { name: "Overnemen: Wie is de belastingschuldige?" }).click();
  await dvPaneel.getByText("Deelvraag vervangen", { exact: false }).waitFor();
  assert.equal(wg1.deelvragen.find((d) => d.id === "d2").status, "actief");
  // Na herladen: de chip opent het paneel van d1, dat zegt dat ze vervangen is en de opvolger opent.
  await page.goto(`${base}/workbench?gesprek=g2`);
  const dvChip = page.locator('button[data-artefact-soort="deelvraag"]');
  await dvChip.waitFor();
  await dvChip.click();
  await dvPaneel.locator('[data-deelvraag-paneel=d1][data-status="vervangen"]').waitFor();
  await dvPaneel.locator("[data-opvolger=d2]").click();
  await page.getByRole("region", { name: "Deelvraag: Wie is de belastingschuldige?" }).locator("[data-deelvraag-paneel=d2]").waitFor();

  // --- Verlaten: een beurt draagt het werkgebied niet meer ---
  runs.length = 0;
  await page.goto(`${base}/workbench?werkgebied=wg1`);
  await balk2.getByRole("button", { name: /Uit de context/ }).click();
  await balk2.waitFor({ state: "detached" });
  assert.ok(!new URL(page.url()).searchParams.has("werkgebied"), "verlaten haalt het werkgebied uit de URL");
  const invoer2 = page.getByRole("textbox").last();
  await invoer2.fill("Stel begrippen voor");
  await invoer2.press("Enter");
  for (let i = 0; i < 50 && runs.length < 1; i++) await page.waitForTimeout(100);
  assert.equal(runs[0]?.werkgebied_id, undefined, "na verlaten draagt een beurt geen werkgebied meer");

  // --- Verwijderen in het paneel, zoals een annotatie: begrip en werkgebied, daarna de verwijderd-stand ---
  await page.goto(`${base}/workbench?gesprek=g3`);
  await page.locator('button[data-artefact-soort="begrip"]', { hasText: "Termijn" }).click();
  const bp = page.getByRole("region", { name: "Begrip: Termijn" });
  await bp.getByRole("button", { name: "Begrip verwijderen" }).click();
  await bp.getByRole("button", { name: "Verwijderen?", exact: true }).click();
  await bp.locator("[data-verwijderd]").getByText("Dit begrip is verwijderd op 15 okt 2026 door t.").waitFor();
  // Werkgebied: vanuit de werkplek in dat werkgebied; na verwijderen verlaat de werkplek het.
  await page.goto(`${base}/workbench?werkgebied=wg1&gesprek=g5`);
  await balk2.waitFor();
  await page.locator('button[data-artefact-soort="werkgebied"]').click();
  const wp = page.getByRole("region", { name: "Werkgebied: Invordering" });
  await wp.locator("[data-werkgebied-inhoud]").waitFor();
  await wp.getByRole("button", { name: "Werkgebied verwijderen" }).click();
  await wp.getByRole("button", { name: "Verwijderen?", exact: true }).click();
  await wp.locator("[data-verwijderd]").getByText("Dit werkgebied is verwijderd op 15 okt 2026 door t.").waitFor();
  await balk2.waitFor({ state: "detached" });
  // Een oud gesprek dat het opent, krijgt dezelfde stand in plaats van een fout.
  await page.goto(`${base}/workbench?gesprek=g5`);
  await page.locator('button[data-artefact-soort="werkgebied"]').click();
  await wp.locator("[data-verwijderd]").waitFor();
  assert.equal(await wp.getByText("kon niet worden geladen", { exact: false }).count(), 0);

  assert.deepEqual(errors, []);
  console.log("Browser OK: begrippenartefact na herladen en live, één artefact tegelijk, laatste-artefactbalk, regels gereserveerd, begrip- en deelvraagpaneel, suggesties, werkgebiedcontext in de werkplek, verwijderen in het begrip- en werkgebiedpaneel.");
} finally {
  await browser.close();
}
