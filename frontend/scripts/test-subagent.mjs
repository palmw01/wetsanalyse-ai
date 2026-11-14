/** Browserregressie voor de delegatie van de centrale agent (ADR-016 §A4, §A5): wat de subagents doen, in het gesprek
 * en in de sidebar. Op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-subagent.mjs`.
 *
 * Bewaakt:
 *  - `regie` en `regie_taak` worden een voortgangsblok in het gesprek: het plan, per subagent de stand en een link naar
 *    het deelgesprek;
 *  - de vraag van een subagent (`sa_vraag`) staat als vraagkaart met *Laat maar*; het antwoord hervat de subagent en de
 *    bundel volgt, en het blok van de eerste beurt toont daarna de stand van nu;
 *  - de sidebar toont de stand van elk deelgesprek uit `/api/delegaties` (wacht op antwoord, klaar);
 *  - *Stop* stopt de beurt, en het blok zegt dat de subagent gestopt is;
 *  - herladen tijdens de run hangt weer aan en toont hetzelfde blok; daarna staat de stand van de api er;
 *  - de bundel van een regie (een artefact) draagt de knop voor de volgende fase (graph-qa #1521, `plan_id` zestien
 *    nullen), live en na herladen, en een regiekind toont zijn profiel zonder "subagent";
 *  - op 375 px past alles, zonder horizontaal scrollen;
 *  - de werkplek schrijft geen assistent-bericht.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const errors = [], geschreven = [], gestopt = new Set(), geopend = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const taak = (titel, profiel) => ({ titel, profiel });
const kindStart = (id, index, gesprek, titel, profiel) => ({ type: "regie_taak", fase: "start", regie_id: id, index, titel,
  gesprek_id: gesprek, profiel, gekozen_model: "licht-model" });
const kindEind = (id, index, gesprek, titel, profiel, uitkomst) => ({ type: "regie_taak", fase: "eind", regie_id: id, index,
  titel, gesprek_id: gesprek, profiel, uitkomst, model: "zwaar-model", modellen: ["licht-model", "zwaar-model"],
  rapport: { status: uitkomst, afbakening: ["alleen de Hoge Raad"], periode: [2020, 2024] } });

// --- de scenario's: per run de events, en wat de api daarna over de delegatie zegt --------------------------------
const VRAAG = { intake_id: "sa-d1", modus: "subagent", stap: "sa_vraag", nr: 1, totaal: 1,
  vraag: "Welke periode bedoel je?", opties: [{ label: "2024", waarde: "2024" }], vrije_tekst: true, overslaanbaar: false };
const PLAN = { opdracht: "subagent", taken: [taak("Uitspraak A", "algemeen"), taak("Uitspraak B", "duiding")] };
const runs = {
  sub1: () => [
    { type: "status", message: "Lex zet twee subagents aan het werk" },
    { type: "regie", fase: "start", regie_id: "d1", soort: "subagent", plan: PLAN },
    kindStart("d1", 0, "g1", "Uitspraak A", "algemeen"),
    kindEind("d1", 0, "g1", "Uitspraak A", "algemeen", "klaar"),
    kindStart("d1", 1, "g2", "Uitspraak B", "duiding"),
    kindEind("d1", 1, "g2", "Uitspraak B", "duiding", "vraag"),
    { type: "regie", fase: "eind", regie_id: "d1", soort: "subagent", uitkomst: "wacht", opgeleverd: 1, wacht: 1,
      kinderen: [{ gesprek_id: "g1", uitkomst: "klaar", profiel: "algemeen" },
        { gesprek_id: "g2", uitkomst: "vraag", profiel: "duiding", vragen: [{ tekst: "Welke periode bedoel je?" }] }] },
    { type: "token", content: "Een subagent heeft een vraag voor je." },
    { type: "vraagkaart", vraagkaart: VRAAG },
    { type: "opgeslagen", run_id: "sub1" },
    { type: "done", uitkomst: "klaar" },
  ],
  sub2: () => [
    { type: "regie", fase: "start", regie_id: "d1", soort: "subagent", hervat: true,
      plan: { opdracht: "subagent", taken: [taak("Uitspraak B", "duiding")] } },
    kindStart("d1", 0, "g2", "Uitspraak B", "duiding"),
    kindEind("d1", 0, "g2", "Uitspraak B", "duiding", "klaar"),
    { type: "regie", fase: "eind", regie_id: "d1", soort: "subagent", uitkomst: "klaar", opgeleverd: 2,
      kinderen: [{ gesprek_id: "g1", uitkomst: "klaar" }, { gesprek_id: "g2", uitkomst: "klaar", hervat: true }] },
    { type: "token", content: "De bundel van beide uitspraken." },
    { type: "opgeslagen", run_id: "sub2" },
    { type: "done", uitkomst: "klaar" },
  ],
  // Loopt tot *Stop*: daarna sluit de stroom met het eind van de subagent.
  stop: () => [
    { type: "regie", fase: "start", regie_id: "d3", soort: "subagent", plan: { opdracht: "subagent", taken: [taak("Uitspraak C", "algemeen")] } },
    kindStart("d3", 0, "g3", "Uitspraak C", "algemeen"),
    ...(gestopt.has("stop") ? [
      kindEind("d3", 0, "g3", "Uitspraak C", "algemeen", "gestopt"),
      { type: "regie", fase: "eind", regie_id: "d3", soort: "subagent", uitkomst: "gestopt", kinderen: [{ gesprek_id: "g3", uitkomst: "gestopt" }] },
      { type: "token", content: "_(gestopt)_" }, { type: "opgeslagen", run_id: "stop" }, { type: "done", uitkomst: "gestopt" },
    ] : []),
  ],
  // Loopt tot de test hem laat aflopen (`klaar`), ook over een herlaadbeurt heen.
  herlaad: () => [
    { type: "regie", fase: "start", regie_id: "d4", soort: "subagent", plan: { opdracht: "subagent", taken: [taak("Uitspraak D", "definitie")] } },
    kindStart("d4", 0, "g4", "Uitspraak D", "definitie"),
    ...(gestopt.has("herlaad") ? [
      kindEind("d4", 0, "g4", "Uitspraak D", "definitie", "klaar"),
      { type: "regie", fase: "eind", regie_id: "d4", soort: "subagent", uitkomst: "klaar", kinderen: [{ gesprek_id: "g4", uitkomst: "klaar" }] },
      { type: "token", content: "Het rapport van de subagent." }, { type: "opgeslagen", run_id: "herlaad" }, { type: "done", uitkomst: "klaar" },
    ] : []),
  ],
};
const VOLGENDE_FASE = { soort: "regie", werkgebied_id: "wg1", opdracht: "annoteren", plan_id: "0".repeat(16), aantal: 2, schatting: null };
const NU = new Date().toISOString();
const WG1 = { id: "wg1", naam: "Invordering", analysevraag: "Wie is aansprakelijk?", afbakening: "", aanleiding: "", context: "",
  doel: "", praktijkvoorbeeld: "", peildatum: null, status: "in_voorbereiding", revisie: 1, aangemaakt_door: "t",
  aangemaakt: NU, gewijzigd: NU, gearchiveerd: null, bronnen: [], deelvragen: [] };
const REGIE_ARTEFACT = { soort: "regie", ref: { werkgebied_id: "wg1", regie_id: "r5" }, titel: "Regie · bronnen" };
runs.regie = () => [
  { type: "regie", fase: "start", regie_id: "r5", plan: { opdracht: "bronnen", taken: [{ titel: "Deelvraag 1" }, { titel: "Deelvraag 2" }] } },
  { type: "regie_taak", fase: "start", regie_id: "r5", index: 0, titel: "Deelvraag 1", gesprek_id: "g5", profiel: "retrieval" },
  { type: "regie_taak", fase: "eind", regie_id: "r5", index: 0, titel: "Deelvraag 1", gesprek_id: "g5", uitkomst: "klaar" },
  { type: "regie_taak", fase: "start", regie_id: "r5", index: 1, titel: "Deelvraag 2", gesprek_id: "g6", profiel: "retrieval" },
  { type: "regie_taak", fase: "eind", regie_id: "r5", index: 1, titel: "Deelvraag 2", gesprek_id: "g6", uitkomst: "klaar" },
  { type: "regie", fase: "eind", regie_id: "r5", uitkomst: "klaar", opgeleverd: 2, wacht: 0, mislukt: 0 },
  { type: "token", content: "De bronnen per deelvraag staan klaar." },
  { type: "opgeslagen", run_id: "regie", artefact: REGIE_ARTEFACT, bevestiging: VOLGENDE_FASE },
  { type: "done", uitkomst: "klaar" },
];
const delegatie = (id, gesprek, status, taken, kinderen) => ({ id, soort: "subagent", werkgebied_id: "", gesprek_id: gesprek,
  user_id: "browser-test", opdracht: "subagent", plan_id: "p".repeat(16), plan: { taken }, status,
  uitkomst: kinderen ? { kinderen } : {}, budget_aandeel: 0, later_gewijzigd: false });
let stand = { sub: "loopt", stopg: "loopt", herlaad: "loopt" };
const delegaties = (gesprek) => gesprek === "sub" ? [delegatie("d1", "sub", stand.sub === "klaar" ? "klaar" : "wacht", PLAN.taken,
  [{ gesprek_id: "g1", uitkomst: "klaar", modellen: ["zwaar-model"], afbakening: ["alleen de Hoge Raad"], periode: [2020, 2024] },
    { gesprek_id: "g2", uitkomst: stand.sub === "klaar" ? "klaar" : "vraag" }])]
  : gesprek === "stopg" ? [delegatie("d3", "stopg", stand.stopg, [taak("Uitspraak C", "algemeen")],
    stand.stopg === "loopt" ? undefined : [{ gesprek_id: "g3", uitkomst: "gestopt" }])]
  : gesprek === "regieg" ? [{ ...delegatie("r5", "regieg", "klaar", [{ titel: "Deelvraag 1" }, { titel: "Deelvraag 2" }]),
    soort: "regie", opdracht: "bronnen", werkgebied_id: "wg1", uitkomst: { opgeleverd: 2 } }]
  : gesprek === "herlaad" ? [delegatie("d4", "herlaad", stand.herlaad, [taak("Uitspraak D", "definitie")],
    stand.herlaad === "loopt" ? undefined : [{ gesprek_id: "g4", uitkomst: "klaar" }])] : [];

const gesprekken = [
  { id: "sub", titel: "Twee uitspraken", aantal_berichten: 4 },
  { id: "g1", titel: "Uitspraak A", aantal_berichten: 1, ouder_id: "sub", delegatie_id: "d1", profiel: "algemeen" },
  { id: "g2", titel: "Uitspraak B", aantal_berichten: 2, ouder_id: "sub", delegatie_id: "d1", profiel: "duiding" },
];
const berichten = {
  sub: [
    { rol: "user", tekst: "Vat deze twee uitspraken samen", ...leeg },
    { rol: "assistant", tekst: "Een subagent heeft een vraag voor je.", ...leeg, run_id: "sub1", delegaties: ["d1"], vraagkaart: VRAAG },
    { rol: "user", tekst: "2024", ...leeg, intake_antwoord: { intake_id: "sa-d1", stap: "sa_vraag", actie: "antwoord" } },
    { rol: "assistant", tekst: "De bundel van beide uitspraken.", ...leeg, run_id: "sub2", delegaties: ["d1"] },
  ],
  herlaad: [{ rol: "user", tekst: "Zoek de definitie op", ...leeg }],
  regieg: [{ rol: "user", tekst: "Zoek per deelvraag de bronnen", ...leeg },
    { rol: "assistant", tekst: "De bronnen per deelvraag staan klaar.", ...leeg, run_id: "regie", artefact: REGIE_ARTEFACT,
      bevestiging: VOLGENDE_FASE, delegaties: ["r5"] }],
  g1: [{ rol: "user", tekst: "OPDRACHT: vat uitspraak A samen.", ...leeg, doorgegeven: "opdracht" },
    { rol: "assistant", tekst: "Rapport van uitspraak A.", ...leeg, run_id: "k1" },
    { rol: "user", tekst: "ANTWOORD OP JE VRAGEN: 2024", ...leeg, doorgegeven: "antwoorden" }],
};
let volgendeRun = "sub1", gid = "sub", actief = null;
const gestart = [];

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/annotatie/run") {
    if (m === "GET") return route.fulfill({ json: actief && url.searchParams.get("gesprek") === actief.conversation_id ? actief : null });
    const run = volgendeRun;
    gestart.push(req.postDataJSON());
    if (run === "sub2") stand.sub = "klaar";
    return route.fulfill({ json: { run_id: run, conversation_id: gid, status: "loopt", vraag: "", volgende_seq: 0, weggevallen: 0 } });
  }
  const stop = p.match(/^\/api\/annotatie\/run\/(\w+)\/cancel$/);
  if (stop) {
    gestopt.add(stop[1]);
    stand.stopg = "gestopt";
    return route.fulfill({ json: { ok: true } });
  }
  const run = p.match(/^\/api\/annotatie\/run\/(\w+)\/events$/);
  if (run) {
    const events = runs[run[1]]();
    // Een stroom zonder `done` laat de werkplek opnieuw aanhaken: even wachten, zoals een run die doorloopt.
    if (events.at(-1)?.type !== "done") await new Promise((r) => setTimeout(r, 400));
    return route.fulfill({ contentType: "text/event-stream", body: sse(events) });
  }
  // Het werkgebied van de regie: de bundel opent het naast het gesprek.
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: WG1 });
  if (p.startsWith("/api/werkgebieden/wg1/")) return route.fulfill({ json: {} });
  if (p === "/api/delegaties") {
    assert.equal(m, "GET");
    return route.fulfill({ json: delegaties(url.searchParams.get("gesprek_id")) });
  }
  const gesprek = p.match(/^\/api\/gesprekken\/(\w+)$/);
  if (gesprek && m === "GET") {
    geopend.push(gesprek[1]);
    return route.fulfill({ json: { id: gesprek[1], titel: gesprek[1], berichten: berichten[gesprek[1]] ?? [] } });
  }
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: gid, titel: "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: gid === "sub" ? gesprekken : [] });
  if (p.endsWith("/berichten") && m === "POST") {
    geschreven.push(req.postDataJSON());
    return route.fulfill({ status: 201, json: { id: geschreven.length } });
  }
  return route.fulfill({ json: {} });
});

async function vraag(id, run, tekst) {
  gid = id;
  volgendeRun = run;
  await page.goto(`${base}/workbench`);
  const veld = page.locator("textarea").first();
  await veld.waitFor();
  await veld.fill(tekst);
  await veld.press("Enter");
}
const taakStanden = async (id) => page.locator(`[data-delegatie=${id}] [data-delegatie-taak]`)
  .evaluateAll((els) => els.map((e) => e.getAttribute("data-delegatie-taak")));
async function wachtOpStanden(id, verwacht) {
  for (let i = 0; i < 100; i++) {
    if (JSON.stringify(await taakStanden(id)) === JSON.stringify(verwacht)) return;
    await page.waitForTimeout(100);
  }
  assert.deepEqual(await taakStanden(id), verwacht, `standen van ${id}`);
}

// 1. Twee subagents, één met een vraag: het blok, de vraagkaart en de sidebar.
await vraag("sub", "sub1", "Vat deze twee uitspraken samen");
await page.locator("[data-delegatie=d1]").first().waitFor();
await wachtOpStanden("d1", ["klaar", "vraag"]);
const blok = await page.locator("[data-delegatie=d1]").first().innerText();
assert.match(blok, /Subagents/);
assert.match(blok, /2 subagents · 1 klaar · 1 wacht op antwoord/);
assert.match(blok, /subagent algemeen · zwaar-model · afbakening: alleen de Hoge Raad · periode 2020–2024/);
assert.equal(await page.locator("[data-delegatie=d1] [data-deelgesprek-link]").count(), 2, "een link per deelgesprek");
await page.locator("[data-vraagdock=sa_vraag]").waitFor();
assert.match(await page.locator("[data-vraagdock=sa_vraag]").innerText(), /Laat maar/);
await page.locator("[data-deelgesprek-stand=vraag]").waitFor();
assert.equal(await page.locator("[data-gesprek-rij=g2] [data-deelgesprek-stand]").getAttribute("data-deelgesprek-stand"), "vraag");

// 2. Het antwoord hervat de subagent; de bundel volgt, en ook het blok van de eerste beurt staat op klaar.
volgendeRun = "sub2";
await page.locator("[data-vraagdock=sa_vraag] [role=option]", { hasText: "2024" }).click();
await page.locator("[data-vraagdock=sa_vraag] button", { hasText: "Verzend" }).click();
await page.getByText("De bundel van beide uitspraken.").waitFor();
assert.equal(await page.locator("[data-delegatie=d1]").count(), 2, "een blok per beurt");
assert.match(await page.locator("[data-delegatie=d1]").last().innerText(), /Subagent gaat verder|Subagents/);
for (let i = 0; i < 50 && (await page.locator("[data-delegatie=d1] [data-delegatie-taak=vraag]").count()); i++) await page.waitForTimeout(100);
assert.equal(await page.locator("[data-delegatie=d1] [data-delegatie-taak=vraag]").count(), 0, "geen open vraag meer");
await page.locator("[data-gesprek-rij=g2] [data-deelgesprek-stand=klaar]").waitFor();

// 3. De link opent het deelgesprek in de werkplek.
await page.locator("[data-delegatie=d1] [data-deelgesprek-link=g1]").first().click();
await page.getByText("Rapport van uitspraak A.").waitFor();
assert.match(page.url(), /gesprek=g1/);
// Wat de code in het deelgesprek doorgaf, is een blok van Lex, geen bubbel van de jurist (bugonderzoek B5).
assert.match(await page.locator("[data-doorgegeven=opdracht]").innerText(), /Opdracht aan de subagent[\s\S]*vat uitspraak A samen/);
assert.match(await page.locator("[data-doorgegeven=antwoorden]").innerText(), /Antwoorden van de jurist, doorgegeven/);
assert.equal(await page.locator(".rounded-bubbel", { hasText: "OPDRACHT" }).count(), 0, "geen bubbel van de jurist");

// 4. Na herladen: de blokken uit de api, met de stand van nu.
await page.goto(`${base}/workbench?gesprek=sub`);
await page.locator("[data-delegatie=d1]").first().waitFor();
await wachtOpStanden("d1", ["klaar", "klaar", "klaar", "klaar"]);

// 5. *Stop*: de subagent stopt mee, en het blok zegt het.
await vraag("stopg", "stop", "Lees uitspraak C");
await page.locator("[data-delegatie=d3] [data-delegatie-taak=loopt]").waitFor();
await page.getByRole("button", { name: "Stoppen" }).click();
await page.locator("[data-delegatie=d3] [data-delegatie-taak=gestopt]").waitFor({ timeout: 10_000 });
await page.getByText("(gestopt)").waitFor();

// 6. Herladen terwijl de subagent loopt: de werkplek hangt weer aan en toont hetzelfde blok.
await vraag("herlaad", "herlaad", "Zoek de definitie op");
await page.locator("[data-delegatie=d4] [data-delegatie-taak=loopt]").waitFor();
actief = { run_id: "herlaad", conversation_id: "herlaad", status: "loopt", vraag: "Zoek de definitie op", volgende_seq: 0, weggevallen: 0 };
await page.goto(`${base}/workbench?gesprek=herlaad`);
await page.locator("[data-delegatie=d4] [data-delegatie-taak=loopt]").waitFor({ timeout: 10_000 });
gestopt.add("herlaad");
stand.herlaad = "klaar";
await page.getByText("Het rapport van de subagent.").waitFor({ timeout: 10_000 });
await page.locator("[data-delegatie=d4] [data-delegatie-taak=klaar]").waitFor();
actief = null;

// 7. De bundel van een regie: de knop voor de volgende fase, live en na herladen; een regiekind heet geen subagent.
await vraag("regieg", "regie", "Zoek per deelvraag de bronnen");
await page.getByText("De bronnen per deelvraag staan klaar.").waitFor();
await page.locator("[data-delegatie=r5] [data-delegatie-taak=klaar]").first().waitFor();
const regieBlok = await page.locator("[data-delegatie=r5]").innerText();
assert.match(regieBlok, /Regie[\s\S]*2 deelgesprekken · 2 klaar/);
assert.ok(!/subagent retrieval/.test(regieBlok), "een regiekind is geen subagent");
await page.getByRole("button", { name: "Start de regie (2 deelgesprekken)" }).waitFor();
await page.goto(`${base}/workbench?gesprek=regieg`);
const knop = page.getByRole("button", { name: "Start de regie (2 deelgesprekken)" });
await knop.waitFor();
volgendeRun = "sub2";
await knop.click();
for (let i = 0; i < 50 && !gestart.some((b) => b.actie === "regie_annoteren"); i++) await page.waitForTimeout(100);
const volgende = gestart.find((b) => b.actie === "regie_annoteren");
assert.ok(volgende, "de knop start de volgende fase");
assert.equal(volgende.plan_id, "0".repeat(16));
assert.equal(volgende.werkgebied_id, "wg1");
assert.ok(geschreven.some((b) => b.bevestiging_antwoord?.keuze === "gestart"), "de keuze wordt bewaard");

// 8. Mobiel (375 px): het blok past, zonder horizontaal scrollen; de link is een volle knop.
await page.setViewportSize({ width: 375, height: 812 });
gid = "sub";
await page.goto(`${base}/workbench?gesprek=sub`);
await page.locator("[data-delegatie=d1]").first().waitFor();
await wachtOpStanden("d1", ["klaar", "klaar", "klaar", "klaar"]);
const maat = await page.evaluate(() => {
  const blok = document.querySelector("[data-delegatie]").getBoundingClientRect();
  const link = document.querySelector("[data-deelgesprek-link]").getBoundingClientRect();
  return { scroll: document.documentElement.scrollWidth, breed: window.innerWidth, rechts: blok.right, link: link.height };
});
assert.ok(maat.scroll <= maat.breed, `geen horizontaal scrollen (${maat.scroll} > ${maat.breed})`);
assert.ok(maat.rechts <= maat.breed, "het blok valt binnen het scherm");
assert.ok(maat.link >= 24, "de link is een klikdoel");

assert.deepEqual(geschreven.filter((b) => b.rol === "assistant"), [], "de werkplek schrijft geen beurt weg");
assert.ok(geopend.includes("g1"), "het deelgesprek is geopend");
assert.deepEqual(errors, []);
await browser.close();
console.log("subagent: alles groen");
