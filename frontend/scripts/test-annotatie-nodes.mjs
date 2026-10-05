/** Browserregressie op echte Next-UI met gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * npm run test:browser (na npx playwright install chromium)
 * Gebruik `localhost`, niet `127.0.0.1`: Next 16 weigert dev-assets aan een andere origin dan de
 * server kent, en dan hydrateert de pagina niet – elke stap time-out dan zonder duidelijke fout.
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
const doel = (lid) => ({ bron_iri: `urn:lid${lid}`, label: `Invorderingswet – artikel 9 lid ${lid}`, snapshot_id: "snapshot",
  type: "Lid", bwb_id: "BWBR0004770", artikel: "9", lid: String(lid), citeertitel: "Invorderingswet 1990" });
const segment = (lid) => ({ bron_iri: `urn:lid${lid}`, parent_iri: "urn:artikel9", type: "Lid", nummer: String(lid), label: `Lid ${lid}`,
  tekst: lid === 1 ? "A😀 ontvanger" : "UITSLUITEND TWEE", bron_hash: `hash${lid}`, volgorde: lid });
// Bepalingen waarvan de annotatie in deze run is verwijderd (POST weergave/verwijder).
const verwijderd = new Set();
const view = (iri) => verwijderd.has(iri)
  ? { ...volledigeView(iri), lagen: [], elementen: [], verwijderd: { op: "2026-09-25T10:00:00+00:00" } }
  : volledigeView(iri);
function volledigeView(iri) {
  const ids = iri === "urn:artikel9" ? [1, 2] : [iri === "urn:lid2" ? 2 : 1];
  return { schema_versie: 2, doel: iri === "urn:artikel9"
      ? { bron_iri: iri, label: "Artikel 9", type: "Artikel", bwb_id: "BWBR0004770", artikel: "9", citeertitel: "Invorderingswet 1990" }
      : doel(ids[0]),
    snapshot_id: "snapshot", segmenten: ids.map(segment),
    lagen: ids.map((id) => ({ id: `laag${id}`, bron_iri: `urn:lid${id}`, status: "in_review", revisie: 1 })),
    elementen: ids.includes(1) ? [{ id: "e1", eigenaar_iri: "urn:lid1", laag_id: "laag1", klasse: "Rechtssubject", tekst: "ontvanger", toelichting: "Voert de handeling uit", lifecycle: "voorgesteld", herkomst: "agent",
      ankers: [{ bron_iri: "urn:lid1", start: 3, eind: 12, tekst: "ontvanger", bron_hash: "hash1" }],
      review_uitleg: "Handelende instantie geverifieerd", aandacht: "groen",
      alternatieven: [{ klasse: "Rechtsobject", motivatie: "De ontvanger is hier handelend" }],
      beslissingen: [{ type: "comment", actor: "Reviewer", comment: "Bron nagekeken", wijziging: {} }],
      trace: { kandidaat: { gedegradeerd: true, mogelijke_klassen: ["Rechtssubject", "Rechtsobject"],
        span: { bron_iri: "urn:lid1", start: 3, eind: 12 }, spanopties: [{ soort: "zin", start: 0, eind: 12 }],
        bewijs: [{ detector: "rol", code: "ROL_ACTOR", regel: "jas.subject.actor", detail: "ontvanger" }] },
        beslissing: { door: "model", klasse: "Rechtssubject" }, vraag: "k1 | ontvanger | Rechtssubject, Rechtsobject",
        twijfel: [{ reden: "DETECTOR_CONFLICT", alternatieven: ["Rechtsobject"] }], resolutie: [{ regel: "R-CONFLICT-KEEP" }] },
    }] : [], verwijzingen: [],
    // Dekkingsmeting: in lid 2 vond geen detector iets bij "TWEE" (codepoints 12–16), en de
    // tijdsdimensie draaide niet.
    dekking: ids.includes(2) ? { voltooid: true, structureel: { "urn:lid2": {
      dimensies: { actor: "uitgevoerd", tijd: "overgeslagen" }, ongedekt: [{ tekst: "TWEE", start: 12, eind: 16 }] } } } : {} };
}
const verklaringen = {
  besluit: { model: { naam: "model", uitleg: "Het model koos uit de klassen die het patroon toeliet." } },
  regels: { "jas.subject.actor": { naam: "Handelende partij", uitleg: "Wie de handeling verricht.", soort: "detector" } },
  twijfel: { DETECTOR_CONFLICT: { naam: "Detectoren spreken elkaar tegen", uitleg: "Twee klassen kwamen in aanmerking." } },
  resolutie: { "R-CONFLICT-KEEP": { naam: "Klasse behouden", uitleg: "De reviewer bevestigde de klasse." } },
};
// Een bewaard spoor met start én einde van dezelfde aanroep los. Na herladen
// hoort dat één regel te zijn ("1 aanroepen"), niet twee.
const trace = [
  { run_id: "r1", call_id: "call1", tool: "search_annotaties", phase: "start", status: "running" },
  { run_id: "r1", call_id: "call1", tool: "search_annotaties", phase: "end", status: "ok", aantal: 2, has_more: true },
];
const berichten = [1, 2].flatMap((lid) => [
  { rol: "user", tekst: `Annoteer artikel 9 lid ${lid}`, denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" },
  { rol: "assistant", tekst: "", denk: "", bronnen: [], annotatie_slug: "zelfde-oude-laag", annotatie_titel: "Artikel 9", annotatie_doel: doel(lid),
    tool_executions: trace, run_id: `r${lid}` },
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
  else if (url.pathname.endsWith("/verklaringen")) body = verklaringen;
  else if (url.pathname.endsWith("/elementen/e1/graaf")) body = { element_id: "e1", laag_id: "laag1",
    turtle: "<urn:jas:element:e1> a <urn:jas-ns:Markering> .",
    graafcontrole: { laag_id: "laag1", revisie: 1, status: "in_orde", afwijkingen: [], shacl: { beschikbaar: true, conform: true, aantal: 0 } } };
  else if (url.pathname.endsWith("/lagen/laag1/revisies")) body = [
    { revisie: 2, actor: "jan", tijdstip: "2026-10-05T10:00:00+00:00", acties: [{ actie: "approve", element_id: "e1" }] },
    { revisie: 1, actor: "lex", tijdstip: "2026-10-04T10:00:00+00:00", acties: [{ actie: "element-gemaakt", element_id: "e1" }, { actie: "batch" }] }];
  else if (url.pathname === "/api/gesprekken/g1") body = { id: "g1", user_id: "browser-test", titel: "Test", berichten };
  else if (url.pathname === "/api/gesprekken") body = [{ id: "g1", titel: "Test", aantal_berichten: 4 }];
  else if (url.pathname.includes("/actief")) return route.fulfill({ status: 404, json: {} });
  else if (url.pathname.includes("/verbruik")) body = { actief: false, geblokkeerd: false };
  else if (url.pathname.endsWith("/elementen")) body = { id: "nieuw" };
  if (url.pathname.endsWith("/weergave/verwijder")) {
    verwijderd.add(req.postDataJSON().bron_iri);
    return route.fulfill({ json: { verwijderd: { lagen: 2, elementen: 1 }, graaf: "verwijderd" } });
  }
  if (url.pathname.endsWith("/weergave/export")) return route.fulfill({ contentType: "application/json", body: "{}" });
  return route.fulfill({ status: 200, json: body });
});
// De wettekst staat in `DocumentPaneel` als blokken met `data-offset`; per lid is de tweede
// tekstknoop de lidtekst zelf (de eerste is het lidnummer "1.").
const wettekst = () => page.locator('[data-tour="wettekst"]');
async function selecteer(van, tot) {
  await page.evaluate(([van, tot]) => {
    const blokken = document.querySelectorAll('[data-tour="wettekst"] [data-offset]');
    const knoop = (i) => { const w = document.createTreeWalker(blokken[i], NodeFilter.SHOW_TEXT); w.nextNode(); return w.nextNode(); };
    const r = document.createRange(); r.setStart(knoop(van[0]), van[1]); r.setEnd(knoop(tot[0]), tot[1]);
    window.getSelection().removeAllRanges(); window.getSelection().addRange(r);
    blokken[tot[0]].dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  }, [van, tot]);
}
// Wacht op een vastgelegde request; `waitForResponse` na de klik mist een gemockt antwoord dat al binnen is.
async function verzoek(pred, aantal = 1) {
  for (let i = 0; i < 100 && requests.filter(pred).length < aantal; i++) await page.waitForTimeout(100);
  const treffers = requests.filter(pred);
  assert.ok(treffers.length >= aantal, "verwachte request bleef uit");
  return treffers.at(-1);
}
const isNieuw = (r) => r.path.endsWith("/elementen") && r.method === "POST";
try {
  await page.goto(`${base}/annotaties/node?bron_iri=urn:lid1&snapshot_id=snapshot`);
  await wettekst().getByText("ontvanger", { exact: false }).waitFor();
  assert.equal(await page.getByText("UITSLUITEND TWEE", { exact: false }).count(), 0);
  // Het vertrouwde paneel: kop met statuspil, exportknop en afronden.
  await page.getByText("Invorderingswet 1990 – art. 9 lid 1", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Annotatie afronden", exact: true }).waitFor();
  // Historie: per revisie wie wat deed, pas bij openklappen geladen; een geraakt element kies je met één klik.
  assert.equal(requests.filter((r) => r.path.endsWith("/revisies")).length, 0);
  const historie = page.getByTestId("revisies");
  await historie.locator("summary").click();
  await historie.getByText("ronde van Lex: 1 markering", { exact: false }).waitFor();
  await historie.getByText("akkoord", { exact: false }).first().waitFor();
  await historie.getByRole("button", { name: "ontvanger" }).first().click();
  await page.getByText("Review: Handelende instantie geverifieerd", { exact: true }).waitFor();
  await historie.locator("summary").click();
  // De klasse is de knop; het palet wijzigt meteen.
  await page.getByTitle("Andere klasse kiezen").click();
  await page.getByText("Review: Handelende instantie geverifieerd", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Rechtsobject", exact: true }).first().click();
  const decision = await verzoek((r) => r.path.endsWith("/beslissing"));
  assert.equal(decision.body.type, "edit");
  assert.deepEqual(decision.body.wijziging, { klasse: "Rechtsobject" });
  assert.equal(decision.body.snapshot_id, "snapshot");
  assert.deepEqual(decision.body.verwachte_revisies, { "urn:lid1": 1 });
  // Waarom: leesbare namen in beeld, het id in de tooltip, de modelvraag onder technisch detail.
  const waarom = page.getByTestId("waarom").first();
  await waarom.getByText("Waarom?", { exact: true }).click();
  await waarom.getByText("Handelende partij", { exact: true }).waitFor();
  assert.match(await waarom.getByText("Handelende partij", { exact: true }).getAttribute("title"), /^jas\.subject\.actor – /);
  await waarom.getByText("Detectoren spreken elkaar tegen", { exact: true }).waitFor();
  await waarom.getByText("Klasse behouden", { exact: true }).waitFor();
  await waarom.getByText("Beoordeeld zonder zinsontleding", { exact: false }).waitFor();
  await page.getByText("gedegradeerd", { exact: true }).first().waitFor();
  await waarom.getByText("Technisch detail", { exact: true }).click();
  await waarom.getByText("k1 | ontvanger | Rechtssubject, Rechtsobject", { exact: true }).waitFor();
  // Technisch detail: de graafcontrole van de laag en de RDF van deze markering, pas nu opgehaald.
  await waarom.getByTestId("graaf-technisch").getByText("De graaf klopt met de database (revisie 1).").waitFor();
  await waarom.getByText("<urn:jas:element:e1> a <urn:jas-ns:Markering> .", { exact: true }).waitFor();
  // Grenskeuze: de chip stuurt alleen de optie; het anker rekent de api uit de bron.
  await page.getByRole("button", { name: "“A😀 ontvanger”", exact: true }).click();
  const grens = await verzoek((r) => r.path.endsWith("/beslissing") && r.body?.type === "grens");
  assert.deepEqual(grens.body.wijziging, { optie: 0 });
  // Zelf markeren via de selectiepopover: " A😀 ontvanger", de emoji op UTF-16 2..4 = codepoint 1..2.
  await selecteer([0, 2], [0, 4]);
  await page.getByRole("dialog", { name: "Markering toevoegen" }).getByRole("button", { name: "Rechtssubject", exact: true }).click();
  const creation = await verzoek(isNieuw);
  assert.deepEqual(creation.body.element.ankers, [{ bron_iri: "urn:lid1", start: 1, eind: 2, tekst: "😀", bron_hash: "hash1" }]);
  assert.equal(creation.body.element.tekst, "😀");
  assert.equal(creation.body.snapshot_id, "snapshot");
  assert.deepEqual(creation.body.verwachte_revisies, { "urn:lid1": 1 });
  await page.getByRole("button", { name: "Exporteren", exact: true }).click();
  await page.getByRole("button", { name: /^JSON/ }).click();
  assert.deepEqual((await verzoek((r) => r.path.endsWith("/weergave/export"))).body, { bron_iri: "urn:lid1", snapshot_id: "snapshot", formaat: "json" });
  await page.getByRole("button", { name: "Exporteren", exact: true }).click();
  await page.getByRole("button", { name: /^RDF \(TriG\)/ }).click();
  assert.deepEqual((await verzoek((r) => r.path.endsWith("/weergave/export") && r.body?.formaat === "trig")).body,
    { bron_iri: "urn:lid1", snapshot_id: "snapshot", formaat: "trig" });
  // Een selectie over twee leden wordt twee bronankers, zonder lidnummer ertussen.
  await page.goto(`${base}/annotaties/node?bron_iri=urn:artikel9`);
  await wettekst().getByText("UITSLUITEND TWEE", { exact: false }).waitFor();
  await selecteer([0, 2], [1, 5]);
  await page.getByRole("dialog", { name: "Markering toevoegen" }).getByRole("button", { name: "Rechtssubject", exact: true }).click();
  const multi = (await verzoek(isNieuw, 2)).body;
  assert.equal(multi.element.ankers.length, 2);
  assert.equal(multi.element.ankers[0].tekst, "😀 ontvanger");
  assert.equal(multi.element.ankers[1].tekst, "UITS");
  assert.equal(multi.element.tekst, "😀 ontvanger UITS");
  // Dekking: het zinsdeel zonder treffer is onderstreept; één klik opent dezelfde popover met het
  // hele zinsdeel, en het overzicht noemt de dimensie die niet draaide.
  await page.getByTestId("dekking-balk").getByText("1 zinsdeel zonder treffer", { exact: false }).waitFor();
  await wettekst().locator("[data-ongedekt]").click();
  await page.getByRole("dialog", { name: "Markering toevoegen" }).getByRole("button", { name: "Rechtsobject", exact: true }).click();
  const zelf = (await verzoek(isNieuw, 3)).body;
  assert.deepEqual(zelf.element.ankers, [{ bron_iri: "urn:lid2", start: 12, eind: 16, tekst: "TWEE", bron_hash: "hash2" }]);
  await page.getByTestId("dekking").locator("summary").click();
  await page.getByTestId("dekking").getByText("tijd overgeslagen", { exact: false }).waitFor();
  await page.getByTestId("dekking-balk").getByRole("button", { name: "Verbergen" }).click();
  assert.equal(await wettekst().locator("[data-ongedekt]").count(), 0);
  // Verwijderen: naast afronden, tweede klik bevestigt, alle lagen in beeld met hun revisie.
  await page.getByRole("button", { name: "Annotatie verwijderen", exact: true }).click();
  await page.getByRole("button", { name: "Verwijderen?", exact: true }).click();
  assert.deepEqual((await verzoek((r) => r.path.endsWith("/weergave/verwijder"))).body,
    { bron_iri: "urn:artikel9", snapshot_id: "snapshot", verwachte_revisies: { "urn:lid1": 1, "urn:lid2": 1 } });
  await page.getByText("Deze annotatie is verwijderd op", { exact: false }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Annotatie verwijderen", exact: true }).count(), 0);
  assert.equal(await page.getByRole("button", { name: "Annotatie afronden", exact: true }).count(), 0);
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByText("Invorderingswet – artikel 9 lid 1", { exact: true }).last().click();
  await wettekst().getByText("ontvanger", { exact: false }).waitFor();
  assert.equal(await wettekst().getByText("UITSLUITEND TWEE", { exact: false }).count(), 0);
  // Kaart kiezen met het toetsenbord (de focus mag niet in het chatveld staan), dan Vraag Lex.
  await wettekst().click();
  await page.keyboard.press("j");
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
  await wettekst().getByText("UITSLUITEND TWEE", { exact: false }).waitFor();
  assert.equal(await wettekst().getByText("ontvanger", { exact: false }).count(), 0);
  await page.reload();
  await page.getByText("Graaf geraadpleegd · 1 aanroepen", { exact: true }).first().click();
  await page.getByText("search_annotaties", { exact: true }).first().waitFor();
  assert.equal(await page.getByText("meer resultaten beschikbaar", { exact: false }).count() >= 1, true);
  assert.deepEqual(errors, []);
  console.log("Browser OK: vertrouwd paneel op bronnodes, verwijderen met bevestiging, lidselectie, twee doelen, herladen toolspoor, Unicode/multiankers, klasse via palet, Vraag Lex/live SSE en mutatie/exportcontract.");
} finally { await browser.close(); }
