/** Browserregressie voor de contenttoets in het gesprek (plan docs/architectuur/plan-contenttoets.md, C3), op de echte
 * Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-contenttoets.mjs` (met `CONTENTTOETS_SCREENSHOT=<map>` beelden op 1440 en 390 px).
 *
 * Bewaakt:
 *  - de plugin staat in *Bronnen en tools* (C4); uitgezet is `/contenttoets` uit het menu, aangezet weer erin;
 *  - `/content` toont `/contenttoets` in het menu; Enter vult het commando aan en verstuurt niets;
 *  - met tekst erachter is het menu dicht, en Enter verstuurt de hele tekst als vraag, zonder actie of doel, met de
 *    plugins van het gesprek;
 *  - het rapport staat als blok in het gesprek: de telling, *Voor de redacteur*, per bewering het oordeel met de
 *    letterlijke bron en de vindplaats, het voorstel van Lex, *Ontbreekt* en *Niet getoetst*;
 *  - op een telefoon (390 px) loopt niets buiten beeld.
 */
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";
import { SCHIL, controleerOnbekend, onbekend, sse } from "./nepApi.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const shots = process.env.CONTENTTOETS_SCREENSHOT || "";
if (shots) mkdirSync(shots, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addCookies(await sessieCookies(base));
await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
const errors = [], runs = [];

// Een zelfgemaakte testtekst met bewust geplaatste fouten; de bron is letterlijk de Leidraad Invordering 2008.
const CONTENT = "Betaalt u liever in termijnen? Dan kunt u een standaardbetalingsregeling van maximaal 12 maanden krijgen. " +
  "U betaalt uw belastingschuld in maximaal 24 maanden, in gelijke termijnen van minimaal € 20 per maand. " +
  "Uw belastingschuld is niet hoger dan € 90.000. Vul het formulier in met uw DigiD.";
const LI = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie25%2FCirculaire.divisie25.3a%2FCirculaire.divisie25.3a.";
const vp = (n, label) => ({ iri: `${LI}${n}`, label, jci: "", regeling: "Leidraad Invordering 2008" });
const TWAALF = { tekst: "een standaardbetalingsregeling verlenen met een looptijd van maximaal twaalf maanden", vindplaats: vp(1, "Artikel 25.3a.1") };
const plek = (s) => { const b = [...CONTENT].length - [...CONTENT.slice(CONTENT.indexOf(s))].length; return { begin: b, eind: b + [...s].length }; };
const bevinding = (nr, citaat, oordeel, criterium, bronnen, rest = {}) => ({ nr, citaat, ...plek(citaat), oordeel, criterium,
  bronnen, toelichting: "", twijfel: "", voorstel: "", ...rest });
const RAPPORT = {
  soort: "contenttoets", door: "lex", content: CONTENT, peildatum: "2026-11-25", getoetst_tegen: ["Leidraad Invordering 2008"],
  voor_redacteur: ["[2] Zet de looptijd op 12 maanden: 24 maanden geldt voor toeslagschulden, niet voor belastingschulden.",
    "[4] Vraag: is € 90.000 de grens van het online formulier? In de Leidraad ligt de grens bij € 100.000."],
  bevindingen: [
    bevinding(1, "standaardbetalingsregeling van maximaal 12 maanden", "juist", "", [TWAALF]),
    bevinding(2, "maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF], {
      toelichting: "Voor belastingschulden noemt de Leidraad twaalf maanden; de tekst zegt bovenaan zelf ook 12.",
      voorstel: "U betaalt uw belastingschuld in maximaal 12 maanden." }),
    bevinding(3, "gelijke termijnen van minimaal € 20 per maand", "juist", "", [{ tekst: "De belastingschuldige betaalt de belastingschuld in gelijke maandelijkse termijnen van ten minste € 20.", vindplaats: vp(1, "Artikel 25.3a.1") }]),
    bevinding(4, "Uw belastingschuld is niet hoger dan € 90.000.", "mogelijk_onjuist", "J2", [{ tekst: "de belastingschuld waarvoor de standaardbetalingsregeling wordt gevraagd bedraagt ten tijde van indiening van het verzoek ten minste € 100.000.", vindplaats: vp(3, "Artikel 25.3a.3") }], {
      toelichting: "Een schuld tussen € 90.000 en € 100.000 valt volgens de Leidraad wel onder de regeling.",
      twijfel: "€ 90.000 kan een grens van het online formulier zijn; die staat niet in de graaf.",
      voorstel: "Is € 90.000 de grens van het online formulier? Zeg dat dan in de tekst." }),
  ],
  ontbreekt: [{ tekst: "Tijdens de standaardregeling verrekent de ontvanger teruggaven met de schuld.", bronnen: [{ tekst: "Gedurende de looptijd van de standaardbetalingsregeling verrekent de ontvanger belastingteruggaven en andere teruggaven met de openstaande belastingschuld.", vindplaats: vp(2, "Artikel 25.3a.2") }] }],
  niet_getoetst: ["Het formulier en DigiD: procesinformatie."],
};
const ANTWOORD = { sjabloon: "contenttoets", versie: 1, doelen: [vp(1, "Artikel 25.3a.1"), vp(3, "Artikel 25.3a.3")], blokken: [
  { soort: "toelichting", door: "lex", kop: "Kort antwoord", tekst: "Getoetst tegen de Leidraad Invordering 2008. De looptijd van 24 maanden en de grens van € 90.000 wijken mogelijk af van de bron." },
  RAPPORT] };
