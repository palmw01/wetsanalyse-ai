/** Browserregressie voor de ene paneelkop (8 nov 2026, melding van de gebruiker: de kop van de annotatie stond in drie
 * rijen met twee uitlijningen). Op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-paneelkop.mjs`.
 *
 * Voor elk paneel naast het gesprek – annotatie (Tekst en Graaf), begripsvoorstellen, werkgebied, begrip, deelvraag,
 * bronselectie, Bronnen – en voor de annotatiepagina, op 375, 400, 800 en 1280 px:
 *  - geen horizontale scroll;
 *  - de kop heeft hoogstens twee rijen: titel met ↗ ⋯ ✕ rechtsboven, en de status links met de hoofdactie rechts;
 *  - ✕ staat het meest rechts, ↗ en ⋯ ervoor op dezelfde hoogte, en het gereedschap blijft binnen het paneel, ook bij een
 *    lange titel;
 *  - in het menu ⋯ staat *Verwijderen* als laatste (annotatie, werkgebied, begrip);
 *  - op een aanraakscherm zijn de knoppen in de kop minstens 44 × 44 px.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });

const nu = "2026-10-15T10:00:00+00:00";
const LANG = "Invorderingswet 1990 met een uitzonderlijk lange citeertitel die moet afkappen";
const doel = { bron_iri: "urn:lid1", label: "Invorderingswet – artikel 9 lid 1", snapshot_id: "snapshot" };
const view = { schema_versie: 2, doel: { ...doel, type: "Lid", bwb_id: "BWBR0004770", artikel: "9", lid: "1", citeertitel: LANG },
  snapshot_id: "snapshot",
  segmenten: [{ bron_iri: "urn:lid1", parent_iri: "urn:artikel9", type: "Lid", nummer: "1", label: "Lid 1",
    tekst: "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.", bron_hash: "hash1", volgorde: 1 }],
  lagen: [{ id: "laag1", bron_iri: "urn:lid1", status: "in_review", revisie: 1 }],
  elementen: [], verwijzingen: [], dekking: {} };
const leeg = { denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" };
const berichten = [
  { rol: "assistant", tekst: "", ...leeg, run_id: "a1", artefact: { soort: "annotatie", ref: doel, titel: doel.label } },
  { rol: "assistant", tekst: "Voorstellen.", ...leeg, run_id: "b1", artefact: { soort: "begrippen", ref: { werkgebied_id: "wg1", run_id: "r1" }, titel: "" } },
  { rol: "assistant", tekst: "Werkgebied.", ...leeg, run_id: "w1", artefact: { soort: "werkgebied", titel: "Invordering", ref: { werkgebied_id: "wg1" } } },
  { rol: "assistant", tekst: "Begrip.", ...leeg, run_id: "k1", artefact: { soort: "begrip", titel: "Termijn", ref: { werkgebied_id: "wg1", begrip_id: "b9" } } },
  { rol: "assistant", tekst: "Deelvraag.", ...leeg, run_id: "d1", artefact: { soort: "deelvraag", titel: "Wie betaalt?", ref: { werkgebied_id: "wg1", deelvraag_id: "d1" } } },
];
const LEEG = { naam: "", alternatieve_termen: [], context: "", definitie: "", definitie_herkomst: null, definitie_door: "", uitleg: "", voorbeelden: [] };
const termijn = { id: "b9", iri: "urn:wa:begrip:b9", werkgebied_id: "wg1", kader_iri: "urn:wa:kader:wg1", status: "concept", revisie: 3,
  inhoud: { ...LEEG, naam: "Termijn", definitie: "Een tijdvak." }, koppelingen: [], aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu,
  geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
  accorderen: { mag: false, redenen: ["De toelichting ontbreekt."] }, aandachtspunten: [], vervangen_door: null, vervangt: [] };
const dv = { id: "d1", vraag: "Wie betaalt?", volgorde: 0, status: "actief", herkomst: "analist", reden: "", vervangt: "",
  aangemaakt_door: "t", aangemaakt: nu, bronnen: ["s1"], begrippen: [] };
const wg1 = { id: "wg1", naam: "Invordering", revisie: 2, status: "actief", analysevraag: "Wanneer is een aanslag invorderbaar?",
  bronnen: [{ id: "s1", bron_iri: "urn:lid1", label: "art. 9 lid 1 Iw", rol: "analyseren", bereik: "precies" }], deelvragen: [dv] };
const run = { id: "r1", werkgebied_id: "wg1", manifest_id: "M1", status: "klaar", reden: "", aantal_formuleringen: 0, overgeslagen: [],
  uitkomst: { groep_ids: [], meting: {}, vragen: [], relaties: [] }, vragen_besluiten: {}, gestart_door: "t", gestart: nu, gewijzigd: nu };

async function mock(page, metGraaf) {
  await page.context().addCookies(await sessieCookies(base));
  await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  await page.route("**/api/**", async (route) => {
    const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
    if (p.startsWith("/api/auth/")) return route.continue();
    if (p === "/api/annotatie/run") return route.fulfill({ json: null });
    if (p.endsWith("/weergave")) return route.fulfill({ json: view });
    if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg1 });
    if (p === "/api/werkgebieden/wg1/bronselectie")
      return route.fulfill({ json: { werkgebied_id: "wg1", naam: wg1.naam, revisie: wg1.revisie, modus: "deelvragen", actief: null, volgende: null,
        alle_klaar: false, zonder_deelvraag: [], zoekdekking: { gezocht: false, verouderd: false, volledig: true, onvolledig: [], reden: "" },
        deelvragen: [{ id: "d1", nr: 1, vraag: dv.vraag, status: "in_behandeling", fase: "kern", open_punten: [], revisie: 0,
          opnieuw_bekijken: false, klaar: false, kandidaten: [], bronnen: [{ selectie_id: "s1", bron_iri: "urn:lid1", label: "art. 9 lid 1 Iw", rol: "analyseren" }],
          telling: { voorgesteld: 0, niet_gekozen: 0, uitgesloten: 0, opgenomen: 1 }, beoordelen: { mag: false, redenen: [] } }] } });
    if (p === "/api/werkgebieden/wg1/deelvragen/d1") return route.fulfill({ json: { ...dv, opvolgers: [], voorstellen: [] } });
    if (p === "/api/werkgebieden/wg1/kandidaten") return route.fulfill({ json: { kandidaten: [], run: null } });
    if (p === "/api/werkgebieden/wg1/bronnen-runs/laatste") return route.fulfill({ json: { run: null } });
    if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run } });
    if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: { run, groepen: [], passages: {} } });
    if (p === "/api/werkgebieden/wg1/begrippen" && m === "GET")
      return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", begrippen: [termijn], primair: {} } });
    if (p === "/api/werkgebieden/wg1/begrippen/b9") return route.fulfill({ json: termijn });
    if (p === "/api/werkgebieden/wg1/begrippen/b9/voorstellen") return route.fulfill({ json: { voorstellen: [], runs: {}, schatting: {}, budget: null } });
    if (p === "/api/werkgebieden/wg1/relaties") return route.fulfill({ json: { relaties: [], voorstellen: [] } });
    if (p === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", titel: "Test", werkgebied_id: "wg1", berichten } });
    if (p === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Test", aantal_berichten: berichten.length, werkgebied_id: "wg1" }] });
    if (p === "/api/werkgebieden") return route.fulfill({ json: [wg1] });
    if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (p.endsWith("/capabilities")) return route.fulfill({ json: { samenhang: metGraaf } });
    if (p.endsWith("/annotatie/v2/samenhang") || p.endsWith("/annotatie/v2/samenhang/antwoord"))
      return route.fulfill({ json: { doel: "urn:lid1", knopen: [{ id: "urn:lid1", soort: "lid", label: "Lid 1", tekst: "", klasse: "",
        lifecycle: "", element_id: "", bwb_id: "BWBR0004770", artikel: "9", lid: "1", rand: false }], relaties: [] } });
    return route.fulfill({ json: [] });
  });
}

/** Meet de kop: rijen, plek van het gereedschap, scroll. */
async function meetKop(page, naam) {
  const kop = page.locator("[data-paneel-kop]").last();
  await kop.waitFor();
  const r = await kop.evaluate((el) => {
    const doos = (x) => { const b = x.getBoundingClientRect(); return { x: b.x, y: b.y, r: b.right, b: b.bottom, h: b.height, w: b.width }; };
    const binnen = el.querySelector('[data-tour="artefact-acties"]');
    const knoppen = [...binnen.querySelectorAll("button, a")].filter((k) => k.getBoundingClientRect().width > 0);
    const midden = [...new Set(knoppen.map((k) => { const b = k.getBoundingClientRect(); return Math.round((b.top + b.bottom) / 2); }))];
    const rijen = midden.sort((a, b) => a - b).reduce((acc, y) => (acc.length && y - acc[acc.length - 1] < 12 ? acc : [...acc, y]), []);
    const sluit = el.querySelector('[data-kop-gereedschap] button[aria-label="Sluiten"]');
    const gereedschap = [...el.querySelectorAll("[data-kop-gereedschap] > *")].map(doos);
    const stand = el.querySelector('[data-kop-rij="stand"]');
    return {
      rijen: rijen.length, kop: doos(binnen), gereedschap, sluit: sluit && doos(sluit),
      stand: stand && { links: doos(stand.firstElementChild), rechts: stand.children[1] && doos(stand.children[1]) },
      scroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
  assert.ok(r.scroll <= 0, `${naam}: horizontale scroll (${r.scroll}px)`);
  assert.ok(r.rijen <= 2, `${naam}: de kop heeft ${r.rijen} rijen knoppen`);
  if (r.sluit) {
    const rechts = Math.max(...r.gereedschap.map((g) => g.r));
    assert.ok(Math.abs(rechts - r.sluit.r) < 1, `${naam}: ✕ staat het meest rechts`);
    const mid = (g) => g.y + g.h / 2;
    for (const g of r.gereedschap) assert.ok(Math.abs(mid(g) - mid(r.sluit)) <= 2, `${naam}: ↗ ⋯ ✕ op één hoogte`);
    assert.ok(r.sluit.r <= r.kop.r + 1, `${naam}: het gereedschap blijft binnen de kop`);
  }
  if (r.stand?.rechts) {
    assert.ok(r.stand.links.x < r.stand.rechts.x, `${naam}: de status links, de hoofdactie rechts`);
    assert.ok(Math.abs((r.stand.links.y + r.stand.links.h / 2) - (r.stand.rechts.y + r.stand.rechts.h / 2)) <= 3, `${naam}: status en hoofdactie op één rij`);
    assert.ok(Math.abs(r.stand.rechts.r - r.sluit.r) <= 6, `${naam}: de hoofdactie lijnt rechts uit met ✕`);
  }
  return r;
}

/** De laatste regel van het menu ⋯ is Verwijderen. */
async function laatsteMenuregel(page) {
  await page.locator("[data-paneel-kop]").last().locator("[data-meer-knop]").click();
  const menu = page.locator("[data-meer-menu]").last();
  await menu.waitFor();
  const regels = await menu.getByRole("menuitem").allTextContents();
  await page.keyboard.press("Escape");
  await menu.waitFor({ state: "detached" });
  return regels.at(-1) ?? "";
}

const PANELEN = [
  { naam: "annotatie", open: (p) => p.locator("button", { hasText: "Invorderingswet – artikel 9 lid 1" }).first().click(), verwijder: true, stand: true },
  { naam: "begripsvoorstellen", open: (p) => p.locator('button[data-artefact-soort="begrippen"]').click() },
  { naam: "werkgebied", open: (p) => p.locator('button[data-artefact-soort="werkgebied"]').click(), verwijder: true, stand: true },
  { naam: "begrip", open: (p) => p.locator('button[data-artefact-soort="begrip"]').click(), verwijder: true, stand: true },
  { naam: "deelvraag", open: (p) => p.locator('button[data-artefact-soort="deelvraag"]').click() },
  { naam: "Bronnen", open: (p) => p.locator("[data-chatkop-bronnen]").first().click() },
];

const fouten = [];
for (const breedte of [375, 400, 800, 1280]) {
  const page = await browser.newPage({ viewport: { width: breedte, height: 900 } });
  page.on("pageerror", (e) => fouten.push(`${breedte}: ${e.message}`));
  await mock(page, true);
  for (const paneel of PANELEN) {
    await page.goto(`${base}/workbench?gesprek=g1`);
    if (paneel.naam === "Bronnen" && breedte < 1024) {
      // Onder lg staat de chatkop niet; Bronnen zit dan in de topbar of niet. Overslaan.
      if (await page.locator("[data-chatkop-bronnen]").first().isHidden()) continue;
    }
    await paneel.open(page);
    const naam = `${paneel.naam} @${breedte}`;
    const r = await meetKop(page, naam);
    if (paneel.stand) {
      assert.ok(r.stand, `${naam}: de status staat in de kop`);
      const label = (await page.locator('[data-paneel-kop] [data-kop-rij="stand"]').last().textContent()).trim();
      assert.match(label, /^[A-Z]/, `${naam}: het statuslabel is niet leeg ("${label}")`);
    }
    if (paneel.verwijder) assert.match(await laatsteMenuregel(page), /Verwijderen/, `${naam}: Verwijderen onderaan in ⋯`);
    // Met SCHERMAFDRUK=<map> bewaart het script de kop per paneel en breedte, als bewijs bij een PR.
    if (process.env.SCHERMAFDRUK)
      await page.locator("[data-paneel-kop]").last().screenshot({ path: `${process.env.SCHERMAFDRUK}/kop-${paneel.naam}-${breedte}.png` });
    if (paneel.naam === "annotatie") {
      // Op de tab Graaf dezelfde kop: status en afronden springen niet weg.
      await page.getByRole("button", { name: "Graaf", exact: true }).click();
      const g = await meetKop(page, `${naam} (graaf)`);
      assert.ok(g.stand?.rechts, `${naam}: de tab Graaf houdt status en afronden`);
      await page.getByRole("button", { name: "Tekst", exact: true }).click();
    }
  }
  // De annotatiepagina gebruikt dezelfde kop.
  await page.goto(`${base}/annotaties/node?bron_iri=urn:lid1`);
  await meetKop(page, `annotatiepagina @${breedte}`);
  await page.close();
}

// Een aanraakscherm: elke knop in de kop minstens 44 × 44 px.
{
  const ctx = await browser.newContext({ viewport: { width: 400, height: 900 }, hasTouch: true, isMobile: true });
  const page = await ctx.newPage();
  await mock(page, false);
  await page.emulateMedia({ media: "screen" });
  await page.goto(`${base}/workbench?gesprek=g1`);
  assert.ok(await page.evaluate(() => matchMedia("(pointer: coarse)").matches), "de emulatie geeft pointer: coarse");
  for (const paneel of PANELEN.filter((x) => x.naam !== "Bronnen")) {
    await page.goto(`${base}/workbench?gesprek=g1`);
    await paneel.open(page);
    const kop = page.locator('[data-paneel-kop] [data-tour="artefact-acties"]').last();
    await kop.waitFor();
    const klein = await kop.evaluate((el) => [...el.querySelectorAll("button, a")]
      .map((k) => ({ t: k.getAttribute("aria-label") || k.textContent, b: k.getBoundingClientRect() }))
      .filter(({ b }) => b.width > 0 && (b.width < 43.5 || b.height < 43.5)).map(({ t, b }) => `${t} ${Math.round(b.width)}×${Math.round(b.height)}`));
    assert.deepEqual(klein, [], `${paneel.naam}: raakvlakken onder 44 px`);
  }
  await ctx.close();
}

assert.deepEqual(fouten, []);
await browser.close();
console.log("Browser OK: één paneelkop voor annotatie (Tekst en Graaf), begripsvoorstellen, werkgebied, begrip, deelvraag, Bronnen en de annotatiepagina op 375, 400, 800 en 1280 px; geen horizontale scroll, hoogstens twee rijen, ↗ ⋯ ✕ rechtsboven, Verwijderen onderaan in ⋯, 44 px op touch.");
