/** Browserregressie voor "Lex annoteert het werkgebied" (spoor D, fase B) op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-werkgebied-annoteren.mjs`.
 *
 * De mock gedraagt zich als api + graph-qa: een run met `modus: "werkgebied_annoteren"` + `bevestigd` levert
 * de reeksstroom met een samenvatting (`tools/graph-qa/agent/werkgebied_annotatie.py`). De werkvoorraad en de
 * bevestiging maakt graph-qa zelf; de werkplek leest ze niet meer (F3e).
 *
 * Bewaakt:
 *  - op de tab Elementen geen Lex-knop meer; *Vraag Lex* in de kop wijst naar het gesprek in het werkgebied;
 *  - in het werkgebied is *Annoteer wat nog niet geannoteerd is* een suggestie boven het invoerveld (F3d):
 *    een beurt met de actie en zonder `bevestigd` – de bevestiging komt in het gesprek;
 *  - `?annoteer=` op de werkplek start niets (F3e);
 *  - de knop bij een voorstel van Lex in het gesprek start de run met het bevestigde aantal, ook na herladen;
 *  - de voortgang als reeksblok over artikelen heen, met de samenvatting erna.
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
const IW = "urn:bwb:BWBR0004770";
const A9 = `${IW}:artikel:9`, L1 = `${A9}:lid:1`, L2 = `${A9}:lid:2`, A10 = `${IW}:artikel:10`, A4 = `${IW}:artikel:4`;
const sel = (iri, label, rol = "analyseren") => ({ id: `s-${iri}`, bron_iri: iri, label, rol, bereik: "onderliggend", reden: "",
  bwb_id: "BWBR0004770", snapshot_id: "s", bron_hash: "h", toegevoegd_door: "t", toegevoegd: nu });
const wg = { id: "wg1", naam: "Invorderbaarheid", analysevraag: "Wanneer is een aanslag invorderbaar?", afbakening: "", peildatum: null,
  status: "actief", revisie: 4, aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null,
  bronnen: [sel(A9, "Artikel 9 – Invorderingswet 1990"), sel(A10, "Artikel 10 – Invorderingswet 1990"),
    sel(A4, "Artikel 4 – Invorderingswet 1990", "context")] };
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const OUDER = "werkgebied Invorderbaarheid";
const deel = (index, iri, label) => [
  { type: "onderdeel", fase: "start", index, totaal: 2, bron_iri: iri, label },
  { type: "status", message: `Bron · ${label}`, onderdeel: iri },
  { type: "opgeslagen", run_id: `w1.${index + 1}`, annotatie_doel: { bron_iri: iri, label, snapshot_id: "s" }, onderdeel: iri },
  { type: "onderdeel", fase: "eind", index, totaal: 2, bron_iri: iri, uitkomst: "klaar", voorstellen: 4 },
];
const runStroom = [
  { type: "status", message: "Lex · Werkvoorraad van het werkgebied bepalen" },
  { type: "reeks", fase: "start", run_id: "w1", totaal: 2, ouder: { bron_iri: "urn:wa:werkgebied:wg1", label: OUDER },
    onderdelen: [{ bron_iri: L1, label: "Invorderingswet 1990, Artikel 9, Lid 1" }, { bron_iri: A10, label: "Invorderingswet 1990, Artikel 10" }] },
  ...deel(0, L1, "Invorderingswet 1990, Artikel 9, Lid 1"),
  ...deel(1, A10, "Invorderingswet 1990, Artikel 10"),
  { type: "reeks", fase: "eind", run_id: "w1", totaal: 2, verwerkt: 2, overgeslagen: [] },
  { type: "token", content: "2 bepalingen geannoteerd in werkgebied *Invorderbaarheid*." },
  { type: "opgeslagen", run_id: "w1" },
  { type: "done" },
];
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const gesprekken = {
  g2: [
    { rol: "user", tekst: "Annoteer het werkgebied", ...leeg },
    { rol: "assistant", tekst: "In werkgebied *Invorderbaarheid* zijn **3** bepalingen nog niet geannoteerd.", ...leeg, run_id: "v1",
      bevestiging: { soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 3, schatting: 9000 } },
  ],
  g9: [],
};
const starts = [];
const metStroom = new Set();   // de runs met een bevestigd aantal: die leveren de reeks

await context.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  requests.push({ p, m, body });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/elementen")
    return route.fulfill({ json: { werkgebied_id: "wg1", revisie: 4, volledig: true, elementen: [],
      selecties: wg.bronnen.map((b) => ({ id: b.id, bron_iri: b.bron_iri, label: b.label, rol: b.rol, bereik: b.bereik,
        aantal: 0, afgewezen: 0, bron_gewijzigd: false, onbereikbaar: null })) } });
  if (p.startsWith("/api/werkgebieden/wg1/")) return route.fulfill({ json: {} });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g9", titel: body?.titel ?? "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g2", titel: "Voorstel", aantal_berichten: 2 }] });
  const gesprek = p.match(/^\/api\/gesprekken\/(g\d)$/);
  if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: "Test", berichten: gesprekken[gesprek[1]] ?? [] } });
  if (p === "/api/annotatie/run" && m === "POST") {
    starts.push(body);
    if (body.bevestigd) metStroom.add(`w${starts.length}`);
    return route.fulfill({ status: 201, json: { run_id: `w${starts.length}`, conversation_id: body.conversation_id, status: "loopt" } });
  }
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  const events = p.match(/\/run\/([^/]+)\/events$/);
  if (events) return route.fulfill({ contentType: "text/event-stream", body: sse(metStroom.has(events[1]) ? runStroom : [{ type: "done" }]) });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: p.endsWith("/berichten") && m === "POST" ? { id: 1 } : [] });
});

try {
  // --- De tab Elementen: geen Lex-knop; *Vraag Lex* in de kop wijst naar het gesprek ---
  await page.goto(`${base}/werkgebieden/wg1?tab=elementen`);
  const vraag = page.locator("header [data-vraag-lex=werkgebied]");
  await vraag.waitFor();
  assert.equal(await page.getByRole("region", { name: "Annoteren door Lex" }).count(), 0);
  assert.equal(await page.getByRole("button", { name: /^Laat Lex annoteren/ }).count(), 0);
  assert.match(await vraag.getAttribute("href"), /^\/workbench\?werkgebied=wg1&vraag=werkgebied%3Awg1/);

  // --- `?annoteer=` start niets meer: alleen de bevestiging in het gesprek doet dat ---
  await page.goto(`${base}/workbench?werkgebied=wg1&annoteer=2`);
  const suggestie = page.getByTestId("vraag-suggesties").getByRole("button", { name: "Annoteer wat nog niet geannoteerd is" });
  await suggestie.waitFor();
  await page.waitForTimeout(300);
  assert.equal(starts.length, 0, "Lex begint niet vanuit de URL");

  // --- In het werkgebied: de suggestie vraagt Lex om het voorstel; de bevestiging komt in het gesprek ---
  await suggestie.click();
  for (let i = 0; i < 50 && starts.length < 1; i++) await page.waitForTimeout(50);
  assert.deepEqual({ actie: starts[0].actie, bevestigd: starts[0].bevestigd, modus: starts[0].modus,
    werkgebied_id: starts[0].werkgebied_id },
  { actie: "werkgebied_annoteren", bevestigd: undefined, modus: undefined, werkgebied_id: "wg1" },
  "zonder bevestigd: Lex begint niet, hij doet een voorstel");

  // --- Een voorstel van Lex in het gesprek: de knop staat er na herladen en start de run ---
  await page.goto(`${base}/workbench?gesprek=g2`);
  const knop = page.getByRole("button", { name: "Laat Lex annoteren (3 bepalingen)" });
  await knop.click();
  for (let i = 0; i < 50 && starts.length < 2; i++) await page.waitForTimeout(50);
  assert.deepEqual({ modus: starts[1].modus, bevestigd: starts[1].bevestigd, werkgebied_id: starts[1].werkgebied_id,
    conversation_id: starts[1].conversation_id },
  { modus: "werkgebied_annoteren", bevestigd: 3, werkgebied_id: "wg1", conversation_id: "g2" },
  "het werkgebied uit de bevestiging, ook zonder werkgebied in de URL");

  // --- De voortgang: één reeksblok over artikelen heen, de samenvatting erna ---
  await page.getByText("2 bepalingen geannoteerd in werkgebied", { exact: false }).waitFor();
  await page.getByText(`Annotatie ${OUDER}`).waitFor();
  await page.getByText("2 van 2 geannoteerd").waitFor();
  for (const label of ["Invorderingswet 1990, Artikel 9, Lid 1", "Invorderingswet 1990, Artikel 10"])
    await page.getByText(label, { exact: true }).first().waitFor();

  assert.deepEqual(errors, []);
  console.log("Browser OK: geen Lex-knop op de tab Elementen, Vraag Lex in de kop, annoteer= start niets, de suggestie in het werkgebied, knop bij een voorstel na herladen met het bevestigde aantal, reeks over artikelen met samenvatting.");
} finally {
  await browser.close();
}
