/** Browserregressie op echte Next-UI met gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * npm run test:browser (na npx playwright install chromium)
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { encode } from "../node_modules/next-auth/jwt.js";
const base = process.env.TEST_URL || "http://127.0.0.1:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [], requests = [];
page.on("pageerror", (e) => errors.push(e.message));
const token = await encode({ secret: "annotatie-browser-test-only-secret", salt: "authjs.session-token",
  token: { userid: "browser-test", role: "analist", email: "test@example.test", verifiedAt: Date.now(), loginAt: Date.now() } });
await page.context().addCookies([
  { name: "authjs.session-token", value: token, url: base },
  { name: "wa-disclaimer", value: "1", url: base },
]);
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
const doel = (lid) => ({ bron_iri: `urn:lid${lid}`, label: `Invorderingswet – artikel 9 lid ${lid}`, snapshot_id: "snapshot" });
const segment = (lid) => ({ bron_iri: `urn:lid${lid}`, parent_iri: "urn:artikel9", type: "Lid", label: `Lid ${lid}`,
  tekst: lid === 1 ? "A😀 ontvanger" : "UITSLUITEND TWEE", bron_hash: `hash${lid}`, volgorde: lid });
function view(iri) {
  const ids = iri === "urn:artikel9" ? [1, 2] : [iri === "urn:lid2" ? 2 : 1];
  return { schema_versie: 2, doel: iri === "urn:artikel9" ? { bron_iri: iri, label: "Artikel 9" } : doel(ids[0]),
    snapshot_id: "snapshot", segmenten: ids.map(segment),
    lagen: ids.map((id) => ({ id: `laag${id}`, bron_iri: `urn:lid${id}`, status: "in_review", revisie: 1 })),
    elementen: ids.includes(1) ? [{ id: "e1", eigenaar_iri: "urn:lid1", laag_id: "laag1", klasse: "Rechtssubject", tekst: "ontvanger", toelichting: "Voert de handeling uit", lifecycle: "critic_checked", herkomst: "agent",
      ankers: [{ bron_iri: "urn:lid1", start: 3, eind: 12, tekst: "ontvanger", bron_hash: "hash1" }],
      critic: "Handelende instantie geverifieerd", aandacht: "groen",
      alternatieven: [{ klasse: "Rechtsobject", motivatie: "De ontvanger is hier handelend" }],
      critic_rondes: [{ ronde: 1, motivatie: "Actor staat letterlijk in de bron", actie: "behoud", toegepast: true }],
      beslissingen: [{ type: "comment", actor: "Reviewer", comment: "Bron nagekeken", wijziging: {} }],
    }] : [], verwijzingen: [], dekking: {} };
}
const trace = [{ run_id: "r1", call_id: "call1", tool: "search_annotaties", phase: "end", status: "ok", aantal: 2, has_more: true }];
const berichten = [1, 2].flatMap((lid) => [
  { rol: "user", tekst: `Annoteer artikel 9 lid ${lid}`, denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "", ontbrekend: [] },
  { rol: "assistant", tekst: "", denk: "", bronnen: [], annotatie_slug: "zelfde-oude-laag", annotatie_titel: "Artikel 9", annotatie_doel: doel(lid),
    tool_executions: trace, ontbrekend: [], run_id: `r${lid}` },
]);
await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url());
  if (url.pathname.startsWith("/api/auth/")) return route.continue();
  if (url.pathname.includes("/v2/") || (url.pathname === "/api/annotatie/run" && req.method() === "POST")) requests.push({ path: url.pathname, method: req.method(), body: req.postDataJSON(), query: url.search });
  if (url.pathname === "/api/annotatie/run") return route.fulfill({ json: req.method() === "POST" ? { run_id: "live", conversation_id: "g1", status: "loopt" } : null });
  if (url.pathname.endsWith("/events")) return route.fulfill({ contentType: "text/event-stream", body: [
    { type: "tool_execution", run_id: "live", call_id: "live-call", tool: "get_annotatie", phase: "start", status: "running" },
    { type: "tool_execution", run_id: "live", call_id: "live-call", tool: "get_annotatie", phase: "end", status: "ok", aantal: 1 },
    { type: "token", content: "Het element betreft de handelende instantie." },
    { type: "opgeslagen", run_id: "live", annotatie_slug: "" }, { type: "done" },
  ].map((event) => `data: ${JSON.stringify(event)}\n\n`).join("") });
  let body = [];
  if (url.pathname.endsWith("/weergave")) body = view(url.searchParams.get("bron_iri"));
  else if (url.pathname === "/api/gesprekken/g1") body = { id: "g1", user_id: "browser-test", titel: "Test", berichten };
  else if (url.pathname === "/api/gesprekken") body = [{ id: "g1", titel: "Test", aantal_berichten: 4 }];
  else if (url.pathname.includes("/actief")) return route.fulfill({ status: 404, json: {} });
  else if (url.pathname.includes("/verbruik")) body = { actief: false, geblokkeerd: false };
  else if (url.pathname.endsWith("/elementen")) body = { id: "nieuw" };
  if (url.pathname.endsWith("/weergave/export")) return route.fulfill({ contentType: "application/json", body: "{}" });
  return route.fulfill({ status: 200, json: body });
});
try {
  await page.goto(`${base}/annotaties/node?bron_iri=urn:lid1&snapshot_id=snapshot`);
  await page.locator('[data-bron="urn:lid1"]').waitFor();
  assert.equal(await page.locator('[data-bron="urn:lid2"]').count(), 0);
  assert.equal(await page.getByText("UITSLUITEND TWEE", { exact: true }).count(), 0);
  await page.getByText("Onderbouwing en historie", { exact: true }).click();
  await page.getByText("Handelende instantie geverifieerd", { exact: false }).waitFor();
  await page.getByText("Actor staat letterlijk in de bron", { exact: false }).waitFor();
  await page.getByText("Bron nagekeken", { exact: true }).waitFor();
  await page.getByLabel("Klasse", { exact: true }).selectOption("Rechtsobject");
  await page.getByRole("button", { name: "Classificatie opslaan", exact: true }).click();
  await page.getByText("Wijziging opgeslagen.").waitFor();
  const decision = requests.find((r) => r.path.endsWith("/beslissing"));
  assert.equal(decision.body.type, "edit");
  assert.equal(decision.body.wijziging.klasse, "Rechtsobject");
  assert.deepEqual(decision.body.verwachte_revisies, { "urn:lid1": 1 });
  await page.locator('[data-bron="urn:lid1"]').evaluate((root) => {
    const text = root.firstChild.firstChild, r = document.createRange(); r.setStart(text, 1); r.setEnd(text, 3);
    window.getSelection().removeAllRanges(); window.getSelection().addRange(r);
    root.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  });
  await page.getByLabel("JAS-klasse").selectOption("Rechtssubject");
  await page.getByRole("button", { name: "Markering toevoegen", exact: true }).click();
  await page.getByText("Wijziging opgeslagen.").waitFor();
  const creation = requests.find((r) => r.path.endsWith("/elementen") && r.method === "POST");
  assert.deepEqual(creation.body.element.ankers, [{ bron_iri: "urn:lid1", start: 1, eind: 2, tekst: "😀", bron_hash: "hash1" }]);
  assert.equal(creation.body.snapshot_id, "snapshot");
  assert.deepEqual(creation.body.verwachte_revisies, { "urn:lid1": 1 });
  await page.getByRole("button", { name: "Export JSON", exact: true }).click();
  await page.waitForTimeout(100);
  assert.deepEqual(requests.find((r) => r.path.endsWith("/weergave/export")).body, { bron_iri: "urn:lid1", snapshot_id: "snapshot", formaat: "json" });
  await page.goto(`${base}/annotaties/node?bron_iri=urn:artikel9`);
  await page.locator('[data-bron="urn:lid2"]').waitFor();
  await page.locator('[data-bron="urn:lid1"]').evaluate((root) => {
    const end = document.querySelector('[data-bron="urn:lid2"]');
    const r = document.createRange(); r.setStart(root.firstChild.firstChild, 1); r.setEnd(end.firstChild.firstChild, 4);
    window.getSelection().removeAllRanges(); window.getSelection().addRange(r);
    root.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  });
  await page.getByLabel("JAS-klasse").selectOption("Rechtssubject");
  await page.getByRole("button", { name: "Markering toevoegen", exact: true }).click();
  await page.getByText("Wijziging opgeslagen.").waitFor();
  const multi = requests.filter((r) => r.path.endsWith("/elementen") && r.method === "POST").at(-1).body;
  assert.equal(multi.element.ankers.length, 2);
  assert.equal(multi.element.ankers[0].tekst, "😀 ontvanger");
  assert.equal(multi.element.ankers[1].tekst, "UITS");
  assert.equal(multi.element.tekst, "😀 ontvanger UITS");
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByText("Invorderingswet – artikel 9 lid 1", { exact: true }).last().click();
  await page.locator('[data-bron="urn:lid1"]').waitFor();
  assert.equal(await page.locator('[data-bron="urn:lid2"]').count(), 0);
  await page.getByRole("button", { name: "Vraag Lex", exact: true }).click();
  await page.getByRole("button", { name: "Versturen", exact: true }).click();
  await page.getByText("Het element betreft de handelende instantie.", { exact: true }).waitFor();
  const advice = requests.find((r) => r.path === "/api/annotatie/run").body;
  assert.equal(advice.modus, "advies"); assert.equal(advice.context.element_id, "e1");
  assert.equal(advice.context.bron_iri, "urn:lid1");
  await page.getByText("Graaf geraadpleegd · 1 aanroepen", { exact: true }).last().click();
  await page.getByText("get_annotatie", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Sluiten", exact: true }).last().click();
  await page.getByText("Invorderingswet – artikel 9 lid 2", { exact: true }).last().click();
  await page.locator('[data-bron="urn:lid2"]').waitFor();
  assert.equal(await page.locator('[data-bron="urn:lid1"]').count(), 0);
  await page.reload();
  await page.getByText("Graaf geraadpleegd · 1 aanroepen", { exact: true }).first().click();
  await page.getByText("search_annotaties", { exact: true }).first().waitFor();
  assert.equal(await page.getByText("meer resultaten beschikbaar", { exact: false }).count() >= 1, true);
  assert.deepEqual(errors, []);
  console.log("Browser OK: lidselectie, twee doelen, herladen toolspoor, Unicode/multiankers, reviewhistorie/classificatie, Vraag Lex/live SSE en mutatie/exportcontract.");
} finally { await browser.close(); }
