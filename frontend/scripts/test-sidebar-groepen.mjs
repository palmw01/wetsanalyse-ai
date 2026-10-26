/** Browserregressie voor de gesprekken in de sidebar (spoor G1). Op de echte Next-UI met een gemockte
 * BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-sidebar-groepen.mjs`.
 *
 * Bewaakt:
 *  - gesprekken staan onder hun werkgebied, losse onder *Recente gesprekken*, gearchiveerde ingeklapt
 *    in *Archief*; een groep klapt in en blijft na herladen ingeklapt;
 *  - een gesprek openen neemt zijn werkgebied mee (de chatkop noemt het, de URL draagt het);
 *  - archiveren, herstellen en verplaatsen zijn drie handelingen met elk hun PATCH;
 *  - verwijderen vraagt een expliciete bevestiging die eerst archiveren aanbiedt, en stuurt pas dan
 *    een DELETE;
 *  - *Nieuw gesprek* bij een groep maakt een gesprek dat bij dat werkgebied hoort.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [], patches = [], deletes = [], aangemaakt = [], runs = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-26T10:00:00+00:00";
const werkgebied = (id, naam) => ({ id, naam, status: "in_voorbereiding", revisie: 1, peildatum: null, aangemaakt_door: "t",
  aangemaakt: nu, gewijzigd: nu, analysevraag: "Hoe?", afbakening: "", aanleiding: "", context: "", doel: "",
  praktijkvoorbeeld: "", bronnen: [], deelvragen: [] });
const werkgebieden = { wg1: werkgebied("wg1", "Invorderingsrente"), wg2: werkgebied("wg2", "Uitstel van betaling") };
let lijst = [
  { id: "g1", titel: "Deelvragen formuleren", aantal_berichten: 4, updated: nu, werkgebied_id: "wg1", werkgebied_naam: "Invorderingsrente", gearchiveerd: null },
  { id: "g2", titel: "Losse vraag over uitstel", aantal_berichten: 2, updated: nu, werkgebied_id: "", werkgebied_naam: "", gearchiveerd: null },
  { id: "g3", titel: "Oude verkenning", aantal_berichten: 6, updated: nu, werkgebied_id: "", werkgebied_naam: "", gearchiveerd: nu },
];
const vind = (id) => lijst.find((g) => g.id === id);

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/annotatie/run") {
    if (m === "GET") return route.fulfill({ json: null });
    runs.push(req.postDataJSON());
    return route.fulfill({ json: { run_id: "live", conversation_id: req.postDataJSON().conversation_id, status: "loopt" } });
  }
  if (p === "/api/annotatie/run/live/events")
    return route.fulfill({ contentType: "text/event-stream", body: `data: ${JSON.stringify({ seq: 0, type: "done" })}\n\n` });
  if (p === "/api/werkgebieden") return route.fulfill({ json: { werkgebieden: Object.values(werkgebieden) } });
  const wg = p.match(/^\/api\/werkgebieden\/(wg\d)$/);
  if (wg) return route.fulfill({ json: werkgebieden[wg[1]] });
  if (p.startsWith("/api/werkgebieden/")) return route.fulfill({ json: { kandidaten: [], run: null } });
  const gesprek = p.match(/^\/api\/gesprekken\/(g\d+)$/);
  if (gesprek && m === "PATCH") {
    const body = req.postDataJSON();
    patches.push({ id: gesprek[1], ...body });
    const g = vind(gesprek[1]);
    if (body.werkgebied_id !== undefined)
      Object.assign(g, { werkgebied_id: body.werkgebied_id, werkgebied_naam: werkgebieden[body.werkgebied_id]?.naam ?? "" });
    if (body.gearchiveerd !== undefined) g.gearchiveerd = body.gearchiveerd ? nu : null;
    return route.fulfill({ json: { ...g, berichten: [] } });
  }
  if (gesprek && m === "DELETE") {
    deletes.push(gesprek[1]);
    lijst = lijst.filter((g) => g.id !== gesprek[1]);
    return route.fulfill({ status: 204, body: "" });
  }
  if (gesprek) return route.fulfill({ json: { ...vind(gesprek[1]), user_id: "t", berichten: [] } });
  if (p === "/api/gesprekken" && m === "POST") {
    const body = req.postDataJSON();
    aangemaakt.push(body);
    const g = { id: "g9", titel: body.titel, aantal_berichten: 0, updated: nu, werkgebied_id: body.werkgebied_id,
      werkgebied_naam: werkgebieden[body.werkgebied_id]?.naam ?? "", gearchiveerd: null };
    lijst = [g, ...lijst];
    return route.fulfill({ status: 201, json: { ...g, berichten: [] } });
  }
  if (p === "/api/gesprekken") return route.fulfill({ json: lijst });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ json: p.endsWith("/berichten") && m === "POST" ? { id: 1 } : [] });
});

const sidebar = page.locator("aside[data-tour=sidebar]");
const groep = (id) => sidebar.locator(`[data-werkgebied-groep=${id}]`);
const rij = (id) => sidebar.locator(`[data-gesprek-rij=${id}]`);
const kop = page.locator("[data-chatkop]");

try {
  await page.goto(`${base}/workbench`);
  // --- De indeling ---
  await groep("wg1").getByText("Invorderingsrente").waitFor();
  assert.equal(await groep("wg1").locator("[data-gesprek-rij]").count(), 1);
  await sidebar.locator("[data-groep=recent]").locator("[data-gesprek-rij=g2]").waitFor();
  assert.equal(await rij("g3").count(), 0, "een gearchiveerd gesprek staat niet in de gewone navigatie");
  await sidebar.getByRole("button", { name: /Archief \(1\)/ }).click();
  await sidebar.locator("[data-groep=archief]").locator("[data-gesprek-rij=g3]").waitFor();

  // Een groep klapt in, en blijft na herladen ingeklapt.
  await groep("wg1").getByRole("button", { name: "Invorderingsrente", exact: true }).click();
  await rij("g1").waitFor({ state: "detached" });
  await page.reload();
  await groep("wg1").waitFor();
  assert.equal(await rij("g1").count(), 0, "de ingeklapte groep blijft ingeklapt");
  await groep("wg1").getByRole("button", { name: "Invorderingsrente", exact: true }).click();

  // --- Een gesprek openen neemt zijn werkgebied mee ---
  await rij("g1").getByRole("button", { name: /^Deelvragen formuleren/ }).click();
  await page.locator("[data-chatkop][data-werkgebied=wg1]").waitFor();
  await kop.getByRole("link", { name: "Invorderingsrente" }).first().waitFor();
  assert.equal(new URL(page.url()).searchParams.get("werkgebied"), "wg1");
  await rij("g2").getByRole("button", { name: /^Losse vraag/ }).click();
  await kop.getByText("Los gesprek").waitFor();
  assert.ok(!new URL(page.url()).searchParams.has("werkgebied"), "een los gesprek heeft geen werkgebied in de URL");

  // --- Verplaatsen: een los gesprek naar een werkgebied ---
  await rij("g2").getByRole("button", { name: /Acties voor Losse vraag/ }).click();
  await rij("g2").getByRole("menuitem", { name: "Toevoegen aan werkgebied…" }).click();
  await rij("g2").getByRole("button", { name: "Uitstel van betaling" }).click();
  await groep("wg2").locator("[data-gesprek-rij=g2]").waitFor();
  assert.deepEqual(patches.at(-1), { id: "g2", werkgebied_id: "wg2" });
  await page.locator("[data-chatkop][data-werkgebied=wg2]").waitFor();

  // --- Archiveren en herstellen ---
  await rij("g2").getByRole("button", { name: /Acties voor Losse vraag/ }).click();
  await rij("g2").getByRole("menuitem", { name: "Archiveren" }).click();
  // Het archief staat na het herladen hierboven weer ingeklapt; het gesprek staat er wel in.
  await sidebar.getByRole("button", { name: /Archief \(2\)/ }).click();
  await sidebar.locator("[data-groep=archief]").locator("[data-gesprek-rij=g2]").waitFor();
  assert.deepEqual(patches.at(-1), { id: "g2", gearchiveerd: true });
  await rij("g2").getByRole("button", { name: /Acties voor Losse vraag/ }).click();
  await rij("g2").getByRole("menuitem", { name: "Herstellen uit archief" }).click();
  await groep("wg2").locator("[data-gesprek-rij=g2]").waitFor();

  // --- Verwijderen vraagt een bevestiging en biedt eerst archiveren aan ---
  await rij("g1").getByRole("button", { name: /Acties voor Deelvragen/ }).click();
  await rij("g1").getByRole("menuitem", { name: "Verwijderen…" }).click();
  const bevestig = rij("g1").locator("[data-gesprek-verwijderen]");
  await bevestig.getByText("Annotaties, begrippen en werkgebieden blijven bestaan", { exact: false }).waitFor();
  await bevestig.getByRole("button", { name: "Archiveren" }).waitFor();
  assert.deepEqual(deletes, [], "nog niets verwijderd zonder de tweede bevestiging");
  await bevestig.getByRole("button", { name: "Definitief verwijderen" }).click();
  await rij("g1").waitFor({ state: "detached" });
  assert.deepEqual(deletes, ["g1"]);

  // --- Nieuw gesprek bij een groep hoort bij dat werkgebied ---
  await groep("wg2").hover();
  await groep("wg2").getByRole("button", { name: "Nieuw gesprek in Uitstel van betaling" }).click();
  await page.locator("[data-chatkop][data-werkgebied=wg2]").waitFor();
  const invoer = page.getByRole("textbox").last();
  await invoer.fill("Welke termijnen gelden?");
  await invoer.press("Enter");
  for (let i = 0; i < 50 && runs.length < 1; i++) await page.waitForTimeout(100);
  assert.equal(aangemaakt.at(-1)?.werkgebied_id, "wg2", "het nieuwe gesprek wordt aan het werkgebied gekoppeld");
  assert.equal(runs.at(-1)?.werkgebied_id, "wg2", "en de beurt draagt het werkgebied");

  assert.deepEqual(errors, []);
  console.log("Browser OK: gesprekken per werkgebied, recent en archief; openen neemt het werkgebied mee; verplaatsen, archiveren, herstellen; verwijderen met bevestiging; nieuw gesprek in een werkgebied.");
} finally {
  await browser.close();
}
