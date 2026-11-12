/** Browserregressie voor de werkwijze van Lex (ADR-014) op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-werkwijze.mjs`.
 *
 * Toetst: het sidebar-item, de balk (een soortkeuze met tellers en het zoekveld, zonder *Door mij bewerkt*), de
 * groepen per soort met het modellabel, soort en zoekterm in de URL, de pagina van een workflow (stappen met hun
 * model, herkomst, repo) en van een regelset (regels met hun voorbeeldzinnen), en doorklikken via *Leunt op*.
 *
 * `WERKWIJZE_FIXTURE=<pad>` laat de pagina's de echte catalogus tonen (een dump van `agent.catalogus`), en
 * `WERKWIJZE_SCREENSHOT=<map>` bewaart een screenshot van elk scherm, op 1280 en 390 px.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const SHOTS = process.env.WERKWIJZE_SCREENSHOT;

const herkomst = { bron: "eigen werk van dit platform", licentie: "repo", letterlijk: false, verwijzing: [] };
const o = (id, extra = {}) => ({
  id, soort: id.split("/")[0], label: id.split("/")[1], doel: `Doel van ${id}.`, model: "geen", versie: "abc123def456",
  herkomst, bestand: ["tools/graph-qa/agent/x.py"], ingang: [], context: "", tools: [], uitvoer: "", twijfel: "",
  tests: ["tools/graph-qa/tests/test_x.py"], hangt_af_van: [], straat: null, bewerkbaar: [], laag: null, stappen: [],
  aan: true, concept: "skill", deel_van: null, ...extra,
});
const INLINE = [
  o("rol/duiding", { concept: "skill", bewerkbaar: ["duiding"] }),
  o("workflow/annotatieketen", { label: "Annotatieketen (ADR-001)", laag: "taakagent", model: "strict", concept: "workflow",
    hangt_af_van: ["regelset/jas.detector.tijd"],
    stappen: [{ naam: "Detectie", model: "geen", onderdeel: null }, { naam: "Classificatie", model: "strict", onderdeel: null }] }),
  o("workflow/bronnen_vinden", { label: "Bronnen vinden", laag: "workflow", concept: "workflow" }),
  o("connector/kamerstukken", { label: "Kamerstukken", straat: "CONNECTOR_KAMERSTUKKEN", aan: false, concept: "tool" }),
  o("regelset/jas.detector.tijd", { label: "jas.detector.tijd", doel: "Tijdsaanduiding (H2:107-109)." }),
];
const fixture = process.env.WERKWIJZE_FIXTURE ? JSON.parse(readFileSync(process.env.WERKWIJZE_FIXTURE, "utf8")) : null;
const LIJST = fixture?.lijst ?? { soorten: ["methode", "rol", "regelset", "tool", "connector", "sjabloon", "workflow",
  "specialist", "agent", "route", "controle"], onderdelen: INLINE };
const detail = (id) => fixture?.detail?.[id] ?? { ...INLINE.find((x) => x.id === id),
  inhoud: id === "rol/duiding" ? { secties: [{ id: "duiding", skill: "wetsanalyse", bestand: ".claude/skills/wetsanalyse/references/agentrollen.md",
    bronnen: ["M01"], sha256: "x", tekst: "Oude methodetekst." }] } : id.startsWith("regelset/") ? { regels: [{ id: "jas.tijd.datum", code: "TEMPORAL_DATE", klassen: ["Tijdsaanduiding"],
    bron: "H2:109", versie: 2, voorbeelden: { positief: ["Deze wet treedt in werking op 1 september 2009."], negatief: ["Zie Stb. 2009, 1."] } }] } : {},
  gebruikt_door: id === "regelset/jas.detector.tijd" ? ["workflow/annotatieketen"] : [] };

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
try {
  for (const breedte of SHOTS ? [1280, 390] : [1280]) {
    const page = await browser.newPage({ viewport: { width: breedte, height: 900 } });
    const errors = [];
    const voorstellen = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.context().addCookies(await sessieCookies(base));
    await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
    await page.route("**/api/**", async (route) => {
      const p = new URL(route.request().url()).pathname;
      if (p.startsWith("/api/auth/")) return route.continue();
      if (p === "/api/catalogus") return route.fulfill({ json: LIJST });
      const m = p.match(/^\/api\/catalogus\/([a-z]+)\/(.+)$/);
      if (m) {
        const d = detail(`${m[1]}/${decodeURIComponent(m[2])}`);
        return d?.id ? route.fulfill({ json: d }) : route.fulfill({ status: 404, json: { detail: "Onbekend onderdeel" } });
      }
      if (p === "/api/gesprekken") return route.fulfill({ json: [] });
      // Voorstellen voor de methode (ADR-014 C7): aan, en een concept-PR als antwoord.
      if (p === "/api/admin/catalogus/voorstellen/stand") return route.fulfill({ json: { aan: true, reden: "" } });
      if (p === "/api/admin/catalogus/voorstellen") {
        voorstellen.push(route.request().postDataJSON());
        return route.fulfill({ status: 201, json: { pr_url: "https://example.test/pull/7", branch: "claude/x", pr_nummer: 7 } });
      }
      return route.fulfill({ json: {} });
    });
    const shot = async (naam) => SHOTS && page.screenshot({ path: `${SHOTS}/werkwijze-${naam}-${breedte}.png`, fullPage: true });

    // Het sidebar-item opent de werkwijze (op een telefoon via de drawer: dat toetst sidebar.test.ts al).
    await page.goto(`${base}/workbench`);
    if (breedte >= 1024) {
      // Wachten tot de werkplek gehydrateerd is: een klik daarvóór gaat verloren.
      await page.getByRole("link", { name: "Werkwijze" }).waitFor();
      await page.waitForLoadState("networkidle");
      await page.getByRole("link", { name: "Werkwijze" }).click();
      await page.waitForURL(/\/werkwijze$/, { waitUntil: "commit" });
    } else {
      await page.goto(`${base}/werkwijze`);
    }
    const lijst = page.getByTestId("werkwijze");
    await lijst.waitFor();
    await shot("lijst");

    if (!fixture) {
      // Geen *Door mij bewerkt*: in de catalogus bewerkt niemand iets.
      assert.equal(await page.getByRole("checkbox", { name: "Door mij bewerkt" }).count(), 0);
      // Een groep per concept met onderdelen, in de vaste volgorde; een concept zonder onderdelen staat er niet. Binnen
      // een concept staat bij elke rij zijn soort.
      assert.deepEqual(await page.locator("[data-concept]").evaluateAll((els) => els.map((e) => e.dataset.concept)),
        ["skill", "workflow", "tool"]);
      assert.equal(await page.getByRole("button", { name: /^Ingangen/ }).count(), 0);
      assert.match(await page.locator('[data-onderdeel="regelset/jas.detector.tijd"] [data-soort]').innerText(), /Regelset/);
      // Het modellabel, en *hier uit* bij een connector die deze omgeving niet aanbiedt.
      const keten = page.locator('[data-onderdeel="workflow/annotatieketen"]');
      assert.equal(await keten.locator("[data-model]").getAttribute("data-model"), "strict");
      assert.match(await page.locator('[data-onderdeel="connector/kamerstukken"]').innerText(), /hier uit/);

      // Soort en zoekterm in de URL, en na herladen nog zo.
      await page.getByRole("button", { name: /^Vaste ketens/ }).click();
      await page.waitForURL(/concept=workflow/);
      assert.equal(await page.locator("[data-onderdeel]").count(), 2);
      await page.getByLabel("Zoeken in de werkwijze").fill("bronnen");
      await page.waitForURL(/q=bronnen/);
      await page.waitForFunction(() => document.querySelectorAll("[data-onderdeel]").length === 1);
      await page.reload();
      await lijst.waitFor();
      assert.equal(await page.locator("[data-onderdeel]").count(), 1);
      assert.equal(await page.getByLabel("Zoeken in de werkwijze").inputValue(), "bronnen");
      await page.goto(`${base}/werkwijze`);
      await lijst.waitFor();
    }

    // De pagina van een workflow: de stappen met hun model, de herkomst en de repo.
    await page.locator('[data-onderdeel="workflow/annotatieketen"] a').click();
    await page.waitForURL(/\/werkwijze\/workflow\/annotatieketen$/);
    await page.locator('[data-blok="stappen"]').waitFor();
    assert.ok(await page.locator("[data-stap]").count() >= 2);
    assert.match(await page.locator('[data-stap="Classificatie"]').innerText(), /Model in één stap/);
    assert.match(await page.locator('[data-blok="herkomst"]').innerText(), /Licentie/);
    assert.match(await page.locator('[data-blok="repo"]').innerText(), /keten|agent/);
    await shot("workflow");

    // Via *Leunt op* naar een regelset: de regels met hun voorbeeldzinnen.
    await page.locator('[data-blok="leunt-op"]').getByRole("link", { name: "jas.detector.tijd" }).click();
    await page.waitForURL(/\/werkwijze\/regelset\/jas\.detector\.tijd$/);
    await page.locator("[data-regel]").first().waitFor();
    assert.match(await page.locator('[data-regel="jas.tijd.datum"]').innerText(), /Wel: “Deze wet treedt in werking/);
    assert.match(await page.locator('[data-blok="gebruikt-door"]').innerText(), /annotatieketen/);
    await shot("regelset");

    if (!fixture) {
      // Een methoderol: per sectie *Wijziging voorstellen*, dat een concept-PR opent (ADR-014 C7).
      await page.goto(`${base}/werkwijze/rol/duiding`);
      await page.locator('[data-sectie="duiding"]').waitFor();
      await page.locator('[data-actie="voorstel-openen"]').click();
      await page.getByLabel("Voorgestelde tekst").fill("Nieuwe methodetekst.");
      await page.getByLabel("Toelichting voor de reviewer").fill("Scherper.");
      await page.locator('[data-actie="voorstel-indienen"]').click();
      await page.getByRole("link", { name: "#7" }).waitFor();
      assert.deepEqual(voorstellen, [{ onderdeel_id: "rol/duiding", bestand: ".claude/skills/wetsanalyse/references/agentrollen.md",
        sectie: "duiding", tekst: "Nieuwe methodetekst.", toelichting: "Scherper." }]);
      assert.match(await page.locator('[data-sectie="duiding"]').innerText(), /Oude methodetekst/);
      await shot("voorstel");
    }

    // Een onbekend onderdeel is een melding, geen lege pagina.
    await page.goto(`${base}/werkwijze/rol/bestaat_niet`);
    await page.getByText("Onbekend onderdeel").waitFor();

    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log("OK test-werkwijze");
} finally {
  await browser.close();
}
