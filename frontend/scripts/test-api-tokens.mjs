/** Browserregressie voor de tab API-tokens op de echte Next-UI met een gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-api-tokens.mjs`.
 *
 * Bewaakt:
 *  - zonder keuze blijft het een admin-token: de body draagt geen `userid`;
 *  - met een gekozen account gaat de `userid` mee, en toont de lijst het account en de verloopdatum;
 *  - een inactief account staat niet in de keuzelijst;
 *  - lukt het laden van de accounts niet, dan blijft het admin-token mogelijk.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base, { role: "beheerder" }));
await context.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-11-05T10:00:00+00:00";
const gebruiker = (userid, active) => ({
  userid, email: `${userid}@example.test`, role: "analist", totp_enabled: false, active, token_budget: null, created: nu, updated: nu,
});
const tokens = [];
const bodies = [];
let accountsKapot = false;

await page.route("**/api/admin/users", (route) =>
  accountsKapot
    ? route.fulfill({ status: 500, json: { detail: "stuk" } })
    : route.fulfill({ json: [gebruiker("acc-analist", true), gebruiker("oud-account", false)] }),
);
await page.route("**/api/admin/api-tokens", async (route) => {
  if (route.request().method() === "GET") return route.fulfill({ json: tokens });
  const body = route.request().postDataJSON();
  bodies.push(body);
  const record = {
    id: `t${tokens.length}`, label: body.label, token_prefix: "wa_pat_abcdefghi", scope: body.userid ? "gebruiker" : "admin",
    active: true, created_by: "adm", created: nu, last_used: null, userid: body.userid ?? null,
    verloopt: body.userid ? "2027-02-03T10:00:00+00:00" : null,
  };
  tokens.push(record);
  return route.fulfill({ status: 201, json: { ...record, token: "wa_pat_geheim" } });
});

await page.goto(`${base}/instellingen/beheer/api-tokens`);
const kiezer = page.getByLabel("Inloggen als");
await kiezer.waitFor();
await page.getByRole("option", { name: "acc-analist (analist)" }).waitFor({ state: "attached" });
assert.equal(await page.getByRole("option", { name: /oud-account/ }).count(), 0, "inactief account staat niet in de lijst");

await page.getByLabel("Label").fill("claude-admin-mcp");
await page.getByRole("button", { name: "Token genereren" }).click();
await page.getByText("Token – kopieer dit nu").waitFor();
assert.deepEqual(bodies[0], { label: "claude-admin-mcp" });

await page.getByLabel("Label").fill("acceptatie-mcp");
await kiezer.selectOption("acc-analist");
await page.getByRole("button", { name: "Token genereren" }).click();
await page.getByText("acceptatie-mcp").first().waitFor();
assert.deepEqual(bodies[1], { label: "acceptatie-mcp", userid: "acc-analist" });
await page.getByText(/verloopt:/).waitFor();
assert.equal(await kiezer.inputValue(), "", "de keuze staat na het genereren weer op admin-token");

accountsKapot = true;
await page.reload();
await page.getByLabel("Inloggen als").waitFor();
await page.getByLabel("Label").fill("nog-een");
await page.getByRole("button", { name: "Token genereren" }).click();
await page.waitForFunction(() => document.body.innerText.includes("kopieer dit nu"));
assert.deepEqual(bodies[2], { label: "nog-een" });

assert.deepEqual(errors, []);
await browser.close();
console.log("ok - API-tokens");
