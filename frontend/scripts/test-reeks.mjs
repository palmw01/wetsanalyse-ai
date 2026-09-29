/** Browserregressie: keuzekaart (leden van één artikel) en de reeks, op echte Next-UI met gemockte BFF.
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * npm run test:browser (na npx playwright install chromium)
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { encode } from "../node_modules/next-auth/jwt.js";
const base = process.env.TEST_URL || "http://127.0.0.1:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [], starts = [], weergaven = [];
page.on("pageerror", (e) => errors.push(e.message));
const token = await encode({ secret: "annotatie-browser-test-only-secret", salt: "authjs.session-token",
  token: { userid: "browser-test", role: "analist", email: "test@example.test", verifiedAt: Date.now(), loginAt: Date.now() } });
await page.context().addCookies([
  { name: "authjs.session-token", value: token, url: base },
  { name: "wa-disclaimer", value: "1", url: base },
]);
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const ART = "urn:bwb:BWBR0004770:artikel:9";
const lid = (n) => `${ART}:lid:${n}`;
const OUDER = "Invorderingswet 1990 – Artikel 9";
const kandidaat = (n, stand) => ({ bwbId: "BWBR0004770", artikel: "9", lid: String(n), citeertitel: "Invorderingswet 1990",
  fragment: `Tekst van lid ${n}.`, bron_iri: lid(n), nummer: String(n), soort: "Lid", label: `Lid ${n}`, stand });
const sse = (events) => events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

// Wat de agent per run stuurt. Run k1: de keuzekaart. Run r2: een reeks over lid 1 en 3.
const stromen = {
  k1: [
    { type: "kandidaten", keuze: { soort: "onderdeel", ouder: OUDER, alles: true }, kandidaten: [
      kandidaat(1, { status: "nieuw", voorstellen: 0, te_beoordelen: 0 }),
      kandidaat(2, { status: "afgerond", voorstellen: 5, te_beoordelen: 0 }),
      kandidaat(3, { status: "te_beoordelen", voorstellen: 3, te_beoordelen: 2 }),
    ] },
    { type: "token", content: `${OUDER} heeft 3 leden. Welk deel wil je annoteren?` },
    { type: "done" },
  ],
  r2: [
    { type: "reeks", fase: "start", run_id: "r2", totaal: 2, ouder: { bron_iri: ART, label: OUDER },
      onderdelen: [{ bron_iri: lid(1), label: "Lid 1" }, { bron_iri: lid(3), label: "Lid 3" }] },
    { type: "onderdeel", fase: "start", index: 0, totaal: 2, bron_iri: lid(1), label: "Lid 1" },
    { type: "status", message: "Bron · art. 9 lid 1 (120 tekens)", onderdeel: lid(1) },
    { type: "tool_execution", run_id: "r2.1", call_id: "c1", tool: "get_bronnode", phase: "end", status: "ok", onderdeel: lid(1) },
    { type: "opgeslagen", run_id: "r2.1", annotatie_slug: "", annotatie_doel: { bron_iri: lid(1), label: `${OUDER}, Lid 1`, snapshot_id: "s" }, onderdeel: lid(1) },
    { type: "done", onderdeel: lid(1) },
    { type: "onderdeel", fase: "eind", index: 0, totaal: 2, bron_iri: lid(1), uitkomst: "klaar", voorstellen: 4 },
    { type: "onderdeel", fase: "start", index: 1, totaal: 2, bron_iri: lid(3), label: "Lid 3" },
    { type: "status", message: "Bron · art. 9 lid 3 (80 tekens)", onderdeel: lid(3) },
    { type: "error", message: "De bron veranderde tijdens het ophalen; probeer opnieuw.", onderdeel: lid(3) },
    { type: "onderdeel", fase: "eind", index: 1, totaal: 2, bron_iri: lid(3), uitkomst: "fout", voorstellen: 0,
      fout: "De bron veranderde tijdens het ophalen; probeer opnieuw." },
    { type: "reeks", fase: "eind", run_id: "r2", totaal: 2, verwerkt: 2, overgeslagen: [] },
    { type: "done" },
  ],
};
let volgendeRun = "k1";
let berichten = [];

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url());
  if (url.pathname.startsWith("/api/auth/")) return route.continue();
  if (url.pathname === "/api/annotatie/run" && req.method() === "POST") {
    starts.push(req.postDataJSON());
    const id = volgendeRun;
    volgendeRun = "r2";
    return route.fulfill({ status: 201, json: { run_id: id, conversation_id: "g1", status: "loopt" } });
  }
  if (url.pathname === "/api/annotatie/run") return route.fulfill({ json: null });
  const events = url.pathname.match(/\/run\/([^/]+)\/events$/);
  if (events) return route.fulfill({ contentType: "text/event-stream", body: sse(stromen[events[1]] ?? [{ type: "done" }]) });
  if (url.pathname.endsWith("/weergave")) {
    weergaven.push(url.searchParams.get("bron_iri"));
    return route.fulfill({ json: { schema_versie: 2, snapshot_id: "s",
      doel: { bron_iri: url.searchParams.get("bron_iri"), label: `${OUDER}, Lid 1`, type: "Lid", bwb_id: "BWBR0004770", artikel: "9", lid: "1" },
      segmenten: [{ bron_iri: lid(1), parent_iri: ART, type: "Lid", nummer: "1", label: "Lid 1", tekst: "Tekst van lid 1.", bron_hash: "h", volgorde: 1 }],
      lagen: [], elementen: [], verwijzingen: [], dekking: {} } });
  }
  if (url.pathname === "/api/gesprekken/g1/berichten" && req.method() === "POST") {
    berichten.push(req.postDataJSON());
    return route.fulfill({ status: 201, json: {} });
  }
  if (url.pathname === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", user_id: "browser-test", titel: "Test", berichten } });
  if (url.pathname === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Test", aantal_berichten: berichten.length }] });
  if (url.pathname.includes("/actief")) return route.fulfill({ status: 404, json: {} });
  if (url.pathname.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (url.pathname.includes("/verklaringen")) return route.fulfill({ json: {} });
  return route.fulfill({ status: 200, json: [] });
});

async function wacht(pred, wat) {
  for (let i = 0; i < 100 && !pred(); i++) await page.waitForTimeout(100);
  assert.ok(pred(), `${wat} bleef uit`);
}

try {
  await page.goto(`${base}/workbench?gesprek=g1`);
  const invoer = page.locator("textarea").last();
  // Pas typen als de hydratatie van het gesprek klaar is; die zet het invoerveld anders terug.
  await page.waitForLoadState("networkidle");
  // De gesprekkenlijst is pas gevuld als de app gehydrateerd is (de eerste keer compileert dev).
  await page.getByText("Test", { exact: true }).first().waitFor({ timeout: 120000 });
  await invoer.click();
  await invoer.pressSequentially("annoteer artikel 9 IW 1990");
  assert.equal(await invoer.inputValue(), "annoteer artikel 9 IW 1990");
  await page.getByRole("button", { name: "Versturen", exact: true }).click();

  // De keuzekaart: drie leden met hun stand, focus in de lijst.
  const lijst = page.getByRole("listbox", { name: "Kies leden om te annoteren" });
  await lijst.waitFor();
  assert.equal(await lijst.getByRole("option").count(), 3);
  await lijst.getByText("afgerond", { exact: true }).waitFor();
  await lijst.getByText("2 te beoordelen", { exact: true }).waitFor();
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute("role")), "listbox");

  // Met het toetsenbord: spatie selecteert lid 1, pijl omlaag twee keer, spatie selecteert lid 3.
  await page.keyboard.press(" ");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press(" ");
  await page.getByText("2 gekozen · 1 nieuw · 1 al geannoteerd", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Annoteer geselecteerde (2)", exact: true }).click();

  // Eén run met twee doelen, elk met zijn bronnode.
  await wacht(() => starts.length === 2, "de reeks-run");
  assert.deepEqual(starts[1].doelen.map((d) => d.bron_iri), [lid(1), lid(3)]);
  assert.equal(starts[1].doel, undefined);

  // Het reeksblok: per lid een regel, een fout blijft bij zijn eigen lid.
  await page.getByText("1 van 2 geannoteerd · 1 mislukt", { exact: true }).waitFor();
  await page.getByText("4 voorstellen", { exact: true }).waitFor();
  await page.getByText("De bron veranderde tijdens het ophalen; probeer opnieuw.", { exact: true }).first().waitFor();
  assert.equal(await page.getByRole("button", { name: "Open ›", exact: true }).count(), 1);

  // Het spoor van een lid klapt uit.
  await page.getByRole("button", { name: /Lid 1/ }).first().click();
  await page.getByText("Zo is dit tot stand gekomen", { exact: true }).first().click();
  await page.getByText("Bron · art. 9 lid 1 (120 tekens)", { exact: false }).first().waitFor();

  // Open › opent de annotatie van dat lid.
  await page.getByRole("button", { name: "Open ›", exact: true }).click();
  await wacht(() => weergaven.includes(lid(1)), "de weergave van lid 1");

  // Na herladen staat de reeks er één keer, uit de bewaarde berichten.
  berichten = [
    { rol: "user", tekst: "Annoteer Invorderingswet 1990 – Artikel 9: Lid 1 en Lid 3", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "", run_id: "" },
    { rol: "assistant", tekst: "", denk: "· Bron · art. 9 lid 1", bronnen: [], annotatie_slug: "", annotatie_titel: "IW – art. 9 lid 1", run_id: "r2.1",
      annotatie_doel: { bron_iri: lid(1), label: `${OUDER}, Lid 1`, snapshot_id: "s" }, reeks: { run_id: "r2", index: 0, totaal: 2, ouder: OUDER } },
  ];
  await page.reload();
  await page.getByText("1 van 2 geannoteerd · 1 niet aan bod gekomen", { exact: true }).waitFor();
  assert.equal(await page.getByText(`Annotatie ${OUDER}`, { exact: true }).count(), 1);
  assert.deepEqual(errors, []);
  console.log("Browser OK: keuzekaart met stand en toetsenbord, reeks als één run met twee doelen, blok per lid met fout per lid, Open › per lid, herladen zonder dubbel blok.");
} finally { await browser.close(); }
