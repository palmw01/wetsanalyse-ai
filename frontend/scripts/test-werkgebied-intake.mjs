/** Browserregressie voor "Lex stelt een werkgebied samen" (activiteit 1) op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-werkgebied-intake.mjs`.
 *
 * De mock gedraagt zich als graph-qa (`agent/werkgebied_intake.py`): elke run levert het volgende
 * kaartje als `vraagkaart`-event, en *Aanmaken* een bericht met het artefact `werkgebied`.
 *
 * Bewaakt (F1, zoals Claude een vraag stelt):
 *  - de open vraag staat onderaan in plaats van het invoerveld (de dock), in de thread alleen de
 *    Vragen-kaart met "Een vraag stellen ›";
 *  - *Volgende* stuurt de `intake_actie`; het antwoord komt in de Vragen-kaart, niet als bubbel, en het
 *    user-bericht draagt `intake_antwoord` (zodat het na herladen klopt);
 *  - opties met omschrijving; een klik selecteert alleen; "Weet ik (nog) niet" sluit de rest uit; eigen
 *    tekst vervangt bij één keuze de gekozen optie (de aanleiding);
 *  - F2: de deelvragen – voorstellen kiezen én meerdere eigen regels (Enter of *+ Nog een deelvraag*),
 *    als `teksten`; de samenvatting toont het hele dossier; het paneel na aanmaken ook, met de dekking
 *    per deelvraag;
 *  - F3f: de bepalingen per deelvraag – een kaartje per deelvraag met de deelvraag erbij en `deel` in de
 *    klik; ‹ bladert naar het vorige deel (`naar_deel`), en de Vragen-kaart houdt een paar per deel;
 *  - de laatste vraag (het laatste deel) heeft *Verzend*; de samenvatting *Werkgebied aanmaken*;
 *  - ✕ geeft het invoerveld terug, "Een vraag stellen ›" opent de vraag weer;
 *  - ‹ stuurt `wijzig` naar de vorige stap;
 *  - na aanmaken: de werkgebiedkaart, het eigen paneel met link, de werkplek in het werkgebied, en
 *    geen open vraag meer;
 *  - na herladen: dezelfde Vragen-kaart en de open vraag onderaan;
 *  - op een smal scherm past de dock zonder horizontale scroll.
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

const nu = "2026-10-20T10:00:00+00:00";
const IB = "BWBR0011353", L21 = `urn:bwb:${IB}:artikel:2.1:lid:1`, L52 = `urn:bwb:${IB}:artikel:5.2:lid:1`;
const kaart = (stap, nr, vraag, over = {}) => ({
  intake_id: "ik1", soort: "vraag", stap, nr, totaal: 10, vraag, toelichting: "", opties: [], meerkeuze: false,
  vrije_tekst: true, meer_tekst: false, overslaanbaar: stap !== "naam", vooringevuld: [], samenvatting: {},
  terug: stap !== "naam", beantwoord: false, ...over,
});
const DV1 = "Wie is belastingplichtig voor box 3?";
const NAAM = kaart("naam", 1, "Hoe noemen we het werkgebied?");
const AANLEIDING = kaart("aanleiding", 2, "Wat is de aanleiding voor deze wetsanalyse?", {
  opties: [{ label: "Een wetswijziging raakt een bestaand proces", waarde: "wetswijziging", bron: {},
    omschrijving: "Gewijzigde wetgeving vraagt om aanpassing van de uitvoering" },
  { label: "Een handmatig proces digitaliseren", waarde: "digitaliseren", bron: {}, omschrijving: "" }],
});
const DEELVRAGEN = kaart("deelvragen", 7, "Welke deelvragen horen bij de analysevraag?", {
  meerkeuze: true, meer_tekst: true,
  opties: [{ label: DV1, waarde: DV1, bron: {}, omschrijving: "voorstel van Lex" },
    { label: "Hoe wordt het voordeel berekend?", waarde: "Hoe wordt het voordeel berekend?", bron: {}, omschrijving: "voorstel van Lex" }],
});
const REGELINGEN = kaart("regelingen", 9, "Welke regeling(en) horen erbij?", {
  meerkeuze: true,
  opties: [{ label: "Wet inkomstenbelasting 2001", waarde: IB, bron: { bwb_id: IB }, omschrijving: "wet · 2 delen over ‘box 3’ · bij een deelvraag" },
    { label: "Algemene wet inzake rijksbelastingen", waarde: "BWBR0002320", bron: { bwb_id: "BWBR0002320" }, omschrijving: "genoemd in je vraag" },
    { label: "Weet ik (nog) niet", waarde: "onbekend", bron: {}, omschrijving: "Je kunt bronnen later toevoegen" }],
});
const bepalingen = (index, over = {}) => kaart("bepalingen", 10 + index, `Welke bepalingen horen bij deelvraag ${index + 1}?`, {
  meerkeuze: true, totaal: 11, deel: { index, totaal: 2, deelvraag: index ? "Telt een tweede huis mee?" : DV1 },
  opties: [{ label: "Artikel 2.1, lid 1 – Wet IB 2001", waarde: L21, bron: { bwb_id: IB, iri: L21 },
    omschrijving: "Belastingplichtig zijn natuurlijke personen … · raakt: belastingplichtig" },
  { label: "Artikel 5.2, lid 1 – Wet IB 2001", waarde: L52, bron: { bwb_id: IB, iri: L52 },
    omschrijving: "valt mogelijk buiten de afbakening" },
  { label: "Weet ik (nog) niet", waarde: "onbekend", bron: {}, omschrijving: "Je kunt bronnen later toevoegen" }],
  ...over,
});
const BEP1 = bepalingen(0), BEP2 = bepalingen(1);
const BEP1_TERUG = bepalingen(0, { vooringevuld: [L21], beantwoord: true });
const SAMENVATTING = kaart("samenvatting", 11, "Klopt dit werkgebied?", {
  totaal: 11,
  soort: "samenvatting", vrije_tekst: false, overslaanbaar: false, terug: true,
  samenvatting: { naam: "Box 3", aanleiding: "Een wetswijziging raakt een bestaand proces.", context: "", doel: "",
    analysevraag: "Wie is belastingplichtig voor box 3?", praktijkvoorbeeld: "",
    deelvragen: [DV1, "Telt een tweede huis mee?", "Wat is het heffingsvermogen?"],
    afbakening: "Regelingen: Wet inkomstenbelasting 2001.", bronnen: ["Artikel 2.1, lid 1 – Wet IB 2001 (deelvraag 1)"] },
});
const ARTEFACT = { soort: "werkgebied", titel: "Box 3", ref: { werkgebied_id: "wg5" } };
const wg = { id: "wg5", naam: "Box 3", analysevraag: "Wie is belastingplichtig voor box 3?",
  afbakening: "Regelingen: Wet inkomstenbelasting 2001.", aanleiding: "Een wetswijziging raakt een bestaand proces.",
  context: "De aangifte 2026 moet blijven werken.", doel: "", praktijkvoorbeeld: "",
  peildatum: null, status: "in_voorbereiding", revisie: 1,
  aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null, bronnen: [],
  deelvragen: [{ id: "d1", vraag: DV1, volgorde: 0, status: "actief", herkomst: "lex", reden: "", aangemaakt_door: "t",
    aangemaakt: nu, bronnen: [], begrippen: [] }] };
const DEKKING = { deelvragen: [{ id: "d1", vraag: DV1, stand: "geen_bron", bronnen: [], begrippen: [] }],
  telling: { gedekt: 0, geen_begrip: 0, geen_bron: 1 }, totaal: 1 };

const beurt = (run, tekst, k) => [{ type: "token", content: tekst }, { type: "vraagkaart", vraagkaart: k },
  { type: "opgeslagen", run_id: run }, { type: "done" }];
const stromen = {
  r1: beurt("r1", "Laten we het werkgebied samen bepalen.", NAAM),
  r2: beurt("r2", "Eerst waarom we analyseren.", AANLEIDING),
  r3: beurt("r3", "Nu maken we de analysevraag concreet.", DEELVRAGEN),
  r4: beurt("r4", "Nu de bronnen.", REGELINGEN),
  r5: beurt("r5", "Nu per deelvraag de bepalingen die erbij horen.", BEP1),
  r6: beurt("r6", "Dan deelvraag 2.", BEP2),
  r7: beurt("r7", "", BEP1_TERUG),
  r8: beurt("r8", "Dan deelvraag 2.", BEP2),
  r9: beurt("r9", "Dit is het werkgebied.", SAMENVATTING),
  r10: [{ type: "token", content: "Werkgebied *Box 3* is aangemaakt." }, { type: "opgeslagen", run_id: "r10", artefact: ARTEFACT }, { type: "done" }],
};
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const ia = (stap) => ({ intake_id: "ik1", stap, actie: "antwoord" });
const gesprekken = {
  g9: [],
  g4: [
    { rol: "user", tekst: "Kunnen we een werkgebied samenstellen?", ...leeg },
    { rol: "assistant", tekst: "Laten we het werkgebied samen bepalen.", ...leeg, run_id: "x1", vraagkaart: NAAM },
    { rol: "user", tekst: "Box 3", ...leeg, intake_antwoord: ia("naam") },
    { rol: "assistant", tekst: "Eerst waarom we analyseren.", ...leeg, run_id: "x2", vraagkaart: AANLEIDING },
    { rol: "user", tekst: "Een wetswijziging raakt een bestaand proces", ...leeg, intake_antwoord: ia("aanleiding") },
    { rol: "assistant", tekst: "Nu de bronnen.", ...leeg, run_id: "x3", vraagkaart: REGELINGEN },
  ],
};
const starts = [], berichten = [];

await context.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" ? null : req.postDataJSON?.() ?? null;
  if (p === "/api/werkgebieden/wg5") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg5/deelvragen/dekking") return route.fulfill({ json: DEKKING });
  if (p.startsWith("/api/werkgebieden/wg5/")) return route.fulfill({ json: {} });
  if (p === "/api/gesprekken" && m === "POST") return route.fulfill({ status: 201, json: { id: "g9", titel: body?.titel ?? "", berichten: [] } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  const gesprek = p.match(/^\/api\/gesprekken\/(g\d)$/);
  if (gesprek) return route.fulfill({ json: { id: gesprek[1], titel: "Test", berichten: gesprekken[gesprek[1]] ?? [] } });
  if (p.endsWith("/berichten") && m === "POST") { berichten.push(body); return route.fulfill({ status: 201, json: { id: berichten.length } }); }
  if (p === "/api/annotatie/run" && m === "POST") {
    starts.push(body);
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
const dock = (stap, deel) => page.locator(deel === undefined ? `[data-vraagdock=${stap}]` : `[data-vraagdock=${stap}][data-deel="${deel}"]`);
const invoer = () => page.getByPlaceholder("Stel een vraag of geef een opdracht aan Lex…");
const kaartIn = () => page.locator("[data-vragenkaart]");

try {
  await page.goto(`${base}/workbench`);

  // --- De startzin: de vraag onderaan, in plaats van het invoerveld ---
  await invoer().fill("Kunnen we een werkgebied samenstellen?");
  await page.getByRole("button", { name: "Versturen" }).click();
  await dock("naam").getByText("Hoe noemen we het werkgebied?").waitFor();
  assert.equal(await invoer().count(), 0, "de vraag vervangt het invoerveld");
  assert.equal(await dock("naam").getByRole("button", { name: "Sla over" }).count(), 0, "de naam is verplicht");
  assert.ok(await dock("naam").getByRole("button", { name: "Vorige vraag" }).isDisabled());
  await page.locator("[data-vraag-open]").waitFor();

  // --- ✕ geeft het invoerveld terug; "Een vraag stellen ›" opent de vraag weer ---
  await dock("naam").getByRole("button", { name: "Vraag wegklikken" }).click();
  await invoer().waitFor();
  await page.locator("[data-vraag-open]").click();
  await dock("naam").waitFor();

  // --- Volgende: de intake_actie; het antwoord in de Vragen-kaart, geen bubbel ---
  await dock("naam").getByLabel("Typ je antwoord").fill("Box 3");
  await dock("naam").getByRole("button", { name: "Volgende", exact: true }).click();
  await wacht(2);
  assert.deepEqual(starts[1].intake_actie, { intake_id: "ik1", stap: "naam", actie: "antwoord", keuzes: [], tekst: "Box 3" });
  await dock("aanleiding").waitFor();
  await kaartIn().locator("[data-vraagpaar=naam]").getByText("Box 3", { exact: true }).waitFor();
  assert.equal(await page.getByText("Box 3", { exact: true }).count(), 1, "geen losse antwoordbubbel");
  assert.equal(await kaartIn().getByText("Vraag", { exact: true }).count(), 1, "één paar heet 'Vraag'");
  assert.deepEqual(berichten.find((b) => b.rol === "user" && b.tekst === "Box 3")?.intake_antwoord, ia("naam"));

  // --- Aanleiding: eigen tekst vervangt bij één keuze de gekozen optie ---
  await dock("aanleiding").getByText("Gewijzigde wetgeving vraagt om aanpassing van de uitvoering").waitFor();
  const voorstel = dock("aanleiding").getByRole("option", { name: /^Een wetswijziging/ });
  await voorstel.click();
  assert.equal(await voorstel.getAttribute("aria-selected"), "true");
  await dock("aanleiding").getByLabel("Typ je antwoord").fill("Herstel na het Kerstarrest");
  assert.equal(await voorstel.getAttribute("aria-selected"), "false");
  await dock("aanleiding").getByLabel("Typ je antwoord").fill("");
  await voorstel.click();
  await dock("aanleiding").getByRole("button", { name: "Volgende", exact: true }).click();
  await wacht(3);
  assert.deepEqual(starts[2].intake_actie.keuzes, ["wetswijziging"]);

  // --- Deelvragen: voorstellen kiezen én meerdere eigen regels ---
  const dv = dock("deelvragen");
  await dv.getByRole("option", { name: new RegExp(`^${DV1}`) }).click();
  await dv.getByLabel("Eigen deelvraag 1").fill("Telt een tweede huis mee?");
  await dv.getByLabel("Eigen deelvraag 1").press("Enter");
  await dv.getByLabel("Eigen deelvraag 2").waitFor();
  assert.equal(await dv.getByLabel("Eigen deelvraag 2").evaluate((el) => el === document.activeElement), true,
    "Enter opent de volgende regel, met de focus erin");
  await page.keyboard.type("Wat is het heffingsvermogen?");
  await dv.getByRole("button", { name: "+ Nog een deelvraag" }).click();
  await dv.getByLabel("Eigen deelvraag 3").waitFor();
  assert.equal(starts.length, 3, "een nieuwe regel start geen beurt");
  await dv.getByRole("button", { name: "Volgende", exact: true }).click();
  await wacht(4);
  assert.deepEqual(starts[3].intake_actie, { intake_id: "ik1", stap: "deelvragen", actie: "antwoord", keuzes: [DV1],
    teksten: ["Telt een tweede huis mee?", "Wat is het heffingsvermogen?"] });
  await kaartIn().locator("[data-vraagpaar=deelvragen]").getByText(`${DV1}; Telt een tweede huis mee?; Wat is het heffingsvermogen?`).waitFor();

  // --- Regelingen: omschrijving, alleen selecteren, "Weet ik (nog) niet" exclusief ---
  await dock("regelingen").getByText("wet · 2 delen over ‘box 3’ · bij een deelvraag").waitFor();
  const optie = (naam) => dock("regelingen").getByRole("option", { name: new RegExp(`^${naam}`) });
  await optie("Wet inkomstenbelasting 2001").click();
  await optie("Algemene wet").click();
  assert.equal(starts.length, 4, "een klik op een voorstel start geen beurt");
  await optie("Weet ik").click();
  assert.equal(await dock("regelingen").locator("[aria-selected=true]").count(), 1);
  await optie("Wet inkomstenbelasting 2001").click();
  assert.equal(await kaartIn().getByText("Vragen", { exact: true }).count(), 1, "meer paren heten 'Vragen'");
  await dock("regelingen").getByRole("button", { name: "Volgende", exact: true }).click();
  await wacht(5);
  assert.deepEqual(starts[4].intake_actie.keuzes, [IB]);

  // --- F3f: de bepalingen, een kaartje per deelvraag ---
  const b1 = dock("bepalingen", 0);
  await b1.getByText(`“${DV1}”`).waitFor();
  await b1.getByText("10 van 11").waitFor();
  await b1.getByText("valt mogelijk buiten de afbakening").waitFor();
  assert.equal(await b1.locator("[aria-selected=true]").count(), 0, "niets is aangevinkt");
  assert.equal(await b1.getByRole("button", { name: "Verzend" }).count(), 0, "deelvraag 1 is niet de laatste vraag");
  await b1.getByRole("option", { name: /^Artikel 2\.1, lid 1/ }).click();
  await b1.getByRole("button", { name: "Volgende", exact: true }).click();
  await wacht(6);
  assert.deepEqual(starts[5].intake_actie, { intake_id: "ik1", stap: "bepalingen", deel: 0, actie: "antwoord", keuzes: [L21] });
  assert.deepEqual(berichten.find((b) => b.rol === "user" && b.intake_antwoord?.stap === "bepalingen")?.intake_antwoord,
    { intake_id: "ik1", stap: "bepalingen", deel: 0, actie: "antwoord" });
  // Deelvraag 2: de laatste vraag, en ‹ gaat naar deelvraag 1 (niet naar de regelingen).
  const b2 = dock("bepalingen", 1);
  await b2.getByText("“Telt een tweede huis mee?”").waitFor();
  await b2.getByRole("button", { name: "Verzend" }).waitFor();
  await b2.getByRole("button", { name: "Vorige vraag" }).click();
  await wacht(7);
  assert.deepEqual({ ...starts[6].intake_actie }, { intake_id: "ik1", stap: "bepalingen", deel: 1, actie: "wijzig",
    naar: "bepalingen", naar_deel: 0 });
  // Terug op deelvraag 1 staat de keuze er nog; › gaat verder met hetzelfde antwoord.
  await dock("bepalingen", 0).getByRole("option", { name: /^Artikel 2\.1, lid 1/, selected: true }).waitFor();
  await dock("bepalingen", 0).getByRole("button", { name: "Volgende vraag" }).click();
  await wacht(8);
  assert.deepEqual(starts[7].intake_actie.keuzes, [L21]);
  await dock("bepalingen", 1).getByRole("button", { name: "Sla over" }).click();
  await wacht(9);
  assert.deepEqual([starts[8].intake_actie.actie, starts[8].intake_actie.deel], ["overslaan", 1]);
  // Een paar per deel in de Vragen-kaart: deelvraag 2 vervangt deelvraag 1 niet.
  assert.equal(await kaartIn().locator("[data-vraagpaar=bepalingen]").count(), 2);
  await kaartIn().locator("[data-vraagpaar=bepalingen]").last().getByText("Overgeslagen").waitFor();

  // --- De samenvatting: het hele dossier, de bronnen met hun deelvraag, en aanmaken ---
  const samen = dock("samenvatting");
  await samen.getByText("Een wetswijziging raakt een bestaand proces.").waitFor();
  assert.equal(await samen.locator("ol li").count(), 3, "de drie deelvragen");
  await samen.getByText("Artikel 2.1, lid 1 – Wet IB 2001 (deelvraag 1)").waitFor();
  await samen.getByRole("button", { name: /Werkgebied aanmaken/ }).click();
  await wacht(10);
  assert.equal(starts[9].intake_actie.actie, "aanmaken");

  // --- Na aanmaken: kaart, eigen paneel, de werkplek in het werkgebied, geen open vraag ---
  const paneel = page.locator("[data-artefact-soort=werkgebied][data-artefact]");
  await paneel.getByText("Samengesteld met Lex").waitFor();
  // F2: het hele dossier en de deelvragen met hun dekking, ook naast het gesprek.
  await paneel.locator("[data-dossier-veld=context]").getByText("De aangifte 2026 moet blijven werken.").waitFor();
  await paneel.locator("[data-dossier-veld=doel]").getByText("Nog geen doel.").waitFor();
  await paneel.locator("[data-samenvatting=deelvragen]").getByText("Nog geen bron").waitFor();
  await paneel.locator("[data-samenvatting=deelvragen]").getByText("0 van 1 deelvraag gedekt", { exact: false }).waitFor();
  assert.equal(await paneel.getByRole("link", { name: "Open het werkgebied" }).first().getAttribute("href"), "/werkgebieden/wg5");
  for (let i = 0; i < 40 && new URL(page.url()).searchParams.get("werkgebied") !== "wg5"; i++) await page.waitForTimeout(50);
  assert.equal(new URL(page.url()).searchParams.get("werkgebied"), "wg5");
  assert.equal(await page.locator("[data-vraagdock]").count(), 0, "geen open vraag meer");
  await invoer().waitFor();
  await page.locator("button[data-artefact-soort=werkgebied]").getByText("Werkgebied · bekijken").waitFor();

  // --- Na herladen: dezelfde Vragen-kaart, de open vraag onderaan, en ‹ terug ---
  await page.goto(`${base}/workbench?gesprek=g4`);
  await dock("regelingen").waitFor();
  assert.equal(await kaartIn().locator("[data-vraagpaar]").count(), 2);
  assert.equal(await page.getByText("Box 3", { exact: true }).count(), 1, "ook na herladen geen bubbel");
  const voor = starts.length;
  await dock("regelingen").getByRole("button", { name: "Vorige vraag" }).click();
  await wacht(voor + 1);
  assert.deepEqual({ actie: starts[voor].intake_actie.actie, naar: starts[voor].intake_actie.naar, stap: starts[voor].intake_actie.stap },
    { actie: "wijzig", naar: "buiten", stap: "regelingen" });

  // --- Smal scherm: de dock past ---
  const smal = await context.newPage();
  smal.on("pageerror", (e) => errors.push(e.message));
  await smal.setViewportSize({ width: 390, height: 844 });
  await smal.goto(`${base}/workbench?gesprek=g4`);
  await smal.locator("[data-vraagdock=regelingen]").waitFor();
  const vak = await smal.locator("[data-vraagdock=regelingen]").boundingBox();
  assert.ok(vak && vak.x >= 0 && vak.x + vak.width <= 391 && vak.y + vak.height <= 845, `de dock past (${JSON.stringify(vak)})`);
  assert.equal(await smal.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, "geen horizontale scroll");
  if (process.env.SCHERMAFDRUK) {
    await smal.screenshot({ path: `${process.env.SCHERMAFDRUK}/dock-mobiel.png` });
    await page.goto(`${base}/workbench?gesprek=g4`);
    await dock("regelingen").waitFor();
    await page.screenshot({ path: `${process.env.SCHERMAFDRUK}/dock-desktop.png` });
  }

  assert.deepEqual(errors, []);
  console.log("Browser OK: vraag onderaan i.p.v. het invoerveld, ✕ en 'Een vraag stellen ›', antwoorden in één Vragen-kaart zonder bubbels (ook na herladen), intake_antwoord bewaard, omschrijving, eigen tekst vervangt keuze, deelvragen met meerdere eigen regels, Weet ik (nog) niet exclusief, bepalingen per deelvraag met ‹ per deel, Verzend, samenvatting met het dossier, Werkgebied aanmaken, ‹ terug, werkgebiedpaneel met dossier en dekking, smal scherm.");
} finally {
  await browser.close();
}