const STROOM = [{ type: "antwoord", antwoord: ANTWOORD }, { type: "token", content: "Het rapport." },
  { type: "grounding", grounded: true, cited: 3, unsupported: [], niet_letterlijk: [], niveau: "gegrond" },
  { type: "opgeslagen", run_id: "r1" }, { type: "done" }];

const page = await context.newPage();
page.on("pageerror", (e) => errors.push(e.message));
await page.route("**/api/**", async (route) => {
  const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g9", titel: body?.titel ?? "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p === "/api/gesprekken/g9") return route.fulfill({ json: { id: "g9", titel: "Contenttoets", berichten: [] } });
  if (p.endsWith("/berichten") && m === "POST") return route.fulfill({ status: 201, json: { id: 1 } });
  if (p === "/api/annotatie/run" && m === "POST") {
    runs.push(body);
    return route.fulfill({ status: 201, json: { run_id: "r1", conversation_id: body.conversation_id, status: "loopt" } });
  }
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  if (p === "/api/annotatie/run/r1/events") return route.fulfill({ contentType: "text/event-stream", body: sse(STROOM) });
  if (p === "/api/plugins") return route.fulfill({ json: { aan: ["contenttoets"], plugins: [{ naam: "contenttoets",
    label: "Contenttoets", beschrijving: "Toetst content op juistheid en volledigheid.", commando: "contenttoets" }] } });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  return onbekend(route, { stil: SCHIL, leeg: [] });
});

