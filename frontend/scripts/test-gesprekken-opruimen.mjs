/** Browserregressie voor het opruimen van gesprekken in de instellingen (tab Gesprekken). Op de echte Next-UI met een
 * gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-gesprekken-opruimen.mjs`.
 *
 * Bewaakt:
 *  - de tab Gesprekken telt *Recente gesprekken* en *Archief* apart;
 *  - verwijderen vraagt een tweede klik met het aantal, en stuurt dan één DELETE voor de hele groep;
 *  - daarna ververst de sidebar, en was het open gesprek erbij, dan blijft de werkplek leeg achter;
 *  - *Archiveren* zet de recente gesprekken in het archief, zonder bevestiging en zonder het open gesprek te sluiten;
 *  - een groep zonder gesprekken heeft een uitgeschakelde knop; een gesprek in een werkgebied blijft staan.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [], bulk = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.context().addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-11-10T10:00:00+00:00";
const gesprek = (id, titel, extra = {}) => ({ id, titel, aantal_berichten: 2, updated: nu, werkgebied_id: "",
  werkgebied_naam: "", gearchiveerd: null, ...extra });
let lijst = [
  gesprek("g1", "In het werkgebied", { werkgebied_id: "wg1", werkgebied_naam: "Invorderingsrente" }),
  gesprek("g2", "Losse vraag over uitstel"),
  gesprek("g3", "Nog een losse vraag"),
  gesprek("g4", "Oude verkenning", { gearchiveerd: nu }),
  gesprek("g5", "Oud in het werkgebied", { werkgebied_id: "wg1", werkgebied_naam: "Invorderingsrente", gearchiveerd: nu }),
];
// Zoals de api (`_groep_filter`): recent = actief en los, archief = alles wat gearchiveerd is.
const inGroep = (groep) => lijst.filter((g) => groep === "recent" ? !g.gearchiveerd && !g.werkgebied_id : Boolean(g.gearchiveerd));

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  if (p === "/api/annotatie/run") return route.fulfill({ json: null });
  if (p === "/api/werkgebieden") return route.fulfill({ json: { werkgebieden: [] } });
  if (p === "/api/gesprekken/telling") return route.fulfill({ json: { recent: inGroep("recent").length, archief: inGroep("archief").length } });
  const groep = p.match(/^\/api\/gesprekken\/groep\/(recent|archief)(\/archiveren)?$/);
  if (groep) {
    const ids = inGroep(groep[1]).map((g) => g.id);
    bulk.push(`${m} ${groep[1]}${groep[2] ?? ""}`);
    if (groep[2]) {
      for (const g of lijst) if (ids.includes(g.id)) g.gearchiveerd = nu;
    } else {
      lijst = lijst.filter((g) => !ids.includes(g.id));
    }
    return route.fulfill({ json: { aantal: ids.length, ids } });
  }
  const een = p.match(/^\/api\/gesprekken\/(g\d+)$/);
  if (een) return route.fulfill({ json: { ...lijst.find((g) => g.id === een[1]), user_id: "t", berichten: [] } });
  if (p === "/api/gesprekken") {
    const q = url.searchParams;
    let uit = lijst;
    if (q.has("gearchiveerd")) uit = uit.filter((g) => Boolean(g.gearchiveerd) === (q.get("gearchiveerd") === "true"));
    return route.fulfill({ json: uit });
  }
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  if (p === "/api/account/me") return route.fulfill({ json: { userid: "t", email: "t@example.test", role: "analist",
    totp_enabled: false, tfa_nodig: false, rondleiding_knop: false } });
  return route.fulfill({ json: [] });
});

const sidebar = page.locator("aside[data-tour=sidebar]");
const rij = (id) => sidebar.locator(`[data-gesprek-rij=${id}]`);
const venster = page.getByRole("dialog");
const recentRij = venster.locator("[data-groep-opruimen=recent]");
const archiefRij = venster.locator("[data-groep-opruimen=archief]");

async function openTab() {
  await page.getByRole("button", { name: /· instellingen/ }).click();
  await page.getByRole("link", { name: "Account & instellingen" }).click();
  await venster.getByRole("tab", { name: "Gesprekken" }).click();
  await page.waitForURL("**instellingen=gesprekken");
}
async function sluitVenster() {
  await page.getByRole("button", { name: "Instellingen sluiten" }).click();
  await venster.waitFor({ state: "detached" });
}

try {
  await page.goto(`${base}/workbench`);
  // --- Het archief leegmaken, met het open gesprek erin ---
  await sidebar.getByRole("button", { name: /^Archief/ }).click();
  await rij("g4").getByRole("button", { name: /^Oude verkenning/ }).click();
  await page.waitForURL("**gesprek=g4**");
  await openTab();
  await venster.getByText("2 gesprekken in het archief", { exact: false }).waitFor();
  await venster.getByText("2 gesprekken die niet in een werkgebied staan", { exact: false }).waitFor();
  await venster.getByText("Annotaties, begrippen en werkgebieden blijven bestaan", { exact: false }).waitFor();

  await archiefRij.getByRole("button", { name: "Gesprekken verwijderen" }).click();
  await archiefRij.getByRole("button", { name: "2 gesprekken verwijderen?" }).waitFor();
  assert.deepEqual(bulk, [], "de eerste klik verwijdert nog niets");
  if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/gesprekken-opruimen.png` });
  await archiefRij.getByRole("button", { name: "2 gesprekken verwijderen?" }).click();
  await venster.getByText("2 gesprekken verwijderd.").waitFor();
  assert.deepEqual(bulk, ["DELETE archief"], "één verzoek voor de hele groep");
  await venster.getByText("Geen gesprekken in het archief", { exact: false }).waitFor();
  assert.ok(await archiefRij.getByRole("button", { name: "Gesprekken verwijderen" }).isDisabled(), "een lege groep heeft niets te verwijderen");

  await sluitVenster();
  // Het open gesprek was erbij: de werkplek staat leeg, de sidebar is ververst.
  await page.waitForFunction(() => !new URL(location.href).searchParams.has("gesprek"));
  await rij("g4").waitFor({ state: "detached" });
  await rij("g2").waitFor();

  // --- De recente gesprekken archiveren, met een ander gesprek open ---
  await rij("g1").getByRole("button", { name: /^In het werkgebied/ }).click();
  await page.waitForURL("**gesprek=g1**");
  await openTab();
  await recentRij.getByRole("button", { name: "Archiveren" }).click();
  await venster.getByText("2 gesprekken gearchiveerd.").waitFor();
  assert.deepEqual(bulk.at(-1), "POST recent/archiveren");
  await venster.getByText("Geen gesprekken die niet in een werkgebied staan", { exact: false }).waitFor();

  // --- En de recente gesprekken verwijderen kan nu niet: de groep is leeg ---
  assert.ok(await recentRij.getByRole("button", { name: "Gesprekken verwijderen" }).isDisabled());
  await sluitVenster();
  assert.ok(new URL(page.url()).searchParams.get("gesprek") === "g1", "het open gesprek blijft open");
  // Het archief staat nog open: daar staan ze nu, en onder *Recente gesprekken* niet meer.
  await sidebar.locator("[data-groep=archief]").locator("[data-gesprek-rij=g2]").waitFor();
  assert.equal(await sidebar.locator("[data-groep=recent] [data-gesprek-rij]").count(), 0);
  await rij("g1").waitFor();

  assert.deepEqual(errors, []);
  console.log("Browser OK: tab Gesprekken telt recent en archief; verwijderen met aantal en tweede klik, één verzoek; sidebar ververst en het open gesprek sluit; archiveren zonder bevestiging; werkgebiedgesprekken blijven.");
} finally {
  await browser.close();
}
