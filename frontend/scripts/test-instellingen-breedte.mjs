/** Browserregressie voor de breedte van het instellingenvenster, op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-instellingen-breedte.mjs`.
 *
 * Loopt elke tab en elk formulier na, als venster over de werkplek en als volle pagina, op 375, 640, 800 en 1280 px, met
 * lange namen en adressen. Op elk scherm mag er niets overlappen, niets buiten de kolom vallen en niets horizontaal
 * scrollen. De aanleiding: de rijen keken naar de breedte van het venster, terwijl de inhoud in een smalle kolom naast
 * het menu staat, dus op 640 px liep een wachtwoordveld over zijn label heen.
 *
 * `SCHERMAFDRUK=<map>` bewaart per scherm een afbeelding, `RAPPORT=1` meldt de bevindingen zonder te falen en
 * `ALLEEN=<tekst>` beperkt de ronde, bijvoorbeeld tot "venster 640" of "gebruikers".
 */
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const afdruk = process.env.SCHERMAFDRUK;
const rapport = process.env.RAPPORT === "1";
const alleen = process.env.ALLEEN; // bijvoorbeeld "venster 640" of "gebruikers"
const nu = "2026-11-05T09:42:00Z", straks = "2026-11-12T09:42:00Z";
const BREEDTES = [375, 640, 800, 1280];
const lang = "johanna.van-den-berg-oosterhuis";
const adres = `${lang}@belastingdienst.example.test`;
const gebruiker = (userid, role, extra = {}) => ({ userid, email: `${userid}@belastingdienst.example.test`, role, totp_enabled: false,
  active: true, created: nu, updated: nu, ...extra });
const aanvraag = (id, status, extra = {}) => ({ id, voornaam: "Johanna", achternaam: "van den Berg-Oosterhuis", email: adres,
  userid_voorstel: lang, status, reden: null, userid: status === "goedgekeurd" ? lang : null, besloten_door: null, besloten_op: null,
  created: nu, updated: nu, ...extra });
const profiel = (name, extra = {}) => ({ name, provider: "azure_ai", model: "claude-sonnet-model-met-een-lange-naam-2026-08-01",
  api_base: "https://voorbeeld.services.ai.azure.example.test", api_version: null, output_strategy: "prompt_and_parse", temperature: 0,
  is_default: false, api_key_set: true, updated_by: "wpalm", updated: nu, ...extra });
const bericht = (id, extra = {}) => ({ id, titel: "Nieuw in Lex: een bericht met een titel die over meer dan één regel doorloopt",
  inhoud: "## Wat is er nieuw\n\nLex houdt nu de **bronselectie** per deelvraag bij.\n\n- eerste punt\n- tweede punt", type: "update",
  versie: "v1.12.0-rc.1", gepubliceerd: true, gepubliceerd_op: nu, gelezen: false, aangemaakt_door: "wpalm", created: nu, updated: nu, ...extra });
const token = (id, extra = {}) => ({ id, label: "claude-acceptatie-mcp-van-de-gegevensspecialist", token_prefix: "wa_pat_abcd1234", scope: "account",
  active: true, created_by: "wpalm", created: nu, last_used: nu, userid: lang, verloopt: straks, ...extra });
const feedback = (id) => ({ id, categorie: "verbetering", userid: lang, client_id: "webapp-frontend-acceptatie", created: nu,
  pagina: "/werkgebieden/12345678-aaaa-bbbb-cccc-1234567890ab/begrippen/een-lang-pad", tekst: "De knop staat op mijn scherm over de tekst heen, zie de pagina hierboven.",
  gezien: false });

const ACCOUNT = { userid: lang, email: adres, role: "beheerder", totp_enabled: false, tfa_nodig: false, herstelcodes_over: 0 };

const browser = await chromium.launch();

