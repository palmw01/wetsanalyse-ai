/** Browserregressie voor het instellingenvenster op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-instellingen.mjs`.
 *
 * Bewaakt:
 *  - de kop *Beheer* in de tabkolom, alleen voor een beheerder;
 *  - een nieuwe gebruiker via *Nieuwe gebruiker*, en het tijdelijke wachtwoord dat je kunt kopiëren;
 *  - de acties van een gebruiker in het menu ⋯; Escape sluit het menu en niet het venster;
 *  - het tokenbudget: een samenvatting per rol, en bewerken ter plekke; alleen de gewijzigde rol gaat over de lijn;
 *  - per gebruiker geen budgetveld: alleen het budget van zijn rol, en een reset met twee klikken;
 *  - een tab op de volle pagina opent geen venster erbovenop, en een tab in het venster is geen navigatie;
 *  - de berichten verschijnen meteen, en de bulkknop van de aanvragen pas na een selectie;
 *  - op een smal scherm staat de actieve tab in beeld, ook nadat een telbadge de rij breder maakte;
 *  - 2FA inschakelen vraagt eerst het huidige wachtwoord, en een fout wachtwoord toont geen QR-code;
 *  - een beheerder zonder 2FA ziet op de beheertabs waarom het dicht is, koppelt, ziet zijn herstelcodes
 *    één keer en loopt dan zonder herladen door naar het beheer;
 *  - een andere beheerder reset 2FA met twee klikken, en een beheerder zonder 2FA valt op in de lijst;
 *  - het 2FA-scherm neemt een herstelcode aan.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";
import { toetsToegankelijkheid } from "./axe.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const nu = "2026-11-05T09:42:00Z", straks = "2026-11-12T09:42:00Z";
const gebruiker = (userid, role, active = true) => ({ userid, email: `${userid}@example.test`, role, totp_enabled: false, active,
  created: nu, updated: nu });
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
    budget: { periode_dagen: 7, anker: nu, actief: true, updated_by: "wpalm", updated: nu, reset_op: straks,
      rollen: [{ rol: "beheerder", tokens: 1000000, updated_by: "seed", updated: nu }, { rol: "analist", tokens: 500000, updated_by: "seed", updated: nu }] },
    verbruik: [],
    verzoeken: [],
    account: { totp_enabled: false, tfa_nodig: false, herstelcodes_over: 0 },
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
    if (p.endsWith("/2fa-reset")) {
      stand.users.find((u) => p.includes(`/${u.userid}/`)).totp_enabled = false;
      return route.fulfill({ status: 204 });
    }
    if (p === "/api/account/2fa/activate") {
      Object.assign(stand.account, { totp_enabled: true, tfa_nodig: false, herstelcodes_over: 10 });
      return route.fulfill({ json: { codes: ["AAAA-BBBB-CCCC-DDDD", "EEEE-FFFF-GGGG-HHHH"] } });
    }
    if (p === "/api/login-2fa") return route.fulfill({ json: { ok: false, code: "totp_required", userid: "wpalm" } });
    if (/\/api\/admin\/users\/[^/]+\/reset/.test(p)) return route.fulfill({ json: { ...gebruiker("jdevries", "analist"), temp_password: "tijdelijk-2" } });
    if (p === "/api/admin/users") return route.fulfill({ json: stand.users });
    if (p === "/api/admin/verbruik") return route.fulfill({ json: stand.verbruik });
    if (p.endsWith("/verbruik-reset")) {
      const regel = stand.verbruik.find((r) => p.includes(`/${r.userid}/`));
      Object.assign(regel, { gebruikt: 0, percentage: 0, gereset_op: nu, gereset_door: "wpalm" });
      return route.fulfill({ json: regel });
    }
    if (p.startsWith("/api/admin/budget/rollen/")) {
      const rol = stand.budget.rollen.find((r) => p.endsWith(`/${r.rol}`));
      rol.tokens = body.tokens;
      return route.fulfill({ json: rol });
    }
    if (p === "/api/admin/budget") {
      if (m !== "GET") Object.assign(stand.budget, body);
      return route.fulfill({ json: stand.budget });
    }
    if (p === "/api/admin/registraties") return route.fulfill({ json: [aanvraag(1, "sanne")] });
    if (p === "/api/admin/berichten") return route.fulfill({ json: { totaal: 1, pagina: 1, per_pagina: 20, items: [{ id: 1, titel: "Nieuw in Lex",
      inhoud: "Tekst", type: "update", versie: null, gepubliceerd: false, gepubliceerd_op: null, created: nu, updated: nu }] } });
    if (p === "/api/admin/feedback") return route.fulfill({ json: { items: [], totaal: 0 } });
    if (p === "/api/admin/feedback/ongelezen-aantal") return route.fulfill({ json: { aantal: 0 } });
    if (p === "/api/account/2fa/begin") {
      const { password } = route.request().postDataJSON();
      return password === "goed"
        ? route.fulfill({ json: { otpauth_uri: "otpauth://totp/Wetsanalyse:wpalm?secret=TESTSECRET&issuer=Wetsanalyse" } })
        : route.fulfill({ status: 400, json: { detail: "Huidig wachtwoord onjuist." } });
    }
    if (p === "/api/account/me") return route.fulfill({ json: { userid: "wpalm", email: "w@example.test", role, ...stand.account } });
    return route.fulfill({ json: [] });
  });
  return { page, stand, fouten, context };
}

try {
  // Een analist ziet geen groepskop: er is maar één soort tab.
  const analist = await open("analist");
  // Een oude link naar /instellingen opent het venster als pop-up op de werkplek, nooit als losse pagina.
  await analist.page.goto(`${base}/instellingen/account`);
  await analist.page.waitForURL("**/workbench?instellingen=account");
  await analist.page.getByRole("dialog", { name: "Instellingen" }).getByRole("tablist", { name: "Instellingen" }).waitFor();
  assert.equal(await analist.page.getByText("Terug naar de werkplek").count(), 0, "geen losse instellingenpagina");
  // Herladen houdt het venster open.
  await analist.page.reload();
  await analist.page.getByRole("dialog", { name: "Instellingen" }).waitFor();
  assert.equal(await analist.page.getByText("Beheer", { exact: true }).count(), 0);

  // 2FA koppelen vraagt het wachtwoord: de QR-code verschijnt pas na het juiste.
  await analist.page.goto(`${base}/workbench?instellingen=beveiliging`);
  await analist.page.getByRole("button", { name: "2FA inschakelen" }).click();
  const wachtwoord = analist.page.getByLabel("Huidig wachtwoord");
  await wachtwoord.fill("fout");
  await analist.page.getByRole("button", { name: "Doorgaan" }).click();
  await analist.page.getByText("Huidig wachtwoord onjuist.").waitFor();
  await toetsToegankelijkheid(analist.page, "instellingen – beveiliging met fout");
  assert.equal(await analist.page.getByAltText("QR-code voor 2FA").count(), 0);
  await wachtwoord.fill("goed");
  await analist.page.getByRole("button", { name: "Doorgaan" }).click();
  await analist.page.getByAltText("QR-code voor 2FA").waitFor();
  assert.equal(await wachtwoord.count(), 0);
  await analist.context.close();

  const { page, fouten, stand } = await open("beheerder");
  await page.goto(`${base}/workbench?instellingen=gebruikers`);
  await page.getByText("Beheer", { exact: true }).waitFor();
  await toetsToegankelijkheid(page, "instellingen – gebruikers");

  // Het budget is een samenvatting; bewerken gebeurt ter plekke.
  const budget = page.locator("[data-budget-beleid]");
  await budget.getByText("Per 7 dagen, per rol", { exact: false }).waitFor();
  await budget.getByText("Beheerder: 1.000.000 tokens").waitFor();
  await budget.getByText("Analist: 500.000 tokens").waitFor();
  await budget.getByRole("button", { name: /bewerken/i }).click();
  await budget.getByLabel(/Analist: tokens per periode/).fill("300000");
  await budget.getByRole("button", { name: "Opslaan" }).click();
  await budget.getByText("Analist: 300.000 tokens").waitFor();
  await budget.getByText("Beheerder: 1.000.000 tokens").waitFor();
  assert.deepEqual(stand.verzoeken.filter((v) => v.p.startsWith("/api/admin/budget/rollen/")),
    [{ p: "/api/admin/budget/rollen/analist", m: "PUT", body: { tokens: 300000 } }], "alleen wat veranderde gaat over de lijn");

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

  // De berichten staan er meteen, zonder *Toon berichten*. Een tab wisselt in hetzelfde venster: er komt er geen bij.
  await page.getByRole("tab", { name: "Berichten beheren" }).click();
  await page.waitForURL("**instellingen=berichtenbeheer");
  assert.equal(await page.getByRole("dialog").count(), 1);
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
  await venster.page.waitForURL("**/workbench?instellingen=account");
  assert.deepEqual(serververzoeken, [], "een tabwissel haalt niets bij de server");
  assert.equal(await venster.page.getByRole("dialog").count(), 1);
  await venster.page.getByRole("button", { name: /· instellingen/ }).waitFor({ state: "attached" });
  await venster.page.getByRole("button", { name: "Instellingen sluiten" }).click();
  await venster.page.waitForURL("**/workbench");
  await venster.page.getByRole("dialog").waitFor({ state: "detached" });

  // Op een smal scherm is de tabkolom een rij: de actieve tab staat in beeld.
  const smal = await open("beheerder", { width: 390, height: 800 });
  await smal.page.goto(`${base}/workbench?instellingen=feedback`);
  const tab = smal.page.getByRole("tab", { name: "Feedback" });
  await tab.waitFor();
  // Pas ná de telbadge meten: die maakt *Aanvragen* breder en duwt de tab erachter opzij. Daarvoor zegt de stand niets.
  await smal.page.getByRole("tab", { name: "Aanvragen" }).getByText("1", { exact: true }).waitFor();
  await smal.page.waitForFunction(() => {
    const t = [...document.querySelectorAll("[role=tab]")].find((x) => x.textContent?.startsWith("Feedback"));
    const r = t?.getBoundingClientRect();
    return r && r.left >= 0 && r.right <= window.innerWidth;
  });
  // Een beheerder zonder 2FA: het beheer legt uit waarom het dicht is, en koppelen opent het zonder herladen.
  const plicht = await open("beheerder");
  plicht.stand.account.tfa_nodig = true;
  await plicht.page.goto(`${base}/workbench?instellingen=gebruikers`);
  await plicht.page.getByText("Koppel eerst tweestapsverificatie").waitFor();
  assert.equal(await plicht.page.getByRole("button", { name: "Nieuwe gebruiker" }).count(), 0);
  await plicht.page.getByRole("button", { name: "Naar Beveiliging" }).click();
  await plicht.page.getByText("Het beheer is dicht tot je koppelt").waitFor();
  await plicht.page.getByRole("button", { name: "2FA inschakelen" }).click();
  await plicht.page.getByLabel("Huidig wachtwoord").fill("goed");
  await plicht.page.getByRole("button", { name: "Doorgaan" }).click();
  await plicht.page.getByLabel(/Code uit de app/).fill("123456");
  await plicht.page.getByRole("button", { name: "Bevestigen" }).click();
  await plicht.page.getByText("Herstelcodes – bewaar ze nu").waitFor();
  await plicht.page.getByText("AAAA-BBBB-CCCC-DDDD").waitFor();
  await plicht.page.getByText("10 over").waitFor();
  assert.equal(await plicht.page.getByText("Het beheer is dicht tot je koppelt").count(), 0);
  await plicht.page.getByRole("tab", { name: "Gebruikers" }).click();
  await plicht.page.getByRole("button", { name: "Nieuwe gebruiker" }).waitFor();
  assert.equal(await plicht.page.getByText("Koppel eerst tweestapsverificatie").count(), 0);

  // De reset: alleen bij wie 2FA heeft, met een tweede klik. Een beheerder zonder 2FA valt op.
  const reset = await open("beheerder");
  reset.stand.users[1].totp_enabled = true;
  await reset.page.goto(`${base}/workbench?instellingen=gebruikers`);
  const rij = (id) => reset.page.locator(`[data-gebruiker="${id}"]`);
  await rij("wpalm").getByText("2FA ontbreekt").waitFor();
  assert.equal(await rij("jdevries").getByText("2FA ontbreekt").count(), 0);
  await rij("wpalm").getByRole("button", { name: "Acties voor wpalm" }).click();
  assert.equal(await reset.page.getByRole("menuitem", { name: "2FA resetten" }).count(), 0, "zonder 2FA valt er niets te resetten");
  await reset.page.keyboard.press("Escape");
  await rij("jdevries").getByRole("button", { name: "Acties voor jdevries" }).click();
  await reset.page.getByRole("menuitem", { name: "2FA resetten" }).click();
  assert.equal(reset.stand.verzoeken.filter((v) => v.p.endsWith("/2fa-reset")).length, 0, "de eerste klik vraagt alleen");
  await reset.page.getByRole("menuitem", { name: /resetten\?/ }).click();
  await rij("jdevries").getByText("2FA aan").waitFor({ state: "detached" });
  assert.equal(reset.stand.verzoeken.filter((v) => v.p === "/api/admin/users/jdevries/2fa-reset").length, 1);

  // Per gebruiker geen budgetveld: je ziet wat zijn rol geeft, en resetten vraagt een tweede klik.
  const beurt = await open("beheerder");
  beurt.stand.verbruik = [{ userid: "jdevries", gebruikt: 400000, budget: 500000, percentage: 80, rol: "analist", geblokkeerd: false,
    gereset_op: null, gereset_door: "" }];
  await beurt.page.goto(`${base}/workbench?instellingen=gebruikers`);
  const beurtRij = beurt.page.locator(`[data-gebruiker="jdevries"]`);
  await beurtRij.getByText("Budget van de rol analist: 500.000 tokens").waitFor();
  assert.equal(await beurt.page.getByText("Eigen budget").count(), 0);
  assert.equal(await beurtRij.getByRole("spinbutton").count(), 0);
  await beurt.page.getByRole("button", { name: "Acties voor wpalm" }).click();
  assert.equal(await beurt.page.getByRole("menuitem", { name: "Verbruik resetten" }).count(), 0, "zonder verbruik valt er niets te resetten");
  await beurt.page.keyboard.press("Escape");
  await beurtRij.getByRole("button", { name: "Acties voor jdevries" }).click();
  await beurt.page.getByRole("menuitem", { name: "Verbruik resetten" }).click();
  assert.equal(beurt.stand.verzoeken.filter((v) => v.p.endsWith("/verbruik-reset")).length, 0, "de eerste klik vraagt alleen");
  await beurt.page.getByRole("menuitem", { name: /Verbruik van "jdevries" resetten\?/ }).click();
  await beurtRij.getByText(/^Gereset op .* door wpalm$/).waitFor();
  assert.equal(beurt.stand.verzoeken.filter((v) => v.p === "/api/admin/users/jdevries/verbruik-reset" && v.m === "POST").length, 1);
  assert.deepEqual(beurt.fouten, []);

  // Het 2FA-scherm: de herstelcode gaat door hetzelfde veld, en wisselen maakt het veld leeg.
  const inlog = await open("analist");
  await inlog.context.clearCookies();
  await inlog.context.addCookies([{ name: "wa-login-ticket", value: "ticket", url: base },
    { name: "__Secure-wa-login-ticket", value: "ticket", domain: new URL(base).hostname, path: "/", secure: true }]);
  await inlog.page.addInitScript(() => sessionStorage.setItem("wa_login_userid", "wpalm"));
  await inlog.page.goto(`${base}/login/2fa`);
  await inlog.page.getByLabel(/2FA-code/).fill("123");
  await inlog.page.getByRole("button", { name: /Gebruik een herstelcode/ }).click();
  const herstelveld = inlog.page.getByLabel(/Herstelcode/);
  assert.equal(await herstelveld.inputValue(), "");
  await herstelveld.fill("AAAA-BBBB-CCCC-DDDD");
  await inlog.page.getByRole("button", { name: "Verifiëren" }).click();
  await inlog.page.getByText(/Onjuiste of verlopen code/).waitFor();
  assert.equal(inlog.stand.verzoeken.find((v) => v.p === "/api/login-2fa").body.totp, "AAAA-BBBB-CCCC-DDDD");
  for (const v of [plicht, reset, inlog]) assert.deepEqual(v.fouten, []);
  console.log("OK test-instellingen");
} finally {
  await browser.close();
}
