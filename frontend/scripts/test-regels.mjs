/** Browserregressie voor de afleidingsregels (ADR-018, R2): de keten en de regelkaart op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-regels.mjs`. Met `REGELS_SCREENSHOT=<map>` maakt hij een beeld van de kaart.
 *
 * De mock gedraagt zich als de api (`api/app/regel_store.py`): revisies, de poort voor accorderen (grondslag akkoord,
 * een beoordeeld voorbeeld per geval, een reden), dragers beoordelen, heropenen, en 412 bij een oude revisie.
 *
 * Bewaakt:
 *  - de zijbalk heeft *Afleidingsregels* na *Begrippen*; het overzicht over werkgebieden heen heeft de vorm van de andere
 *    (statusknoppen met tellers in de URL, werkgebiedkeuze, zoeken) en een kaart opent de regel;
 *  - de tab Artefacten heeft de kaart Afleidingsregels met de telling;
 *  - de keten staat van onder naar boven (R2 vóór R4), met de basisgegevens en het signaal "zelfde uitvoer";
 *  - de regelkaart van R4: de regeltekst van de api, de gevallen met hun voorbeelden, de grondslag, de poort letterlijk,
 *    *Volgt op* uit de keten;
 *  - een drager akkoord geven, accorderen met een reden en heropenen, elk tegen de revisie in beeld;
 *  - een open interpretatiekeuze op een geval (R3, lessenbundel 4) houdt de poort tegen; de jurist besluit op de kaart
 *    (lezing, methode, motivering) via de ene besluitroute, en dan opent de poort;
 *  - een voorbeeld beoordeel je apart, via de eigen route (e2e-run 20 nov 2026, B4), en een open punt hang je om met de
 *    route `omhangen`, die alleen `hangt_aan` meestuurt (A2);
 *  - een 412 laadt de nieuwste stand en zegt dat;
 *  - op 390 px schuift de pagina niet zijwaarts.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";
import { SCHIL, controleerOnbekend, onbekend } from "./nepApi.mjs";

/** Paden die de werkplek hier aanroept en deze test bewust niet nabootst (`nepApi.mjs`); al het andere is een fout. */
const NIET_NAGEBOOTST = [
  /^GET \/api\/werkgebieden\/wg1\/kandidaten$/,
  /^GET \/api\/werkgebieden\/wg1\/begrippen$/,
  /^GET \/api\/begrippen$/,
];

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [], mutaties = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-11-19T10:00:00Z";
const wg = { id: "wg1", naam: "Termijnen", status: "in_voorbereiding", revisie: 1, peildatum: null, aangemaakt_door: "t",
  aangemaakt: nu, gewijzigd: nu, analysevraag: "Hoe hoog is een termijnbedrag?", afbakening: "", aanleiding: "", context: "",
  doel: "", praktijkvoorbeeld: "", deelvragen: [], bronnen: [] };
const begrippen = {
  rb2: "bepalen aantal termijnen", rb4: "bepalen termijnbedrag", at: "aantal termijnen", tb: "termijnbedrag",
  ab: "bedrag van de aanslag", rb3: "bepalen aantal termijnen bij uitstel",
};
const b = (id) => ({ id, naam: begrippen[id], status: "geaccordeerd" });

function poort(r) {
  const redenen = [];
  const grond = r.dragers.filter((d) => d.rol === "grondslag" && d.beoordeling !== "afgewezen");
  if (!grond.some((d) => d.beoordeling === "akkoord")) redenen.push("De grondslag is nog niet beoordeeld, of de passage is gewijzigd, verworpen of verdwenen.");
  const beoordeeld = new Set(r.inhoud.voorbeelden.filter((v) => v.oordeel !== "open").map((v) => v.geval));
  if (r.inhoud.gevallen.length === 1) {
    if (!beoordeeld.size) redenen.push("Er is nog geen beoordeeld voorbeeld.");
  } else {
    const zonder = r.inhoud.gevallen.map((g) => g.label).filter((l) => !beoordeeld.has(l));
    if (zonder.length) redenen.push(`Nog geen beoordeeld voorbeeld bij geval ${zonder.join(", ")}.`);
  }
  // Elk open punt van elke soort houdt tegen (besluit gebruiker 20 nov 2026), zoals `regel_store.poort`.
  const keuzes = openPunten.filter((p) => p.status === "open" && p.inhoud.hangt_aan.some((a) => a.id === r.id));
  if (keuzes.length) redenen.push(`${keuzes.length} open punt is nog niet besloten: ${keuzes.map((p) => p.inhoud.vraag.replace(/[.?]$/, "")).join("; ")}.`);
  return { mag: !redenen.length, redenen };
}

