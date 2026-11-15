/** Browserregressie voor Instellingen › Aanpassingen › Methodes en Agents (plan instellingen-aanpassingen) op de echte
 * Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-aanpassingen.mjs`.
 *
 * Toetst:
 * - de werkwijze is weg: geen sidebaritem, en `/werkwijze` en elke oude link eronder komen in het venster uit, in de tab
 *   waar het onderdeel nu staat (ketens, routes en controles openen Agents zonder onderdeel);
 * - een analist ziet Methodes en Agents onder Aanpassingen, als lijst met een zoekveld (zonder werkplaats geen segmenten);
 * - Agents: per profiel wat het doet en hoeveel connectors en sjablonen; het tweede niveau met wat het gebruikt, de
 *   opdracht (ingeklapt) en de herkomst, en *‹ Agents* terug; een methode in het detail opent Methodes;
 * - Methodes: per methode haar rollen; het tweede niveau met de rollen en hun methodetekst; een oude link naar een rol
 *   opent de methode met die rol open;
 * - de stand (tab, onderdeel, zoekterm) staat in de URL en overleeft herladen; een tabwissel laat hem vallen;
 * - op 375 px scrolt geen scherm zijwaarts, en de schermen zijn toegankelijk (axe).
 *
 * `CATALOGUS_FIXTURE=<pad>` laat de echte catalogus zien (een dump van `agent.catalogus`: `{ lijst, detail }`), en
 * `AANPASSINGEN_SCREENSHOT=<map>` bewaart een beeld van elk scherm, op 1280 en 375 px.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { chromium } from "playwright";
import { toetsToegankelijkheid } from "./axe.mjs";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const SHOTS = process.env.AANPASSINGEN_SCREENSHOT;

const herkomst = { bron: "eigen werk van dit platform", licentie: "repo", letterlijk: false, verwijzing: [] };
const o = (id, extra = {}) => ({
  id, soort: id.split("/")[0], label: id.split("/")[1], doel: `Doel van ${id}.`, model: "geen", versie: "abc123def456",
  herkomst, bestand: [], ingang: [], context: "", tools: [], uitvoer: "", twijfel: "", tests: [], hangt_af_van: [],
  straat: null, bewerkbaar: [], laag: null, stappen: [], aan: true, concept: "skill", deel_van: null, ...extra,
});
const INLINE = [
  o("methode/wetsanalyse", { label: "Wetsanalyse", doel: "De methode Wetsanalyse met het Juridisch Analyseschema." }),
  o("methode/wetsuitvoering", { label: "Wetsuitvoering", doel: "Het Juridisch Referentiemodel." }),
  o("rol/duiding", { deel_van: "methode/wetsanalyse", ingang: ["antwoord", "duiding"] }),
  o("rol/supervisor", { deel_van: "methode/wetsanalyse", ingang: ["supervisor"] }),
  o("agentprofiel/definitie", { label: "Definitie", model: "agent", concept: "agent", doel: "Wat een begrip in de wet betekent.",
    uitvoer: "antwoord_begrip", hangt_af_van: ["rol/duiding", "methode/wetsanalyse", "sjabloon/antwoord_begrip",
      "connector/kamerstukken", "connector/rechtspraak", "tool/get_artikel"] }),
  o("agentprofiel/centraal_breed_met_een_heel_lange_naam_die_moet_afbreken", { label: "Centraal breed met een heel lange naam die moet afbreken",
    model: "agent", concept: "agent", straat: "CENTRALE_AGENT", aan: false }),
  o("connector/kamerstukken", { label: "Kamerstukken", concept: "tool" }),
  o("connector/rechtspraak", { label: "Rechtspraak", concept: "tool" }),
  o("sjabloon/antwoord_begrip", { label: "Begrip", concept: "tool" }),
  o("workflow/annotatieketen", { label: "Annotatieketen", concept: "workflow" }),
];
const fixture = process.env.CATALOGUS_FIXTURE ? JSON.parse(readFileSync(process.env.CATALOGUS_FIXTURE, "utf8")) : null;
const LIJST = fixture?.lijst ?? { soorten: [], onderdelen: INLINE };
const detail = (id) => fixture?.detail?.[id] ?? {
  ...INLINE.find((x) => x.id === id), gebruikt_door: [],
  inhoud: id === "agentprofiel/definitie" ? { systeemtekst: "AFRONDEN: haal eerst de definitie op." }
    : id === "rol/duiding" ? { secties: [{ id: "duiding", skill: "wetsanalyse", bronnen: ["M01"], tekst: "De methodetekst van duiding." }] }
      : id.startsWith("methode/") ? { rollen: { duiding: ["duiding"] } } : {},
};

const zonderOverloop = async (page, naam) => assert.ok(await page.evaluate(() =>
  document.documentElement.scrollWidth <= document.documentElement.clientWidth), `${naam} scrolt zijwaarts`);

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
try {
  for (const breedte of [1280, 375]) {
    const context = await browser.newContext({ viewport: { width: breedte, height: 860 } });
    await context.addCookies(await sessieCookies(base, { role: "analist" }));
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
    await page.route("**/api/**", (route) => {
      const p = new URL(route.request().url()).pathname;
      if (p.startsWith("/api/auth/")) return route.continue();
      if (p === "/api/catalogus") return route.fulfill({ json: LIJST });
      const m = p.match(/^\/api\/catalogus\/([a-z]+)\/(.+)$/);
      if (m) {
        const d = detail(`${m[1]}/${decodeURIComponent(m[2])}`);
        return d?.id ? route.fulfill({ json: d }) : route.fulfill({ status: 404, json: { detail: "Onbekend onderdeel" } });
      }
      if (p === "/api/werkplaats/stand") return route.fulfill({ json: { aan: false } });
      if (p === "/api/gesprekken") return route.fulfill({ json: [] });
      return route.fulfill({ json: {} });
    });
    const shot = async (naam) => SHOTS && page.screenshot({ path: `${SHOTS}/aanpassingen-${naam}-${breedte}.png`, fullPage: true });
    const venster = page.getByRole("dialog", { name: "Instellingen" });

    // De werkwijze is weg: `/werkwijze` opent Agents in het venster, en de sidebar noemt haar niet.
    await page.goto(`${base}/werkwijze`);
    await page.waitForURL(/\/workbench\?instellingen=agents$/);
    const agents = venster.locator('[data-aanpassing-lijst="agents"]');
    await agents.locator('[data-onderdeel="agentprofiel/definitie"]').waitFor();
    assert.equal(await page.getByRole("link", { name: "Werkwijze" }).count(), 0, "geen sidebaritem Werkwijze");
    // Zonder werkplaats geen segmenten en geen *Voeg toe*; een analist ziet Methodes en Agents, geen Modellen.
    assert.equal(await agents.locator("[data-overzichtbalk]").getByText("Concepten").count(), 0);
    assert.equal(await page.locator('[data-actie="voeg-toe"]').count(), 0);
    assert.equal(await page.getByRole("tab", { name: "Modellen", includeHidden: true }).count(), 0);
    assert.match(await agents.locator('[data-onderdeel="agentprofiel/definitie"]').innerText(),
      /Definitie[\s\S]*Wat een begrip in de wet betekent\.[\s\S]*2 connectors · 1 sjabloon/);
    assert.match(await agents.locator('[data-onderdeel^="agentprofiel/centraal_breed"]').innerText(), /hier uit/);
    await zonderOverloop(page, "Agents");
    await toetsToegankelijkheid(page, `aanpassingen – agents ${breedte}`);
    await shot("agents");

    // Zoeken filtert, en de zoekterm staat in de URL.
    await venster.getByLabel("Zoeken in de agents").fill("begrip");
    await page.waitForURL(/q=begrip/);
    assert.equal(await agents.locator("[data-onderdeel]").count(), 1);
    await venster.getByLabel("Zoeken in de agents").fill("");
    await page.waitForFunction(() => !location.search.includes("q="));

    // Het tweede niveau: wat het gebruikt, de opdracht ingeklapt, de herkomst; herladen houdt het open.
    await agents.getByRole("button", { name: "Open Definitie" }).click();
    await page.waitForURL(/onderdeel=agentprofiel%2Fdefinitie/);
    const detailblok = venster.locator("[data-aanpassing-detail]");
    await detailblok.locator('[data-blok="gebruikt"]').waitFor();
    assert.match(await detailblok.locator('[data-blok="gebruikt"]').innerText(),
      /Methode[\s\S]*Wetsanalyse[\s\S]*rol duiding[\s\S]*Connectors[\s\S]*Kamerstukken, Rechtspraak[\s\S]*Sjablonen[\s\S]*Begrip/);
    assert.doesNotMatch(await detailblok.innerText(), /AFRONDEN/, "de opdracht staat ingeklapt");
    await detailblok.locator('[data-blok="opdracht"]').getByRole("button", { name: "Lezen" }).click();
    await detailblok.getByText("AFRONDEN: haal eerst de definitie op.").waitFor();
    await zonderOverloop(page, "een agent");
    await toetsToegankelijkheid(page, `aanpassingen – agent ${breedte}`);
    await shot("agent");
    await page.reload();
    await detailblok.locator('[data-blok="gebruikt"]').waitFor();
    // De methode in het detail opent haar eigen tab, met de rol open.
    await detailblok.getByRole("button", { name: "duiding" }).click();
    await page.waitForURL(/instellingen=methodes&onderdeel=rol%2Fduiding/);
    await detailblok.getByText("De methodetekst van duiding.").waitFor();
    assert.equal(await detailblok.locator("h3").first().innerText(), "Wetsanalyse");
    // Terug naar de lijst van Methodes.
    await detailblok.getByRole("button", { name: "Methodes" }).click();
    const methodes = venster.locator('[data-aanpassing-lijst="methodes"]');
    await methodes.locator('[data-onderdeel="methode/wetsanalyse"]').waitFor();
    assert.match(await methodes.locator('[data-onderdeel="methode/wetsanalyse"]').innerText(), /2 rollen/);
    assert.match(await methodes.locator('[data-onderdeel="methode/wetsuitvoering"]').innerText(), /nog aan geen rol gekoppeld/);
    await zonderOverloop(page, "Methodes");
    await toetsToegankelijkheid(page, `aanpassingen – methodes ${breedte}`);
    await shot("methodes");

    // Een methode: haar rollen, de methodetekst pas als je hem opent.
    await methodes.getByRole("button", { name: "Open Wetsanalyse" }).click();
    await detailblok.locator('[data-blok="rollen"]').waitFor();
    assert.match(await detailblok.locator('[data-blok="rollen"]').innerText(), /duiding[\s\S]*voor antwoord, duiding[\s\S]*supervisor/);
    await detailblok.locator('[data-rol="duiding"]').getByRole("button", { name: "Methodetekst" }).click();
    await detailblok.getByText("De methodetekst van duiding.").waitFor();
    await shot("methode");

    // Oude links per soort: de tab waar het nu staat.
    for (const [pad, verwacht] of [
      ["/werkwijze/methode/wetsuitvoering", /instellingen=methodes&onderdeel=methode%2Fwetsuitvoering$/],
      ["/werkwijze/agentprofiel/definitie", /instellingen=agents&onderdeel=agentprofiel%2Fdefinitie$/],
      ["/werkwijze/workflow/annotatieketen", /instellingen=agents$/],
      ["/werkwijze/regelset/jas.detector.tijd", /instellingen=agents$/],
    ]) {
      await page.goto(`${base}${pad}`);
      await page.waitForURL(verwacht);
    }
    await venster.locator('[data-aanpassing-lijst="agents"]').waitFor();

    // Een tabwissel laat de stand van de lijst vallen.
    await page.goto(`${base}/workbench?instellingen=agents&onderdeel=agentprofiel%2Fdefinitie&q=x`);
    await detailblok.waitFor();
    const naarLijst = page.getByRole("button", { name: "Alle instellingen" });
    if (await naarLijst.isVisible()) await naarLijst.click();
    await page.getByRole("tab", { name: "Methodes" }).click();
    await page.waitForURL(/\/workbench\?instellingen=methodes$/);

    assert.deepEqual(errors, []);
    await context.close();
  }
  console.log("OK test-aanpassingen");
} finally {
  await browser.close();
}
