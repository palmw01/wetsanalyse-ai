/** Browserregressie: de werkwijze van Lex (ADR-014) past op een telefoon (375 px). Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-werkwijze-breedte.mjs`.
 *
 * Toetst op het overzicht, op elk concept en op de pagina van elk onderdeel dat de pagina niet horizontaal scrolt en
 * dat geen element buiten zijn kaart steekt (een lang pad, een testbestand, een id zonder spaties). Wat erin geldt,
 * komt niet uit een lijst in deze test: zonder fixture krijgt elke soort uit `lib/catalogus.ts` een onderdeel met de
 * langste waarden die we kennen, en met `WERKWIJZE_FIXTURE=<pad>` (een dump van `agent.catalogus`, zie
 * test-werkwijze.mjs) loopt hij elk echt onderdeel na. Een nieuwe soort of een nieuw onderdeel valt er dus vanzelf onder.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const BREEDTE = 375;
const fixture = process.env.WERKWIJZE_FIXTURE ? JSON.parse(readFileSync(process.env.WERKWIJZE_FIXTURE, "utf8")) : null;

const bron = readFileSync(new URL("../lib/catalogus.ts", import.meta.url), "utf8");
const SOORTEN = JSON.parse(bron.match(/export const SOORTEN = (\[[^\]]*\])/s)[1].replace(/,\s*\]/, "]"));
const CONCEPTEN = JSON.parse(bron.match(/export const CONCEPTEN = (\[[^\]]*\])/s)[1]);
const CONCEPT_VAN = { methode: "skill", rol: "skill", regelset: "skill", tool: "tool", connector: "tool", sjabloon: "tool",
  workflow: "workflow", agentprofiel: "agent", agent: "agent", route: "ingang", controle: "hook" };

// De langste waarden die in de echte catalogus voorkomen, en langer: paden en id's zonder spaties.
const PAD = ".claude/skills/wetsanalyse-met-een-hele-lange-naam/references/markeren-fragmentgrenzen-en-verwijzingen-volgen.md";
const TEST = "tools/graph-qa/tests/test_context_per_agent_met_een_heel_lange_naam_zonder_spaties.py";
const ID = "jas.detector.tijdsaanduiding.verbijzondert_parameter_met_een_lange_naam";
const lang = (soort) => {
  const id = `${soort}/${soort === "regelset" ? ID : `${soort}_met_een_heel_lange_naam_zonder_spaties_erin`}`;
  return {
    id, soort, label: `${soort} met een lange naam: ${ID}`, doel: `Doel met een lang pad ${PAD} erin.`, model: "strict",
    versie: "abc123def456abc123def456", concept: CONCEPT_VAN[soort] ?? "skill", aan: soort !== "connector",
    herkomst: { bron: "eigen werk van dit platform", licentie: "repo", letterlijk: false, verwijzing: [PAD, `${PAD}#BRON.md`] },
    bestand: [PAD, `${PAD.replace(".md", "")}/agentrollen.json`], tests: [TEST, TEST.replace("agent", "skill")],
    ingang: [`actie:${ID}`], context: `vóór de systeemprompt, ${PAD}`, tools: [ID, `${ID}_2`], uitvoer: ID, twijfel: "",
    hangt_af_van: [`regelset/${ID}`, `rol/${ID}`], straat: soort === "connector" ? `CONNECTOR_${ID.toUpperCase()}` : null,
    bewerkbaar: [], laag: "taakagent", deel_van: soort === "rol" ? `methode/${ID}` : null,
    stappen: soort === "workflow" ? [{ naam: ID, model: "strict", onderdeel: `regelset/${ID}` }, { naam: "Detectie", model: "geen", onderdeel: null }] : [],
  };
};
const inhoud = {
  methode: { rollen: { [ID]: [ID, `${ID}_2`] } },
  rol: { secties: [{ id: ID, skill: ID, bronnen: [ID, "M01"], sha256: "x".repeat(64), tekst: `Methodetekst met ${PAD}.` }] },
  regelset: { regels: [{ id: ID, code: ID.toUpperCase(), klassen: ["Tijdsaanduiding"], bron: "H2:109", versie: 2,
    voorbeelden: { positief: [`Zie ${PAD}.`], negatief: [ID] } }] },
  tool: { beschrijving: `Een handeling met ${PAD}.`, argumenten: [ID, `${ID}_2`] },
  connector: { dekt: PAD, rol_in_antwoord: ID, levert: TEST, niet_in_tekst: ID, voorbeeldvragen: [`Wat zegt ${ID}?`] },
  sjabloon: { beschrijving: ID, velden: { [ID]: PAD } },
  agentprofiel: { systeemtekst: `Instructie met ${PAD}.` },
  agent: { taken: [{ taak: ID, acties: [ID, `${ID}_2`], model: true }] },
  route: { moment: ID, herkenner: `agent.supervisie:${ID}` },
};

const ONDERDELEN = fixture ? fixture.lijst.onderdelen : SOORTEN.map(lang);
const LIJST = fixture?.lijst ?? { soorten: SOORTEN, onderdelen: ONDERDELEN };
const detail = (id) => fixture?.detail?.[id]
  ?? (() => { const o = ONDERDELEN.find((x) => x.id === id); return o && { ...o, inhoud: inhoud[o.soort] ?? {}, gebruikt_door: [ID] }; })();

/** Wat buiten beeld of buiten zijn kaart valt. Een rij die bewust zijwaarts scrolt (tabs, chips) telt niet. */
function meet() {
  const fouten = [];
  const html = document.documentElement;
  if (html.scrollWidth > html.clientWidth) fouten.push(`pagina scrolt horizontaal (${html.scrollWidth} > ${html.clientWidth})`);
  // Alleen een rij die bewust zijwaarts scrolt (tabs, chips: overflow-x auto mét overflow-y hidden) mag breder zijn
  // dan zijn plek. Een gewone scrollcontainer (overflow-y auto, waardoor overflow-x ook auto wordt) niet: wat daarin
  // breder is, is precies de fout.
  const zijwaarts = (a) => { const s = getComputedStyle(a); return ["auto", "scroll"].includes(s.overflowX) && s.overflowY === "hidden"; };
  const scrolt = (el) => { for (let a = el.parentElement; a; a = a.parentElement) if (zijwaarts(a)) return true; return false; };
  for (const a of document.querySelectorAll("body *")) {
    const s = getComputedStyle(a);
    if (["auto", "scroll"].includes(s.overflowX) && !zijwaarts(a) && a.scrollWidth > a.clientWidth + 1)
      fouten.push(`${a.tagName.toLowerCase()}.${String(a.className).split(" ").slice(0, 3).join(".")} scrolt horizontaal (${a.scrollWidth} > ${a.clientWidth})`);
  }
  const naam = (el) => `${el.tagName.toLowerCase()} “${(el.textContent ?? "").trim().slice(0, 50)}”`;
  for (const el of document.querySelectorAll("body *")) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || el.closest(".sr-only") || scrolt(el)) continue;
    if (r.right > html.clientWidth + 1) { fouten.push(`${naam(el)} steekt buiten beeld (${Math.round(r.right)} px)`); continue; }
    const kaart = el.parentElement?.closest("section, [data-blok], [data-onderdeel]");
    if (kaart) {
      const k = kaart.getBoundingClientRect();
      if (r.right > k.right + 1) fouten.push(`${naam(el)} steekt buiten zijn kaart (${Math.round(r.right)} > ${Math.round(k.right)})`);
    }
    if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX === "hidden" && !el.matches("[title], .truncate"))
      fouten.push(`${naam(el)} kapt tekst af zonder ellips`);
  }
  return [...new Set(fouten)].slice(0, 10);
}

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const fouten = [];
try {
  const page = await browser.newPage({ viewport: { width: BREEDTE, height: 800 }, isMobile: true, hasTouch: true });
  const errors = [];
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
      return d ? route.fulfill({ json: d }) : route.fulfill({ status: 404, json: { detail: "Onbekend onderdeel" } });
    }
    if (p === "/api/gesprekken") return route.fulfill({ json: [] });
    return route.fulfill({ json: {} });
  });

  const toets = async (wat) => { for (const f of await page.evaluate(meet)) fouten.push(`${wat}: ${f}`); };

  await page.goto(`${base}/werkwijze`);
  await page.getByTestId("werkwijze").waitFor();
  await page.locator("[data-onderdeel]").first().waitFor();
  await toets("overzicht");
  for (const c of CONCEPTEN) {
    await page.goto(`${base}/werkwijze?concept=${c}`);
    await page.getByTestId("werkwijze").waitFor();
    await toets(`concept ${c}`);
  }
  for (const o of ONDERDELEN) {
    const [soort, ...rest] = o.id.split("/");
    await page.goto(`${base}/werkwijze/${soort}/${encodeURIComponent(rest.join("/"))}`);
    await page.locator('[data-blok="repo"]').waitFor();
    await toets(o.id);
  }
  assert.deepEqual(errors, []);
} finally {
  await browser.close();
}
if (fouten.length) {
  console.error(fouten.join("\n"));
  process.exit(1);
}
console.log(`OK test-werkwijze-breedte (${BREEDTE} px)`);
