/** Browserregressie voor de werkplaats (ADR-016 deel B, stap B2-1) op de echte Next-UI met een gemockte BFF. Start
 * Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-werkplaats.mjs`.
 *
 * Toetst:
 * - met de werkplaats uit: geen groep *Concepten*, geen *Bewerken*, geen aanroep van de concepten, en de pagina van
 *   een concept zegt dat de werkplaats niet aanstaat;
 * - met de werkplaats aan: de groep met de eigen en gedeelde concepten en hun stand (ook "nog onbekend wat er
 *   draait"), *Nieuw concept* (een ongeldige naam, dan aanmaken en openen), de pagina van een concept (bestanden,
 *   het gekozen bestand in de URL, de bevindingen van de controle), *Bewerken* op een methode (`uit_image`), *Open
 *   mijn concept* als ik er al een heb, en de melding als Lex nog niet weet wat er draait;
 * - op 375 px scrolt geen van die schermen zijwaarts.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
// `WERKPLAATS_SCREENSHOT=<map>` bewaart een beeld van het overzicht en van een concept, op 1280 en 375 px.
const SHOTS = process.env.WERKPLAATS_SCREENSHOT;

const herkomst = { bron: "eigen werk van dit platform", licentie: "repo", letterlijk: false, verwijzing: [] };
const o = (id, extra = {}) => ({
  id, soort: id.split("/")[0], label: id.split("/")[1], doel: `Doel van ${id}.`, model: "geen", versie: "abc123def456",
  herkomst, bestand: [".claude/skills/x/SKILL.md"], ingang: [], context: "", tools: [], uitvoer: "", twijfel: "",
  tests: [], hangt_af_van: [], straat: null, bewerkbaar: [], laag: null, stappen: [], aan: true, concept: "skill",
  deel_van: null, ...extra,
});
const CATALOGUS = [o("methode/wetsanalyse", { label: "Wetsanalyse" }), o("methode/wetsuitvoering", { label: "Wetsuitvoering" }),
  o("rol/duiding"), o("workflow/annotatieketen", { concept: "workflow" })];

const versie = (nummer, extra = {}) => ({
  id: `v${nummer}`, nummer, hash: String(nummer).repeat(64).slice(0, 64), basis_hash: "", toelichting: "", geldig: true,
  bevindingen: [], door: "browser-test", gemaakt: "2026-11-13T10:00:00+00:00", actief: false, ...extra,
});
const concept = (id, naam, extra = {}) => ({
  id, soort: "skill", naam, eigenaar: "browser-test", gedeeld: false, stand: "concept", in_image: false, actief_versie: null,
  basis_verouderd: false, image_bekend: true, versies: 1, laatste: versie(1), zelfde_naam: 0, gemaakt: "", bijgewerkt: "",
  ingetrokken_op: "", ingetrokken_door: "", ...extra,
});
const BEVINDING = { code: "beschrijving", melding: "description: beschrijf wat de skill doet en wanneer Lex hem gebruikt", bestand: "SKILL.md" };
const BESTANDEN = {
  "references/een-heel-lange-bestandsnaam-die-op-een-telefoon-moet-afbreken-zonder-overloop.md": "# Uitwerking\n\nTekst van de uitwerking.",
  "SKILL.md": "---\nname: jrm-proef\n---\n\n# jrm-proef\n" + "Een lange regel zonder afbreekpunt: " + "x".repeat(300),
  "agentrollen.json": '{"secties": {}, "rollen": {}}',
};
const STAND = { aan: true, soorten: [], mag_maken: true, beheerder: false, beleid: { analist_mag_maken: true },
  image: { bekend: true, pakket_hash: "p", revisie: "abc1234", gemeld_op: "2026-11-13T09:00:00+00:00", onderdelen: 10 },
  grenzen: { bestanden: 60, tekens_per_bestand: 100000, tekens: 400000, versies: 200, onderdelen: 50 } };

async function open(browser, breedte, { stand, concepten, maak }) {
  const page = await browser.newPage({ viewport: { width: breedte, height: 900 } });
  const gezien = { errors: [], paden: [], gemaakt: [] };
  page.on("pageerror", (e) => gezien.errors.push(e.message));
  await page.context().addCookies(await sessieCookies(base));
  await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const p = new URL(req.url()).pathname;
    if (p.startsWith("/api/auth/")) return route.continue();
    if (p.startsWith("/api/werkplaats/")) gezien.paden.push(`${req.method()} ${p}`);
    if (p === "/api/catalogus") return route.fulfill({ json: { soorten: [], onderdelen: CATALOGUS } });
    const m = p.match(/^\/api\/catalogus\/([a-z]+)\/(.+)$/);
    if (m) {
      const d = CATALOGUS.find((x) => x.id === `${m[1]}/${m[2]}`);
      return d ? route.fulfill({ json: { ...d, inhoud: {}, gebruikt_door: [] } }) : route.fulfill({ status: 404, json: { detail: "Onbekend onderdeel" } });
    }
    if (p === "/api/gesprekken") return route.fulfill({ json: [] });
    if (p === "/api/werkplaats/stand") return route.fulfill({ json: stand });
    // Met de werkplaats uit bestaan de andere routes niet.
    if (p.startsWith("/api/werkplaats/") && !stand.aan) return route.fulfill({ status: 404, json: { detail: "De werkplaats staat op deze omgeving niet aan." } });
    if (p === "/api/werkplaats/onderdelen" && req.method() === "POST") {
      const body = req.postDataJSON();
      gezien.gemaakt.push(body);
      const uit = maak(body);
      return route.fulfill(uit.status ? uit : { status: 201, json: uit });
    }
    if (p === "/api/werkplaats/onderdelen") return route.fulfill({ json: concepten });
    const c = p.match(/^\/api\/werkplaats\/onderdelen\/([^/]+)(?:\/versies\/(\d+))?$/);
    if (c) {
      const gevonden = [...concepten, concept("nieuw-1", "jrm-scenario"), concept("uit-image-1", "wetsuitvoering", { stand: "actief", actief_versie: 1, in_image: true })]
        .find((x) => x.id === decodeURIComponent(c[1]));
      if (!gevonden) return route.fulfill({ status: 404, json: { detail: { melding: "Onbekend onderdeel." } } });
      if (c[2]) return route.fulfill({ json: { ...gevonden.laatste, bestanden: BESTANDEN } });
      return route.fulfill({ json: { ...gevonden, versielijst: [gevonden.laatste] } });
    }
    return route.fulfill({ json: {} });
  });
  return { page, gezien };
}

const zonderOverloop = async (page, naam) => assert.ok(await page.evaluate(() =>
  document.documentElement.scrollWidth <= document.documentElement.clientWidth), `${naam} scrolt zijwaarts`);

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
try {
  // --- De werkplaats staat uit: er is niets te zien en niets wordt gevraagd -----------------------------------------
  for (const stand of [{ aan: false }, {}]) {
    const { page, gezien } = await open(browser, 1280, { stand, concepten: [], maak: () => ({}) });
    await page.goto(`${base}/werkwijze`);
    await page.getByTestId("werkwijze").waitFor();
    await page.waitForLoadState("networkidle");
    assert.equal(await page.locator("[data-concepten]").count(), 0);
    assert.equal(await page.getByRole("button", { name: "Nieuw concept" }).count(), 0);
    await page.goto(`${base}/werkwijze/methode/wetsanalyse`);
    await page.locator("[data-paginakop]").waitFor();
    await page.waitForLoadState("networkidle");
    assert.equal(await page.locator('[data-actie="concept-bewerken"], [data-actie="concept-openen"]').count(), 0);
    // De kop van de pagina houdt geen lege ruimte over voor een knop die er niet is.
    assert.equal(await page.locator("[data-paginakop] > div > div").evaluateAll((els) => els.filter((e) => e.getBoundingClientRect().height > 0).length), 1);
    await page.goto(`${base}/werkwijze/concepten/o1`);
    await page.locator('[data-werkplaats="uit"]').waitFor();
    assert.deepEqual([...new Set(gezien.paden)], ["GET /api/werkplaats/stand"]);
    assert.deepEqual(gezien.errors, []);
    await page.close();
  }

  // --- De werkplaats staat aan --------------------------------------------------------------------------------------
  const CONCEPTEN = [
    concept("o1", "jrm-proef", { laatste: versie(2, { geldig: false, bevindingen: [BEVINDING] }), versies: 2 }),
    concept("o2", "wetsanalyse", { eigenaar: "piet", gedeeld: true, stand: "actief", actief_versie: 1, in_image: true }),
    concept("o3", "achterloper", { basis_verouderd: true, in_image: true }),
    concept("o4", "onbekend", { image_bekend: false, in_image: null, basis_verouderd: null }),
    concept("o5", "weg", { stand: "ingetrokken" }),
    concept("o6", "een-profiel", { soort: "agentprofiel" }),
  ];
  for (const breedte of [1280, 375]) {
    const { page, gezien } = await open(browser, breedte, { stand: STAND, concepten: CONCEPTEN,
      maak: (body) => (body.uit_image ? concept("uit-image-1", body.naam) : concept("nieuw-1", body.naam)) });
    await page.goto(`${base}/werkwijze`);
    const groep = page.locator("[data-concepten]");
    await groep.waitFor();
    await page.locator('[data-concept-id="o1"]').waitFor();
    // De eigen concepten eerst, dan wat gedeeld is, ingetrokken onderaan; een profiel opent de editor nog niet.
    assert.deepEqual(await groep.locator("[data-concept-id]").evaluateAll((els) => els.map((e) => e.dataset.conceptId)),
      ["o3", "o1", "o4", "o2", "o5"]);
    assert.match(await page.locator('[data-concept-id="o1"]').innerText(), /Concept[\s\S]*1 bevinding/);
    assert.match(await page.locator('[data-concept-id="o2"]').innerText(), /van piet[\s\S]*Draait nu[\s\S]*Geldig/);
    assert.match(await page.locator('[data-concept-id="o3"]').innerText(), /loopt achter/);
    // Weet Lex niet wat er draait, dan zegt het label dat, en niet dat het concept niet draait.
    const onbekend = await page.locator('[data-concept-id="o4"]').innerText();
    assert.match(onbekend, /nog onbekend wat er draait/);
    assert.doesNotMatch(onbekend, /draait niet/i);
    assert.match(await page.locator('[data-concept-id="o5"]').innerText(), /Ingetrokken/);
    await zonderOverloop(page, "het overzicht");
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/werkplaats-overzicht-${breedte}.png`, fullPage: true });
    // De groep hoort bij kennis en methode: bij een ander concept staat ze er niet, en de zoekterm filtert op naam.
    await page.getByLabel("Zoeken in de werkwijze").fill("jrm");
    await page.waitForFunction(() => document.querySelectorAll("[data-concept-id]").length === 1);
    await page.getByLabel("Zoeken in de werkwijze").fill("");
    await page.waitForFunction(() => document.querySelectorAll("[data-concept-id]").length === 5);

    // Nieuw concept: een naam die de api zou weigeren, zegt het formulier al.
    await page.locator('[data-actie="concept-nieuw"]').click();
    const formulier = page.locator("[data-concept-nieuw]");
    await formulier.getByRole("textbox").fill("Geen_Naam");
    await formulier.getByText(/Alleen kleine letters/).waitFor();
    assert.ok(await page.locator('[data-actie="concept-maken"]').isDisabled());
    await zonderOverloop(page, "het formulier");
    await formulier.getByRole("textbox").fill("jrm-scenario");
    await page.locator('[data-actie="concept-maken"]').click();
    await page.waitForURL(/\/werkwijze\/concepten\/nieuw-1$/);
    assert.deepEqual(gezien.gemaakt, [{ soort: "skill", naam: "jrm-scenario" }]);

    // De pagina van een concept: de bestanden in een vaste volgorde, het gekozen bestand in de URL.
    await page.goto(`${base}/werkwijze/concepten/o1`);
    await page.locator('[data-blok="bestanden"]').waitFor();
    assert.match(await page.locator("[data-paginakop]").innerText(), /jrm-proef[\s\S]*Skill[\s\S]*1 bevinding[\s\S]*versie 2/);
    assert.deepEqual(await page.locator("[data-bestand]").evaluateAll((els) => els.map((e) => e.dataset.bestand)),
      ["SKILL.md", "agentrollen.json", Object.keys(BESTANDEN)[0]]);
    assert.equal(await page.locator("[data-bestand-inhoud]").getAttribute("data-bestand-inhoud"), "SKILL.md");
    assert.match(await page.locator('[data-bestand="SKILL.md"]').innerText(), /1/);
    assert.match(await page.locator('[data-blok="controle"]').innerText(), /haalt de controle niet[\s\S]*SKILL\.md[\s\S]*beschrijf wat de skill doet/);
    await zonderOverloop(page, "de pagina van een concept");
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/werkplaats-concept-${breedte}.png`, fullPage: true });
    await page.locator('[data-bestand="agentrollen.json"]').click();
    await page.waitForURL(/bestand=agentrollen\.json/);
    assert.match(await page.locator("[data-bestand-inhoud]").innerText(), /"secties"/);
    await page.reload();
    await page.locator('[data-bestand-inhoud="agentrollen.json"]').waitFor();
    await page.locator("[data-bestand]").last().click();
    await page.locator(`[data-bestand-inhoud="${Object.keys(BESTANDEN)[0]}"]`).waitFor();
    await zonderOverloop(page, "een bestand met een lange naam");
    // Een concept dat achterloopt, zegt dat ook op zijn pagina; een onbekend concept is een melding.
    await page.goto(`${base}/werkwijze/concepten/o3`);
    await page.locator('[data-melding="loopt-achter"]').waitFor();
    await page.goto(`${base}/werkwijze/concepten/bestaat-niet`);
    await page.getByText("Dit concept bestaat niet, of het is niet met je gedeeld.").waitFor();

    // Bewerken op een methode: een concept met de versie die draait. Niets op de pagina start Lex.
    gezien.gemaakt.length = 0;
    await page.goto(`${base}/werkwijze/methode/wetsuitvoering`);
    await page.locator('[data-actie="concept-bewerken"]').click();
    await page.waitForURL(/\/werkwijze\/concepten\/uit-image-1$/);
    assert.deepEqual(gezien.gemaakt, [{ soort: "skill", naam: "wetsuitvoering", uit_image: true }]);
    await page.locator('[data-blok="bestanden"]').waitFor();
    // Een methode waar ik al een concept van heb, opent dat. Het gedeelde concept van piet telt niet als het mijne.
    await page.goto(`${base}/werkwijze/methode/wetsanalyse`);
    await page.locator('[data-actie="concept-bewerken"]').waitFor();
    assert.equal(await page.locator('[data-actie="concept-openen"]').count(), 0);
    await zonderOverloop(page, "de pagina van een methode");
    // Een rol is geen skill: daar staat geen knop.
    await page.goto(`${base}/werkwijze/rol/duiding`);
    await page.locator("[data-paginakop]").waitFor();
    await page.waitForLoadState("networkidle");
    assert.equal(await page.locator('[data-actie="concept-bewerken"]').count(), 0);
    assert.ok(!gezien.paden.some((p) => /^(PUT|DELETE|PATCH)/.test(p)));
    assert.deepEqual(gezien.errors, []);
    await page.close();
  }

  // Ik heb al een concept van deze methode: de knop opent het.
  {
    const { page } = await open(browser, 1280, { stand: STAND, concepten: [concept("o7", "wetsanalyse")], maak: () => ({}) });
    await page.goto(`${base}/werkwijze/methode/wetsanalyse`);
    await page.locator('[data-actie="concept-openen"]').click();
    await page.waitForURL(/\/werkwijze\/concepten\/o7$/);
    await page.close();
  }
  // Lex weet nog niet wat er draait: Bewerken zegt dat, en er ontstaat geen concept. Wie niet mag maken, ziet geen knop.
  {
    const { page } = await open(browser, 1280, { stand: STAND, concepten: [], maak: () => ({ status: 409,
      json: { detail: { melding: "Lex weet nog niet wat er draait; probeer het zo opnieuw.", fout: "image_onbekend" } } }) });
    await page.goto(`${base}/werkwijze/methode/wetsanalyse`);
    await page.locator('[data-actie="concept-bewerken"]').click();
    await page.getByText("Lex weet nog niet wat er draait; probeer het zo opnieuw.").waitFor();
    assert.match(page.url(), /\/werkwijze\/methode\/wetsanalyse$/);
    await page.close();
  }
  {
    const { page } = await open(browser, 1280, { stand: { ...STAND, mag_maken: false }, concepten: [], maak: () => ({}) });
    await page.goto(`${base}/werkwijze/methode/wetsanalyse`);
    await page.locator("[data-paginakop]").waitFor();
    await page.waitForLoadState("networkidle");
    assert.equal(await page.locator('[data-actie="concept-bewerken"]').count(), 0);
    await page.goto(`${base}/werkwijze`);
    await page.getByTestId("werkwijze").waitFor();
    await page.waitForLoadState("networkidle");
    assert.equal(await page.locator("[data-concepten]").count(), 0);
    await page.close();
  }
  console.log("OK test-werkplaats");
} finally {
  await browser.close();
}
