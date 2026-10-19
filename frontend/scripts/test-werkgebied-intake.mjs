/** Browserregressie voor "Lex stelt een werkgebied samen" (activiteit 1) op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-werkgebied-intake.mjs`.
 *
 * De mock gedraagt zich als graph-qa (`agent/werkgebied_intake.py`): elke run levert het volgende
 * kaartje als `vraagkaart`-event, en *Aanmaken* een bericht met het artefact `werkgebied`.
 *
 * Bewaakt:
 *  - een startzin geeft het eerste kaartje; *Volgende* stuurt de `intake_actie` mee, met de leesbare
 *    tekst als vraag in het gesprek;
 *  - een klik op een voorstel selecteert alleen; "Weet ik (nog) niet" sluit de andere keuzes uit;
 *  - alleen het laatste kaartje is te bedienen;
 *  - de samenvatting toont wat er aangemaakt wordt; *Werkgebied aanmaken* stuurt `aanmaken`;
 *  - daarna een werkgebiedkaart in de thread, het werkgebiedpaneel ernaast (los van een annotatie) met
 *    de link naar het werkgebied, en de werkplek in de context van het werkgebied;
 *  - de kaart opent het paneel opnieuw;
 *  - na herladen is het laatste kaartje nog te beantwoorden;
 *  - op een smal scherm past het kaartje zonder horizontale scroll.
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

const nu = "2026-10-19T10:00:00+00:00";
const IB = "BWBR0011353", AFD = `urn:bwb:${IB}:hoofdstuk:5:afdeling:5.1`;
const kaart = (stap, nr, vraag, over = {}) => ({
  intake_id: "ik1", soort: "vraag", stap, nr, totaal: 5, vraag, toelichting: "", opties: [], meerkeuze: false,
  vrije_tekst: true, overslaanbaar: stap !== "naam", vooringevuld: [], samenvatting: {}, ...over,
});
const NAAM = kaart("naam", 1, "Hoe noemen we het werkgebied?");
const REGELINGEN = kaart("regelingen", 3, "Welke regeling(en) horen erbij?", {
  meerkeuze: true,
  opties: [{ label: "Wet inkomstenbelasting 2001", waarde: IB, bron: { bwb_id: IB } },
    { label: "Algemene wet inzake rijksbelastingen", waarde: "BWBR0002320", bron: { bwb_id: "BWBR0002320" } },
    { label: "Weet ik (nog) niet", waarde: "onbekend", bron: {} }],
});
const SAMENVATTING = kaart("samenvatting", 5, "Klopt dit werkgebied?", {
  soort: "samenvatting", vrije_tekst: false, overslaanbaar: false,
  samenvatting: { naam: "Box 3", analysevraag: "Wie is belastingplichtig voor box 3?",
    afbakening: "Regelingen: Wet inkomstenbelasting 2001.\nOnderdelen: Afdeling 5.1 – Box 3.", bronnen: ["Afdeling 5.1 – Box 3"] },
});
const ARTEFACT = { soort: "werkgebied", titel: "Box 3", ref: { werkgebied_id: "wg5" } };
const wg = { id: "wg5", naam: "Box 3", analysevraag: "Wie is belastingplichtig voor box 3?",
  afbakening: "Regelingen: Wet inkomstenbelasting 2001.\nOnderdelen: Afdeling 5.1 – Box 3.", peildatum: null,
  status: "in_voorbereiding", revisie: 2, aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null, deelvragen: [],
  bronnen: [{ id: "s1", bron_iri: AFD, label: "Afdeling 5.1 – Box 3", rol: "analyseren", bereik: "onderliggend", reden: "",
    bwb_id: IB, snapshot_id: "s", bron_hash: "h", toegevoegd_door: "t", toegevoegd: nu }] };

const beurt = (run, tekst, extra = []) => [{ type: "token", content: tekst }, ...extra, { type: "opgeslagen", run_id: run }, { type: "done" }];
const stromen = {
  r1: beurt("r1", "Laten we het werkgebied samen bepalen.", [{ type: "vraagkaart", vraagkaart: NAAM }]),
  r2: beurt("r2", "Nu de afbakening.", [{ type: "vraagkaart", vraagkaart: REGELINGEN }]),
  r3: beurt("r3", "Dit is het werkgebied.", [{ type: "vraagkaart", vraagkaart: SAMENVATTING }]),
  r4: [{ type: "token", content: "Werkgebied *Box 3* is aangemaakt met 1 bron." },
    { type: "opgeslagen", run_id: "r4", artefact: ARTEFACT }, { type: "done" }],
};
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const gesprekken = {
  g9: [],
  g3: [
    { rol: "user", tekst: "Kunnen we een werkgebied samenstellen?", ...leeg },
    { rol: "assistant", tekst: "Laten we het werkgebied samen bepalen.", ...leeg, run_id: "x1", vraagkaart: NAAM },
  ],
};
const starts = [];

await context.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  if (p === "/api/werkgebieden/wg5") return route.fulfill({ json: wg });
  if (p.startsWith("/api/werkgebieden/wg5/")) return route.fulfill({ json: {} });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g9", titel: body?.titel ?? "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  const gesprek = p.match(/^\/api\/gesprekken\/(g\d)$/);
  if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: "Test", berichten: gesprekken[gesprek[1]] ?? [] } });
  if (p === "/api/annotatie/run" && m === "POST") {
    starts.push(body);
    return route.fulfill({ status: 201, json: { run_id: `r${starts.length}`, conversation_id: body.conversation_id, status: "loopt" } });
  }
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  const events = p.match(/\/run\/([^/]+)\/events$/);
  if (events) return route.fulfill({ contentType: "text/event-stream", body: sse(stromen[events[1]] ?? [{ type: "done" }]) });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: p.endsWith("/berichten") && m === "POST" ? { id: 1 } : [] });
});

const wacht = async (n) => { for (let i = 0; i < 60 && starts.length < n; i++) await page.waitForTimeout(50); };
const kaartje = (stap) => page.locator(`[data-vraagkaart=${stap}]`);

try {
  await page.goto(`${base}/workbench`);

  // --- De startzin: het eerste kaartje, met alleen een tekstveld ---
  await page.getByPlaceholder("Stel een vraag of geef een opdracht aan Lex…").fill("Kunnen we een werkgebied samenstellen?");
  await page.getByRole("button", { name: "Versturen" }).click();
  await kaartje("naam").getByText("Hoe noemen we het werkgebied?").waitFor();
  assert.equal(await kaartje("naam").getByRole("button", { name: "Overslaan" }).count(), 0, "de naam is verplicht");
  assert.ok(await kaartje("naam").getByRole("button", { name: "Volgende" }).isDisabled(), "zonder antwoord geen Volgende");

  // --- Volgende: de intake_actie, en het antwoord als vraag in het gesprek ---
  await kaartje("naam").locator("textarea").fill("Box 3");
  await kaartje("naam").getByRole("button", { name: "Volgende" }).click();
  await wacht(2);
  assert.equal(starts[1].question, "Box 3");
  assert.deepEqual(starts[1].intake_actie, { intake_id: "ik1", stap: "naam", actie: "antwoord", keuzes: [], tekst: "Box 3" });
  await kaartje("regelingen").waitFor();
  assert.equal(await page.locator("[data-vraagkaart][data-actief]").count(), 1, "alleen het laatste kaartje is actief");
  assert.equal(await kaartje("naam").locator("textarea").count(), 0, "het oude kaartje toont alleen de vraag");

  // --- Een klik selecteert alleen; "Weet ik (nog) niet" sluit de rest uit ---
  const optie = (naam) => kaartje("regelingen").getByRole("option", { name: naam });
  await optie("Wet inkomstenbelasting 2001").click();
  await optie("Algemene wet inzake rijksbelastingen").click();
  assert.equal(starts.length, 2, "een klik op een voorstel start geen beurt");
  await optie("Weet ik (nog) niet").click();
  assert.equal(await kaartje("regelingen").locator("[aria-selected=true]").count(), 1);
  await optie("Wet inkomstenbelasting 2001").click();
  assert.equal(await optie("Weet ik (nog) niet").getAttribute("aria-selected"), "false");
  await kaartje("regelingen").getByRole("button", { name: "Volgende" }).click();
  await wacht(3);
  assert.deepEqual(starts[2].intake_actie.keuzes, [IB]);
  assert.equal(starts[2].question, "Wet inkomstenbelasting 2001");

  // --- De samenvatting en Aanmaken ---
  const samen = kaartje("samenvatting");
  await samen.getByText("Afdeling 5.1 – Box 3", { exact: true }).waitFor();
  await samen.getByRole("button", { name: "Werkgebied aanmaken" }).click();
  await wacht(4);
  assert.equal(starts[3].intake_actie.actie, "aanmaken");

  // --- De werkgebiedkaart, het eigen paneel en de context van het werkgebied ---
  const paneel = page.locator("[data-artefact-soort=werkgebied][data-artefact]");
  await paneel.getByText("Wie is belastingplichtig voor box 3?").waitFor();
  await paneel.getByText("Samengesteld met Lex").waitFor();
  assert.equal(await page.locator("[data-artefact-soort=annotatie]").count(), 0, "geen annotatiepaneel");
  const links = paneel.getByRole("link", { name: "Open het werkgebied" });
  assert.equal(await links.first().getAttribute("href"), "/werkgebieden/wg5");
  for (let i = 0; i < 40 && new URL(page.url()).searchParams.get("werkgebied") !== "wg5"; i++) await page.waitForTimeout(50);
  assert.equal(new URL(page.url()).searchParams.get("werkgebied"), "wg5", "de werkplek gaat verder in het werkgebied");
  assert.equal(await page.locator("[data-vraagkaart][data-actief]").count(), 0, "na het aanmaken is geen kaartje meer actief");
  await paneel.getByRole("button", { name: "Sluiten" }).first().click();
  await paneel.waitFor({ state: "detached" });
  const chip = page.locator("button[data-artefact-soort=werkgebied]").first();
  await chip.getByText("Werkgebied · bekijken").waitFor();
  await chip.click();
  await paneel.getByText("Afdeling 5.1 – Box 3", { exact: true }).waitFor();

  // --- Na herladen is het laatste kaartje nog te beantwoorden ---
  await page.goto(`${base}/workbench?gesprek=g3`);
  await kaartje("naam").locator("textarea").fill("Invordering");
  await kaartje("naam").getByRole("button", { name: "Volgende" }).click();
  await wacht(5);
  assert.equal(starts[4].conversation_id, "g3");
  assert.equal(starts[4].intake_actie.tekst, "Invordering");

  // --- Smal scherm: het kaartje past ---
  const smal = await context.newPage();
  smal.on("pageerror", (e) => errors.push(e.message));
  await smal.setViewportSize({ width: 390, height: 844 });
  await smal.goto(`${base}/workbench?gesprek=g3`);
  await smal.locator("[data-vraagkaart=naam]").waitFor();
  assert.equal(await smal.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, "geen horizontale scroll");

  assert.deepEqual(errors, []);
  console.log("Browser OK: startzin → kaartje, Volgende met intake_actie, selecteren zonder beurt, Weet ik (nog) niet exclusief, alleen het laatste kaartje actief, samenvatting en Aanmaken, werkgebiedkaart en eigen paneel met link, werkplek in het werkgebied, kaartje na herladen, smal scherm.");
} finally {
  await browser.close();
}