try {
  await page.goto(`${base}/workbench`);
  const veld = page.locator('[data-tour="invoer"] textarea');
  const menu = page.locator("[data-commandomenu]");

  // De plugin staat in *Bronnen en tools*: uitgezet is het commando weg, aangezet weer terug.
  const bronnenKnop = page.locator("[data-connectors-menu]");
  await bronnenKnop.waitFor();
  assert.ok(await bronnenKnop.locator('[data-plugin="contenttoets"][data-aan]').count(), "de plugin staat standaard aan");
  await bronnenKnop.click();
  const pluginsMenu = page.locator("[data-plugins-menu]");
  if (shots) { await pluginsMenu.waitFor(); await page.screenshot({ path: `${shots}/contenttoets-bronnen-en-tools-1440.png` }); }
  await pluginsMenu.getByText("Contenttoets", { exact: true }).click();
  await page.keyboard.press("Escape");
  await veld.fill("/content");
  await page.waitForTimeout(200);
  assert.equal(await menu.getByText("/contenttoets").count(), 0, "uitgezet staat het commando niet in het menu");
  await veld.fill("");
  await bronnenKnop.click();
  await pluginsMenu.getByText("Contenttoets", { exact: true }).click();
  await page.keyboard.press("Escape");

  // Het commando staat in het menu en vult aan; er gaat niets weg.
  await veld.fill("/content");
  await menu.getByText("/contenttoets").first().waitFor();
  if (shots) await page.screenshot({ path: `${shots}/contenttoets-menu-1440.png` });
  await veld.press("Enter");
  assert.equal(await veld.inputValue(), "/contenttoets ");
  assert.equal(runs.length, 0, "aanvullen start geen beurt");

  // Met tekst erachter is het menu dicht; Enter verstuurt de hele tekst als vraag.
  await veld.fill(`/contenttoets ${CONTENT}`);
  assert.equal(await menu.count(), 0, "het menu is dicht zodra er tekst achter het commando staat");
  await veld.press("Enter");
  for (let i = 0; i < 100 && !runs.length; i++) await page.waitForTimeout(50);
  assert.equal(runs.length, 1);
  assert.equal(runs[0].question, `/contenttoets ${CONTENT}`);
  assert.ok(!runs[0].actie && !runs[0].doel, "graph-qa herkent het commando zelf");
  assert.deepEqual(runs[0].plugins, ["contenttoets"], "de beurt draagt de plugins van het gesprek");

  // Het rapport in het gesprek.
  const rapport = page.locator("[data-contenttoets]");
  await rapport.waitFor();
  const tekst = await rapport.innerText();
  assert.match(tekst, /Getoetst tegen Leidraad Invordering 2008, geldend op/);
  assert.match(tekst, /Voor de redacteur/);
  assert.equal(await rapport.locator("[data-toetsbevinding]").count(), 4);
  const twee = rapport.locator('[data-toetsbevinding="2"]');
  assert.equal(await twee.getAttribute("data-oordeel"), "mogelijk_onjuist");
  assert.match(await twee.innerText(), /J1 Waarde[\s\S]*“maximaal 24 maanden”[\s\S]*maximaal twaalf maanden[\s\S]*Artikel 25\.3a\.1[\s\S]*Voorstel van Lex/);
  assert.match(await rapport.locator('[data-toetsbevinding="4"]').innerText(), /Twijfel of aanname/);
  assert.match(tekst, /Ontbreekt[\s\S]*verrekent de ontvanger/);
  assert.match(tekst, /Niet getoetst[\s\S]*DigiD/);
  await rapport.scrollIntoViewIfNeeded();
  const naarBegin = () => rapport.evaluate((el) => el.scrollIntoView({ block: "start" }));
  if (shots) {
    await page.screenshot({ path: `${shots}/contenttoets-einde-1440.png` });
    await naarBegin();
    await page.waitForTimeout(200);
    await page.screenshot({ path: `${shots}/contenttoets-begin-1440.png` });
  }

  // Op een telefoon loopt niets buiten beeld.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(300);
  const breed = await page.evaluate(() => document.documentElement.scrollWidth);
  assert.ok(breed <= 390, `de pagina is ${breed} px breed op 390 px`);
  if (shots) {
    await naarBegin();
    await page.waitForTimeout(200);
    await page.screenshot({ path: `${shots}/contenttoets-begin-390.png` });
    await rapport.locator('[data-toetsbevinding="2"]').evaluate((el) => el.scrollIntoView({ block: "start" }));
    await page.waitForTimeout(200);
    await page.screenshot({ path: `${shots}/contenttoets-bevinding-390.png` });
  }

  controleerOnbekend();
  assert.deepEqual(errors, []);
  console.log("OK contenttoets");
} finally {
  await browser.close();
}
