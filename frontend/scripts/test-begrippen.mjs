/** Browserregressie voor de begrippenwerkplek (spoor D, levering 2) op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-begrippen.mjs` (na npx playwright install chromium).
 *
 * De mock gedraagt zich als de api (api/app/begrip_store.py): revisies met 412, de poort met
 * dezelfde zinnen, één primaire duiding per element (409 `al_primair`) en de export. Het pad is de
 * acceptatie uit PLAN D: uit annotaties in twee regelingen één begrip maken, het beoordelen en
 * accorderen, en elke passage terugvinden.
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
const page = await context.newPage();
const errors = [], requests = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-15T10:00:00+00:00";
const IW = "urn:bwb:BWBR0004770", AWR = "urn:bwb:BWBR0002320";
const ART9 = `${IW}:artikel:9`, ART2 = `${AWR}:artikel:2`;
const wg = { id: "wg1", naam: "Invordering", analysevraag: "", afbakening: "", peildatum: null, status: "actief", revisie: 3,
  aangemaakt_door: "browser-test", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null,
  bronnen: [
    { id: "s1", bron_iri: ART9, bereik: "onderliggend", rol: "analyseren", reden: "", label: "Invorderingswet 1990 – artikel 9", bwb_id: "BWBR0004770", snapshot_id: "s", bron_hash: "h", toegevoegd_door: "a", toegevoegd: nu },
    { id: "s2", bron_iri: ART2, bereik: "onderliggend", rol: "analyseren", reden: "", label: "AWR – artikel 2", bwb_id: "BWBR0002320", snapshot_id: "s", bron_hash: "h", toegevoegd_door: "a", toegevoegd: nu },
  ] };
// Vier annotatie-elementen; e2 is nog niet door een jurist beoordeeld, e4 duidt al "Ontvanger" aan.
const elementen = {
  e1: { tekst: "de belastingschuldige", eigenaar_iri: `${ART9}:lid:1`, vindplaats: "Invorderingswet 1990 – artikel 9 · Lid 1", selectie: "s1", lifecycle: "human_approved" },
  e2: { tekst: "degene die de belasting verschuldigd is", eigenaar_iri: `${ART9}:lid:2`, vindplaats: "Invorderingswet 1990 – artikel 9 · Lid 2", selectie: "s1", lifecycle: "voorgesteld" },
  e3: { tekst: "de belastingplichtige", eigenaar_iri: ART2, vindplaats: "AWR – artikel 2", selectie: "s2", lifecycle: "human_approved" },
  e4: { tekst: "de ontvanger", eigenaar_iri: `${ART9}:lid:1`, vindplaats: "Invorderingswet 1990 – artikel 9 · Lid 1", selectie: "s1", lifecycle: "human_approved" },
};
const inventaris = () => ({ werkgebied_id: "wg1", revisie: wg.revisie, volledig: true,
  selecties: wg.bronnen.map((s) => ({ id: s.id, bron_iri: s.bron_iri, label: s.label, rol: s.rol, bereik: s.bereik,
    aantal: 2, afgewezen: 0, bron_gewijzigd: false, onbereikbaar: null })),
  elementen: Object.entries(elementen).map(([id, e]) => ({ id, klasse: "Rechtssubject", tekst: e.tekst, lifecycle: e.lifecycle,
    eigenaar_iri: e.eigenaar_iri, laag_id: "l", ankers: [], rol: "analyseren", selecties: [e.selectie], deels_buiten: false })) });

const LEEG = { naam: "", alternatieve_termen: [], context: "", definitie: "", definitie_herkomst: null, uitleg: "", voorbeelden: [] };
const begrippen = new Map();
let teller = 0, conflictBijOpslaan = false;
const koppeling = (bid, eid, rol) => ({ id: `k${++teller}`, begrip_id: bid, element_id: eid, rol, motivatie: "",
  bewijs: { tekst: elementen[eid].tekst, klasse: "Rechtssubject", ankers: [], eigenaar_iri: elementen[eid].eigenaar_iri,
    laag_id: "l", snapshot_id: "s", lifecycle: elementen[eid].lifecycle, vindplaats: elementen[eid].vindplaats, element_hash: "h" },
  beoordeling: "open", beoordeeld_door: null, beoordeeld_op: null, toegevoegd_door: "browser-test", toegevoegd: nu });
function maak(naam, eids = [], rol = "duiding") {
  const id = `b${++teller}`;
  begrippen.set(id, { id, status: "concept", revisie: 1, inhoud: { ...LEEG, naam }, aangemaakt_door: "browser-test",
    aangemaakt: nu, gewijzigd: nu, geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
    koppelingen: eids.map((e) => koppeling(id, e, rol)), revisies: [{ revisie: 1, actie: "begrip-aangemaakt", detail: { element_ids: eids }, actor: "browser-test" }] });
  return id;
}
maak("Ontvanger", ["e4"]);                        // e4 duidt al een begrip aan
const meervoud = (n, een, meer) => (n === 1 ? een : meer.replace("{n}", n));
function poort(b) {
  const r = [], i = b.inhoud;
  if (!i.definitie.trim()) r.push("Er is nog geen definitie.");
  if (!i.context.trim()) r.push("De toelichting ontbreekt.");
  const dragend = b.koppelingen.filter((k) => k.rol !== "context" && k.beoordeling !== "afgewezen");
  if (!dragend.some((k) => k.rol === "duiding")) r.push("Er is nog geen passage die dit begrip aanduidt.");
  const open = dragend.filter((k) => k.beoordeling === "open").length;
  if (open) r.push(meervoud(open, "1 dragende koppeling is nog niet beoordeeld.", "{n} dragende koppelingen zijn nog niet beoordeeld."));
  const onb = dragend.filter((k) => elementen[k.element_id].lifecycle !== "human_approved").length;
  if (onb) r.push(meervoud(onb, "1 dragende annotatie is nog niet door een jurist beoordeeld.", "{n} dragende annotaties zijn nog niet door een jurist beoordeeld."));
  return { mag: !r.length, redenen: r };
}
const uit = (b) => {
  const { revisies, ...rest } = b;
  const koppelingen = b.koppelingen.map((k) => ({ ...k, actualiteit: "actueel", lifecycle_nu: elementen[k.element_id].lifecycle,
    annotatie_beoordeeld: elementen[k.element_id].lifecycle === "human_approved" }));
  const p = poort(b);
  return { ...rest, iri: `urn:wa:begrip:${b.id}`, werkgebied_id: "wg1", kader_iri: "urn:wa:kader:wg1", koppelingen,
    accorderen: p, aandachtspunten: b.status === "geaccordeerd" ? [] : p.redenen };
};
const primair = () => Object.fromEntries([...begrippen.values()].flatMap((b) =>
  b.koppelingen.filter((k) => k.rol === "duiding").map((k) => [k.element_id, { begrip_id: b.id, naam: b.inhoud.naam }])));
function alPrimair(bid, eids, rol) {
  if (rol !== "duiding") return null;
  const p = primair();
  const eid = eids.find((e) => p[e] && p[e].begrip_id !== bid);
  return eid ? { fout: "al_primair", element_id: eid, begrip_id: p[eid].begrip_id, begrip_naam: p[eid].naam,
    melding: `Dit element duidt al het begrip "${p[eid].naam}" aan. Koppel het hier als definitie of context, of wijzig het daar.` } : null;
}
function muteer(route, b, verwacht, actie, detail, doe) {
  if (verwacht !== b.revisie) return route.fulfill({ status: 412, json: { detail: { fout: "revisie_conflict", revisie: b.revisie } } });
  const fout = doe();
  if (fout) return route.fulfill({ status: fout.status, json: { detail: fout.detail } });
  b.revisie += 1;
  if (actie !== "begrip-geaccordeerd" && b.status === "geaccordeerd") b.status = "concept";
  b.revisies.unshift({ revisie: b.revisie, actie, detail, actor: "browser-test" });
  return route.fulfill({ json: uit(b) });
}

const bulkOp = [];
await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" || m === "DELETE" ? null : req.postDataJSON();
  if (p.startsWith("/api/werkgebieden")) requests.push({ p, m, body });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/elementen") return route.fulfill({ json: inventaris() });
  if (p === "/api/werkgebieden/wg1/audit") return route.fulfill({ json: { audit: [] } });
  if (p === "/api/werkgebieden/wg1/begrippen" && m === "GET")
    return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", primair: primair(),
      begrippen: [...begrippen.values()].map((b) => { const { koppelingen, ...r } = uit(b);
        return { ...r, aantal_koppelingen: koppelingen.length, element_ids: koppelingen.map((k) => k.element_id) }; }) } });
  if (p === "/api/werkgebieden/wg1/begrippen" && m === "POST") {
    const fout = alPrimair(null, body.element_ids ?? [], body.rol ?? "duiding");
    if (fout) return route.fulfill({ status: 409, json: { detail: fout } });
    return route.fulfill({ status: 201, json: uit(begrippen.get(maak(body.inhoud.naam, body.element_ids, body.rol))) });
  }
  if (p === "/api/werkgebieden/wg1/begrippen/export") {
    const rijen = [...begrippen.values()].flatMap((b) => b.koppelingen.map((k) => [b.inhoud.naam, b.status, k.bewijs.tekst, k.bewijs.vindplaats].join(",")));
    return route.fulfill({ status: 200, headers: { "Content-Type": "text/csv", "Content-Disposition": 'attachment; filename="begrippen.csv"' },
      body: ["begrip,status,passage,vindplaats", ...rijen].join("\n") });
  }
  const pm = p.match(/^\/api\/werkgebieden\/wg1\/begrippen\/(b\d+)(?:\/(\w+))?(?:\/(k\d+|beoordelen))?$/);
  if (pm) {
    const b = begrippen.get(pm[1]), deel = pm[2], kid = pm[3];
    if (!deel && m === "GET") return route.fulfill({ json: uit(b) });
    if (!deel && m === "PATCH") {
      if (conflictBijOpslaan) {         // iemand anders slaat net eerder op
        conflictBijOpslaan = false;
        b.revisie += 1;
        b.inhoud = { ...b.inhoud, context: "Van een ander" };
      }
      return muteer(route, b, body.verwachte_revisie, "begrip-gewijzigd", { velden: ["definitie"] }, () => {
        // Zoals de api (spoor I1): de herkomst rekent de server; een eigen of gewijzigde tekst is geformuleerd.
        const def = (body.inhoud.definitie ?? "").trim();
        const herkomst = !def ? null : def === b.inhoud.definitie.trim() && b.inhoud.definitie_herkomst ? b.inhoud.definitie_herkomst : "geformuleerd";
        b.inhoud = { ...LEEG, ...body.inhoud, definitie_herkomst: herkomst };
      });
    }
    if (deel === "revisies") return route.fulfill({ json: { revisies: b.revisies.map((r) => ({ ...r, status: b.status, inhoud: b.inhoud, tijdstip: nu })) } });
    if (kid === "beoordelen")
      return muteer(route, b, body.verwachte_revisie, "koppeling-gewijzigd", { beoordeling: body.beoordeling, koppelingen: body.koppeling_ids }, () => {
        bulkOp.push(body.koppeling_ids.length);
        for (const k of b.koppelingen) if (body.koppeling_ids.includes(k.id)) Object.assign(k, { beoordeling: body.beoordeling, beoordeeld_door: "browser-test" });
      });
    if (deel === "koppelingen" && !kid)
      return muteer(route, b, body.verwachte_revisie, "begrip-gekoppeld", { element_ids: body.element_ids }, () => {
        const fout = alPrimair(b.id, body.element_ids, body.rol);
        if (fout) return { status: 409, detail: fout };
        body.element_ids.forEach((e) => b.koppelingen.push(koppeling(b.id, e, body.rol)));
      });
    if (deel === "koppelingen" && m === "PATCH")
      return muteer(route, b, body.verwachte_revisie, "koppeling-gewijzigd", { beoordeling: body.beoordeling }, () => {
        const k = b.koppelingen.find((x) => x.id === kid);
        if (body.beoordeling) Object.assign(k, { beoordeling: body.beoordeling, beoordeeld_door: "browser-test" });
        if (body.rol) k.rol = body.rol;
      });
    if (deel === "accorderen")
      return muteer(route, b, body.verwachte_revisie, "begrip-geaccordeerd", { reden: body.reden }, () => {
        const pt = poort(b);
        if (!pt.mag) return { status: 409, detail: { fout: "poort", redenen: pt.redenen, melding: "Nog niet te accorderen." } };
        Object.assign(b, { status: "geaccordeerd", geaccordeerd_door: "browser-test", geaccordeerd_op: nu, geaccordeerd_revisie: b.revisie + 1 });
      });
  }
  // De strook "Voorstellen van Lex" staat op dezelfde tab; hier zonder voorstellen.
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: { run: null, groepen: [], passages: {} } });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run: null } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ status: 404, json: { detail: "Niet in deze test." } });
});

const foto = (naam) => process.env.SCREENSHOT_DIR
  ? page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/${naam}.png`, fullPage: true }) : null;
const zie = (tekst) => page.getByText(tekst, { exact: false }).first().waitFor();
const kaart = () => page.locator("[data-begrip-paneel]");
try {
  // 1. Uit de inventaris: passages uit twee regelingen kiezen. Met e4 erbij weigert de api (al_primair).
  await page.goto(`${base}/werkgebieden/wg1?tab=elementen`);
  await zie("Duidt het begrip");
  for (const t of ["de belastingschuldige", "degene die de belasting verschuldigd is", "de belastingplichtige", "de ontvanger"])
    await page.getByRole("checkbox", { name: `Kies "${t}"` }).check();
  await zie("4 elementen gekozen");
  await page.getByRole("textbox", { name: "Naam van het nieuwe begrip" }).fill("Belastingschuldige");
  await page.getByRole("button", { name: "Nieuw begrip uit selectie" }).click();
  await zie('duidt al het begrip "Ontvanger" aan');
  await page.getByRole("checkbox", { name: 'Kies "de ontvanger"' }).uncheck();
  await page.getByRole("button", { name: "Nieuw begrip uit selectie" }).click();
  // Spoor N: een nieuw begrip opent op zijn eigen pagina. In het kader is het een rij; geen *Vraag Lex* in een rij.
  await page.waitForURL(/\/werkgebieden\/wg1\/begrippen\/b\d+$/);
  await page.locator("[data-begrip-pagina]").waitFor();
  // De knop staat er zodra het begrip geladen is; eerst wachten, dan tellen.
  const bespreek = page.locator("[data-paginakop]").getByRole("link", { name: /^Bespreek .* met Lex$/ });
  await bespreek.first().waitFor();
  assert.equal(await bespreek.count(), 1);
  const passages = page.getByRole("list", { name: "Passages van dit begrip" }).getByRole("listitem");
  await page.getByRole("heading", { name: "Passages 3" }).waitFor();
  assert.equal(await passages.count(), 3);
  // Spoor N: passages toevoegen gaat in een venster, als boom; wat een ander begrip aanduidt zegt dat, en een rol kies je
  // achter het menu van de rij.
  await page.getByRole("button", { name: "Passages toevoegen" }).click();
  const dialoog = page.locator("[data-passages-dialoog]");
  await dialoog.getByRole("checkbox", { name: "Kies “de ontvanger”" }).waitFor();
  await dialoog.getByText("duidt al “Ontvanger” aan").waitFor();
  await dialoog.getByRole("button", { name: "Annuleren" }).click();

  // 2. De poort zegt wat er nog nodig is; accorderen kan nog niet.
  const nodig = page.getByRole("list", { name: "Nog nodig om te accorderen" });
  for (const r of ["Er is nog geen definitie.", "De toelichting ontbreekt.", "3 dragende koppelingen zijn nog niet beoordeeld.",
    "1 dragende annotatie is nog niet door een jurist beoordeeld."]) await nodig.getByText(r).waitFor();
  assert.equal(await page.getByRole("button", { name: "Accorderen" }).isDisabled(), true);
  await foto("begrip-nieuw");

  // Spoor N: in rust staat alles te lezen; *Bewerken* maakt van het blok ter plekke een formulier. De NL-SBB-eigenschappen
  // staan alleen in de bewerkstand, en niemand kiest de herkomst.
  const betekenis = () => kaart().locator("[data-blok=betekenis]");
  assert.equal(await betekenis().getByRole("textbox").count(), 0, "in rust staat er geen invoerveld");
  assert.equal(await kaart().locator("[data-kaart-groep]").count(), 0);
  await betekenis().getByRole("button", { name: "Betekenis bewerken" }).click();
  await kaart().getByLabel(/^Definitie/).fill("Degene die de belasting verschuldigd is.");
  assert.deepEqual(await kaart().locator("[data-kaart-groep]").evaluateAll((g) => g.map((x) => x.dataset.kaartGroep)),
    ["Term", "Definitie, uitleg en toelichting"]);
  assert.equal(await betekenis().getByRole("radio").count(), 0);
  for (const weg of ["JAS-duiding", "Begripstype", "Onderbouwing", "Open vragen", "Eigenschappen"])
    assert.equal(await kaart().getByText(weg, { exact: true }).count(), 0, weg);
  await betekenis().locator("[data-definitie-aard=analysebegrip]").getByText("geen wettelijke definitie", { exact: false }).waitFor();
  await betekenis().getByLabel(/^Toelichting/).fill("Invordering van rijksbelastingen.");
  await zie("Sla eerst je wijzigingen op");
  await betekenis().getByRole("button", { name: "Opslaan" }).click();
  await zie("Opgeslagen.");
  const laatstePatch = () => requests.filter((r) => r.m === "PATCH" && /begrippen\/b\d+$/.test(r.p)).at(-1);
  assert.equal(laatstePatch().body.verwachte_revisie, 1);
  assert.equal(laatstePatch().body.inhoud.jas_klasse, undefined);
  await kaart().locator("[data-begrip-lees]").getByText("Degene die de belasting verschuldigd is.").waitFor();

  // Spoor I3: een voorbeeld met het oordeel als gekleurde keuzepil, in een tekstvak dat alles toont; een eigen blok.
  await kaart().getByRole("button", { name: "Voorbeelden bewerken" }).click();
  await kaart().getByRole("button", { name: "Voorbeeld toevoegen" }).click();
  const vb = kaart().getByLabel("Voorbeeld 1", { exact: true });
  await vb.fill("Iemand die een aanslag inkomstenbelasting krijgt maar in het buitenland woont en daar ook zijn "
    + "inkomen verdient, met een lange zin die over meerdere regels loopt zodat het vak moet meegroeien.");
  assert.equal(await vb.evaluate((el) => getComputedStyle(el).resize), "none");
  assert.ok(await vb.evaluate((el) => el.scrollHeight <= el.clientHeight + 1), "het tekstvak toont alle tekst");
  const oordeel = kaart().getByRole("radiogroup", { name: "Oordeel bij voorbeeld 1" });
  assert.equal(await oordeel.getByRole("radio").count(), 3);
  await oordeel.getByText("valt er niet onder").click();
  assert.equal(await oordeel.getByRole("radio", { name: "valt er niet onder" }).isChecked(), true);
  await foto("begrip-voorbeelden");
  await kaart().locator("[data-blok=voorbeelden]").getByRole("button", { name: "Opslaan" }).click();
  await kaart().getByRole("list", { name: "Voorbeelden" }).waitFor();
  assert.equal(laatstePatch().body.verwachte_revisie, 2);
  assert.deepEqual(laatstePatch().body.inhoud.voorbeelden.map((v) => v.oordeel), ["niet"]);
  assert.equal(laatstePatch().body.inhoud.context, "Invordering van rijksbelastingen.", "een blok laat de andere velden staan");

  // Spoor M: rust de bewaarde definitie op fragmenten (een overgenomen voorstel van Lex), dan staan die eronder – bij
  // het bewerken alleen zolang de tekst de bewaarde is.
  const bid = laatstePatch().p.split("/").at(-1);
  begrippen.get(bid).definitie_onderbouwing = { voorstel_id: "v1", actie: "scherper", herkomst: "geformuleerd",
    definitie_bron_iri: "", definitie_vindplaats: "", duiding: null, onderzoek_id: "O1",
    fragmenten: [{ bron_iri: "urn:bwb:BWBR0004770:artikel:9:lid:1", start: 0, eind: 18, tekst: "de belastingschuldige", rol: "ondersteunend" }] };
  await page.reload();
  const blok = kaart().locator("[data-definitie-onderbouwing]");
  await blok.waitFor();
  assert.match(await blok.locator("summary").innerText(), /Rust op 1 fragment uit de bron – via een voorstel van Lex/);
  await kaart().getByRole("button", { name: "Betekenis bewerken" }).click();
  const definitie = kaart().getByLabel(/^Definitie/);
  await definitie.fill("Een andere tekst.");
  assert.equal(await blok.count(), 0, "een andere definitie rust niet op deze fragmenten");
  await definitie.fill("Degene die de belasting verschuldigd is.");
  await blok.waitFor();
  await kaart().locator("[data-bewerk-voet]").getByRole("button", { name: "Annuleren" }).click();
  delete begrippen.get(bid).definitie_onderbouwing;

  // Een tweede wijziging terwijl iemand anders net opsloeg: 412, de nieuwe stand erachter, jouw tekst blijft staan.
  await kaart().getByRole("button", { name: "Betekenis bewerken" }).click();
  await kaart().getByLabel(/^Uitleg/).fill("Mijn uitleg");
  conflictBijOpslaan = true;
  await kaart().locator("[data-bewerk-voet]").getByRole("button", { name: "Opslaan" }).click();
  await zie("Iemand anders wijzigde dit begrip net.");
  assert.equal(await kaart().getByLabel(/^Uitleg/).inputValue(), "Mijn uitleg");
  await kaart().locator("[data-bewerk-voet]").getByRole("button", { name: "Annuleren" }).click();
  await kaart().locator("[data-begrip-lees]").getByText("Van een ander").waitFor();
  await kaart().getByText("Nog geen uitleg.").waitFor();

  // Terug naar het begrippenkader met onbewaarde wijzigingen vraagt eerst bevestiging (het is een link).
  await kaart().getByRole("button", { name: "Betekenis bewerken" }).click();
  await kaart().getByLabel(/^Uitleg/).fill("Nog niet bewaard");
  const kaartUrl = page.url();
  await page.getByRole("navigation", { name: "Kruimelpad" }).getByRole("link").nth(1).click();
  await zie("Niet-bewaarde wijzigingen");
  await page.getByRole("button", { name: "Blijf hier" }).click();
  await page.locator("[data-begrip-pagina]").waitFor();
  assert.equal(page.url(), kaartUrl);
  assert.equal(await kaart().getByLabel(/^Uitleg/).inputValue(), "Nog niet bewaard");
  // Ook een link in de sidebar (client-side navigatie) wacht op die vraag.
  const voor = page.url();
  await page.locator("aside").getByRole("link", { name: /^Werkgebieden/ }).click();
  await page.getByRole("button", { name: "Toch verlaten" }).waitFor();
  await page.getByRole("button", { name: "Blijf hier" }).click();
  assert.equal(page.url(), voor);
  assert.equal(await kaart().getByLabel(/^Uitleg/).inputValue(), "Nog niet bewaard");
  await page.locator("[data-bewerk-voet]").getByRole("button", { name: "Annuleren" }).click();
  // Zonder wijzigingen gaat dezelfde link gewoon.
  await page.locator("aside").getByRole("link", { name: /^Werkgebieden/ }).click();
  await page.waitForURL(/\/werkgebieden$/);
  await page.goBack();
  await kaart().waitFor();

  // 3. De passages beoordelen; de jurist keurt intussen de laatste annotatie goed.
  const openPassages = (n) => page.waitForFunction((n) => [...document.querySelectorAll("button")]
    .filter((b) => b.getAttribute("aria-label")?.startsWith("Akkoord met ")).length === n, n);
  await page.getByRole("button", { name: /^Akkoord met “/ }).first().click();
  await page.getByRole("button", { name: "Akkoord?" }).click();
  await openPassages(2);
  // De rest in één handeling: één verzoek, één revisie.
  elementen.e2.lifecycle = "human_approved";
  await page.getByRole("button", { name: "Alle open akkoord (2)" }).click();
  await page.getByRole("button", { name: "2 akkoord?" }).click();
  await openPassages(0);
  assert.deepEqual(bulkOp, [2]);
  await zie("Alles is er");
  // Accorderen vraagt een reden: zonder blijft de knop uit, en de reden gaat mee.
  assert.equal(await page.getByRole("button", { name: "Accorderen" }).isDisabled(), true);
  await page.getByLabel("Reden van accorderen").fill("Getoetst aan de bron.");
  await page.getByRole("button", { name: "Accorderen" }).click();
  await zie("Geaccordeerd door browser-test");
  await foto("begrip-geaccordeerd");

  // 4. Elke passage terugvinden: de link naar de annotatie wijst het element aan, en de export draagt ze alle drie.
  await passages.first().getByRole("button", { name: /^Acties: / }).click();
  const href = await page.getByRole("menuitem", { name: /^Bekijk “.*” in de annotatie$/ }).getAttribute("href");
  await page.keyboard.press("Escape");
  assert.match(href, /^\/annotaties\/node\?bron_iri=.+&element=e\d$/);
  // Exporteren hoort bij het begrippenkader, niet bij één begrip.
  await page.goto(`${base}/werkgebieden/wg1/artefacten/begrippen`);
  assert.equal(await page.locator("[data-begrip-rij] [data-vraag-lex]").count(), 0);
  await page.locator("[data-begrip-rij]").first().waitFor();
  assert.equal(await page.locator("[data-paginakop]").getByRole("link", { name: /^Bespreek .* met Lex$/ }).count(), 1);
  // Zoeken en de status werken op de rijen.
  await page.getByRole("searchbox", { name: "Begrippen doorzoeken" }).fill("ontvanger");
  await page.waitForFunction(() => document.querySelectorAll("[data-begrip-rij]").length === 1);
  await page.getByRole("searchbox", { name: "Begrippen doorzoeken" }).fill("");
  await page.getByRole("group", { name: "Status" }).getByRole("button", { name: "Geaccordeerd" }).click();
  await page.waitForFunction(() => document.querySelectorAll("[data-begrip-rij]").length === 1);
  await page.getByRole("group", { name: "Status" }).getByRole("button", { name: "Alle" }).click();
  // *Nieuw begrip*: de naam ter plekke, daarna de pagina.
  await page.getByRole("button", { name: "Nieuw begrip" }).click();
  await page.getByRole("textbox", { name: "Naam van het nieuwe begrip" }).fill("Termijn");
  await page.getByRole("button", { name: "Aanmaken" }).click();
  await page.waitForURL(/\/werkgebieden\/wg1\/begrippen\/b\d+$/);
  await page.getByRole("heading", { name: "Termijn", level: 1 }).waitFor();
  await page.goto(`${base}/werkgebieden/wg1/artefacten/begrippen`);
  await page.locator("[data-begrip-rij]").first().waitFor();
  await page.getByRole("button", { name: "Exporteren" }).click();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /^CSV/ }).click()]);
  assert.equal(download.suggestedFilename(), "begrippen.csv");
  const csv = await readFile(await download.path(), "utf8");
  for (const v of ["Invorderingswet 1990 – artikel 9 · Lid 1", "Invorderingswet 1990 – artikel 9 · Lid 2", "AWR – artikel 2"])
    assert.ok(csv.includes(`Belastingschuldige,geaccordeerd,`) && csv.includes(v), v);

  // Een oude link naar een begrip gaat door naar zijn plek in het werkgebied.
  await page.goto(kaartUrl.replace("/werkgebieden/wg1/begrippen/", "/begrippen/wg1/"));
  await page.waitForURL(kaartUrl);
  // Herladen houdt de pagina en het begrip; de historie leest als zinnen.
  await page.goto(kaartUrl);
  await page.reload();
  await page.locator("[data-begrip-pagina]").waitFor();
  await kaart().waitFor();
  await kaart().getByText("Historie").click();
  await page.getByRole("list", { name: "Historie van het begrip" }).getByText("Geaccordeerd").waitFor();

  // Smal scherm: alles onder elkaar, zonder horizontale scroll.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("heading", { name: "Passages 3" }).waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  // Het kruimelpad blijft bereikbaar.
  assert.ok(await page.getByRole("navigation", { name: "Kruimelpad" }).isVisible());
  await page.waitForTimeout(300);
  await foto("begrip-mobiel");
  assert.deepEqual(errors, []);
  console.log("Browser OK: begrip uit passages in twee regelingen (met al_primair), poort met redenen, opslaan met revisie, 412 met behoud van invoer, tabwissel bewaakt, beoordelen, accorderen, link naar het element, CSV-export met elke passage, herladen, historie, smal scherm.");
} catch (e) {
  await foto("begrippen-fout");
  throw e;
} finally { await browser.close(); }