async function open(viewport) {
  const context = await browser.newContext({ viewport });
  await context.addCookies(await sessieCookies(base, { role: "beheerder", userid: "wpalm" }));
  await context.grantPermissions(["clipboard-write"]).catch(() => {});
  const page = await context.newPage();
  await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));
  const stand = { account: { ...ACCOUNT } };
  await page.route("**/api/**", async (route) => {
    const req = route.request(), p = new URL(req.url()).pathname, m = req.method();
    if (p.startsWith("/api/auth/")) return route.continue();
    if (p === "/api/account/me") return route.fulfill({ json: stand.account });
    if (p === "/api/account/2fa/begin") return route.fulfill({ json: { otpauth_uri: "otpauth://totp/Wetsanalyse:wpalm?secret=JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP&issuer=Wetsanalyse" } });
    if (p === "/api/account/verbruik") return route.fulfill({ json: { userid: lang, gebruikt: 824000, budget: 1000000, percentage: 82, resterend: 176000, reset_op: straks,
      waarschuwing: true, geblokkeerd: false, actief: true } });
    if (p === "/api/admin/users" && m === "GET") return route.fulfill({ json: [gebruiker("wpalm", "beheerder"), gebruiker(lang, "beheerder", { totp_enabled: true }), gebruiker("jdevries", "analist", { active: false })] });
    if (p === "/api/admin/users" && m === "POST") return route.fulfill({ status: 201, json: { ...gebruiker("nieuw", "analist"), temp_password: "tijdelijk-wachtwoord-1234" } });
    if (p === "/api/admin/verbruik") return route.fulfill({ json: [{ userid: "wpalm", gebruikt: 10000, budget: 1000000, percentage: 1, rol: "beheerder", geblokkeerd: false, gereset_op: null, gereset_door: "" },
      { userid: lang, gebruikt: 1000000, budget: 1000000, percentage: 100, rol: "analist", geblokkeerd: true, gereset_op: nu, gereset_door: lang }] });
    if (p === "/api/admin/budget") return route.fulfill({ json: { periode_dagen: 7, anker: nu, actief: true, updated_by: "wpalm", updated: nu, reset_op: straks,
      rollen: [{ rol: "beheerder", tokens: 1000000, updated_by: "seed", updated: nu }, { rol: "analist", tokens: 500000, updated_by: "seed", updated: nu }] } });
    if (p === "/api/admin/registraties") return route.fulfill({ json: [aanvraag(1, "aangevraagd"), aanvraag(2, "goedgekeurd")] });
    if (p === "/api/admin/profiles") return route.fulfill({ json: [profiel("azure-sonnet-standaard-profiel", { is_default: true }), profiel("anthropic-reserve", { api_key_set: false })] });
    if (p.endsWith("/test") && p.includes("/profiles/")) return route.fulfill({ json: { ok: false, model: "", tokens_in: 0, tokens_out: 0, detail: "De verbinding met https://voorbeeld.services.ai.azure.example.test/openai/deployments is verbroken." } });
    if (p === "/api/admin/api-tokens" && m === "GET") return route.fulfill({ json: [token("1"), token("2", { active: false, userid: null, verloopt: null, scope: "admin", last_used: null })] });
    if (p === "/api/admin/api-tokens" && m === "POST") return route.fulfill({ status: 201, json: { ...token("3"), token: `wa_pat_${"abcd1234".repeat(6)}` } });
    if (p === "/api/admin/berichten") return route.fulfill({ json: { totaal: 45, pagina: 1, per_pagina: 20, items: [bericht(1), bericht(2, { gepubliceerd: false })] } });
    if (p === "/api/admin/feedback") return route.fulfill({ json: { items: [feedback(1), feedback(2)], totaal: 45 } });
    if (p === "/api/admin/feedback/ongelezen-aantal") return route.fulfill({ json: { aantal: 12 } });
    if (p === "/api/berichten/ongelezen-aantal") return route.fulfill({ json: { aantal: 2 } });
    if (p === "/api/berichten") return route.fulfill({ json: { totaal: 45, pagina: 1, per_pagina: 20, items: [bericht(1), bericht(2)] } });
    return route.fulfill({ json: [] });
  });
  return { page, context, stand };
}