/** Het object van lessenbundel 4, zoals `open_punt_store._punt` het geeft. */
const openPunten = [{
  id: "op1", werkgebied_id: "wg1", status: "open", revisie: 1, soort: "interpretatiekeuze", soort_naam: "interpretatiekeuze",
  herkomst: "lex", keuze: null,
  inhoud: { soort: "interpretatiekeuze", vraag: "Telt een gedeeltelijke betaling als termijn?", toelichting: "",
    hangt_aan: [{ soort: "geval", id: "r4", geval: "1", bestaat: true }],
    lezingen: [
      { label: "A", omschrijving: "Ja, elke betaling telt.", grondslag: [{ soort: "markering", id: "el-r4", label: "art. 9 lid 1" }] },
      { label: "B", omschrijving: "Nee, alleen het volle termijnbedrag.", grondslag: [] }],
    te_toetsen: [{ bronsoort: "wetsgeschiedenis", omschrijving: "de MvT bij art. 9", getoetst: false, uitkomst: "" }] },
}];

const regel = (id, regelbegrip, uitvoer, invoer, gevallen, voorbeelden, markdown) => ({
  id, werkgebied_id: "wg1", status: "concept", revisie: 1, herkomst: "import", opvolger_van: null,
  inhoud: { soort: "rekenregel", regelbegrip_id: regelbegrip, uitvoer_begrip_id: uitvoer, onderwerp_begrip_id: "",
    invoer: invoer.map((i) => ({ begrip_id: i, rol: "invoer" })), gevallen, voorbeelden, toelichting: "", brontype: "wet", lidwoord: "het" },
  naam: begrippen[regelbegrip], uitvoer: begrippen[uitvoer],
  regeltekst: { tekst: markdown.replace(/[_*]/g, ""), markdown, gevallen: gevallen.map((g) => ({ label: g.label, tekst: "…" })) },
  begrippen: Object.fromEntries([regelbegrip, uitvoer, ...invoer].map((i) => [i, b(i)])),
  dragers: [{ id: `${id}-d1`, element_id: `el-${id}`, rol: "grondslag", geval: "", bewijs: null, beoordeling: "open",
    beoordeeld_door: null, actualiteit: "actueel" }],
  signalen: [], aangemaakt_door: "import", aangemaakt: nu, gewijzigd: nu,
  geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
});
const regels = {
  r4: regel("r4", "rb4", "tb", ["ab", "at"],
    [{ label: "1", voorwaarden: null, uitkomst: [{ soort: "begrip", begrip_id: "ab" }], voorrang: 0 }],
    [{ geval: "", invoer: "€ 1.200, 12 termijnen", uitkomst: "€ 100", oordeel: "juist", toelichting: "" },
     { geval: "", invoer: "€ 0, 12 termijnen", uitkomst: "€ 0", oordeel: "open", toelichting: "", door: "regelspecialist" }],
    "_Het termijnbedrag_ moet berekend worden als _bedrag van de aanslag_ **gedeeld door** _aantal termijnen_."),
  r2: regel("r2", "rb2", "at", [],
    [{ label: "1", voorwaarden: null, uitkomst: [{ soort: "tekst", tekst: "twaalf" }], voorrang: 0 }], [],
    "_Het aantal termijnen_ moet berekend worden als twaalf."),
  r3: regel("r3", "rb3", "at", [],
    [{ label: "1", voorwaarden: null, uitkomst: [{ soort: "tekst", tekst: "zes" }], voorrang: 0 }], [],
    "_Het aantal termijnen_ moet berekend worden als zes."),
};
const uit = (r) => ({ ...r, accorderen: poort(r) });
const keten = () => ({
  regels: Object.values(regels).map((r) => ({ id: r.id, naam: r.naam, uitvoer: r.uitvoer, status: r.status, soort: "rekenregel",
    gevallen: r.inhoud.gevallen.length, brontype: "wet" })),
  volgorde: ["r2", "r3", "r4"],
  pijlen: [{ van: "r2", naar: "r4", begrip_id: "at" }, { van: "r3", naar: "r4", begrip_id: "at" }],
  basisgegevens: [{ begrip_id: "ab", naam: "bedrag van de aanslag" }],
  signalen: [{ soort: "zelfde_uitvoer", regel_ids: ["r2", "r3"], begrip_id: "at",
    melding: "Meer regels leiden hetzelfde begrip af: hun gevallen moeten elkaar uitsluiten." }],
});
let botsing = false;
const overzichtVragen = [];
const rij = (x) => ({ id: x.id, werkgebied_id: "wg1", werkgebied_naam: "Termijnen", naam: x.naam, uitvoer: x.uitvoer,
  status: x.status, revisie: x.revisie, soort: "rekenregel", brontype: "wet", gevallen: x.inhoud.gevallen.length,
  regeltekst: x.regeltekst.tekst, herkomst: x.herkomst, gewijzigd: nu });

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/regels") {
    overzichtVragen.push(url.search);
    const status = url.searchParams.get("status");
    const alle = Object.values(regels).map(rij);
    const per_status = {};
    for (const x of alle) per_status[x.status] = (per_status[x.status] ?? 0) + 1;
    const resultaten = alle.filter((x) => !status || x.status === status);
    return route.fulfill({ json: { resultaten, totaal: resultaten.length, per_status } });
  }
  if (p === "/api/werkgebieden" && m === "GET") return route.fulfill({ json: { werkgebieden: [wg] } });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/open-punten" && m === "GET") {
    assert.equal(url.searchParams.get("aan"), "regel");
    const id = url.searchParams.get("aan_id");
    return route.fulfill({ json: { open_punten: openPunten.filter((x) => x.inhoud.hangt_aan.some((a) => a.id === id)) } });
  }
  const besluit = p.match(/^\/api\/werkgebieden\/wg1\/open-punten\/(\w+)\/besluit$/);
  if (besluit && m === "POST") {
    const body = req.postDataJSON();
    mutaties.push({ m, rest: `open-punten/${besluit[1]}/besluit`, body });
    const punt = openPunten.find((x) => x.id === besluit[1]);
    punt.keuze = body.gekozen || body.motivering ? { ...body, door: "browser-test", op: nu } : null;
    punt.status = punt.keuze ? "gekozen" : "open";
    punt.revisie += 1;
    return route.fulfill({ json: punt });
  }
  const omhang = p.match(/^\/api\/werkgebieden\/wg1\/open-punten\/(\w+)\/omhangen$/);
  if (omhang && m === "POST") {
    const body = req.postDataJSON();
    mutaties.push({ m, rest: `open-punten/${omhang[1]}/omhangen`, body });
    const punt = openPunten.find((x) => x.id === omhang[1]);
    punt.inhoud.hangt_aan = body.hangt_aan.map((a) => ({ geval: "", ...a, bestaat: true }));
    punt.revisie += 1;
    return route.fulfill({ json: punt });
  }
  if (p === "/api/werkgebieden/wg1/regels" && m === "GET") return route.fulfill({ json: { regels: Object.values(regels).map(uit) } });
  if (p === "/api/werkgebieden/wg1/regels/hierarchie") return route.fulfill({ json: keten() });
  const een = p.match(/^\/api\/werkgebieden\/wg1\/regels\/(r\d)(?:\/(.+))?$/);
  if (een) {
    const r = regels[een[1]], rest = een[2] ?? "";
    if (m === "GET" && !rest) return route.fulfill({ json: uit(r) });
    if (m === "GET" && rest === "revisies")
      return route.fulfill({ json: { revisies: [{ revisie: r.revisie, actie: "regel-aangemaakt", detail: null, status: r.status, actor: "import", tijdstip: nu }] } });
    const body = req.postDataJSON();
    mutaties.push({ m, rest, body });
    if (botsing) {
      botsing = false;
      r.revisie += 1;
      return route.fulfill({ status: 412, json: { detail: { fout: "revisie_conflict", melding: "De regel is intussen gewijzigd." } } });
    }
    if (body.verwachte_revisie !== r.revisie) return route.fulfill({ status: 412, json: { detail: { fout: "revisie_conflict" } } });
    const drager = rest.match(/^dragers\/(.+)$/);
    const vb = rest.match(/^voorbeelden\/(\d+)\/oordeel$/);
    if (drager && m === "PATCH") r.dragers.find((d) => d.id === drager[1]).beoordeling = body.beoordeling;
    else if (vb && m === "POST") r.inhoud.voorbeelden[Number(vb[1]) - 1].oordeel = body.oordeel;
    else if (rest === "accorderen") {
      const pt = poort(r);
      if (!pt.mag || !body.reden) return route.fulfill({ status: 409, json: { detail: { fout: "poort", melding: pt.redenen.join(" ") } } });
      r.status = "geaccordeerd";
      r.geaccordeerd_door = "browser-test";
      r.geaccordeerd_op = nu;
    } else if (rest === "heropenen") r.status = "concept";
    else return onbekend(route);
    r.revisie += 1;
    return route.fulfill({ json: uit(r) });
  }
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return onbekend(route, { stil: [...SCHIL, ...NIET_NAGEBOOTST], leeg: {}, stilStatus: 404 });
});

