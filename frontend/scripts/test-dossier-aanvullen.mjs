/** Browserregressie voor "Lex vult het dossier aan" op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-dossier-aanvullen.mjs`.
 *
 * De mock gedraagt zich als graph-qa (`agent/werkgebied_intake.py`, `modus: "aanvullen"`): de suggestie
 * start de aanvul-intake, elke run levert het volgende kaartje, *Opslaan* een bericht met het artefact
 * `werkgebied`, en daarna geeft het werkgebied de nieuwe stand terug.
 *
 * Bewaakt:
 *  - in een werkgebied staat *Vul het dossier aan* bij de suggesties en stuurt `actie: "dossier_aanvullen"`;
 *  - het kaartje telt over de gevraagde stappen (1 van 2), een gevuld veld staat vooringevuld in het
 *    tekstveld, de laatste gevraagde vraag heeft *Verzend*;
 *  - de samenvatting toont per veld toen → nu ("(leeg)" bij een leeg veld), de knop heet *Opslaan* en stuurt
 *    `intake_actie.actie: "opslaan"`, ook op het user-bericht; *Stop met aanvullen* in plaats van samenstellen;
 *  - na het opslaan laadt het werkgebiedpaneel opnieuw en toont het nieuwe praktijkvoorbeeld;
 *  - *Vraag Lex* bij een leeg veld in het paneel geeft eerst *Vul het doel aan*;
 *  - een samenvatting zonder wijziging zegt "Er verandert niets." en heeft geen knop.
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

const nu = "2026-10-22T10:00:00+00:00";
const VRAAG = "Wie betaalt box 3?", NIEUWE_VRAAG = "Wie betaalt box 3 over 2026?";
const VOORBEELD = "Een spaarder met een tweede huis.";
const kaart = (stap, nr, vraag, over = {}) => ({
  intake_id: "ia1", modus: "aanvullen", soort: "vraag", stap, nr, totaal: 2, vraag, toelichting: "", opties: [],
  meerkeuze: false, vrije_tekst: true, meer_tekst: false, overslaanbaar: true, vooringevuld: [], samenvatting: {},
  terug: nr > 1, beantwoord: true, deel: null, ...over,
});
const PRAKTIJK = kaart("praktijkvoorbeeld", 1, "Is er een gangbaar praktijkvoorbeeld?");
const ANALYSEVRAAG = kaart("analysevraag", 2, "Wat is de analysevraag?", { vooringevuld: [VRAAG] });
const samenvatting = (wijzigingen, over = {}) => kaart("samenvatting", 2, "Klopt dit?", {
  soort: "samenvatting", vrije_tekst: false, overslaanbaar: false, terug: true, beantwoord: false,
  toelichting: wijzigingen.length ? "Sla het op om het werkgebied aan te passen; de wijziging komt in de historie."
    : "Er verandert niets.",
  samenvatting: { wijzigingen }, ...over,
});
const SAMEN = samenvatting([
  { veld: "analysevraag", label: "Analysevraag", toen: VRAAG, nu: NIEUWE_VRAAG },
  { veld: "praktijkvoorbeeld", label: "Praktijkvoorbeeld", toen: "", nu: VOORBEELD },
]);
const NIETS = samenvatting([], { intake_id: "ia2", totaal: 1, nr: 1, terug: true });
// Spoor I7: het thema als kaartje van het aanvullen, met het voorstel van Lex aangevinkt.
const BELASTING = "https://identifier.overheid.nl/tooi/def/thes/top/c_25e30d03";
const THEMA = kaart("thema", 1, "Welk thema heeft het werkgebied?", { intake_id: "ia3", totaal: 1, vrije_tekst: false,
  beantwoord: false, terug: false, vooringevuld: [BELASTING],
  opties: [{ label: "belasting", waarde: BELASTING, bron: {}, omschrijving: "voorstel van Lex, uit Belastingrecht" }] });
const ARTEFACT = { soort: "werkgebied", titel: "Box 3", ref: { werkgebied_id: "wg7" } };

const wg = { id: "wg7", naam: "Box 3", analysevraag: VRAAG, afbakening: "", aanleiding: "", context: "", doel: "",
  praktijkvoorbeeld: "", peildatum: null, status: "in_voorbereiding", revisie: 3, aangemaakt_door: "t",
  aangemaakt: nu, gewijzigd: nu, gearchiveerd: null, bronnen: [], deelvragen: [] };

const beurt = (run, tekst, k) => [{ type: "status", message: "Lex · vult met je het dossier aan" },
  { type: "token", content: tekst }, { type: "vraagkaart", vraagkaart: k }, { type: "opgeslagen", run_id: run }, { type: "done" }];
const stromen = {
  r1: beurt("r1", "Laten we het dossier aanvullen.", PRAKTIJK),
  r2: beurt("r2", "Dan de vraag die het werkgebied moet beantwoorden.", ANALYSEVRAAG),
  r3: beurt("r3", "Dit verandert er in het dossier.", SAMEN),
  r4: [{ type: "token", content: "Het dossier van *Box 3* is aangepast: analysevraag gewijzigd en praktijkvoorbeeld ingevuld." },
    { type: "opgeslagen", run_id: "r4", artefact: ARTEFACT }, { type: "done" }],
  r5: beurt("r5", "Laten we het dossier aanvullen.", NIETS),
  r6: beurt("r6", "Dan het thema. Ik leid het af uit de rechtsgebieden van de bronnen.", THEMA),
};
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const starts = [], berichten = [];
let opgeslagen = false;

await context.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  if (p === "/api/werkgebieden/wg7") {
    return route.fulfill({ json: opgeslagen
      ? { ...wg, analysevraag: NIEUWE_VRAAG, praktijkvoorbeeld: VOORBEELD, revisie: 4 } : wg });
  }
  if (p === "/api/werkgebieden/wg7/deelvragen/dekking") return route.fulfill({ json: { deelvragen: [], telling: {}, totaal: 0 } });
  if (p.startsWith("/api/werkgebieden/wg7/")) return route.fulfill({ json: {} });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g9", titel: body?.titel ?? "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (/^\/api\/gesprekken\/g\d$/.test(p)) return route.fulfill({ json: { id: "g9", titel: "Test", berichten: [] } });
  if (p.endsWith("/berichten") && m === "POST") { berichten.push(body); return route.fulfill({ status: 201, json: { id: berichten.length } }); }
  if (p === "/api/annotatie/run" && m === "POST") {
    starts.push(body);
    if (body?.intake_actie?.actie === "opslaan") opgeslagen = true;
    return route.fulfill({ status: 201, json: { run_id: `r${starts.length}`, conversation_id: body.conversation_id, status: "loopt" } });
  }
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  const events = p.match(/\/run\/([^/]+)\/events$/);
  if (events) return route.fulfill({ contentType: "text/event-stream", body: sse(stromen[events[1]] ?? [{ type: "done" }]) });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return route.fulfill({ json: [] });
});

const wacht = async (n) => { for (let i = 0; i < 80 && starts.length < n; i++) await page.waitForTimeout(50); };
const dock = (stap) => page.locator(`[data-vraagdock=${stap}]`);
const suggesties = () => page.getByTestId("vraag-suggesties");

try {
  await page.goto(`${base}/workbench?werkgebied=wg7`);

  // --- De suggestie in het werkgebied: een vaste handeling, zonder model gekozen ---
  await suggesties().getByRole("button", { name: "Vul het dossier aan" }).click();
  await wacht(1);
  assert.equal(starts[0].actie, "dossier_aanvullen");
  assert.equal(starts[0].werkgebied_id, "wg7");
  assert.equal(starts[0].question, "Vul het dossier aan");

  // --- Het eerste gevraagde veld: 1 van 2, leeg, zonder voorstel ---
  await dock("praktijkvoorbeeld").getByText("1 van 2").waitFor();
  assert.equal(await dock("praktijkvoorbeeld").getByLabel("Typ je antwoord").inputValue(), "");
  assert.equal(await dock("praktijkvoorbeeld").getByRole("option").count(), 0, "een praktijkvoorbeeld verzint Lex niet");
  await dock("praktijkvoorbeeld").getByRole("button", { name: "Stop met aanvullen" }).waitFor();
  await dock("praktijkvoorbeeld").getByLabel("Typ je antwoord").fill(VOORBEELD);
  await dock("praktijkvoorbeeld").getByRole("button", { name: "Volgende", exact: true }).click();
  await wacht(2);
  assert.deepEqual(starts[1].intake_actie, { intake_id: "ia1", stap: "praktijkvoorbeeld", actie: "antwoord", keuzes: [],
    tekst: VOORBEELD });

  // --- Een gevuld veld staat vooringevuld; de laatste gevraagde vraag heeft Verzend ---
  const veld = dock("analysevraag").getByLabel("Typ je antwoord");
  await veld.waitFor();
  assert.equal(await veld.inputValue(), VRAAG, "het veld staat vooringevuld met wat er al staat");
  await veld.fill(NIEUWE_VRAAG);
  await dock("analysevraag").getByRole("button", { name: "Verzend" }).click();
  await wacht(3);
  assert.equal(starts[2].intake_actie.tekst, NIEUWE_VRAAG);

  // --- De samenvatting: toen → nu, en Opslaan ---
  const samen = dock("samenvatting");
  await samen.locator("[data-wijziging=praktijkvoorbeeld] [data-toen]").getByText("(leeg)").waitFor();
  await samen.locator("[data-wijziging=praktijkvoorbeeld] [data-nu]").getByText(VOORBEELD).waitFor();
  assert.equal(await samen.locator("[data-wijziging=analysevraag] del").textContent(), VRAAG);
  await samen.locator("[data-wijziging=analysevraag] [data-nu]").getByText(NIEUWE_VRAAG).waitFor();
  assert.equal(await samen.getByRole("button", { name: /Werkgebied aanmaken/ }).count(), 0);
  await samen.getByRole("button", { name: "Opslaan" }).click();
  await wacht(4);
  assert.deepEqual({ ...starts[3].intake_actie }, { intake_id: "ia1", stap: "samenvatting", actie: "opslaan" });
  assert.deepEqual(berichten.find((b) => b.rol === "user" && b.intake_antwoord?.actie === "opslaan")?.intake_antwoord,
    { intake_id: "ia1", stap: "samenvatting", actie: "opslaan" });
  await page.locator("[data-vragenkaart]").getByText("Sla de wijziging op.").waitFor();

  // --- Na het opslaan: het paneel laadt opnieuw en toont het nieuwe dossier ---
  const paneel = page.locator("[data-artefact-soort=werkgebied][data-artefact]");
  await paneel.locator("[data-dossier-veld=praktijkvoorbeeld]").getByText(VOORBEELD).waitFor();
  await paneel.locator("[data-dossier-veld=analysevraag]").getByText(NIEUWE_VRAAG).waitFor();
  assert.equal(await page.locator("[data-vraagdock]").count(), 0, "geen open vraag meer");

  // --- Vraag Lex bij een leeg veld: eerst de suggestie voor dat veld ---
  await paneel.locator("[data-dossier-veld=doel]").getByRole("button", { name: "Vraag Lex: doel aanvullen" }).click();
  const eerste = suggesties().getByRole("button").first();
  assert.equal(await eerste.textContent(), "Vul het doel aan");
  assert.equal(await eerste.getAttribute("data-actie"), "dossier_aanvullen");
  await eerste.click();
  await wacht(5);
  assert.equal(starts[4].actie, "dossier_aanvullen");
  assert.equal(starts[4].question, "Vul het doel aan");
  assert.equal(starts[4].onderwerp?.soort, "werkgebied");
  assert.equal(starts[4].onderwerp?.veld, undefined, "het veld gaat niet als onderwerp mee: graph-qa leest de tekst");

  // --- Een samenvatting zonder wijziging: geen knop ---
  await dock("samenvatting").getByText("Er verandert niets.").waitFor();
  assert.equal(await dock("samenvatting").getByRole("button", { name: "Opslaan" }).count(), 0);

  // --- Kies een thema: dezelfde vraagkaarten, met het voorstel van Lex aangevinkt ---
  await dock("samenvatting").getByRole("button", { name: "Vraag sluiten" }).click();
  await suggesties().getByRole("button", { name: "Kies een thema" }).click();
  await wacht(6);
  assert.equal(starts[5].actie, "dossier_aanvullen");
  assert.equal(starts[5].question, "Kies een thema");
  const thema = dock("thema");
  await thema.getByText("voorstel van Lex, uit Belastingrecht").waitFor();
  assert.equal(await thema.getByRole("option", { name: /belasting/ }).getAttribute("aria-selected"), "true");
  assert.equal(await thema.getByLabel("Typ je antwoord").count(), 0, "een thema typ je niet: het komt uit tooitop");
  await thema.getByRole("button", { name: "Verzend" }).click();
  await wacht(7);
  assert.deepEqual(starts[6].intake_actie, { intake_id: "ia3", stap: "thema", actie: "antwoord", keuzes: [BELASTING] });

  assert.deepEqual(errors, []);
  console.log("Browser OK: Vul het dossier aan als actie, kaartjes over de gevraagde stappen, vooringevuld, Verzend, samenvatting toen → nu met Opslaan (ook op het user-bericht), Stop met aanvullen, het paneel laadt opnieuw, Vraag Lex bij een leeg veld, geen knop zonder wijziging, Kies een thema als kaartje met het voorstel aangevinkt.");
} finally {
  await browser.close();
}