/** Elk scherm: de tab, en wat je erin openklikt. */
const SCHERMEN = [
  { naam: "account", tab: "Account", klaar: (p) => p.getByLabel("Huidig wachtwoord").waitFor() },
  { naam: "beveiliging", tab: "Beveiliging", klaar: (p) => p.getByRole("button", { name: "2FA inschakelen" }).waitFor() },
  { naam: "beveiliging-wachtwoord", tab: "Beveiliging", klaar: async (p) => {
    await p.getByRole("button", { name: "2FA inschakelen" }).click();
    await p.getByLabel("Huidig wachtwoord").waitFor();
  } },
  { naam: "beveiliging-koppelen", tab: "Beveiliging", klaar: async (p) => {
    await p.getByRole("button", { name: "2FA inschakelen" }).click();
    await p.getByLabel("Huidig wachtwoord").fill("voorbeeld");
    await p.getByRole("button", { name: "Doorgaan" }).click();
    await p.getByAltText("QR-code voor 2FA").waitFor();
  } },
  { naam: "beveiliging-aan", tab: "Beveiliging", vooraf: (s) => Object.assign(s.account, { totp_enabled: true, herstelcodes_over: 3 }), klaar: async (p) => {
    await p.getByRole("button", { name: "Uitschakelen" }).click();
    await p.getByLabel(/^Code/).waitFor();
  } },
  { naam: "verbruik", tab: "Verbruik", klaar: (p) => p.getByText("Reset op").waitFor() },
  { naam: "berichten", tab: "Berichten", klaar: (p) => p.getByText("Wat is er nieuw").first().waitFor() },
  { naam: "modelprofielen", tab: "Modelprofielen", klaar: async (p) => {
    await p.getByRole("button", { name: "Test verbinding" }).first().click();
    await p.getByText(/Test mislukt/).waitFor();
  } },
  { naam: "modelprofiel-bewerken", tab: "Modelprofielen", klaar: async (p) => {
    await p.getByRole("button", { name: "Nieuw profiel" }).click();
    await p.getByLabel(/Output-strategie/).waitFor();
  } },
  { naam: "gebruikers", tab: "Gebruikers", klaar: (p) => p.getByRole("button", { name: "Acties voor wpalm" }).waitFor() },
  { naam: "gebruiker-nieuw", tab: "Gebruikers", klaar: async (p) => {
    await p.getByRole("button", { name: "Nieuwe gebruiker" }).click();
    await p.getByLabel("E-mailadres").waitFor();
  } },
  { naam: "gebruiker-tijdelijk", tab: "Gebruikers", klaar: async (p) => {
    await p.getByRole("button", { name: "Nieuwe gebruiker" }).click();
    await p.getByLabel("Gebruikersnaam").fill("nieuw");
    await p.getByLabel("E-mailadres").fill("nieuw@example.test");
    await p.getByRole("button", { name: "Gebruiker toevoegen" }).click();
    await p.getByLabel("Tijdelijk wachtwoord").waitFor();
  } },
  { naam: "budget-bewerken", tab: "Gebruikers", klaar: async (p) => {
    await p.locator("[data-budget-beleid]").getByRole("button", { name: /bewerken/i }).click();
    await p.getByLabel(/Analist: tokens per periode/).waitFor();
  } },
  { naam: "aanvragen", tab: "Aanvragen", klaar: (p) => p.getByRole("button", { name: "Goedkeuren" }).waitFor() },
  { naam: "aanvraag-afwijzen", tab: "Aanvragen", klaar: async (p) => {
    await p.getByRole("button", { name: "Afwijzen" }).click();
    await p.getByLabel(/Reden/).waitFor();
  } },
  { naam: "api-tokens", tab: "API-tokens", klaar: (p) => p.getByRole("button", { name: "Intrekken" }).waitFor() },
  { naam: "api-token-nieuw", tab: "API-tokens", klaar: async (p) => {
    await p.getByPlaceholder("claude-admin-mcp").fill("voorbeeld");
    await p.getByRole("button", { name: "Token genereren" }).click();
    await p.getByText("Token – kopieer dit nu").waitFor();
  } },
  { naam: "berichtenbeheer", tab: "Berichten beheren", klaar: async (p) => {
    await p.getByRole("button", { name: /Nieuw in Lex/ }).first().click();
    await p.getByRole("button", { name: "Publiceren" }).or(p.getByRole("button", { name: "Depubliceren" })).first().waitFor();
  } },
  { naam: "bericht-nieuw", tab: "Berichten beheren", klaar: async (p) => {
    await p.getByRole("button", { name: "Nieuw bericht" }).click();
    await p.getByLabel(/Inhoud/).waitFor();
  } },
  { naam: "feedback", tab: "Feedback", klaar: (p) => p.getByText("client: webapp-frontend-acceptatie").first().waitFor() },
];

