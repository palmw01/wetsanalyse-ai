/** Browserregressie voor de bronselectie per deelvraag (spoor J) op de echte Next-UI met een gemockte BFF.
 * Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-bronselectie.mjs`.
 *
 * De mock gedraagt zich als graph-qa (`agent/bronselectie.py`): elke beurt levert een kaartje (`vraagkaart`,
 * `modus: "bronselectie"`) en het artefact `bronselectie`; de stand per deelvraag staat bij "de api"
 * (`GET …/bronselectie`), die de mock bijwerkt zoals de echte api.
 *
 * Het scenario uit de opdracht, met vier deelvragen:
 *  - "help mij de bronnen bij dit werkgebied te bepalen" geeft de keuze met deelvraag 1 aangevinkt, en het
 *    paneel ernaast met de vier deelvragen;
 *  - deelvraag 1: een bepaling opnemen, voorlopig afronden → *Hoe wil je verder?* met deelvraag 2 voorop;
 *  - deelvraag 2: een tussenvraag (✕, typen) breekt niets; *Een vraag stellen ›* haalt het kaartje terug;
 *  - in het paneel *Ga verder met deelvraag 4* → de suggestie → de beurt met `actie: bronselectie` en die deelvraag;
 *  - herladen: de Vragen-kaart, de open vraag van deelvraag 4 en de stand van deelvraag 2 (met onderzoekspunt);
 *  - hervatten: het kaartje beantwoorden draagt `deelvraag_id`; een nieuw gesprek in hetzelfde werkgebied begint met
 *    *Verder met de bronselectie*;
 *  - het user-bericht draagt `intake_antwoord` met de deelvraag; de pagina Bronselectie toont dezelfde stand.
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

const nu = "2026-10-27T10:00:00+00:00";
const IW = "BWBR0004770", A9 = `urn:bwb:${IW}:artikel:9:lid:1`, A10 = `urn:bwb:${IW}:artikel:10`, A19 = `urn:bwb:${IW}:artikel:19`;
const VRAGEN = ["Welke algemene betalingstermijn geldt?", "Welke termijnen gelden voor voorlopige aanslagen?",
  "Welke afwijkende betalingstermijnen bestaan er?", "Wanneer wordt iedere afzonderlijke termijn invorderbaar?"];
const IDS = ["d1", "d2", "d3", "d4"];
const wg = { id: "wg1", naam: "Betalingstermijnen", status: "in_voorbereiding", revisie: 5, peildatum: null, aangemaakt_door: "t",
  aangemaakt: nu, gewijzigd: nu, analysevraag: "Wanneer moet een aanslag betaald zijn?", afbakening: "", aanleiding: "",
  context: "", doel: "", praktijkvoorbeeld: "", bronnen: [],
  deelvragen: VRAGEN.map((vraag, i) => ({ id: IDS[i], vraag, volgorde: i, status: "actief", herkomst: "analist", reden: "",
    aangemaakt_door: "t", aangemaakt: nu, bronnen: [], begrippen: [] })) };

// --- "De api": de stand per deelvraag, bijgewerkt zoals api/app/bronselectie.py dat doet -----------------
const kand = { d1: [["K9", A9, "Artikel 9, lid 1"]], d2: [["K10", A10, "Artikel 10"]], d3: [], d4: [["K19", A19, "Artikel 19"]] };
const stand = Object.fromEntries(IDS.map((id) => [id, { status: "niet_gestart", fase: "kern", open_punten: [], revisie: 0, opgenomen: [] }]));
let actief = null;
function overzicht() {
  const deelvragen = IDS.map((id, i) => {
    const s = stand[id];
    const kandidaten = kand[id].map(([kid, iri, label]) => ({ id: kid, bron_iri: iri, label, rol: "kern",
      bewijs_soorten: ["tekst"], stand: s.opgenomen.includes(kid) ? "opgenomen" : "voorgesteld", overal: false,
      elders_opgenomen: false, reden: "" }));
    const open = kandidaten.filter((k) => k.stand === "voorgesteld").length;
    return { id, nr: i + 1, vraag: VRAGEN[i], status: s.status, fase: s.fase, open_punten: s.open_punten, revisie: s.revisie,
      gewijzigd_door: s.revisie ? "t" : null, gewijzigd: s.revisie ? nu : null, opnieuw_bekijken: false,
      klaar: ["voorlopig_afgerond", "beoordeeld"].includes(s.status),
      bronnen: s.opgenomen.map((kid) => ({ selectie_id: `s-${kid}`, bron_iri: kand[id].find((k) => k[0] === kid)[1],
        label: kand[id].find((k) => k[0] === kid)[2], rol: "analyseren" })),
      kandidaten, telling: { voorgesteld: open, later: 0, uitgesloten: 0, opgenomen: s.opgenomen.length },
      beoordelen: { mag: !open && !s.open_punten.length, redenen: open ? [`Er staat nog ${open} voorstel open.`] : [] } };
  });
  return { werkgebied_id: "wg1", naam: wg.naam, revisie: wg.revisie, modus: "deelvragen", deelvragen, actief,
    volgende: deelvragen.find((d) => !d.klaar && d.id !== actief)?.id ?? null, alle_klaar: deelvragen.every((d) => d.klaar),
    zonder_deelvraag: [], zoekdekking: { gezocht: true, verouderd: false, volledig: false, onvolledig: ["deelvraag"], reden: "" } };
}
const open_ = (id) => { if (stand[id].status === "niet_gestart") Object.assign(stand[id], { status: "in_behandeling", revisie: 1 }); actief = id; };

// --- "graph-qa": per beurt een kaartje, zoals agent/bronselectie.py ze maakt -----------------------------
const kaart = (stap, deelvraag_id, vraag, over = {}) => ({ intake_id: "bs-wg1", modus: "bronselectie", soort: "vraag", stap,
  deelvraag_id, nr: deelvraag_id ? IDS.indexOf(deelvraag_id) + 1 : 1, totaal: deelvraag_id ? 4 : 1, deel: null, vraag,
  toelichting: "", opties: [], meerkeuze: false, vrije_tekst: false, meer_tekst: false, overslaanbaar: false, vooringevuld: [],
  samenvatting: {}, terug: false, beantwoord: false, ...over });
const KIES = () => kaart("bs_kies", "", "Met welke deelvraag beginnen we?", {
  opties: IDS.map((id, i) => ({ label: `${i + 1}. ${VRAGEN[i]}`, waarde: id, bron: {}, omschrijving: "nog niet gestart" })),
  vooringevuld: ["d1"] });
const BEPALINGEN = (id) => kaart("bs_bepalingen", id, `Welke bepalingen regelen deelvraag ${IDS.indexOf(id) + 1} zelf? ${VRAGEN[IDS.indexOf(id)]}`, {
  meerkeuze: true, vrije_tekst: true, overslaanbaar: true,
  toelichting: "Niet alles is doorzocht (deelvraag): de lijst kan onvolledig zijn. Een eigen tekst noteer ik als onderzoekspunt.",
  opties: kand[id].map(([kid, iri, label]) => ({ label, waarde: kid, bron: { bwb_id: IW, iri, label }, omschrijving: "kernbepaling · tekstuele overeenkomst" })) });
const AFRONDEN = (id) => kaart("bs_afronden", id, `Hoe rond je deelvraag ${IDS.indexOf(id) + 1} af?`, {
  vrije_tekst: true, vooringevuld: ["afronden"],
  opties: [{ label: "Voorlopig afronden", waarde: "afronden", bron: {}, omschrijving: "Wat openstaat blijft staan." },
    { label: "Verder onderzoeken", waarde: "onderzoeken", bron: {}, omschrijving: "" },
    { label: "Naar het overzicht van de deelvragen", waarde: "overzicht", bron: {}, omschrijving: "" }] });
const VERDER = (id, volgende) => kaart("bs_verder", id, "Hoe wil je verder met de bronselectie?", {
  vooringevuld: [`verder:${volgende}`],
  opties: [{ label: `Verder met deelvraag ${IDS.indexOf(volgende) + 1}`, waarde: `verder:${volgende}`, bron: {}, omschrijving: VRAGEN[IDS.indexOf(volgende)] },
    { label: `Deelvraag ${IDS.indexOf(id) + 1} verder onderzoeken`, waarde: `heropen:${id}`, bron: {}, omschrijving: "" },
    { label: "Terug naar het overzicht van de deelvragen", waarde: "overzicht", bron: {}, omschrijving: "" }] });
const artefact = (id) => ({ soort: "bronselectie", titel: "Bronselectie", ref: { werkgebied_id: "wg1", ...(id ? { deelvraag_id: id } : {}) } });

/** Wat graph-qa met een verzoek doet: de stand bijwerken en het volgende kaartje geven. */
function beurt(body) {
  const a = body.intake_actie;
  if (body.actie === "bronselectie" || /bronnen/.test(body.question ?? "") && !a) {
    const gekozen = body.onderwerp?.soort === "deelvraag" ? body.onderwerp.id : actief;
    if (gekozen) { open_(gekozen); return { tekst: `We waren bij deelvraag ${IDS.indexOf(gekozen) + 1}.`, k: BEPALINGEN(gekozen), id: gekozen }; }
    return { tekst: "Betalingstermijnen heeft 4 deelvragen.", k: KIES(), id: "" };
  }
  if (!a) return { tekst: "Artikel 10 regelt de termijn bij een voorlopige aanslag; dat is een tekstuele overeenkomst, geen verwijzing." };
  const id = a.deelvraag_id;
  if (a.stap === "bs_kies") { open_(a.keuzes[0]); return { tekst: "Dan deelvraag 1.", k: BEPALINGEN(a.keuzes[0]), id: a.keuzes[0] }; }
  if (a.stap === "bs_bepalingen") {
    stand[id].opgenomen.push(...a.keuzes);
    if (a.tekst) stand[id].open_punten.push({ tekst: a.tekst });
    stand[id].fase = "afronden"; stand[id].revisie++;
    return { tekst: a.keuzes.length ? "Opgenomen." : "", k: AFRONDEN(id), id };
  }
  if (a.stap === "bs_afronden") {
    Object.assign(stand[id], { status: "voorlopig_afgerond" }); stand[id].revisie++;
    if (actief === id) actief = null;
    return { tekst: "Deelvraag 1 is voorlopig afgerond.", k: VERDER(id, overzicht().volgende), id };
  }
  if (a.stap === "bs_verder") { const v = a.keuzes[0].slice(7); open_(v); return { tekst: "Dan deelvraag 2.", k: BEPALINGEN(v), id: v }; }
  throw new Error(`onverwacht: ${JSON.stringify(a)}`);
}

