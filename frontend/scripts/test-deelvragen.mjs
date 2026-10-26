/** Browserregressie voor de deelvragen van een werkgebied (optioneel; open keuze 4) op de echte Next-UI
 * met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-deelvragen.mjs`.
 *
 * De mock gedraagt zich als api (`api/app/werkgebied_deelvragen.py`): elke wijziging draagt de revisie en
 * geeft het werkgebied terug, en de dekking volgt de koppelingen (gedekt alleen met een geaccordeerd begrip).
 * Lex stelt deelvragen voor in het gesprek (F3e); hier landen ze als voorstel bij de api.
 *
 * Bewaakt:
 *  - zelf een deelvraag toevoegen, met de revisie in beeld;
 *  - geen Lex-knop op de pagina, wel *Vraag Lex* bij elke deelvraag (een link naar het gesprek);
 *  - de voorstellen van Lex geel; overnemen en afwijzen (met reden);
 *  - bronnen en begrippen koppelen, en de stand per deelvraag (geen bron → geen begrip → gedekt);
 *  - weghalen met een tweede klik.
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

const nu = "2026-10-19T10:00:00+00:00";
const A9 = "urn:bwb:BWBR0004770:artikel:9";
const wg = { id: "wg1", naam: "Invorderbaarheid", analysevraag: "Wanneer is een aanslag invorderbaar?", afbakening: "",
  peildatum: null, status: "in_voorbereiding", revisie: 1, aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu,
  gearchiveerd: null, deelvragen: [],
  bronnen: [{ id: "s9", bron_iri: A9, label: "Artikel 9 – Invorderingswet 1990", rol: "analyseren", bereik: "onderliggend",
    reden: "", bwb_id: "BWBR0004770", snapshot_id: "s", bron_hash: "h", toegevoegd_door: "t", toegevoegd: nu }] };
const begrippen = [
  { id: "b1", status: "geaccordeerd", inhoud: { naam: "invorderbaar" } },
  { id: "b2", status: "concept", inhoud: { naam: "termijn" } },
];
let teller = 0;
const dv = (vraag, extra = {}) => ({ id: `d${++teller}`, vraag, volgorde: teller, status: "actief", herkomst: "analist", reden: "",
  aangemaakt_door: "browser-test", aangemaakt: nu, bronnen: [], begrippen: [], ...extra });
const wijzig = (f) => { f(); wg.revisie += 1; return wg; };
const dekking = () => {
  const lijst = wg.deelvragen.filter((d) => d.status === "actief").map((d) => {
    const bs = begrippen.filter((b) => d.begrippen.includes(b.id)).map((b) => ({ id: b.id, naam: b.inhoud.naam, status: b.status }));
    const stand = bs.some((b) => b.status === "geaccordeerd") ? "gedekt" : d.bronnen.length || bs.length ? "geen_begrip" : "geen_bron";
    return { id: d.id, vraag: d.vraag, stand, bronnen: d.bronnen.map((id) => ({ id, label: "Artikel 9" })), begrippen: bs };
  });
  const telling = { gedekt: 0, geen_begrip: 0, geen_bron: 0 };
  for (const x of lijst) telling[x.stand] += 1;
  return { deelvragen: lijst, telling, totaal: lijst.length };
};

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" || m === "DELETE" ? null : req.postDataJSON?.() ?? null;
  requests.push({ p, m, body, q: url.search });
  const revisie = body?.verwachte_revisie ?? Number(url.searchParams.get("verwachte_revisie") || 0);
  const conflict = () => route.fulfill({ status: 412, json: { detail: { fout: "revisie_conflict", melding: "Iemand anders." } } });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/deelvragen/dekking") return route.fulfill({ json: dekking() });
  if (p === "/api/werkgebieden/wg1/deelvragen" && m === "POST") {
    if (revisie !== wg.revisie) return conflict();
    return route.fulfill({ status: 201, json: wijzig(() => wg.deelvragen.push(dv(body.vraag))) });
  }
  const een = p.match(/^\/api\/werkgebieden\/wg1\/deelvragen\/(d\d+)(\/koppelingen)?$/);
  if (een) {
    if (revisie !== wg.revisie) return conflict();
    const d = wg.deelvragen.find((x) => x.id === een[1]);
    if (een[2]) return route.fulfill({ json: wijzig(() => Object.assign(d, { bronnen: body.bronnen, begrippen: body.begrippen })) });
    if (m === "DELETE") return route.fulfill({ json: wijzig(() => { wg.deelvragen = wg.deelvragen.filter((x) => x !== d); }) });
    if (body.status === "afgewezen" && !body.reden) return route.fulfill({ status: 422, json: { detail: "reden" } });
    return route.fulfill({ json: wijzig(() => {
      if (body.status === "afgewezen") wg.deelvragen = wg.deelvragen.filter((x) => x !== d);
      else Object.assign(d, body.vraag ? { vraag: body.vraag } : {}, body.status ? { status: body.status } : {});
    }) });
  }
  if (p === "/api/werkgebieden/wg1/begrippen") return route.fulfill({ json: { kader_iri: "k", begrippen, primair: {} } });
  if (p.startsWith("/api/werkgebieden/wg1/")) return route.fulfill({ json: {} });
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ json: [] });
});

const sectie = () => page.locator("[data-deelvragen]");
const rij = (vraag) => sectie().locator("[data-deelvraag]", { hasText: vraag });
const stand = (vraag) => rij(vraag).locator("[data-stand]");

try {
  // De deelvragen beheer je in het dossier (spoor G2); het overzicht toont ze als rijen.
  await page.goto(`${base}/werkgebieden/wg1/artefacten/dossier`);
  await sectie().getByRole("heading", { name: "Deelvragen" }).waitFor();

  // 1. Zelf een deelvraag toevoegen; de revisie gaat mee.
  await sectie().getByLabel("Nieuwe deelvraag").fill("Wanneer is een aanslag invorderbaar?");
  await sectie().getByRole("button", { name: "Toevoegen" }).click();
  await rij("Wanneer is een aanslag invorderbaar?").waitFor();
  assert.equal(requests.find((r) => r.m === "POST" && r.p.endsWith("/deelvragen")).body.verwachte_revisie, 1);
  await page.waitForFunction(() => document.querySelector("[data-stand]")?.textContent === "Nog geen bron");
  await sectie().getByText("0 van 1 deelvraag gedekt", { exact: false }).waitFor();

  // 2. Lex vraag je in het gesprek: geen knop in de rij, wel *Bespreek met Lex* op de pagina van de
  //    deelvraag – die opent het gesprek met de deelvraag als onderwerp.
  assert.equal(await page.getByRole("button", { name: /^Laat Lex/ }).count(), 0);
  const d1 = wg.deelvragen[0];
  assert.equal(await rij(d1.vraag).locator("[data-vraag-lex]").count(), 0);
  await page.goto(`${base}/werkgebieden/wg1`);
  await page.locator(`[data-deelvraag-rij="${d1.id}"]`).click();
  await page.waitForURL(`**/werkgebieden/wg1/deelvragen/${d1.id}`);
  assert.equal(await page.locator("[data-paginakop] [data-vraag-lex=deelvraag]").getAttribute("href"),
    `/workbench?werkgebied=wg1&vraag=deelvraag%3A${d1.id}&vraag_label=${encodeURIComponent(d1.vraag).replace(/%20/g, "+")}`);
  await page.goto(`${base}/werkgebieden/wg1/artefacten/dossier`);

  // Lex stelde in het gesprek twee deelvragen voor: geel; één overnemen, één afwijzen (pas met een reden).
  wg.deelvragen.push(dv("Wie is de belastingschuldige?", { status: "voorgesteld", herkomst: "lex" }),
    dv("Welke uitzonderingen zijn er?", { status: "voorgesteld", herkomst: "lex" }));
  await page.reload();
  const voorstellen = sectie().getByRole("list", { name: "Voorstellen van Lex" });
  await voorstellen.getByText("Wie is de belastingschuldige?").waitFor();
  await sectie().getByRole("button", { name: "Overnemen: Wie is de belastingschuldige?" }).click();
  await rij("Wie is de belastingschuldige?").waitFor();
  await sectie().getByRole("button", { name: "Afwijzen: Welke uitzonderingen zijn er?" }).click();
  const afwijzen = sectie().getByRole("button", { name: "Afwijzen", exact: true });
  assert.equal(await afwijzen.isDisabled(), true, "afwijzen vraagt een reden");
  await sectie().getByLabel("Reden van afwijzen").fill("Hoort bij een ander werkgebied");
  await afwijzen.click();
  await voorstellen.waitFor({ state: "detached" });
  const besluit = requests.filter((r) => r.m === "PATCH").at(-1).body;
  assert.deepEqual([besluit.status, besluit.reden], ["afgewezen", "Hoort bij een ander werkgebied"]);

  // 3. Koppelen: een bron en een concept-begrip → nog geen geaccordeerd begrip; met het geaccordeerde → gedekt.
  const vraag = "Wanneer is een aanslag invorderbaar?";
  // Spoor H3: koppelen staat achter ⋯ en gaat in een venster, met de bronnen als boom per regeling.
  const koppel = async () => {
    await sectie().getByRole("button", { name: `Acties: ${vraag}` }).click();
    await page.getByRole("button", { name: `Bronnen en begrippen bij: ${vraag}` }).click();
    const venster = page.getByRole("dialog", { name: `Bronnen en begrippen bij: ${vraag}` });
    await venster.locator("[data-bronboom]").waitFor();
    return venster;
  };
  let venster = await koppel();
  await venster.getByLabel("Artikel 9 – Invorderingswet 1990").check();
  await venster.getByLabel(/termijn/).check();
  await venster.getByRole("button", { name: "Opslaan" }).click();
  await venster.waitFor({ state: "detached" });
  await page.waitForFunction((v) => [...document.querySelectorAll("[data-deelvraag]")]
    .find((li) => li.textContent.includes(v))?.querySelector("[data-stand]")?.textContent === "Nog geen geaccordeerd begrip", vraag);
  // De rij noemt de omvang in plaats van een kommareeks.
  await rij(vraag).getByText("1 bron · 1 begrip", { exact: false }).waitFor();
  venster = await koppel();
  await venster.getByLabel(/invorderbaar \(geaccordeerd\)/).check();
  await venster.getByRole("button", { name: "Opslaan" }).click();
  await page.waitForFunction((v) => [...document.querySelectorAll("[data-deelvraag]")]
    .find((li) => li.textContent.includes(v))?.querySelector("[data-stand]")?.textContent === "Gedekt", vraag);
  assert.equal(await stand(vraag).textContent(), "Gedekt");
  await sectie().getByText("1 van 2 deelvragen gedekt", { exact: false }).waitFor();
  const koppeling = requests.filter((r) => r.m === "PUT").at(-1).body;
  assert.deepEqual([koppeling.bronnen, [...koppeling.begrippen].sort()], [["s9"], ["b1", "b2"]]);

  // 4. Verwijderen (niet "weghalen"): achter ⋯, eerst scherp zetten, dan pas weg.
  await sectie().getByRole("button", { name: "Acties: Wie is de belastingschuldige?" }).click();
  await page.getByRole("button", { name: "Verwijderen: Wie is de belastingschuldige?" }).click();
  assert.equal(await rij("Wie is de belastingschuldige?").count(), 1, "één klik haalt nog niets weg");
  await page.getByRole("button", { name: "Verwijderen?" }).click();
  await rij("Wie is de belastingschuldige?").waitFor({ state: "detached" });

  assert.deepEqual(errors, []);
  console.log("OK test-deelvragen");
} finally {
  await browser.close();
}
