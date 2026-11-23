/** Browserregressie voor tekst en lijst (`components/ui/TekstEnLijst.tsx`; melding gebruiker 23 nov 2026: vergroot stonden
 * de wettekst en de kaartjes onder elkaar, de tekst geperst tot 45% en de kaartjes met veel witruimte). Op de echte
 * Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-tekst-en-lijst.mjs`.
 *
 * Bewaakt, voor de annotatie op de pagina (`/annotaties/node`) en in het zijpaneel (normaal en vergroot):
 *  - breed genoeg naast elkaar: links de tekst over de volle hoogte, rechts de kaartjes, elk met een eigen scroll;
 *  - smal onder elkaar: de tekst bovenin (hoogstens 45%), de kaartjes eronder;
 *  - gekoppeld in twee richtingen: een markering in de tekst kiezen licht het kaartje uit en scrollt het in beeld, en
 *    een kaartje kiezen scrollt de markering in beeld;
 *  - de verdeling is te verslepen (de muis en de pijltjes, `Scheiding`) en blijft na herladen;
 *  - *Wat de graaf weet* staat onder de wettekst, in dezelfde kolom;
 *  - geen horizontale scroll.
 * Met `SCHERMAFBEELDINGEN=<map>` bewaart hij de stand breed en smal (voor de PR).
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";
import { SCHIL, controleerOnbekend, onbekend } from "./nepApi.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const map = process.env.SCHERMAFBEELDINGEN;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });

// Een lange bepaling in acht onderdelen, met een markering per onderdeel: genoeg om in beide kolommen te moeten scrollen.
const ZIN = "De ontvanger kan de belastingschuldige uitstel van betaling verlenen wanneer de belastingaanslag nog niet "
  + "onherroepelijk vaststaat en zekerheid is gesteld voor het bedrag van de aanslag, met de kosten en de rente. ";
const LEDEN = [1, 2, 3, 4, 5, 6, 7, 8];
const UITSTEL = ZIN.indexOf("uitstel van betaling");
const doel = { bron_iri: "urn:art9", label: "Invorderingswet 1990 – artikel 9", snapshot_id: "snapshot" };
const view = {
  schema_versie: 2, doel: { ...doel, type: "Artikel", bwb_id: "BWBR0004770", artikel: "9" }, snapshot_id: "snapshot",
  segmenten: LEDEN.map((n) => ({ bron_iri: `urn:lid${n}`, parent_iri: "urn:art9", type: "Lid", nummer: String(n), label: `Lid ${n}`,
    tekst: ZIN.repeat(3), bron_hash: `h${n}`, volgorde: n })),
  lagen: LEDEN.map((n) => ({ id: `laag${n}`, bron_iri: `urn:lid${n}`, status: "in_review", revisie: 1 })),
  elementen: LEDEN.map((n) => ({ id: `e${n}`, eigenaar_iri: `urn:lid${n}`, laag_id: `laag${n}`, klasse: n % 2 ? "Rechtssubject" : "Rechtsobject",
    tekst: n % 2 ? "ontvanger" : "uitstel van betaling", lifecycle: "voorgesteld", herkomst: "agent",
    ankers: [n % 2 ? { bron_iri: `urn:lid${n}`, start: 3, eind: 12, tekst: "ontvanger", bron_hash: `h${n}` }
      : { bron_iri: `urn:lid${n}`, start: UITSTEL, eind: UITSTEL + 20, tekst: "uitstel van betaling", bron_hash: `h${n}` }] })),
  verwijzingen: [], dekking: {},
};
const VP = (iri, label) => ({ iri, label, jci: "", regeling: "Invorderingswet 1990" });
const NUL = { aantal: 0, volledig: true, items: [] };
const BEPALING = {
  schema_versie: 1, bron_iri: "urn:art9", beschikbaar: true, vindplaats: VP("urn:art9", "Artikel 9"),
  plaats: [{ soort: "hoofdstuk", nummer: "II", titel: "Invordering in eerste aanleg", iri: "urn:hoofdstukII" }],
  status: "goed", inwerking: "2010-07-04", terugwerkend_tot: null, gewijzigd_bij: "Stb.2009-610", geldig_vanaf: "2026-10-01", geldig_tot: null,
  toestand_url: "", verwijst_naar_aantal: 1, verwijst_naar_volledig: true,
  verwijst_naar: [{ van: VP("urn:art9", "Artikel 9"), naar: VP("urn:art8", "Artikel 8"), anker: "artikel 8", in_graaf: true, door: "bron" }],
  verwezen_door: NUL, grondslag_voor: NUL, bevoegdheid_voor: NUL, genoemd_in: NUL, definieert: [],
};
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const berichten = [{ rol: "assistant", tekst: "", ...leeg, run_id: "a1", artefact: { soort: "annotatie", ref: doel, titel: doel.label } }];

const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
await page.route("**/api/**", async (route) => {
  const req = route.request(), p = new URL(req.url()).pathname;
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  if (p.endsWith("/weergave")) return route.fulfill({ json: view });
  if (p === "/api/annotatie/v2/bepaling") return route.fulfill({ json: BEPALING });
  if (p === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", titel: "Invordering", berichten } });
  if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Invordering", aantal_berichten: 1 }] });
  if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: false } });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  // Wat de pagina verder vraagt (werkgebieden, relaties, versies) doet hier niet ter zake.
  return onbekend(route, { stil: [...SCHIL, /^GET \/api\//], leeg: [] });
});

const schil = page.locator(".tekst-en-lijst-schil").first();
const tekst = page.locator("[data-tekst-kolom]").first();
const lijst = page.locator("[data-lijst-kolom]").first();
const doos = (l) => l.boundingBox();

async function naastElkaar(waar) {
  await page.locator('[data-review-kaart="e1"]').waitFor();
  const [s, t, l] = [await doos(schil), await doos(tekst), await doos(lijst)];
  assert.ok(t.x + t.width <= l.x + 1, `${waar}: de tekst staat links van de kaartjes`);
  assert.ok(Math.abs(t.y - l.y) <= 2, `${waar}: tekst en kaartjes beginnen op dezelfde hoogte`);
  assert.ok(t.height >= s.height * 0.9, `${waar}: de tekst over de volle hoogte (${Math.round(t.height)} van ${Math.round(s.height)})`);
  assert.ok(t.width > l.width, `${waar}: de tekst krijgt het grootste deel`);
}
async function onderElkaar(waar) {
  await page.locator('[data-review-kaart="e1"]').waitFor();
  const [s, t, l] = [await doos(schil), await doos(tekst), await doos(lijst)];
  assert.ok(t.y + t.height <= l.y + 1, `${waar}: de tekst staat boven de kaartjes`);
  assert.ok(t.height <= s.height * 0.46, `${waar}: de tekst hoogstens 45% hoog`);
  assert.ok(Math.abs(t.width - l.width) <= 2, `${waar}: tekst en kaartjes even breed`);
}
/** Is `el` binnen de zichtbare rand van zijn kolom? */
async function inBeeld(el, kolom, waar) {
  await page.waitForFunction(([e, k]) => {
    const a = document.querySelector(e)?.getBoundingClientRect(), b = document.querySelector(k)?.getBoundingClientRect();
    return a && b && a.top >= b.top - 1 && a.bottom <= b.bottom + 1;
  }, [el, kolom], { timeout: 5000 }).catch(() => assert.fail(`${waar}: ${el} komt in beeld in ${kolom}`));
}
async function gekoppeld(waar) {
  // Tekst → kaartje: de laatste markering kiezen brengt het laatste kaartje in beeld en licht het uit.
  await page.locator('[data-tekst-kolom] [data-element="e8"]').first().scrollIntoViewIfNeeded();
  await page.locator('[data-tekst-kolom] [data-element="e8"]').first().click();
  await inBeeld('[data-review-kaart="e8"]', "[data-lijst-kolom]", `${waar}, tekst → kaartje`);
  assert.match(await page.locator('[data-review-kaart="e8"]').getAttribute("class"), /ring-1/, `${waar}: het kaartje is uitgelicht`);
  // Kaartje → tekst: het eerste kaartje kiezen brengt de eerste markering in beeld.
  await page.locator('[data-lijst-kolom]').evaluate((el) => { el.scrollTop = 0; });
  await page.locator('[data-review-kaart="e1"] [data-kaart-citaat]').click();
  await inBeeld('[data-tekst-kolom] [data-element="e1"]', "[data-tekst-kolom]", `${waar}, kaartje → tekst`);
}
/** Slepen en de pijltjes op de scheiding: de tekstkolom wordt breder en smaller; dubbelklik zet de standaard terug. */
async function verdeling(waar) {
  const scheiding = page.locator("[data-tekst-scheiding]").first();
  const voor = (await doos(tekst)).width;
  const s = await doos(scheiding), blok = await doos(page.locator("[data-tekst-en-lijst]").first());
  await page.mouse.move(s.x + s.width / 2, s.y + 100);
  await page.mouse.down();
  await page.mouse.move(blok.x + blok.width * 0.45, s.y + 100, { steps: 6 });
  await page.mouse.up();
  const na = (await doos(tekst)).width;
  assert.ok(na < voor - 40, `${waar}: slepen maakt de tekst smaller (${Math.round(voor)} → ${Math.round(na)})`);
  assert.equal(await scheiding.getAttribute("aria-valuenow"), "45", `${waar}: de scheiding meldt de verdeling`);
  await scheiding.focus();
  await page.keyboard.press("ArrowRight");
  assert.equal(await scheiding.getAttribute("aria-valuenow"), "47", `${waar}: → maakt de tekst breder`);
  return scheiding;
}
async function graafOnderTekst(waar) {
  const blok = page.locator('[data-tekst-kolom] [data-blok="graaf"]').first();
  await blok.locator('[data-bepaling-feiten="gereed"]').waitFor();
  assert.ok((await blok.innerText()).includes("Invordering in eerste aanleg"), `${waar}: de plek uit de graaf onder de wettekst`);
}
async function geenScroll(waar) {
  assert.ok(!await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1), `${waar}: geen horizontale scroll`);
}