const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const starts = [], stromen = {}, berichten = [];
const geschiedenis = [];          // wat "de api" van het gesprek bewaart: user-berichten en de beurten van Lex

await context.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/bronselectie") return route.fulfill({ json: overzicht() });
  if (p === "/api/werkgebieden") return route.fulfill({ json: { werkgebieden: [{ ...wg, aantal_bronnen: 0 }] } });
  if (p.startsWith("/api/werkgebieden/wg1/")) return route.fulfill({ json: {} });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: body?.werkgebied_id ? "g2" : "g1", titel: "", werkgebied_id: "wg1", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Bronnen", werkgebied_id: "wg1", werkgebied_naam: wg.naam, created: nu, updated: nu }] });
  if (p === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", titel: "Bronnen", werkgebied_id: "wg1", berichten: geschiedenis } });
  if (/^\/api\/gesprekken\/g\d$/.test(p)) return route.fulfill({ json: { id: p.slice(-2), titel: "", werkgebied_id: "wg1", berichten: [] } });
  if (p.endsWith("/berichten") && m === "POST") {
    berichten.push(body);
    if (p.includes("/g1/")) geschiedenis.push({ ...leeg, ...body });
    return route.fulfill({ status: 201, json: { id: berichten.length } });
  }
  if (p === "/api/annotatie/run" && m === "POST") {
    starts.push(body);
    const run = `r${starts.length}`, b = beurt(body);
    const events = [{ type: "token", content: b.tekst }];
    if (b.k) events.push({ type: "vraagkaart", vraagkaart: b.k });
    events.push({ type: "opgeslagen", run_id: run, ...(b.k ? { artefact: artefact(b.id) } : {}) }, { type: "done" });
    stromen[run] = events;
    // graph-qa bewaart de beurt van Lex (zoals agent/beurt.py), met het kaartje en het artefact.
    if (body.conversation_id === "g1") geschiedenis.push({ rol: "assistant", tekst: b.tekst, ...leeg, run_id: run,
      ...(b.k ? { vraagkaart: b.k, artefact: artefact(b.id) } : {}) });
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
const dock = (stap) => page.locator(`[data-vraagdock=${stap}]`);
const invoer = () => page.getByPlaceholder("Stel een vraag of geef een opdracht aan Lex…");
const paneel = () => page.locator("[data-artefact-soort=bronselectie][data-artefact]");
const deelvraagInPaneel = (id) => paneel().locator(`[data-bronselectie-deelvraag=${id}]`);

try {
  await page.goto(`${base}/workbench?gesprek=g1`);

  // --- Starten: de keuze met deelvraag 1 voorop, en het paneel met de vier deelvragen ---
  await invoer().fill("Lex, help mij de bronnen bij dit werkgebied te bepalen.");
  await page.getByRole("button", { name: "Versturen" }).click();
  await wacht(1);
  assert.equal(starts[0].werkgebied_id, "wg1", "de beurt hoort bij het werkgebied");
  await dock("bs_kies").getByText("Met welke deelvraag beginnen we?").waitFor();
  assert.equal(await dock("bs_kies").getByRole("option").count(), 4, "vier deelvragen");
  await dock("bs_kies").getByRole("option", { name: /^1\. Welke algemene/, selected: true }).waitFor();
  await paneel().waitFor();
  assert.equal(await paneel().locator("[data-bronselectie-deelvraag]").count(), 4);
  await paneel().locator("[data-zoekbeperking]").getByText("onvolledig", { exact: false }).waitFor();

  // --- Deelvraag 1: de kernbepaling opnemen, voorlopig afronden ---
  await dock("bs_kies").getByRole("button", { name: "Verzend", exact: true }).click();
  await wacht(2);
  assert.deepEqual(starts[1].intake_actie, { intake_id: "bs-wg1", stap: "bs_kies", actie: "antwoord", keuzes: ["d1"] });
  await dock("bs_bepalingen").getByText("1 van 4").waitFor();
  await dock("bs_bepalingen").getByText("kernbepaling · tekstuele overeenkomst").waitFor();
  await dock("bs_bepalingen").getByRole("option", { name: /^Artikel 9, lid 1/ }).click();
  await dock("bs_bepalingen").getByRole("button", { name: "Verzend", exact: true }).click();
  await wacht(3);
  assert.deepEqual(starts[2].intake_actie, { intake_id: "bs-wg1", stap: "bs_bepalingen", actie: "antwoord", keuzes: ["K9"], deelvraag_id: "d1" });
  assert.deepEqual(berichten.at(-1)?.intake_antwoord ?? berichten.findLast((b) => b.rol === "user")?.intake_antwoord,
    { intake_id: "bs-wg1", stap: "bs_bepalingen", actie: "antwoord", deelvraag_id: "d1" });
  await dock("bs_afronden").getByRole("button", { name: "Verzend", exact: true }).click();
  await wacht(4);
  assert.equal(stand.d1.status, "voorlopig_afgerond");

  // --- Na deelvraag 1: Hoe wil je verder? met deelvraag 2 voorop ---
  await dock("bs_verder").getByText("Hoe wil je verder met de bronselectie?").waitFor();
  await dock("bs_verder").getByRole("option", { name: /^Verder met deelvraag 2/, selected: true }).waitFor();
  await dock("bs_verder").getByRole("button", { name: "Verzend", exact: true }).click();
  await wacht(5);
  assert.deepEqual(starts[4].intake_actie.keuzes, ["verder:d2"]);
  await dock("bs_bepalingen").getByText("2 van 4").waitFor();
  // Een onderzoekspunt bij deelvraag 2, zonder iets op te nemen – het blijft openstaan.
  await dock("bs_bepalingen").getByLabel("Typ je antwoord").fill("Onderzoek ook de bijzondere invorderbaarheid.");
  await dock("bs_bepalingen").getByRole("button", { name: "Verzend", exact: true }).click();
  await wacht(6);
  assert.equal(starts[5].intake_actie.tekst, "Onderzoek ook de bijzondere invorderbaarheid.");
  await dock("bs_afronden").waitFor();

  // --- Een tussenvraag: ✕, typen, antwoord; de vraag komt terug met "Een vraag stellen ›" ---
  await dock("bs_afronden").getByRole("button", { name: "Vraag sluiten" }).click();
  await invoer().fill("Waarom is artikel 10 relevant?");
  await page.getByRole("button", { name: "Versturen" }).click();
  await wacht(7);
  assert.equal(starts[6].intake_actie, undefined, "een tussenvraag is geen klik op het kaartje");
  await page.getByText("geen verwijzing", { exact: false }).waitFor();
  assert.equal(stand.d2.status, "in_behandeling", "de tussenvraag verandert de stand niet");
  await page.locator("[data-vraag-open]").click();
  await dock("bs_afronden").getByText("Hoe rond je deelvraag 2 af?").waitFor();

  // --- In het paneel naar deelvraag 4 springen, zonder deelvraag 2 af te ronden ---
  await paneel().waitFor();
  await deelvraagInPaneel("d2").locator("[data-onderzoekspunten]").getByText("bijzondere invorderbaarheid", { exact: false }).waitFor();
  await deelvraagInPaneel("d4").locator("summary").click();
  await deelvraagInPaneel("d4").getByRole("button", { name: "Ga verder met deelvraag 4" }).click();
  await page.getByRole("button", { name: "Bepaal de bronnen bij deze deelvraag" }).click();
  await wacht(8);
  assert.equal(starts[7].actie, "bronselectie");
  assert.deepEqual([starts[7].onderwerp?.soort, starts[7].onderwerp?.id], ["deelvraag", "d4"]);
  await dock("bs_bepalingen").getByText("4 van 4").waitFor();
  assert.equal(stand.d2.status, "in_behandeling", "de voortgang van deelvraag 2 blijft");
  assert.deepEqual(stand.d2.open_punten, [{ tekst: "Onderzoek ook de bijzondere invorderbaarheid." }]);

  // --- Herladen: de open vraag van deelvraag 4, de Vragen-kaart en het paneel via de balk ---
  await page.goto(`${base}/workbench?gesprek=g1`);
  await dock("bs_bepalingen").getByText("4 van 4").waitFor();
  assert.ok(await page.locator("[data-vragenkaart]").count() >= 1, "de antwoorden staan in een Vragen-kaart");
  await page.getByRole("button", { name: /Bronselectie.*Openen/ }).click();
  await deelvraagInPaneel("d2").getByText("In behandeling").waitFor();
  await deelvraagInPaneel("d1").getByText("Voorlopig afgerond").waitFor();

  // --- Hervatten: het kaartje van deelvraag 4 beantwoorden ---
  await dock("bs_bepalingen").getByRole("option", { name: /^Artikel 19/ }).click();
  await dock("bs_bepalingen").getByRole("button", { name: "Verzend", exact: true }).click();
  await wacht(9);
  assert.deepEqual([starts[8].intake_actie.stap, starts[8].intake_actie.deelvraag_id, starts[8].intake_actie.keuzes],
    ["bs_bepalingen", "d4", ["K19"]]);
  assert.deepEqual(stand.d4.opgenomen, ["K19"]);

  // --- Een ander gesprek in hetzelfde werkgebied: verder waar we waren ---
  const ander = await context.newPage();
  ander.on("pageerror", (e) => errors.push(e.message));
  await ander.goto(`${base}/workbench?werkgebied=wg1`);
  await ander.getByRole("button", { name: "Verder met de bronselectie" }).click();
  for (let i = 0; i < 100 && starts.length < 10; i++) await ander.waitForTimeout(50);
  assert.equal(starts[9].actie, "bronselectie");
  await ander.locator("[data-vraagdock=bs_bepalingen]").getByText("4 van 4").waitFor();
  await ander.close();

  // --- De pagina Bronselectie: dezelfde stand, zonder gesprek ---
  await page.goto(`${base}/werkgebieden/wg1/artefacten/bronselectie`);
  const pagina = page.locator("[data-bronselectie]");
  await pagina.locator("[data-bronselectie-deelvraag=d1]").getByText("Artikel 9, lid 1").waitFor();
  await pagina.locator("[data-bronselectie-voortgang]").getByText("1 van 4 deelvragen afgerond").waitFor();
  await pagina.locator("[data-bronselectie-slot]").getByText("nog niet beoordeeld", { exact: false }).waitFor();
  assert.equal(await pagina.getByRole("button", { name: /Ga verder met deelvraag/ }).count(), 0, "de pagina start Lex niet");

  assert.deepEqual(errors, []);
  console.log("Browser OK: bronselectie starten met vier deelvragen, deelvraag 1 opnemen en afronden, Hoe wil je verder? met deelvraag 2, een onderzoekspunt, een tussenvraag zonder verlies, via het paneel naar deelvraag 4, herladen met de open vraag en de stand, hervatten met deelvraag_id, een ander gesprek gaat verder bij deelvraag 4, de pagina toont dezelfde stand.");
} finally {
  await browser.close();
}
