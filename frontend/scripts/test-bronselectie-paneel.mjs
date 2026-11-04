/** Browserregressie voor het compacte kaartje van de bronselectie en het paneel dat beslist (3 nov 2026).
 * Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-bronselectie-paneel.mjs`.
 *
 * De mock gedraagt zich als graph-qa (`agent/bronselectie.py`, `weergave: paneel`) en de api (besluiten per deelvraag):
 *  - het kaartje in het gesprek heeft geen vinkjes: het telt de kandidaten, *Bronnen beoordelen* opent het paneel;
 *  - in het paneel klap je een kandidaat open en lees je de wettekst, zonder de werkplek te verlaten;
 *  - *Opnemen* in het paneel verandert de telling op het kaartje (live);
 *  - *Klaar met deze deelvraag* in het paneel stuurt `actie: klaar` – zonder keuzes;
 *  - *+ Bepaling toevoegen* op het kaartje opent het venster met de deelvraag van het kaartje;
 *  - op een telefoon opent *Bronnen beoordelen* het paneel als sheet.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-11-03T10:00:00+00:00";
const IW = "BWBR0004770", A9 = `urn:bwb:${IW}:artikel:9:lid:1`, A10 = `urn:bwb:${IW}:artikel:10`;
const wg = { id: "wg1", naam: "Betalingstermijnen", status: "in_voorbereiding", revisie: 5, peildatum: "2026-11-03",
  aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, analysevraag: "Wanneer moet een aanslag betaald zijn?", afbakening: "",
  aanleiding: "", context: "", doel: "", praktijkvoorbeeld: "", bronnen: [],
  deelvragen: [{ id: "d1", vraag: "Welke algemene betalingstermijn geldt?", volgorde: 0, status: "actief", herkomst: "analist",
    reden: "", aangemaakt_door: "t", aangemaakt: nu, bronnen: [], begrippen: [] }] };
const KAND = [["K9", A9, "Artikel 9, lid 1 – Invorderingswet 1990"], ["K10", A10, "Artikel 10 – Invorderingswet 1990"]];
const stand = { opgenomen: [], fase: "kern", status: "in_behandeling", revisie: 1 };
const besluiten = [];

function overzicht() {
  const kandidaten = KAND.map(([id, bron_iri, label]) => ({ id, bron_iri, label, rol: "kern", bewijs_soorten: ["tekst"],
    stand: stand.opgenomen.includes(id) ? "opgenomen" : "voorgesteld", overal: false, elders_opgenomen: false, reden: "" }));
  const open = kandidaten.filter((k) => k.stand === "voorgesteld").length;
  return { werkgebied_id: "wg1", naam: wg.naam, revisie: wg.revisie, modus: "deelvragen", actief: "d1", volgende: null,
    alle_klaar: false, zonder_deelvraag: [], zoekdekking: { gezocht: true, verouderd: false, volledig: true, onvolledig: [], reden: "" },
    deelvragen: [{ id: "d1", nr: 1, vraag: wg.deelvragen[0].vraag, status: stand.status, fase: stand.fase, open_punten: [],
      revisie: stand.revisie, gewijzigd_door: "t", gewijzigd: nu, opnieuw_bekijken: false, klaar: false,
      bronnen: stand.opgenomen.map((kid) => ({ selectie_id: `s-${kid}`, bron_iri: KAND.find((k) => k[0] === kid)[1],
        label: KAND.find((k) => k[0] === kid)[2], rol: "analyseren" })),
      kandidaten, telling: { voorgesteld: open, niet_gekozen: 0, uitgesloten: 0, opgenomen: stand.opgenomen.length },
      beoordelen: { mag: false, redenen: ["De vragen zijn nog niet doorlopen."] } }] };
}

const kaartje = (stap, over = {}) => ({ intake_id: "bs-wg1", modus: "bronselectie", soort: "vraag", stap, deelvraag_id: "d1",
  nr: 1, totaal: 1, deel: null, vraag: "De kernbepalingen bij deelvraag 1: Welke algemene betalingstermijn geldt?",
  toelichting: "Ik vond 2 kandidaatbronnen. Beoordeel ze in het paneel.", opties: [], meerkeuze: false, vrije_tekst: true,
  meer_tekst: false, overslaanbaar: false, vooringevuld: [], samenvatting: { kandidaten: 2, opgenomen: 0 }, terug: false,
  beantwoord: false, weergave: "paneel", ...over });
const AFRONDEN = kaartje("bs_afronden", { vraag: "Hoe rond je deelvraag 1 af?", weergave: undefined, samenvatting: {},
  opties: [{ label: "Voorlopig afronden", waarde: "afronden", bron: {}, omschrijving: "" }], vooringevuld: ["afronden"] });
const artefact = { soort: "bronselectie", titel: "Bronselectie", ref: { werkgebied_id: "wg1", deelvraag_id: "d1" } };

function beurt(body) {
  const a = body.intake_actie;
  if (!a) return { tekst: "We waren bij deelvraag 1.", k: kaartje("bs_bepalingen") };
  if (a.stap === "bs_bepalingen" && a.actie === "klaar") {
    stand.fase = "afronden";
    return { tekst: "", k: AFRONDEN };
  }
  throw new Error(`onverwacht: ${JSON.stringify(a)}`);
}

const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const starts = [], stromen = {};
await context.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/bronselectie") return route.fulfill({ json: overzicht() });
  const besluit = p.match(/^\/api\/werkgebieden\/wg1\/bronselectie\/d1\/kandidaten\/(K\d+)$/);
  if (besluit && m === "POST") {
    besluiten.push({ kid: besluit[1], ...body });
    if (body.besluit === "opnemen") stand.opgenomen.push(besluit[1]);
    stand.revisie++; wg.revisie++;
    return route.fulfill({ json: overzicht() });
  }
  if (p === "/api/werkgebieden/wg1/regelingen") return route.fulfill({ json: { regelingen: [{ bwb_id: IW, citeertitel: "Invorderingswet 1990" }] } });
  if (p.startsWith("/api/werkgebieden/wg1/")) return route.fulfill({ json: {} });
  if (p === "/api/werkgebieden") return route.fulfill({ json: { werkgebieden: [{ ...wg, aantal_bronnen: 0 }] } });
  if (p === "/api/annotatie/v2/weergave") return route.fulfill({ json: {
    schema_versie: 2, doel: { bron_iri: url.searchParams.get("bron_iri") }, snapshot_id: "snap", lagen: [], elementen: [],
    segmenten: [{ bron_iri: url.searchParams.get("bron_iri"), type: "Lid", nummer: "1", bron_hash: "h",
      tekst: "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet." }] } });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g1", titel: "", werkgebied_id: "wg1", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Bronnen", werkgebied_id: "wg1", werkgebied_naam: wg.naam, created: nu, updated: nu }] });
  if (p === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", titel: "Bronnen", werkgebied_id: "wg1", berichten: [] } });
  if (p.endsWith("/berichten") && m === "POST") return route.fulfill({ status: 201, json: { id: 1 } });
  if (p === "/api/annotatie/run" && m === "POST") {
    starts.push(body);
    const run = `r${starts.length}`, b = beurt(body);
    stromen[run] = [{ type: "token", content: b.tekst }, { type: "vraagkaart", vraagkaart: b.k },
      { type: "opgeslagen", run_id: run, artefact }, { type: "done" }];
    return route.fulfill({ status: 201, json: { run_id: run, conversation_id: body.conversation_id, status: "loopt" } });
  }
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  const events = p.match(/\/run\/([^/]+)\/events$/);
  if (events) return route.fulfill({ contentType: "text/event-stream", body: sse(stromen[events[1]] ?? [{ type: "done" }]) });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: [] });
});

const wacht = async (n) => {
  for (let i = 0; i < 100 && starts.length < n; i++) await page.waitForTimeout(50);
  assert.ok(starts.length >= n, `verwacht ${n} beurten, kreeg ${starts.length}`);
};
const kaart = () => page.locator("[data-bronselectie-kaart=d1]");
const paneel = () => page.locator("[data-artefact-soort=bronselectie][data-artefact]");
const foto = (naam) => process.env.SCREENSHOT_DIR
  ? page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/${naam}.png` }) : null;

try {
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByPlaceholder("Stel een vraag of geef een opdracht aan Lex…").fill("Help mij de bronnen bij dit werkgebied te bepalen.");
  await page.getByRole("button", { name: "Versturen" }).click();
  await wacht(1);

  // Het kaartje: geen vinkjes, wel de telling en drie handelingen.
  await kaart().locator("[data-telling]").getByText("Kernbepalingen · 2 kandidaatbronnen").waitFor();
  assert.equal(await kaart().getByRole("option").count(), 0, "geen vinkjes in het gesprek");
  await kaart().getByRole("button", { name: /Bronnen beoordelen/ }).waitFor();

  // Het paneel (vanaf 1280px open het vanzelf): de kandidaat openklappen en de tekst lezen, zonder weg te gaan.
  await paneel().waitFor();
  await paneel().getByRole("button", { name: "Tekst van Artikel 9, lid 1 – Invorderingswet 1990" }).click();
  await paneel().locator(`[data-wettekst="${A9}"]`).getByText("zes weken na de dagtekening", { exact: false }).waitFor();
  assert.ok(new URL(page.url()).pathname.startsWith("/workbench"), "de werkplek blijft staan");
  await foto("bronselectie-paneel");

  // Opnemen in het paneel; de telling op het kaartje volgt.
  await paneel().getByRole("button", { name: "Opnemen: Artikel 9, lid 1 – Invorderingswet 1990" }).click();
  await kaart().locator("[data-telling]").getByText("1 opgenomen", { exact: false }).waitFor();
  await kaart().locator("[data-telling]").getByText("1 kandidaatbron", { exact: false }).waitFor();
  assert.deepEqual(besluiten.map((b) => [b.kid, b.besluit, b.rol]), [["K9", "opnemen", "analyseren"]]);

  // + Bepaling toevoegen opent het venster met de deelvraag van het kaartje.
  await kaart().getByRole("button", { name: "+ Bepaling toevoegen" }).click();
  const venster = page.locator("[data-bepaling-toevoegen]");
  await venster.waitFor();
  await venster.getByRole("button", { name: "Annuleren" }).click();
  await venster.waitFor({ state: "detached" });

  // Klaar in het paneel: actie klaar, zonder keuzes.
  await paneel().locator("[data-paneel-klaar]").click();
  await wacht(2);
  assert.deepEqual(starts[1].intake_actie, { intake_id: "bs-wg1", stap: "bs_bepalingen", actie: "klaar", deelvraag_id: "d1" });
  await page.locator("[data-vraagdock=bs_afronden]").getByText("Hoe rond je deelvraag 1 af?").waitFor();

  // Een telefoon: Bronnen beoordelen opent het paneel als sheet.
  await page.setViewportSize({ width: 390, height: 844 });
  stand.fase = "kern";
  await page.reload();
  await page.getByPlaceholder("Stel een vraag of geef een opdracht aan Lex…").fill("Verder met de bronselectie.");
  await page.getByRole("button", { name: "Versturen" }).click();
  await wacht(3);
  await kaart().getByRole("button", { name: /Bronnen beoordelen/ }).click();
  await paneel().waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  await foto("bronselectie-paneel-mobiel");

  assert.deepEqual(errors, []);
  console.log("Browser OK: compact kaartje zonder vinkjes, paneel met uitklapbare wettekst, opnemen werkt de telling live bij, Bepaling toevoegen vanaf het kaartje, Klaar in het paneel (actie klaar), het paneel als sheet op een telefoon.");
} finally {
  await browser.close();
}