/** Meet in de browser wat de gebruiker als kapot ziet. Tekst meten we per regel met een Range: de rechthoek van een
 *  element is groter dan zijn tekst, en zou overlap verzinnen of juist missen. */
function meet() {
  const paneel = [...document.querySelectorAll("[data-tabpanel]")].filter((e) => !e.hidden && e.offsetParent !== null)[0];
  if (!paneel) return ["geen paneel"];
  const fouten = [];
  const stijl = getComputedStyle(paneel);
  const p = paneel.getBoundingClientRect();
  const links = p.left + parseFloat(stijl.paddingLeft) - 1;
  const rechts = p.right - parseFloat(stijl.paddingRight) + 1;
  const kort = (t) => t.replace(/\s+/g, " ").trim().slice(0, 40);
  const zichtbaar = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
  };
  // Binnen een eigen scroller (de codeblokken) mag inhoud breder zijn dan de kolom.
  const inScroller = (el) => {
    for (let e = el.parentElement; e && e !== paneel; e = e.parentElement)
      if (["auto", "scroll"].includes(getComputedStyle(e).overflowX)) return true;
    return false;
  };

  if (document.documentElement.scrollWidth > window.innerWidth) fouten.push(`pagina scrolt horizontaal (${document.documentElement.scrollWidth} > ${window.innerWidth})`);
  if (paneel.scrollWidth > paneel.clientWidth + 1) fouten.push(`paneel scrolt horizontaal (${paneel.scrollWidth} > ${paneel.clientWidth})`);

  const velden = [...paneel.querySelectorAll("input:not([type=checkbox]),select,textarea,button,a,img")].filter(zichtbaar);
  for (const el of paneel.querySelectorAll("*")) {
    if (!zichtbaar(el) || inScroller(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.left < links - 1 || r.right > rechts + 1)
      fouten.push(`buiten de kolom: <${el.tagName.toLowerCase()}> ${kort(el.textContent ?? "")} (${Math.round(r.left)}–${Math.round(r.right)}, kolom ${Math.round(links)}–${Math.round(rechts)})`);
  }
  for (const el of velden) {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(el.tagName) && el.getBoundingClientRect().width < 120)
      fouten.push(`veld te smal: ${el.getAttribute("aria-label") ?? el.id ?? el.tagName} (${Math.round(el.getBoundingClientRect().width)} px)`);
    if (el.tagName === "BUTTON" && el.scrollWidth > el.clientWidth + 1) fouten.push(`knop kapt af: ${kort(el.textContent ?? "")}`);
  }

  const regels = [];
  const lopen = document.createTreeWalker(paneel, NodeFilter.SHOW_TEXT);
  for (let n = lopen.nextNode(); n; n = lopen.nextNode()) {
    if (!n.textContent?.trim() || !zichtbaar(n.parentElement) || n.parentElement.closest("option,select,pre,svg")) continue;
    const bereik = document.createRange();
    bereik.selectNodeContents(n);
    const rechthoeken = [...bereik.getClientRects()].filter((r) => r.width > 1 && r.height > 1);
    for (const r of rechthoeken) regels.push({ r, n });
    const lijnen = new Set(rechthoeken.map((r) => Math.round(r.top)));
    const ouder = n.parentElement.getBoundingClientRect();
    if (lijnen.size >= 3 && ouder.width < 110) fouten.push(`tekst in een te smalle kolom: "${kort(n.textContent)}" (${Math.round(ouder.width)} px, ${lijnen.size} regels)`);
  }
  const raakt = (a, b, marge = 2) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > marge && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > marge;
  for (const { r, n } of regels)
    for (const veld of velden)
      if (!veld.contains(n) && raakt(r, veld.getBoundingClientRect()))
        fouten.push(`tekst onder een veld: "${kort(n.textContent)}" raakt <${veld.tagName.toLowerCase()}> ${kort(veld.getAttribute("aria-label") ?? veld.id ?? veld.textContent ?? "")}`);
  for (let i = 0; i < regels.length; i++)
    for (let j = i + 1; j < regels.length; j++)
      if (regels[i].n !== regels[j].n && raakt(regels[i].r, regels[j].r, 3))
        fouten.push(`tekst over tekst: "${kort(regels[i].n.textContent)}" en "${kort(regels[j].n.textContent)}"`);
  return [...new Set(fouten)];
}