try {
  // --- De pagina: breed naast elkaar, smal onder elkaar ---
  await page.goto(`${base}/annotaties/node?bron_iri=urn:art9&snapshot_id=snapshot`);
  await naastElkaar("pagina, 1280 px");
  await gekoppeld("pagina, 1280 px");
  await graafOnderTekst("pagina, 1280 px");
  await geenScroll("pagina, 1280 px");
  if (map) await page.screenshot({ path: `${map}/tekst-en-lijst-pagina-breed.png` });

  await page.setViewportSize({ width: 700, height: 900 });
  await onderElkaar("pagina, 700 px");
  await gekoppeld("pagina, 700 px");
  await geenScroll("pagina, 700 px");
  if (map) await page.screenshot({ path: `${map}/tekst-en-lijst-smal.png` });

  // --- Het zijpaneel: naast het gesprek smal (onder elkaar), vergroot naast elkaar ---
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.locator("button", { hasText: doel.label }).first().click();
  await onderElkaar("paneel naast het gesprek");
  const kop = page.locator("[data-artefact] [data-kop-gereedschap]").first();
  await kop.getByRole("button", { name: "Vergroten", exact: true }).click();
  await page.locator('[data-zijpaneel="vergroot"]').waitFor();
  await naastElkaar("paneel vergroot");
  await gekoppeld("paneel vergroot");
  await graafOnderTekst("paneel vergroot");
  await geenScroll("paneel vergroot");
  if (map) await page.screenshot({ path: `${map}/tekst-en-lijst-vergroot.png` });
  // Handmatig schalen: verslepen, de pijltjes, en na herladen dezelfde verdeling (per browser bewaard).
  const scheiding = await verdeling("paneel vergroot");
  await page.reload();
  await page.locator('[data-zijpaneel="vergroot"]').waitFor();
  await page.locator('[data-review-kaart="e1"]').waitFor();
  assert.equal(await scheiding.getAttribute("aria-valuenow"), "47", "na herladen dezelfde verdeling");
  await scheiding.dblclick();
  assert.equal(await scheiding.getAttribute("aria-valuenow"), "57", "dubbelklik zet de standaard terug");
  await kop.getByRole("button", { name: "Verkleinen", exact: true }).click();
  await page.locator('[data-zijpaneel="open"]').waitFor();
  await onderElkaar("paneel weer naast het gesprek");

  assert.deepEqual(errors, []);
  controleerOnbekend();
  console.log("Browser OK: tekst en lijst naast elkaar op de pagina (1280 px) en in het vergrote paneel, onder elkaar op 700 px en naast het gesprek; tekst ↔ kaartje gekoppeld in twee richtingen; de verdeling te verslepen en bewaard; Wat de graaf weet onder de wettekst; geen horizontale scroll.");
} finally {
  await browser.close();
}
