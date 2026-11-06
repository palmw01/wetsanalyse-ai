/** Browserregressie voor het instellingenvenster op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-instellingen.mjs`.
 *
 * Bewaakt:
 *  - de kop *Beheer* in de tabkolom, alleen voor een beheerder;
 *  - een nieuwe gebruiker via *Nieuwe gebruiker*, en het tijdelijke wachtwoord dat je kunt kopiëren;
 *  - de acties van een gebruiker in het menu ⋯; Escape sluit het menu en niet het venster;
 *  - het tokenbudget: een samenvatting, en bewerken ter plekke;
 *  - een tab op de volle pagina opent geen venster erbovenop, en een tab in het venster is geen navigatie;
 *  - de berichten verschijnen meteen, en de bulkknop van de aanvragen pas na een selectie;
 *  - op een smal scherm staat de actieve tab in beeld, ook nadat een telbadge de rij breder maakte.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const nu = "2026-11-05T09:42:00Z", straks = "2026-11-12T09:42:00Z";
const gebruiker = (userid, role, active = true) => ({ userid, email: `${userid}@example.test`, role, totp_enabled: false, active,
  token_budget: null, created: nu, updated: nu });
const aanvraag = (id, voornaam) => ({ id, voornaam, achternaam: "Test", email: `${voornaam}@example.test`, userid_voorstel: voornaam,
  status: "aangevraagd", reden: null, userid: null, besloten_door: null, besloten_op: null, created: nu, updated: nu });
const browser = await chromium.launch();

async function open(role, viewport = { width: 1280, height: 860 }) {
  const context = await browser.newContext({ viewport });
  await context.addCookies(await sessieCookies(base, { role, userid: "wpalm" }));
  const page = await context.newPage();
  await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  const fouten = [];
  page.on("pageerror", (e) => fouten.push(e.message));
  const stand = {
    users: [gebruiker("wpalm", "beheerder"), gebruiker("jdevries", "analist")],
    budget: { tokens: 1000000, periode_dagen: 7, anker: nu, actief: true, updated_by: "wpalm", updated: nu, reset_op: straks },
    verzoeken: [],
  };
  await page.route("**/api/**", async (route) => {
    const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
    if (p.startsWith("/api/auth/")) return route.continue();
    const body = m === "GET" || m === "DELETE" ? null : req.postDataJSON?.() ?? null;
    if (m !== "GET") stand.verzoeken.push({ p, m, body });
    if (p === "/api/admin/users" && m === "POST") {
      stand.users.push(gebruiker(body.userid, body.role));
      return route.fulfill({ status: 201, json: { ...gebruiker(body.userid, body.role), temp_password: "tijdelijk-1" } });
    }
    if (/\/api\/admin\/users\/[^/]+\/reset/.test(p)) return route.fulfill({ json: { ...gebruiker("jdevries", "analist"), temp_password: "tijdelijk-2" } });
    if (p === "/api/admin/users") return route.fulfill({ json: stand.users });
    if (p === "/api/admin/verbruik") return route.fulfill({ json: [] });
    if (p === "/api/admin/budget") {
      if (m !== "GET") Object.assign(stand.budget, body);
      return route.fulfill({ json: stand.budget });
    }
    if (p === "/api/admin/registraties") return route.fulfill({ json: [aanvraag(1, "sanne")] });
    if (p === "/api/admin/berichten") return route.fulfill({ json: { totaal: 1, pagina: 1, per_pagina: 20, items: [{ id: 1, titel: "Nieuw in Lex",
      inhoud: "Tekst", type: "update", versie: null, gepubliceerd: false, gepubliceerd_op: null, created: nu, updated: nu }] } });
    if (p === "/api/admin/feedback") return route.fulfill({ json: { items: [], totaal: 0 } });
    if (p === "/api/admin/feedback/ongelezen-aantal") return route.fulfill({ json: { aantal: 0 } });
    if (p === "/api/account/me") return route.fulfill({ json: { userid: "wpalm", email: "w@example.test", role, totp_enabled: false } });
    return route.fulfill({ json: [] });
  });
  return { page, stand, fouten, context };
}

try {
  // Een analist ziet geen groepskop: er is maar één soort tab.
  const analist = await open("analist");
  await analist.page.goto(`${base}/instellingen/account`);
  await analist.page.getByRole("tablist", { name: "Instellingen" }).waitFor();
  assert.equal(await analist.page.getByText("Beheer", { exact: true }).count(), 0);
  await analist.context.close();

  const { page, fouten } = await open("beheerder");
  await page.goto(`${base}/instellingen/beheer/gebruikers`);
  await page.getByText("Beheer", { exact: true }).waitFor();

  // Het budget is een samenvatting; bewerken gebeurt ter plekke.
  const budget = page.locator("[data-budget-beleid]");
  await budget.getByText("1.000.000 tokens per 7 dagen", { exact: false }).waitFor();
  await budget.getByRole("button", { name: /bewerken/i }).click();
  await budget.getByLabel(/Tokens per periode/).fill("2000000");
  await budget.getByRole("button", { name: "Opslaan" }).click();
  await budget.getByText("2.000.000 tokens per 7 dagen", { exact: false }).waitFor();

  // Toevoegen staat dicht tot je erom vraagt.
  assert.equal(await page.locator("[data-gebruiker-nieuw]").count(), 0);
  await page.getByRole("button", { name: "Nieuwe gebruiker" }).click();
  await page.getByLabel("Gebruikersnaam").fill("nieuw");
  await page.getByLabel("E-mailadres").fill("nieuw@example.test");
  await page.getByRole("button", { name: "Gebruiker toevoegen" }).click();
  await page.locator("[data-gebruiker=nieuw]").waitFor();
  assert.equal(await page.getByLabel("Tijdelijk wachtwoord").inputValue(), "tijdelijk-1");
  await page.getByRole("button", { name: "Kopiëren" }).waitFor();
  assert.equal(await page.locator("[data-gebruiker-nieuw]").count(), 0, "het formulier sluit na toevoegen");

  // De acties van een gebruiker staan in het menu; Escape sluit het menu en laat de pagina staan.
  await page.getByRole("button", { name: "Acties voor jdevries" }).click();
  await page.getByRole("menuitem", { name: "Wachtwoord resetten" }).waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("menuitem", { name: "Wachtwoord resetten" }).waitFor({ state: "detached" });
  await page.getByRole("button", { name: "Acties voor jdevries" }).click();
  await page.getByRole("menuitem", { name: "Wachtwoord resetten" }).click();
  await page.waitForFunction(() => document.querySelector("[aria-label='Tijdelijk wachtwoord']")?.value === "tijdelijk-2");

  // De berichten staan er meteen, zonder *Toon berichten*. Op de volle pagina opent een tab geen venster erbovenop.
  await page.getByRole("tab", { name: "Berichten beheren" }).click();
  await page.waitForURL("**/instellingen/beheer/berichten");
  assert.equal(await page.getByRole("dialog").count(), 0);
  await page.getByText("Nieuw in Lex").waitFor();

  // De bulkknop verschijnt pas als er iets geselecteerd is.
  await page.getByRole("tab", { name: "Aanvragen" }).click();
  await page.getByLabel("sanne Test selecteren").waitFor();
  assert.equal(await page.getByRole("button", { name: /goedkeuren als analist/ }).count(), 0);
  await page.getByLabel("sanne Test selecteren").check();
  await page.getByRole("button", { name: "1 goedkeuren als analist" }).waitFor();
  assert.deepEqual(fouten, []);

  // In de dialog is een tab geen navigatie: er komt niets van de server, dus de pagina erachter kan niet wegvallen.
  const venster = await open("beheerder");
  await venster.page.goto(`${base}/workbench`);
  await venster.page.getByRole("button", { name: /· instellingen/ }).click();
  await venster.page.getByRole("link", { name: "Account & instellingen" }).click();
  await venster.page.getByRole("dialog").waitFor();
  const serververzoeken = [];
  venster.page.on("request", (r) => { if (r.url().includes("_rsc=")) serververzoeken.push(r.url()); });
  for (const naam of ["Verbruik", "Feedback", "Modelprofielen", "Gebruikers", "Account"]) {
    await venster.page.getByRole("dialog").getByRole("tab", { name: naam }).click();
    await venster.page.waitForFunction((n) => document.querySelector("[role=tab][aria-selected=true]")?.textContent?.startsWith(n), naam);
  }
  await venster.page.waitForURL("**/instellingen/account");
  assert.deepEqual(serververzoeken, [], "een tabwissel haalt niets bij de server");
  assert.equal(await venster.page.getByRole("dialog").count(), 1);
  await venster.page.getByRole("button", { name: /· instellingen/ }).waitFor({ state: "attached" });
  await venster.page.getByRole("button", { name: "Instellingen sluiten" }).click();
  await venster.page.waitForURL("**/workbench");
  await venster.page.getByRole("dialog").waitFor({ state: "detached" });

  // Op een smal scherm is de tabkolom een rij: de actieve tab staat in beeld.
  const smal = await open("beheerder", { width: 390, height: 800 });
  await smal.page.goto(`${base}/instellingen/beheer/feedback`);
  const tab = smal.page.getByRole("tab", { name: "Feedback" });
  await tab.waitFor();
  // Pas ná de telbadge meten: die maakt *Aanvragen* breder en duwt de tab erachter opzij. Daarvoor zegt de stand niets.
  await smal.page.getByRole("tab", { name: "Aanvragen" }).getByText("1", { exact: true }).waitFor();
  await smal.page.waitForFunction(() => {
    const t = [...document.querySelectorAll("[role=tab]")].find((x) => x.textContent?.startsWith("Feedback"));
    const r = t?.getBoundingClientRect();
    return r && r.left >= 0 && r.right <= window.innerWidth;
  });
  console.log("OK test-instellingen");
} finally {
  await browser.close();
}
