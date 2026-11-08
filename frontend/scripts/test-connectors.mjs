/** Browserregressie voor de tab Connectors (ADR-013) op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-connectors.mjs`.
 *
 * Bewaakt:
 *  - de tab staat in het beheer en toont elke connector met zijn stand, brontype en beschrijving;
 *  - *Aanzetten* stuurt `PUT {aan: true}` en de kaart toont daarna *Aan* en wie het deed;
 *  - *Audit* klapt de regels uit, nieuwste eerst, en ververst na een wijziging;
 *  - een weigering van de api (geen 2FA) staat als melding in het paneel, en de stand blijft *Uit*;
 *  - op 375 px scrolt niets horizontaal.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const nu = "2026-11-08T10:00:00+00:00";

async function open(viewport, { weiger = false } = {}) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await context.addCookies(await sessieCookies(base, { role: "beheerder", userid: "wpalm" }));
  await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  const stand = { aan: false, door: "", audit: [], puts: [] };
  const connector = () => ({
    naam: "kamerstukken", label: "Kamerstukken", brontype: "kamerstuk",
    beschrijving: "Wetsgeschiedenis uit de officiële publicaties: memorie van toelichting, nota's, verslagen en het advies van de Raad van State. Openbaar, zonder sleutel.",
    aan: stand.aan, door: stand.door, bijgewerkt: stand.door ? nu : "",
  });
  await page.route("**/api/**", async (route) => {
    const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
    if (p.startsWith("/api/auth/")) return route.continue();
    if (p === "/api/account/me") return route.fulfill({ json: { userid: "wpalm", email: "wpalm@example.test", role: "beheerder", totp_enabled: true, tfa_nodig: false, herstelcodes_over: 5 } });
    if (p === "/api/admin/connectors") return route.fulfill({ json: [connector()] });
    if (p === "/api/admin/connectors/kamerstukken" && m === "PUT") {
      const body = req.postDataJSON();
      stand.puts.push(body);
      if (weiger) return route.fulfill({ status: 403, json: { detail: "Koppel eerst zelf 2FA." } });
      if (stand.aan !== body.aan) stand.audit.unshift({ actie: body.aan ? "aan" : "uit", door: "wpalm", details: {}, tijdstip: nu });
      stand.aan = body.aan;
      stand.door = "wpalm";
      return route.fulfill({ json: connector() });
    }
    if (p === "/api/admin/connectors/kamerstukken/audit") return route.fulfill({ json: stand.audit });
    if (p.endsWith("/ongelezen-aantal")) return route.fulfill({ json: { aantal: 0 } });
    return route.fulfill({ json: [] });
  });
  await page.goto(`${base}/workbench?instellingen=connectors`);
  return { page, context, stand, errors };
}

// 1. Aanzetten, audit en uitzetten.
{
  const { page, context, stand, errors } = await open({ width: 1280, height: 900 });
  const kaart = page.locator('[data-connector="kamerstukken"]');
  await kaart.waitFor();
  assert.ok(await page.getByRole("tab", { name: /Connectors/ }).count(), "de tab Connectors staat in het beheer");
  assert.match(await kaart.innerText(), /Kamerstukken[\s\S]*Uit[\s\S]*kamerstuk[\s\S]*Wetsgeschiedenis/);

  await kaart.getByRole("button", { name: "Aanzetten" }).click();
  await kaart.getByText("Aangezet door wpalm").waitFor();
  assert.deepEqual(stand.puts, [{ aan: true }]);
  assert.match(await kaart.innerText(), /\bAan\b/);

  await kaart.getByRole("button", { name: "Audit" }).click();
  const audit = kaart.getByRole("list", { name: "Audit van Kamerstukken" });
  await audit.getByText(/aangezet door wpalm/).waitFor();

  await kaart.getByRole("button", { name: "Uitzetten" }).click();
  await audit.getByText(/uitgezet door wpalm/).waitFor();
  const regels = await audit.locator("li").allInnerTexts();
  assert.equal(regels.length, 2);
  assert.match(regels[0], /uitgezet/, "de nieuwste regel staat bovenaan");
  assert.deepEqual(errors, []);
  await context.close();
}

// 2. Een weigering van de api is een melding, geen stille mislukking.
{
  const { page, context, errors } = await open({ width: 1280, height: 900 }, { weiger: true });
  const kaart = page.locator('[data-connector="kamerstukken"]');
  await kaart.getByRole("button", { name: "Aanzetten" }).click();
  await page.getByText(/Koppel eerst zelf 2FA/).waitFor();
  assert.match(await kaart.innerText(), /\bUit\b/);
  assert.deepEqual(errors, []);
  await context.close();
}

// 3. Op een telefoon scrolt niets horizontaal.
{
  const { page, context, errors } = await open({ width: 375, height: 812 });
  await page.locator('[data-connector="kamerstukken"]').waitFor();
  const breed = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert.ok(breed <= 0, `de pagina scrolt ${breed}px horizontaal`);
  assert.deepEqual(errors, []);
  await context.close();
}

await browser.close();
console.log("ok - Connectors");
