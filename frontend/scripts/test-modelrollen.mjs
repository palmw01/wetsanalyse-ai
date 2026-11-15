/** Browserregressie voor *Model per rol* onder Modelprofielen, op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-modelrollen.mjs`.
 *
 * Bewaakt:
 *  - onder de profielen staat het blok met de rollen per groep, elk op *Standaard* met het standaardmodel;
 *  - een profiel kiezen stuurt `PUT {profiel}`, en de rol toont daarna het nieuwe model en wie het koos;
 *  - een profiel dat Lex niet kan gebruiken staat uitgeschakeld in de lijst;
 *  - bij een rol met een waarschuwing (het JAS-oordeel) staat die zodra er een ander profiel gekozen is;
 *  - terug naar *Standaard* stuurt `PUT {profiel: null}`;
 *  - een weigering van de api (geen 2FA) is een melding;
 *  - op 375 px scrolt niets horizontaal.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const nu = "2026-11-15T10:00:00+00:00";
const STANDAARD = "claude-sonnet-4-6";
const MODELLEN = { "azure-sonnet": STANDAARD, licht: "claude-haiku-4-5" };
const OORDEEL = "Hier velt het model een oordeel over wetgeving.";

const ROLLEN = [
  ["supervisor", "Router", "Gesprek", ""],
  ["subagent", "Subagents", "Gesprek", ""],
  ["jas_classifier", "JAS-classifier", "Annoteren", OORDEEL],
];

async function open(viewport, { weiger = false } = {}) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await context.addCookies(await sessieCookies(base, { role: "beheerder", userid: "wpalm" }));
  await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  const stand = { gekozen: {}, puts: [] };
  const overzicht = () => ({
    standaard: "azure-sonnet", standaard_model: STANDAARD, standaard_niet_bruikbaar: "",
    profielen: { "azure-sonnet": "", elders: "Het profiel heeft een ander endpoint dan de straat.", licht: "" },
    rollen: ROLLEN.map(([naam, label, groep, waarschuwing]) => ({
      naam, label, groep, beschrijving: `Beschrijving van ${label}.`, waarschuwing,
      profiel: stand.gekozen[naam] ?? null, model: MODELLEN[stand.gekozen[naam]] ?? STANDAARD, niet_bruikbaar: "",
      door: stand.gekozen[naam] ? "wpalm" : "", bijgewerkt: stand.gekozen[naam] ? nu : "",
    })),
  });
  const profiel = (name, model, is_default = false) => ({
    name, provider: "azure_ai", model, api_base: "", api_version: null, output_strategy: "prompt_and_parse",
    temperature: 0, is_default, api_key_set: false, updated_by: "seed", updated: nu,
  });
  await page.route("**/api/**", async (route) => {
    const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
    if (p.startsWith("/api/auth/")) return route.continue();
    if (p === "/api/account/me") return route.fulfill({ json: { userid: "wpalm", email: "wpalm@example.test", role: "beheerder", totp_enabled: true, tfa_nodig: false, herstelcodes_over: 5 } });
    if (p === "/api/admin/profiles") return route.fulfill({ json: [profiel("azure-sonnet", STANDAARD, true), profiel("elders", "claude-haiku-4-5"), profiel("licht", "claude-haiku-4-5")] });
    if (p === "/api/admin/modelrollen") return route.fulfill({ json: overzicht() });
    const rol = p.match(/^\/api\/admin\/modelrollen\/([a-z_]+)$/)?.[1];
    if (rol && m === "PUT") {
      const body = req.postDataJSON();
      stand.puts.push([rol, body]);
      if (weiger) return route.fulfill({ status: 403, json: { detail: "Koppel eerst zelf 2FA." } });
      if (body.profiel) stand.gekozen[rol] = body.profiel; else delete stand.gekozen[rol];
      return route.fulfill({ json: overzicht().rollen.find((r) => r.naam === rol) });
    }
    if (p.endsWith("/ongelezen-aantal")) return route.fulfill({ json: { aantal: 0 } });
    return route.fulfill({ json: [] });
  });
  await page.goto(`${base}/workbench?instellingen=modelprofielen`);
  return { page, context, stand, errors };
}

// 1. Kiezen, waarschuwen en terugzetten.
{
  const { page, context, stand, errors } = await open({ width: 1280, height: 900 });
  const sub = page.locator('[data-modelrol="subagent"]');
  await sub.waitFor();
  assert.deepEqual(await page.locator("[data-modelrol-groep]").evaluateAll((g) => g.map((x) => x.dataset.modelrolGroep)),
    ["Gesprek", "Annoteren"], "de groepen in de volgorde van de api");
  const select = page.getByLabel("Subagents");
  assert.equal(await select.inputValue(), "", "zonder keuze volgt de rol de standaard");
  assert.match(await sub.innerText(), /Nu: claude-sonnet-4-6/);
  assert.equal(await select.locator('option[value="elders"]').isDisabled(), true, "een onbruikbaar profiel is niet te kiezen");
  assert.match(await select.locator('option[value=""]').innerText(), /Standaard \(azure-sonnet\)/);

  await select.selectOption("licht");
  await sub.getByText(/Gekozen door wpalm/).waitFor();
  assert.match(await sub.innerText(), /Nu: claude-haiku-4-5/);
  assert.deepEqual(stand.puts, [["subagent", { profiel: "licht" }]]);

  const jas = page.locator('[data-modelrol="jas_classifier"]');
  assert.equal(await jas.getByText(OORDEEL).count(), 0, "geen waarschuwing zolang de standaard geldt");
  await page.getByLabel("JAS-classifier").selectOption("licht");
  await jas.getByText(OORDEEL).waitFor();

  await select.selectOption("");
  await sub.getByText(/Nu: claude-sonnet-4-6/).waitFor();
  assert.deepEqual(stand.puts.at(-1), ["subagent", { profiel: null }]);
  assert.deepEqual(errors, []);
  await context.close();
}

// 2. Een weigering van de api is een melding, geen stille mislukking.
{
  const { page, context, errors } = await open({ width: 1280, height: 900 }, { weiger: true });
  await page.locator('[data-modelrol="supervisor"]').waitFor();
  await page.getByLabel("Router").selectOption("licht");
  await page.getByText(/Koppel eerst zelf 2FA/).waitFor();
  assert.equal(await page.getByLabel("Router").inputValue(), "", "de rol blijft op de standaard");
  assert.deepEqual(errors, []);
  await context.close();
}

// 3. Op een telefoon scrolt niets horizontaal.
{
  const { page, context, errors } = await open({ width: 375, height: 812 });
  await page.locator('[data-modelrol="subagent"]').waitFor();
  const breed = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert.ok(breed <= 0, `de pagina scrolt ${breed}px horizontaal`);
  assert.deepEqual(errors, []);
  await context.close();
}

await browser.close();
console.log("ok - Model per rol");
