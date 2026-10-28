/** Browserregressie voor "Bronnen vinden met Lex" (spoor D, fase A) op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-bronkandidaten.mjs`.
 *
 * De mock gedraagt zich als api (`api/app/bronnen_run_store.py`): Lex zocht al in het gesprek (F3e), dus
 * de run en de kandidaten staan er; besluiten volgen de regels van de api (opnemen draagt de revisie en
 * maakt een selectie, uitsluiten vraagt een reden, een uitgesloten kandidaat blijft uitgesloten).
 *
 * Bewaakt:
 *  - geen zoekknop op de pagina; de meting per methode, kandidaten met rol en bewijs in gewone woorden;
 *  - spoor J: de boom is een bronverkenner – geen vinkjes, actiebalk of besluiten, geen *later*; kiezen gaat
 *    per deelvraag in de bronselectie;
 *  - geen sneltoetsen;
 *  - *Vraag Lex* bij elke open kandidaat en elke bronselectie;
 *  - in de werkplek: *Maak hier een werkgebied van* onder een overzicht, en het bronnenartefact.
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
const IW = "urn:bwb:BWBR0004770";
const A9 = `${IW}:artikel:9`, A8 = `${IW}:artikel:8`, A10 = `${IW}:artikel:10`, D2 = `${IW}:artikel:2:lid:2:o:c`;
const sel = (iri, label, rol = "analyseren") => ({ id: `s-${iri}`, bron_iri: iri, label, rol, bereik: "onderliggend", reden: "",
  bwb_id: "BWBR0004770", snapshot_id: "s", bron_hash: "h", toegevoegd_door: "t", toegevoegd: nu });
const wg = { id: "wg1", naam: "Invorderbaarheid", analysevraag: "Wanneer is een aanslag invorderbaar?", afbakening: "", peildatum: null,
  status: "in_voorbereiding", revisie: 2, aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null,
  bronnen: [sel(A9, "Artikel 9 – Invorderingswet 1990")] };
const K = (id, iri, label, rol, bewijs) => ({ id, bron_iri: iri, label, bwb_id: "BWBR0004770", rol, bewijs, status: "voorgesteld",
  reden: "", run_id: "r1", in_laatste_run: true, in_selectie: false, besloten_door: null, besloten_op: null });
let kandidaten = [];
const vers = () => [
  K("K8", A8, "Artikel 8 – Invorderingswet 1990", "afhankelijkheid",
    [{ methode: "verwijzing_uit", vanuit: `${A9}:lid:1`, detail: { anker: "artikel 8", functie: "uitzondering" } },
     { methode: "opbouw", vanuit: A9, detail: { deel: `${IW}:hoofdstuk:II` } }]),
  K("KD", D2, "Artikel 2, lid 2, onderdeel c – Invorderingswet 1990", "afhankelijkheid",
    [{ methode: "definitie", vanuit: `${A9}:lid:1`, detail: { begrip: "belastingaanslag" } }]),
  K("K10", A10, "Artikel 10 – Invorderingswet 1990", "aanverwant",
    [{ methode: "verwijzing_in", vanuit: A9, detail: { anker: "artikel 9", functie: "onbekend" } }]),
];
const meting = { overzicht: { aantal: 0, volledig: true }, verwijzing_uit: { aantal: 1, volledig: true },
  definitie: { aantal: 1, volledig: true }, opbouw: { aantal: 2, volledig: false } };
// Lex zocht in het gesprek (de deelvragen-agent): de run is klaar en de kandidaten staan bij de api.
const run = { id: "r1", werkgebied_id: "wg1", invoer_id: "I1", status: "klaar", reden: "", meting, aantal_kern: 1, gestart: nu };
kandidaten = vers();
const antwoord = () => ({ run, kandidaten });
const ovGesprek = {
  gevraagd: "invorderbaarheid", onderwerp_opbouw: "invorderbaarheid", onderwerp_tekst: "invorderbaar", scope: [], volledig: true,
  definities: [], trefwoorden: [],
  regelingen: [{ bwb_id: "BWBR0004770", citeertitel: "Invorderingswet 1990", soort: "wet",
    delen: [{ iri: `${IW}:hoofdstuk:II`, soort: "Hoofdstuk", label: "Hoofdstuk II", jci: "", subdelen: [],
      bepalingen: [{ iri: A8, nummer: "8", label: "Artikel 8" }, { iri: A9, nummer: "9", label: "Artikel 9" }] }],
    ook_genoemd: [] }],
};
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const gesprekken = {
  g1: [
    { rol: "user", tekst: "Welke artikelen gaan over invorderbaarheid?", ...leeg },
    { rol: "assistant", tekst: "Hoofdstuk II regelt de invordering in eerste aanleg.", ...leeg, run_id: "o1", overzicht: ovGesprek },
    { rol: "assistant", tekst: "Ik stel **3** bepalingen voor.", ...leeg, run_id: "b1",
      artefact: { soort: "bronnen", ref: { werkgebied_id: "wg1", run_id: "r1" }, titel: "Invorderbaarheid" } },
  ],
};
let nieuwWg = null;

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  requests.push({ p, m, body });
  if (p === "/api/werkgebieden" && m === "POST") {
    nieuwWg = { ...wg, id: "wg2", naam: body.naam, analysevraag: body.analysevraag, revisie: 1, bronnen: [] };
    return route.fulfill({ status: 201, json: nieuwWg });
  }
  if (p === "/api/werkgebieden/wg2/bronnen" && m === "POST") {
    if (body.verwachte_revisie !== nieuwWg.revisie) return route.fulfill({ status: 412, json: { detail: { fout: "revisie_conflict" } } });
    nieuwWg = { ...nieuwWg, revisie: nieuwWg.revisie + 1, bronnen: [...nieuwWg.bronnen, sel(body.bron_iri, body.bron_iri)] };
    return route.fulfill({ status: 201, json: { selectie: nieuwWg.bronnen.at(-1), werkgebied: nieuwWg } });
  }
  if (p === "/api/werkgebieden/wg2") return route.fulfill({ json: nieuwWg });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/bronnen-runs/laatste") return route.fulfill({ json: { run: run && { ...run, verouderd: false } } });
  if (p === "/api/werkgebieden/wg1/kandidaten") return route.fulfill({ json: antwoord() });
  const besluit = p.match(/^\/api\/werkgebieden\/wg1\/kandidaten\/(K\w+)\/(opnemen|later|uitsluiten|heropenen)$/);
  if (besluit) {
    const k = kandidaten.find((x) => x.id === besluit[1]);
    if (besluit[2] === "opnemen") {
      if (body.verwachte_revisie !== wg.revisie) return route.fulfill({ status: 412, json: { detail: { fout: "revisie_conflict" } } });
      Object.assign(k, { status: "opgenomen", besloten_door: "t" });
      wg.revisie += 1;
      wg.bronnen.push(sel(k.bron_iri, k.label, body.rol ?? (k.rol === "kern" ? "analyseren" : "context")));
      return route.fulfill({ json: { kandidaat: k, selectie: wg.bronnen.at(-1), werkgebied: wg } });
    }
    if (besluit[2] === "uitsluiten") {
      if (!body.reden) return route.fulfill({ status: 422, json: { detail: "Reden verplicht" } });
      Object.assign(k, { status: "uitgesloten", reden: body.reden, besloten_door: "t" });
    } else Object.assign(k, { status: besluit[2] === "later" ? "later" : "voorgesteld", reden: "" });
    return route.fulfill({ json: k });
  }
  if (p.startsWith("/api/werkgebieden/wg1/")) return route.fulfill({ json: {} });
  const gesprek = p.match(/^\/api\/gesprekken\/(g\d)$/);
  if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: "Test", berichten: gesprekken[gesprek[1]] ?? [] } });
  if (p === "/api/annotatie/run" && m === "GET") return route.fulfill({ json: null });
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Test", aantal_berichten: 3 }] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: p.endsWith("/berichten") && m === "POST" ? { id: 1 } : [] });
});

const sectie = () => page.locator("[data-bronkandidaten]").first();
const kaart = (iri) => sectie().locator(`[data-kandidaat="${iri}"]`);
const zie = (tekst) => sectie().getByText(tekst, { exact: false }).first().waitFor();
const laatsteBesluit = (soort) => requests.filter((r) => r.m === "POST" && r.p.endsWith(`/${soort}`)).at(-1);

try {
  // --- De tab Bronnen noemt de voorstellen in één regel; ze staan op een eigen pagina (spoor G2) ---
  await page.goto(`${base}/werkgebieden/wg1?tab=bronnen`);
  await page.waitForURL("**/werkgebieden/wg1/bronnen");
  // Spoor L: de voorstellen staan per deelvraag op de tab; alles wat Lex vond staat in de bronverkenner.
  await page.getByRole("link", { name: /^Bronverkenner/ }).click();
  await page.waitForURL("**/werkgebieden/wg1/bronnen/voorstellen");
  await kaart(A8).waitFor();
  assert.equal(await sectie().getByRole("button", { name: /zoek/i }).count(), 0, "zoeken vraag je Lex in het gesprek");
  assert.equal(await kaart(A8).locator("[data-vraag-lex]").count(), 0, "geen Vraag Lex per rij op een pagina");
  await zie("verwijzingen vanuit de kern: 1");
  await zie("opbouw van de wet: 2");
  assert.equal(await sectie().getByText("(onvolledig)").count(), 1, "een methode die haar plafond raakte, zegt dat");
  await kaart(A8).getByText("verwezen vanuit Artikel 9, lid 1 (“artikel 8”) – uitzondering").waitFor();
  await kaart(D2).getByText("definieert “belastingaanslag”, dat in Artikel 9, lid 1 staat").waitFor();
  assert.equal(await sectie().getByRole("tab", { name: "Voorstellen (3)" }).count(), 1);

  // --- Spoor K: rijen per regeling als bronverkenner (geen boom) – geen vinkjes, geen actiebalk, geen besluiten ---
  await sectie().locator("[data-bronregelingen] section").first().waitFor();
  assert.equal(await sectie().locator("[data-bronboom]").count(), 0, "geen boom om te lezen");
  assert.equal(await sectie().getByRole("checkbox").count(), 0, "kiezen gaat per deelvraag, in de bronselectie");
  assert.equal(await sectie().locator("[data-actiebalk]").count(), 0, "geen actiebalk");
  assert.equal(await sectie().getByRole("button", { name: /Opnemen|Later|Uitsluiten|Heropenen/ }).count(), 0,
    "geen besluitknoppen");
  assert.equal(await sectie().getByRole("tab", { name: /^Later/ }).count(), 0, "er is geen later meer");
  await zie("Kiezen doe je per deelvraag");

  // --- Het register toont de bronnen, zonder knop per rij ---
  await page.goto(`${base}/werkgebieden/wg1/bronnen`);
  await page.locator("[data-bronnen-register] [data-bron]").nth(wg.bronnen.length - 1).waitFor();
  assert.equal(await page.locator("[data-bronnen-register] [data-bron]").count(), wg.bronnen.length);
  assert.equal(await page.locator("[data-bronnen-register] [data-vraag-lex]").count(), 0);
  await page.goBack();
  await kaart(A8).waitFor();

  // --- Geen sneltoetsen; het bewijs klapt uit met een knop; er gaat geen besluit naar de api ---
  await sectie().getByRole("group", { name: /^Bepalingen –/ }).click({ position: { x: 2, y: 2 } });
  for (const t of ["a", "x", "j"]) await page.keyboard.press(t);
  await page.waitForTimeout(300);
  await sectie().getByRole("button", { name: /^Bewijs voor / }).first().click();
  await sectie().getByRole("list", { name: /^Bewijs: / }).first().waitFor();
  assert.equal(requests.filter((r) => r.m === "POST" && r.p.includes("/kandidaten/")).length, 0, "de verkenner beslist niets");

  // --- De werkplek: een werkgebied uit een overzicht, en het bronnenartefact ---
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByRole("button", { name: "Maak hier een werkgebied van" }).click();
  const dialoog = page.getByRole("dialog", { name: "Werkgebied maken uit het overzicht" });
  await dialoog.waitFor();
  assert.equal(await dialoog.getByRole("textbox", { name: /^Naam/ }).inputValue(), "Invorderbaarheid");
  await dialoog.getByRole("checkbox", { name: "art. 8 – Invorderingswet 1990" }).uncheck();
  await dialoog.getByRole("button", { name: "Werkgebied maken" }).click();
  await page.locator("[data-werkgebied=wg2]").waitFor();
  assert.deepEqual(nieuwWg.bronnen.map((b) => b.bron_iri), [A9], "alleen de aangevinkte bepaling");
  assert.equal(requests.find((r) => r.p === "/api/werkgebieden" && r.m === "POST").body.analysevraag,
    "Welke bepalingen gaan over invorderbaarheid?");
  assert.ok(new URL(page.url()).searchParams.get("werkgebied") === "wg2", "de context staat in de URL");

  await page.locator('button[data-artefact-soort="bronnen"]').click();
  const paneel = page.getByRole("region", { name: "Gevonden bepalingen: Invorderbaarheid" });
  await paneel.locator("[data-bronkandidaten]").waitFor();
  await paneel.getByRole("link", { name: "Open volledige pagina" }).waitFor();
  assert.equal(await paneel.getByRole("link", { name: "Open volledige pagina" }).getAttribute("href"), "/werkgebieden/wg1/bronnen/voorstellen");

  assert.deepEqual(errors, []);
  console.log("Browser OK: gevonden bepalingen met meting, geen zoekknop, bewijs in gewone woorden, de voorstellen op een eigen pagina, geen Vraag Lex per rij, de boom per regeling als verkenner zonder besluiten en zonder later, geen sneltoetsen, werkgebied uit een overzicht, bronnenartefact.");
} finally {
  await browser.close();
}
