/** Browserregressie voor "Bronnen vinden met Lex" (spoor D, fase A) op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-bronkandidaten.mjs`.
 *
 * De mock gedraagt zich als api + graph-qa (`api/app/bronnen_run_store.py`): een start geeft een run
 * en een SSE-stroom, daarna staan de kandidaten er; besluiten volgen de regels van de api (opnemen
 * draagt de revisie en maakt een selectie, uitsluiten vraagt een reden, een uitgesloten kandidaat
 * blijft uitgesloten bij opnieuw zoeken).
 *
 * Bewaakt:
 *  - zoeken met voortgang, de meting per methode, kandidaten met rol en bewijs in gewone woorden;
 *  - opnemen met de voorgestelde rol (kern → analyseren, anders context) en de revisie in beeld;
 *  - uitsluiten alleen met een reden, en het filter Uitgesloten met die reden; heropenen;
 *  - het toetsenbord (`j`, `a`) alleen met de focus in de lijst;
 *  - opnieuw zoeken op dezelfde selectie rekent niet, en zegt dat;
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
let run = null;
const meting = { overzicht: { aantal: 0, volledig: true }, verwijzing_uit: { aantal: 1, volledig: true },
  definitie: { aantal: 1, volledig: true }, opbouw: { aantal: 2, volledig: false } };
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
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
  if (p === "/api/bronnen-run" && m === "POST") {
    if (run?.status === "klaar") return route.fulfill({ json: { run, agent_run_id: null } });
    run = { id: "r1", werkgebied_id: "wg1", invoer_id: "I1", status: "wacht", reden: "", meting: null, aantal_kern: 1, gestart: nu };
    return route.fulfill({ status: 201, json: { run, agent_run_id: "ab1" } });
  }
  if (p === "/api/bronnen-run") return route.fulfill({ json: null });
  if (p === "/api/annotatie/run/ab1/events") {
    run = { ...run, status: "klaar", meting };
    kandidaten = vers();
    return route.fulfill({ contentType: "text/event-stream", body: sse([
      { type: "status", message: "Lex · Zoeken vanuit 1 bepalingen en de analysevraag" },
      { type: "status", message: "Lex · Verwijzingen vanuit de kern: 1 (8 ms)" },
      { type: "opgeslagen", bronnen_run: "r1", kandidaten: 3 }, { type: "done" }]) });
  }
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
  // --- Zoeken op de tab Bronnen ---
  await page.goto(`${base}/werkgebieden/wg1?tab=bronnen`);
  await sectie().getByRole("button", { name: "Lex, zoek bepalingen" }).click();
  await kaart(A8).waitFor();
  await zie("verwijzingen vanuit de kern: 1");
  await zie("opbouw van de wet: 2");
  assert.equal(await sectie().getByText("(onvolledig)").count(), 1, "een methode die haar plafond raakte, zegt dat");
  await kaart(A8).getByText("verwezen vanuit Artikel 9, lid 1 (“artikel 8”) – uitzondering").waitFor();
  await kaart(D2).getByText("definieert “belastingaanslag”, dat in Artikel 9, lid 1 staat").waitFor();
  assert.equal(await sectie().getByRole("tab", { name: "Open (3)" }).count(), 1);

  // --- Opnemen: een afhankelijkheid wordt context, met de revisie in beeld ---
  await kaart(A8).getByRole("button", { name: /^Opnemen als contextbron:/ }).click();
  await zie("opgenomen als contextbron");
  const opname = laatsteBesluit("opnemen");
  assert.equal(opname.body.rol, "context");
  assert.equal(opname.body.verwachte_revisie, 2);
  await sectie().getByRole("tab", { name: "Opgenomen (1)" }).waitFor();
  await page.getByRole("tab", { name: "Bronnen (2)" }).waitFor();

  // --- Uitsluiten vraagt een reden ---
  await kaart(A10).getByRole("button", { name: /^Uitsluiten:/ }).click();
  const reden = kaart(A10).getByRole("textbox", { name: /^Reden om/ });
  await reden.waitFor();
  assert.equal(await reden.evaluate((el) => el === document.activeElement), true, "de reden krijgt de focus");
  assert.equal(await kaart(A10).getByRole("button", { name: "Uitsluiten", exact: true }).isDisabled(), true);
  await reden.fill("Gaat over uitstel, niet over invorderbaarheid");
  await kaart(A10).getByRole("button", { name: "Uitsluiten", exact: true }).click();
  await zie("Lex stelt deze bepaling niet opnieuw voor");
  await sectie().getByRole("tab", { name: "Uitgesloten (1)" }).click();
  await kaart(A10).getByText("Gaat over uitstel, niet over invorderbaarheid", { exact: false }).waitFor();

  // --- Opnieuw zoeken op dezelfde selectie: niets te rekenen, en het besluit blijft staan ---
  await sectie().getByRole("button", { name: "Opnieuw zoeken" }).click();
  await zie("had Lex al gezocht");
  assert.equal(await kaart(A10).count(), 1, "de uitgesloten kandidaat blijft uitgesloten");
  await kaart(A10).getByRole("button", { name: /^Heropenen:/ }).click();
  await sectie().getByRole("tab", { name: "Open (2)" }).click();

  // --- Toetsenbord: alleen met de focus in de lijst ---
  await page.keyboard.press("a");
  assert.equal(requests.filter((r) => r.p.endsWith("/opnemen")).length, 1, "`a` buiten de lijst doet niets");
  const lijst = sectie().getByRole("list", { name: /^Kandidaten/ });
  await lijst.focus();
  await page.keyboard.press("j");
  await page.keyboard.press("a");
  await zie("opgenomen als");
  assert.equal(requests.filter((r) => r.p.endsWith("/opnemen")).length, 2);

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
  await paneel.getByRole("link", { name: "Open het werkgebied" }).waitFor();
  assert.equal(await paneel.getByRole("link", { name: "Open het werkgebied" }).getAttribute("href"), "/werkgebieden/wg1?tab=bronnen");

  assert.deepEqual(errors, []);
  console.log("Browser OK: zoeken met voortgang en meting, bewijs in gewone woorden, opnemen met rol en revisie, uitsluiten met reden, opnieuw zoeken zonder herberekening, heropenen, toetsenbord in de lijst, werkgebied uit een overzicht, bronnenartefact.");
} finally {
  await browser.close();
}