try {
  // De zijbalk: Afleidingsregels na Begrippen, naar het overzicht over werkgebieden heen.
  await page.goto(`${base}/begrippen`);
  const nav = page.getByRole("navigation", { name: "Overzichten" });
  await nav.getByRole("link", { name: "Afleidingsregels" }).waitFor();
  const items = await nav.getByRole("link").allInnerTexts();
  assert.deepEqual(items.map((t) => t.trim()), ["Werkgebieden", "Annotaties", "Begrippen", "Afleidingsregels"]);
  await nav.getByRole("link", { name: "Afleidingsregels" }).click();
  await page.waitForURL("**/afleidingsregels");
  assert.equal(await nav.getByRole("link", { name: "Afleidingsregels" }).getAttribute("aria-current"), "page");
  const overzicht = page.getByTestId("regels-overzicht");
  await overzicht.locator("[data-regel-kaart=r4]").waitFor();
  assert.equal(await overzicht.locator("[data-regel-kaart]").count(), 3);
  await overzicht.locator("[data-regel-kaart=r4]").getByText("moet berekend worden als", { exact: false }).waitFor();
  if (process.env.REGELS_SCREENSHOT) await page.screenshot({ path: `${process.env.REGELS_SCREENSHOT}/overzicht.png` });
  await page.getByRole("button", { name: "Concept (3)" }).click();
  await page.waitForURL("**/afleidingsregels?status=concept");
  for (let i = 0; i < 50 && overzichtVragen.at(-1) !== "?status=concept"; i++) await page.waitForTimeout(100);
  assert.equal(overzichtVragen.at(-1), "?status=concept", "het filter gaat naar de api");
  await page.getByRole("button", { name: "Geaccordeerd (0)", exact: true }).click();
  await page.getByText("Geen afleidingsregels bij deze filters.").waitFor();
  await page.getByRole("button", { name: "Alle (3)" }).click();
  await overzicht.locator("[data-regel-kaart=r2]").getByRole("link", { name: "bepalen aantal termijnen", exact: true }).click();
  await page.waitForURL("**/werkgebieden/wg1/regels/r2");
  await page.locator("[data-regel-inhoud=r2]").waitFor();

  // De kaart op de tab Artefacten.
  await page.goto(`${base}/werkgebieden/wg1/artefacten`);
  const kaart = page.locator('[data-artefact-kaart="regels"]');
  await kaart.waitFor();
  await kaart.getByText("3 regels").waitFor();
  await kaart.getByText("0 van 3 geaccordeerd").waitFor();

  // De keten.
  await kaart.click();
  await page.waitForURL("**/werkgebieden/wg1/artefacten/regels");
  const lijst = page.locator("[data-regel-keten-lijst]");
  await lijst.waitFor();
  await lijst.locator("[data-regel-rij=r4]").waitFor();
  const volgorde = await lijst.locator("[data-regel-rij]").evaluateAll((els) => els.map((e) => e.getAttribute("data-regel-rij")));
  assert.deepEqual(volgorde, ["r2", "r3", "r4"], "van onder naar boven");
  await lijst.locator('[data-keten-signaal="zelfde_uitvoer"]').waitFor();
  await lijst.locator("[data-basisgegevens]").getByText("bedrag van de aanslag").waitFor();

  // De regelkaart van R4.
  await lijst.locator("[data-regel-rij=r4] a").click();
  await page.waitForURL("**/werkgebieden/wg1/regels/r4");
  const r4 = page.locator("[data-regel-inhoud=r4]");
  await r4.waitFor();
  await page.getByRole("heading", { name: "bepalen termijnbedrag", level: 1 }).waitFor();
  const tekst = r4.locator("[data-regel-tekst]");
  await tekst.getByText("moet berekend worden als", { exact: false }).waitFor();
  assert.equal(await tekst.locator("strong", { hasText: "gedeeld door" }).count(), 1, "het operatorbegrip vet");
  assert.equal(await tekst.locator("em", { hasText: "termijnbedrag" }).count(), 1, "het begrip cursief");
  await r4.locator('[data-regel-voorbeeld="juist"]').getByText("€ 100").waitFor();
  await r4.locator("[data-regel-poort]").getByText("De grondslag is nog niet beoordeeld", { exact: false }).waitFor();
  await r4.locator("[data-regel-keten]").getByRole("link", { name: "bepalen aantal termijnen", exact: true }).waitFor();
  assert.equal(await r4.locator("[data-regel-keten] a").count(), 2, "volgt op R2 en R3");
  assert.equal(await r4.locator("[data-regel-accorderen]").isDisabled(), true, "de poort is dicht");

  // Een voorbeeld beoordeel je apart (B4): de maker staat erbij, en het oordeel gaat via de eigen route.
  const vb2 = r4.locator('[data-voorbeeld-nr="2"]');
  await vb2.getByText("Gemaakt door regelspecialist").waitFor();
  await vb2.getByRole("button", { name: "Voorbeeld 2: juist" }).click();
  await r4.locator('[data-voorbeeld-nr="2"][data-regel-voorbeeld="juist"]').waitFor();
  assert.deepEqual(mutaties.at(-1), { m: "POST", rest: "voorbeelden/2/oordeel", body: { verwachte_revisie: 1, oordeel: "juist" } });

  // Een drager akkoord geven: de grondslag staat, maar de open keuze houdt de poort nog dicht (R3).
  await r4.getByRole("button", { name: "Akkoord met grondslag el-r4" }).click();
  await r4.locator("[data-regel-poort]").getByText("open punt is nog niet besloten", { exact: false }).waitFor();
  assert.deepEqual(mutaties.at(-1), { m: "PATCH", rest: "dragers/r4-d1", body: { verwachte_revisie: 2, beoordeling: "akkoord" } });

  // Het open punt staat op de kaart als voorstel van Lex, met de lezingen, de grondslag en wat nog getoetst moet worden.
  const punt = r4.locator("[data-open-punt=op1]");
  await punt.getByText("Voorstel van Lex").waitFor();
  await punt.getByText("geval 1").waitFor();
  await punt.getByText("Nog te toetsen: wetsgeschiedenis (de MvT bij art. 9)").waitFor();
  await punt.getByText("Waarop lezing A rust (1)").click();
  assert.equal(await punt.getByRole("link", { name: "art. 9 lid 1" }).getAttribute("href"), "/annotaties/element/el-r4");
  // Besluiten vraagt een lezing, de methode en een motivering; het besluit gaat via de route van het open punt.
  await punt.locator("[data-besluit-vastleggen]").click();
  await punt.getByText("Kies een lezing.").waitFor();
  await punt.getByRole("radio", { name: "Lezing B" }).check();
  assert.equal(await punt.getByText("Kies een lezing.").count(), 0, "de melding gaat weg na het kiezen");
  await punt.getByRole("combobox", { name: "Methode van de interpretatie" }).selectOption("grammaticaal");
  await punt.getByRole("textbox", { name: "Waarom deze lezing" }).fill("Lid 1 spreekt van het termijnbedrag.");
  if (process.env.REGELS_SCREENSHOT) await page.screenshot({ path: `${process.env.REGELS_SCREENSHOT}/open-punt.png`, fullPage: true });
  await punt.locator("[data-besluit-vastleggen]").click();
  await r4.locator('[data-open-punt=op1][data-status="gekozen"]').getByText("Lezing B (grammaticaal): Lid 1 spreekt van het termijnbedrag.").waitFor();
  assert.deepEqual(mutaties.at(-1), { m: "POST", rest: "open-punten/op1/besluit", body: { verwachte_revisie: 1, gekozen: "B",
    motivering: "Lid 1 spreekt van het termijnbedrag.", methode: "grammaticaal" } });
  await r4.locator("[data-regel-poort]").waitFor({ state: "detached" });
  assert.equal(await r4.locator("[data-regel-accorderen]").isDisabled(), true, "zonder reden niet");
  await r4.locator("[data-regel-reden]").fill("Volgt letterlijk uit art. 9 lid 1.");
  if (process.env.REGELS_SCREENSHOT) await page.screenshot({ path: `${process.env.REGELS_SCREENSHOT}/regelkaart.png`, fullPage: true });
  await r4.locator("[data-regel-accorderen]").click();
  await page.locator('[data-regel-inhoud=r4][data-regel-status="geaccordeerd"]').waitFor();
  assert.deepEqual(mutaties.at(-1).body, { verwachte_revisie: 3, reden: "Volgt letterlijk uit art. 9 lid 1." });

  // Omhangen (A2): van geval 1 naar de hele regel; alleen `hangt_aan` gaat mee.
  const om = r4.locator("[data-omhangen=op1]");
  await om.getByText("Omhangen", { exact: true }).first().click();
  await om.getByRole("combobox", { name: "Naar geval" }).getByRole("option", { name: "Geval 1" }).waitFor({ state: "attached" });
  await om.locator("[data-omhangen-vastleggen]").click();
  for (let i = 0; i < 50 && mutaties.at(-1).rest !== "open-punten/op1/omhangen"; i++) await page.waitForTimeout(100);
  assert.deepEqual(mutaties.at(-1), { m: "POST", rest: "open-punten/op1/omhangen",
    body: { verwachte_revisie: 2, hangt_aan: [{ soort: "regel", id: "r4" }] } });

  // Een 412 laadt de nieuwste stand en zegt het; de handeling gaat niet stil opnieuw.
  botsing = true;
  const voor = mutaties.length;
  await r4.getByRole("button", { name: "Heropenen", exact: true }).click();
  await page.locator("[data-regel-melding]").getByText("Iemand anders wijzigde deze regel net", { exact: false }).waitFor();
  assert.equal(mutaties.length, voor + 1);
  await r4.getByRole("button", { name: "Heropenen", exact: true }).click();
  await page.locator('[data-regel-inhoud=r4][data-regel-status="concept"]').waitFor();

  // Smal scherm.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await page.locator("[data-regel-inhoud=r4]").waitFor();
  await page.locator("[data-regel-inhoud=r4] [data-open-punt=op1]").waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, "geen zijwaartse scroll");
  if (process.env.REGELS_SCREENSHOT) await page.screenshot({ path: `${process.env.REGELS_SCREENSHOT}/regelkaart-390.png`, fullPage: true });

  assert.deepEqual(errors, []);
  controleerOnbekend();
  console.log("Browser OK: open punt op een geval houdt de poort tegen, besluit op de kaart via de ene route; Afleidingsregels in de zijbalk en het overzicht met tellers, filter in de URL en doorklikken; kaart Afleidingsregels, de keten van onder naar boven met basisgegevens en signaal, de regelkaart met regeltekst, voorbeelden, grondslag, poort en keten; voorbeeld apart beoordeeld; drager akkoord, accorderen met reden, omhangen, 412 en heropenen; smal scherm.");
} finally {
  await browser.close();
}