async function openVenster(page) {
  await page.goto(`${base}/workbench`);
  if (page.viewportSize().width < 1024) await page.getByRole("button", { name: "Menu openen" }).click({ timeout: 60_000 });
  await page.getByRole("button", { name: /· instellingen|% gebruikt/ }).last().click({ timeout: 60_000 });
  await page.getByRole("link", { name: "Account & instellingen" }).click();
  await page.getByRole("dialog", { name: "Instellingen" }).waitFor();
}

const bevindingen = [];
try {
  if (afdruk) mkdirSync(afdruk, { recursive: true });
  for (const vorm of ["venster", "pagina"]) {
    for (const breedte of BREEDTES) {
      if (alleen && !`${vorm} ${breedte}`.includes(alleen) && !SCHERMEN.some((s) => s.naam.includes(alleen))) continue;
      const { page, context, stand } = await open({ width: breedte, height: 844 });
      if (vorm === "venster") await openVenster(page);
      else await page.goto(`${base}/instellingen/account`);
      // Pas na de telbadge: die maakt de tabrij breder, en dan scrolt de rij terug naar de actieve tab.
      await page.getByRole("tab", { name: "Feedback" }).getByText("12", { exact: true }).waitFor();
      for (const scherm of SCHERMEN) {
        if (alleen && !`${vorm} ${breedte} ${scherm.naam}`.includes(alleen)) continue;
        Object.assign(stand.account, ACCOUNT);
        scherm.vooraf?.(stand);
        try {
          // Een andere tab eerst: het paneel verdwijnt dan, en daarmee wat het vorige scherm openklikte.
          const tussenstap = scherm.tab === "Account" ? "Verbruik" : "Account";
          await page.getByRole("tab", { name: tussenstap }).click();
          await page.getByRole("tab", { name: tussenstap, selected: true }).waitFor();
          await page.getByRole("tab", { name: scherm.tab }).first().click();
          await scherm.klaar(page);
          await page.evaluate(() => document.fonts.ready);
          await page.waitForTimeout(200); // de open-animatie
          for (const f of await page.evaluate(meet)) bevindingen.push(`${vorm} ${breedte} ${scherm.naam}: ${f}`);
        } catch (e) {
          bevindingen.push(`${vorm} ${breedte} ${scherm.naam}: scherm opent niet: ${e.message.split("\n")[0]}`);
        }
        if (afdruk) {
          await page.addStyleTag({ content: "nextjs-portal { display: none; }" });
          await page.screenshot({ path: `${afdruk}/${vorm}-${breedte}-${scherm.naam}.png` });
        }
      }
      await context.close();
      console.log(`${vorm} ${breedte}: klaar`);
    }
  }
  if (rapport) console.log(bevindingen.join("\n") || "geen bevindingen");
  else assert.deepEqual(bevindingen, []);
  console.log("OK test-instellingen-breedte");
} finally {
  await browser.close();
}
