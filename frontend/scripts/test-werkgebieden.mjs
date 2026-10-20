/** Browserregressie voor de werkgebieden (spoor D, levering 1) op de echte Next-UI met een gemockte
 * BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-werkgebieden.mjs` (na npx playwright install chromium).
 *
 * De mock houdt een werkgebied met revisies bij zoals de api: elke mutatie toetst
 * `verwachte_revisie` en hoogt hem op. Zo is te zien dat de pagina de revisie in beeld meestuurt,
 * en wat ze doet als iemand anders er tussendoor kwam (412).
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [], requests = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-15T10:00:00+00:00";
let wg = null;
const audit = [];
let volgendeConflict = false;
const IRI9 = "urn:bwb:BWBR0004770:artikel9";
const IRI3 = "urn:bwb:BWBR0002320:artikel3";
const IRI10 = "urn:bwb:BWBR0004770:artikel10";
const LABELS = { [IRI9]: "Invorderingswet 1990 – artikel 9", [IRI3]: "Algemene wet inzake rijksbelastingen – artikel 3",
  [IRI10]: "Invorderingswet 1990 – artikel 10" };
// De samenhang zoals api/app/samenhang.py hem levert: artikel 9 met een lid dat naar artikel 10 (rand)
// en naar een niet-geïmporteerde bepaling verwijst; artikel 10 en artikel 3 los.
const knoop = (id, soort, label, over = {}) => ({ id, soort, label, tekst: "", klasse: "", lifecycle: "", element_id: "",
  bwb_id: id.split(":")[2] ?? "", artikel: "", lid: "", rand: false, ...over });
function samenhang(iri) {
  const regeling = iri.split(":")[2];
  const reg = knoop(`urn:bwb:${regeling}`, "regeling", regeling === "BWBR0004770" ? "Invorderingswet 1990" : "Algemene wet inzake rijksbelastingen");
  const knopen = [reg, knoop(iri, "artikel", `Artikel ${iri.split("artikel")[1]}`)];
  const relaties = [{ bron: reg.id, doel: iri, soort: "bevat", groep: "structuur", anker_tekst: "" }];
  if (iri === IRI9) {
    knopen.push(knoop(`${IRI9}:lid1`, "lid", "Lid 1", { artikel: "9", lid: "1" }),
      knoop(IRI10, "artikel", "Artikel 10", { rand: true }), knoop("extern:bw6", "extern", "Burgerlijk Wetboek 6, artikel 44", { rand: true, bwb_id: "" }));
    relaties.push({ bron: IRI9, doel: `${IRI9}:lid1`, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: `${IRI9}:lid1`, doel: IRI10, soort: "verwijst_naar", groep: "verwijzingen", anker_tekst: "artikel 10" },
      { bron: `${IRI9}:lid1`, doel: "extern:bw6", soort: "verwijst_naar", groep: "verwijzingen", anker_tekst: "artikel 6:44 BW" });
  }
  return { schema_versie: 1, doel: { bron_iri: iri }, snapshot_id: "snap", artikel_iri: iri, knopen, relaties,
    verwijzingen_beschikbaar: true, afgekapt: false };
}
const uit = () => ({ ...wg, bronnen: wg.bronnen.filter((b) => !b.weg) });
function mutatie(route, verwacht, actie, detail, doe) {
  if (volgendeConflict || verwacht !== wg.revisie) {
    volgendeConflict = false;
    wg.revisie += 1; // iemand anders was ons voor
    return route.fulfill({ status: 412, json: { detail: { fout: "revisie_conflict", revisie: wg.revisie } } });
  }
  doe();
  wg.revisie += 1;
  audit.unshift({ id: audit.length + 1, actor: "browser-test", actie, detail: { ...detail, revisie: wg.revisie }, tijdstip: nu });
  return null;
}

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p.startsWith("/api/werkgebieden")) requests.push({ p, m, body: m === "GET" || m === "DELETE" ? null : req.postDataJSON(), q: url.search });
  if (p === "/api/werkgebieden" && m === "GET")
    return route.fulfill({ json: { werkgebieden: wg ? [{ ...uit(), bronnen: undefined, aantal_bronnen: uit().bronnen.length }] : [] } });
  if (p === "/api/werkgebieden" && m === "POST") {
    const b = req.postDataJSON();
    wg = { id: "wg1", naam: b.naam, analysevraag: b.analysevraag, afbakening: b.afbakening, peildatum: null,
      status: "in_voorbereiding", revisie: 1, aangemaakt_door: "browser-test", aangemaakt: nu, gewijzigd: nu,
      gearchiveerd: null, bronnen: [] };
    audit.unshift({ id: 1, actor: "browser-test", actie: "aangemaakt", detail: { revisie: 1 }, tijdstip: nu });
    return route.fulfill({ status: 201, json: uit() });
  }
  if (p === "/api/werkgebieden/wg1" && m === "GET") return route.fulfill({ json: uit() });
  if (p === "/api/werkgebieden/wg1/bronnen" && m === "POST") {
    const b = req.postDataJSON();
    const iri = b.bron_iri || (b.bwb_id === "BWBR0004770" ? IRI9 : b.bwb_id === "BWBR0002320" ? IRI3 : null);
    if (volgendeConflict) return mutatie(route, -1, "", {}, () => {});
    if (!iri) return route.fulfill({ status: 422, json: { detail: "Bepaling niet gevonden in de graaf." } });
    const bestaand = wg.bronnen.find((s) => s.bron_iri === iri && !s.weg);
    if (bestaand && bestaand.rol === b.rol) return route.fulfill({ status: 200, json: { selectie: bestaand, werkgebied: uit() } });
    if (bestaand) return route.fulfill({ status: 409, json: { detail: { fout: "al_opgenomen", selectie: bestaand } } });
    const s = { id: `s${wg.bronnen.length + 1}`, bron_iri: iri, bereik: b.bereik, rol: b.rol, reden: b.reden,
      label: LABELS[iri],
      bwb_id: iri.split(":")[2], snapshot_id: "snap", bron_hash: "h", toegevoegd_door: "browser-test", toegevoegd: nu };
    const r = mutatie(route, b.verwachte_revisie, "bron-toegevoegd", { bron_iri: iri, rol: b.rol }, () => wg.bronnen.push(s));
    return r ?? route.fulfill({ status: 201, json: { selectie: s, werkgebied: uit() } });
  }
  const sel = p.match(/^\/api\/werkgebieden\/wg1\/bronnen\/(s\d+)$/);
  if (sel && m === "PATCH") {
    const b = req.postDataJSON();
    const r = mutatie(route, b.verwachte_revisie, "bron-gewijzigd", { velden: ["rol"] },
      () => { wg.bronnen.find((s) => s.id === sel[1]).rol = b.rol; });
    return r ?? route.fulfill({ json: uit() });
  }
  if (sel && m === "DELETE") {
    const s = wg.bronnen.find((x) => x.id === sel[1]);
    const r = mutatie(route, Number(url.searchParams.get("verwachte_revisie")), "bron-verwijderd", { bron_iri: s.bron_iri },
      () => { s.weg = true; });
    return r ?? route.fulfill({ json: uit() });
  }
  if (p === "/api/werkgebieden/wg1/elementen") return route.fulfill({ json: {
    werkgebied_id: "wg1", revisie: wg.revisie, volledig: false,
    selecties: [
      { id: "s1", bron_iri: IRI9, label: "Invorderingswet 1990 – artikel 9", rol: "analyseren", bereik: "onderliggend",
        aantal: 2, afgewezen: 1, bron_gewijzigd: true, onbereikbaar: null },
      { id: "s2", bron_iri: IRI3, label: "Algemene wet inzake rijksbelastingen – artikel 3", rol: "context", bereik: "onderliggend",
        aantal: 0, afgewezen: 0, bron_gewijzigd: false, onbereikbaar: "De brongraaf is tijdelijk niet beschikbaar." },
    ],
    elementen: [
      { id: "e1", klasse: "Rechtssubject", tekst: "de ontvanger", lifecycle: "human_approved", eigenaar_iri: `${IRI9}:lid1`,
        laag_id: "l1", ankers: [], rol: "analyseren", selecties: ["s1"], deels_buiten: false },
      { id: "e2", klasse: "Rechtsfeit", tekst: "de aanslag is invorderbaar", lifecycle: "voorgesteld", eigenaar_iri: `${IRI9}:lid2`,
        laag_id: "l2", ankers: [], rol: "analyseren", selecties: ["s1"], deels_buiten: true },
    ] } });
  if (p === "/api/werkgebieden/wg1/audit") return route.fulfill({ json: { audit } });
  if (p === "/api/werkgebieden/wg1/begrippen") return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", begrippen: [], primair: {} } });
  if (p === "/api/annotatie/v2/samenhang") return route.fulfill({ json: samenhang(url.searchParams.get("bron_iri")) });
  if (p === "/api/annotatie/v2/samenhang/meer")
    return route.fulfill({ json: { resultaten: url.searchParams.getAll("bron_iri").map(samenhang), fouten: [] } });
  if (p.startsWith("/api/annotatie/v2/")) return route.fulfill({ status: 404, json: { detail: "Niet in deze test." } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ status: 200, json: {} });
});

// Met SCREENSHOT_DIR legt het script de kernmomenten vast, om de vormgeving na te lopen.
const foto = (naam) => process.env.SCREENSHOT_DIR
  ? page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/${naam}.png`, fullPage: true }) : null;
const melding = (tekst) => page.getByText(tekst, { exact: false }).first().waitFor();
try {
  // Overzicht → nieuw werkgebied → de pagina van het werkgebied.
  await page.goto(`${base}/werkgebieden`);
  await page.getByText("Nog geen werkgebieden", { exact: false }).waitFor();
  await foto("werkgebieden-leeg");
  assert.equal(await page.getByRole("link", { name: "Werkgebieden" }).first().getAttribute("aria-current"), "page");
  await page.getByRole("button", { name: "Nieuw werkgebied" }).click();
  await page.getByLabel("Naam").fill("Invordering bij nalatigheid");
  await page.getByLabel("Analysevraag").fill("Wanneer is een aanslag invorderbaar?");
  await page.getByRole("button", { name: "Aanmaken" }).click();
  await page.waitForURL("**/werkgebieden/wg1");
  await page.getByRole("heading", { name: "Invordering bij nalatigheid" }).waitFor();
  await page.getByText("Nog geen bronnen. Neem hieronder", { exact: false }).waitFor();

  // Een ongeldige regeling komt niet bij de api; een geldige wel, met de revisie in beeld.
  await page.getByLabel("Regeling of bron-IRI").fill("Invorderingswet");
  await page.getByLabel("Artikel", { exact: true }).fill("9");
  await page.getByRole("button", { name: "Opnemen" }).click();
  await melding("Regeling: geef een BWB-id");
  assert.equal(requests.filter((r) => r.p.endsWith("/bronnen")).length, 0);
  await page.getByLabel("Regeling of bron-IRI").fill("bwbr0004770");
  await page.getByLabel("Artikel", { exact: true }).fill("artikel 9");
  await page.getByRole("button", { name: "Opnemen" }).click();
  await page.getByRole("link", { name: "Invorderingswet 1990 – artikel 9" }).waitFor();
  const eerste = requests.find((r) => r.p.endsWith("/bronnen") && r.m === "POST").body;
  assert.deepEqual([eerste.bwb_id, eerste.artikel, eerste.verwachte_revisie, eerste.rol, eerste.bereik],
    ["BWBR0004770", "9", 1, "analyseren", "onderliggend"]);
  // De link naar de bepaling gaat naar haar annotatie, met de IRI als query-parameter.
  assert.equal(await page.getByRole("link", { name: "Invorderingswet 1990 – artikel 9" }).getAttribute("href"),
    `/annotaties/node?bron_iri=${encodeURIComponent(IRI9)}`);

  // Dezelfde bron nog eens: idempotent, en dat staat er.
  await page.getByLabel("Regeling of bron-IRI").fill("BWBR0004770");
  await page.getByLabel("Artikel", { exact: true }).fill("9");
  await page.getByRole("button", { name: "Opnemen" }).click();
  await melding("stond er al in");
  // Een bepaling die de graaf niet kent: de reden van de api staat bij het formulier.
  await page.getByLabel("Regeling of bron-IRI").fill("BWBR0000001");
  await page.getByLabel("Artikel", { exact: true }).fill("1");
  await page.getByRole("button", { name: "Opnemen" }).click();
  await melding("Bepaling niet gevonden in de graaf.");
  // Een contextbron.
  await page.getByLabel("Regeling of bron-IRI").fill("BWBR0002320");
  await page.getByLabel("Artikel", { exact: true }).fill("3");
  await page.getByLabel("Contextbron", { exact: false }).check();
  await page.getByRole("button", { name: "Opnemen" }).click();
  await page.getByRole("link", { name: "Algemene wet inzake rijksbelastingen – artikel 3" }).waitFor();
  await page.getByRole("tab", { name: "Bronnen (2)" }).waitFor();
  await foto("werkgebied-bronnen");

  // Rol wijzigen. Daarna een conflict: iemand anders was ons voor – de pagina laadt opnieuw en zegt het.
  await page.getByLabel("Rol van Invorderingswet 1990 – artikel 9").selectOption("context");
  await melding("Rol gewijzigd naar contextbron.");
  const patch = requests.filter((r) => r.m === "PATCH").at(-1).body;
  assert.deepEqual([patch.rol, patch.verwachte_revisie], ["context", 3]);
  volgendeConflict = true;
  await page.getByLabel("Rol van Invorderingswet 1990 – artikel 9").selectOption("analyseren");
  await melding("Iemand anders wijzigde dit werkgebied net.");
  assert.equal(await page.getByLabel("Rol van Invorderingswet 1990 – artikel 9").inputValue(), "context");

  // Elementen: open punt, onvolledig, signaal, voorbehoud en deels-buiten staan er allemaal.
  await page.getByRole("tab", { name: "Elementen" }).click();
  await page.waitForURL("**/werkgebieden/wg1?tab=elementen");
  await melding("De inventaris is niet volledig");
  await melding("Open punt: De brongraaf is tijdelijk niet beschikbaar.");
  await melding("Brontekst gewijzigd sinds opname");
  await melding("1 verworpen (niet getoond)");
  await melding("voorstel van Lex · nog niet beoordeeld");
  await melding("Valt deels buiten de selecties");
  await melding("1 van 2 in de werkvoorraad beoordeeld");
  await foto("werkgebied-elementen");
  await page.getByLabel("Klasse").selectOption("Rechtsfeit");
  assert.equal(await page.getByText("“de ontvanger”").count(), 0);
  await page.getByText("“de aanslag is invorderbaar”").waitFor();

  // Herladen houdt de tab; de historie leest als zinnen.
  await page.reload();
  await page.getByRole("tab", { name: "Elementen", selected: true }).waitFor();
  await page.getByRole("tab", { name: "Historie" }).click();
  await melding("Invorderingswet 1990 – artikel 9 opgenomen als analyseren");
  await melding("Werkgebied aangemaakt");
  await foto("werkgebied-historie");

  // Samenhang: de graaf van de bronnen. Opnemen kan vanuit de inspector (de suggestielijst eronder is
  // vervangen door de kandidaten van Lex op de tab Bronnen, fase A).
  await page.getByRole("tab", { name: "Samenhang" }).click();
  await page.locator('[data-testid="samenhang-graaf"][data-gereed="true"]').waitFor({ timeout: 30000 });
  assert.equal(await page.getByRole("list", { name: "Verwijzingen buiten dit werkgebied" }).count(), 0);
  // In de inspector: een opgenomen bepaling zegt dat, een randbepaling is op te nemen.
  const zoek = page.getByRole("combobox", { name: "Zoek in de graaf" });
  await zoek.fill("Artikel 9");
  await page.locator(`[role="option"][data-knoop-id="${IRI9}"]`).click();
  await page.getByText("Staat in dit werkgebied").waitFor();
  await foto("werkgebied-samenhang");
  await zoek.fill("Artikel 10");
  await page.locator(`[role="option"][data-knoop-id="${IRI10}"]`).click();
  await page.getByRole("button", { name: "Opnemen in werkgebied" }).click();
  await melding("Artikel 10 opgenomen als analyseren.");
  assert.equal(requests.filter((r) => r.m === "POST" && r.p.endsWith("/bronnen")).at(-1).body.bron_iri, IRI10);
  await page.getByRole("tab", { name: "Bronnen (3)" }).waitFor();

  // Weghalen vraagt een tweede klik; de bepaling verdwijnt uit het werkgebied.
  await page.getByRole("tab", { name: /^Bronnen/ }).click();
  const weg = page.getByRole("button", { name: "Weghalen" }).first();
  await weg.click();
  await page.getByRole("button", { name: "Weghalen?" }).click();
  await melding("De annotaties van de bepaling blijven staan.");
  await page.getByRole("tab", { name: "Bronnen (2)" }).waitFor();
  const del = requests.filter((r) => r.m === "DELETE").at(-1);
  assert.match(del.q, /verwachte_revisie=\d+/);

  // Vanaf de annotatie: opnemen in een werkgebied dat daar niet in beeld is. Iemand anders wijzigt het
  // tussendoor (412); de pagina haalt de revisie opnieuw op en probeert het één keer opnieuw.
  // Artikel 9 is net weggehaald; artikel 3 staat er al als contextbron, dus dat geeft de 409-melding.
  await page.goto(`${base}/annotaties/node?bron_iri=${encodeURIComponent(IRI3)}`);
  await page.getByRole("button", { name: "Opnemen in werkgebied" }).click();
  await page.getByRole("list", { name: "Werkgebieden" }).getByRole("button", { name: /Invordering bij nalatigheid/ }).click();
  await melding("met een andere rol of een ander bereik");
  await page.goto(`${base}/annotaties/node?bron_iri=${encodeURIComponent(IRI9)}`);
  await page.getByRole("button", { name: "Opnemen in werkgebied" }).click();
  await page.getByRole("list", { name: "Werkgebieden" }).getByRole("button", { name: /Invordering bij nalatigheid/ }).waitFor();
  volgendeConflict = true;
  const voor = requests.filter((r) => r.m === "POST" && r.p.endsWith("/bronnen")).length;
  await page.getByRole("list", { name: "Werkgebieden" }).getByRole("button", { name: /Invordering bij nalatigheid/ }).click();
  await melding("Opgenomen in Invordering bij nalatigheid.");
  assert.equal(requests.filter((r) => r.m === "POST" && r.p.endsWith("/bronnen")).length - voor, 2);
  await page.getByRole("link", { name: "Naar het werkgebied" }).waitFor();
  await foto("annotatie-opnemen");

  // Smal scherm: geen horizontale scroll, en de drawer is te openen.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${base}/werkgebieden/wg1`);
  await page.getByRole("tab", { name: "Bronnen (3)" }).waitFor();
  await foto("werkgebied-mobiel");
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  assert.deepEqual(errors, []);
  console.log("Browser OK: werkgebied aanmaken, bron opnemen (ongeldig/idempotent/422/context), rol wijzigen, revisieconflict, inventaris met open punt en signalen, tab in de URL, historie, samenhang met opnemen vanuit de inspector, weghalen met bevestiging, opnemen vanaf een annotatie met herkansing na 412, smal scherm.");
} catch (e) {
  await foto("fout");
  throw e;
} finally { await browser.close(); }
