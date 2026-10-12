/** Browserregressie voor de samenhangsgraaf (sigma.js) op echte Next-UI met gemockte BFF. Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * TEST_URL=http://localhost:3109 node scripts/test-samenhang.mjs   (na npx playwright install chromium)
 * Screenshots: MOCK_SCREENSHOTS (default /tmp/wetsanalyse-samenhang).
 * Gebruik `localhost`, niet `127.0.0.1`: Next 16 weigert dev-assets aan een andere origin dan de
 * server kent, en dan hydrateert de pagina niet – elke stap time-out dan zonder duidelijke fout.
 */
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const shots = process.env.MOCK_SCREENSHOTS || "/tmp/wetsanalyse-samenhang";
mkdirSync(shots, { recursive: true });
const LAW = "urn:bwb:BWBR0004770", ART = `${LAW}:artikel:9`, L1 = `${ART}:lid:1`, L2 = `${ART}:lid:2`;
const A10 = `${LAW}:artikel:10`, A10L1 = `${A10}:lid:1`, STUB = "urn:bwb:BWBR0002320:artikel:3";

const knoop = (id, soort, extra = {}) => ({ id, soort, label: id, tekst: "", klasse: "", lifecycle: "", element_id: "",
  bwb_id: "BWBR0004770", artikel: "", lid: "", rand: false, ...extra });
const rel = (bron, doel, soort, groep, anker_tekst = "") => ({ bron, doel, soort, groep, anker_tekst });
const HII = `${LAW}:hoofdstuk:II`, HV = `${LAW}:hoofdstuk:V`, A28 = `${LAW}:artikel:28`;
function samenhang(iri) {
  // Een structuurdeel: de api levert het deel met zijn artikelen, zonder leden (api/app/samenhang.py).
  if (iri === HII) return { schema_versie: 1, doel: { bron_iri: iri }, snapshot_id: "s2", artikel_iri: HII,
    verwijzingen_beschikbaar: true, afgekapt: false,
    knopen: [knoop(LAW, "regeling", { label: "Invorderingswet 1990" }), knoop(HII, "deel", { label: "Hoofdstuk II" }),
      knoop(ART, "artikel", { label: "Artikel 9", artikel: "9" }), knoop(A10, "artikel", { label: "Artikel 10", artikel: "10" })],
    relaties: [rel(LAW, HII, "bevat", "structuur"), rel(HII, ART, "bevat", "structuur"), rel(HII, A10, "bevat", "structuur")] };
  if (iri === HV) return { schema_versie: 1, doel: { bron_iri: iri }, snapshot_id: "s2", artikel_iri: HV,
    verwijzingen_beschikbaar: true, afgekapt: false,
    knopen: [knoop(LAW, "regeling", { label: "Invorderingswet 1990" }), knoop(HV, "deel", { label: "Hoofdstuk V" }),
      knoop(A28, "artikel", { label: "Artikel 28", artikel: "28" })],
    relaties: [rel(LAW, HV, "bevat", "structuur"), rel(HV, A28, "bevat", "structuur")] };
  if (iri.startsWith(A10)) return { schema_versie: 1, doel: { bron_iri: iri }, snapshot_id: "s10", artikel_iri: A10,
    verwijzingen_beschikbaar: true, afgekapt: false,
    knopen: [knoop(LAW, "regeling", { label: "Invorderingswet 1990" }), knoop(A10, "artikel", { label: "Artikel 10", artikel: "10" }),
      knoop(A10L1, "lid", { label: "Lid 1", artikel: "10", lid: "1", tekst: "De ontvanger kan uitstel verlenen." })],
    relaties: [rel(LAW, A10, "bevat", "structuur"), rel(A10, A10L1, "bevat", "structuur")] };
  return { schema_versie: 1, doel: { bron_iri: iri }, snapshot_id: "s9", artikel_iri: ART, verwijzingen_beschikbaar: true, afgekapt: false,
    knopen: [knoop(LAW, "regeling", { label: "Invorderingswet 1990" }), knoop(ART, "artikel", { label: "Artikel 9", artikel: "9" }),
      knoop(L1, "lid", { label: "Lid 1", artikel: "9", lid: "1", tekst: "De ontvanger vordert de belastingaanslag in." }),
      knoop(L2, "lid", { label: "Lid 2", artikel: "9", lid: "2", tekst: "In afwijking van het eerste lid geldt artikel 10." }),
      knoop("element:e1", "markering", { label: "ontvanger", tekst: "ontvanger", klasse: "Rechtssubject", lifecycle: "voorgesteld", element_id: "e1", artikel: "9", lid: "1",
        herkomst: "agent", aandacht: "" }),
      knoop("klasse:Rechtssubject", "klasse", { label: "Rechtssubject", klasse: "Rechtssubject" }),
      knoop(A10, "artikel", { label: "Artikel 10", artikel: "10", rand: true }),
      knoop(STUB, "extern", { label: "Awb, artikel 3", bwb_id: "BWBR0002320", artikel: "3", rand: true })],
    relaties: [rel(LAW, ART, "bevat", "structuur"), rel(ART, L1, "bevat", "structuur"), rel(ART, L2, "bevat", "structuur"),
      rel(L2, L1, "verwijst_naar", "verwijzingen", "het eerste lid"), rel(L2, A10, "verwijst_naar", "verwijzingen", "artikel 10"),
      rel(L1, STUB, "verwijst_naar", "verwijzingen", "artikel 3 van de Awb"),
      rel("element:e1", L1, "markeert", "annotaties"), rel("element:e1", "klasse:Rechtssubject", "heeft_klasse", "annotaties")] };
}
// Na een mutatie (afronden, markeren, …) levert de api een extra markering op lid 2: zo is te zien
// of de graaf zonder herladen meeloopt.
let bijgewerkt = false;
function samenhangNu(iri) {
  const s = samenhang(iri);
  if (!bijgewerkt || iri.startsWith(A10)) return s;
  return { ...s, knopen: [...s.knopen,
      knoop("element:e2", "markering", { label: "artikel 10", tekst: "artikel 10", klasse: "Rechtsobject", lifecycle: "voorgesteld", element_id: "e2", artikel: "9", lid: "2" }),
      knoop("klasse:Rechtsobject", "klasse", { label: "Rechtsobject", klasse: "Rechtsobject" })],
    relaties: [...s.relaties, rel("element:e2", L2, "markeert", "annotaties"), rel("element:e2", "klasse:Rechtsobject", "heeft_klasse", "annotaties")] };
}
const segment = (iri, lid, tekst) => ({ bron_iri: iri, parent_iri: ART, type: "Lid", nummer: lid, label: `Lid ${lid}`, tekst, bron_hash: `h${lid}`, volgorde: Number(lid) });
function weergave(iri) {
  const segs = [segment(L1, "1", "De ontvanger vordert de belastingaanslag in."), segment(L2, "2", "In afwijking van het eerste lid geldt artikel 10.")]
    .filter((s) => iri === ART || s.bron_iri === iri);
  return { schema_versie: 2, snapshot_id: "s9", segmenten: segs,
    doel: { bron_iri: iri, label: iri === ART ? "Artikel 9" : `Artikel 9 lid ${iri.at(-1)}`, type: iri === ART ? "Artikel" : "Lid",
      bwb_id: "BWBR0004770", artikel: "9", lid: iri === ART ? "" : iri.at(-1), citeertitel: "Invorderingswet 1990" },
    lagen: segs.map((s) => ({ id: `laag${s.nummer}`, bron_iri: s.bron_iri, status: "in_review", revisie: 1 })),
    elementen: segs.some((s) => s.bron_iri === L1) ? [{ id: "e1", eigenaar_iri: L1, laag_id: "laag1", klasse: "Rechtssubject",
      tekst: "ontvanger", toelichting: "Voert de invordering uit", lifecycle: "voorgesteld", herkomst: "agent",
      ankers: [{ bron_iri: L1, start: 3, eind: 12, tekst: "ontvanger", bron_hash: "h1" }],
      trace: { kandidaat: { bewijs: [{ detector: "rol", code: "ROL_ACTOR", regel: "jas.subject.actor" }] }, beslissing: { door: "regel" } } }] : [],
    verwijzingen: [],
    // Dekking: in lid 2 gaf "geldt artikel 10" geen enkele detectortreffer.
    dekking: segs.some((s) => s.bron_iri === L2) ? { voltooid: true, structureel: { [L2]: { dimensies: { actor: "uitgevoerd" },
      ongedekt: [{ tekst: "geldt artikel 10", start: 32, eind: 48 }] } } } : {} };
}
/** Wat de kennisgraaf over een knoop weet (api/app/knoopinfo.py): artikel 9 met geldigheid en "genoemd
 *  in" (artikel 10 staat op de kaart, de AWR niet); lid 2 met een uit de tekst herkende verwijzing. */
function knoopInfo(iri) {
  const leeg = { schema_versie: 1, bron_iri: iri, beschikbaar: true, groepen: [], ruw: [], verwijzingen: [] };
  if (iri === ART) return { ...leeg,
    groepen: [
      { naam: "Geldigheid", feiten: [{ eigenschap: "In werking", waarden: [{ tekst: "2026-07-01" }] }] },
      { naam: "Herkomst van de tekst", feiten: [{ eigenschap: "Eerstverantwoordelijke", waarden: [{ tekst: "Financiën" }] }] },
      { naam: "Genoemd in", feiten: [{ eigenschap: "Genoemd in", waarden: [
        { tekst: "Algemene wet inzake rijksbelastingen", iri: "urn:bwb:BWBR0002320" }, { tekst: "Artikel 10", iri: A10 }] }] },
      { naam: "Vindplaats", feiten: [{ eigenschap: "JCI", waarden: [{ tekst: "jci1.3:c:BWBR0004770&hoofdstuk=II&artikel=9&lid=2&z=2026-10-01&g=2026-10-01" }] }] }],
    ruw: [{ predicaat: "bwb:inwerking", waarde: "2026-07-01" }, { predicaat: "bwb:nummer", waarde: "9" }, { predicaat: "eli:has_part", waarde: L1, iri: L1 }] };
  if (iri === L2) return { ...leeg, verwijzingen: [{ richting: "uit", van: L2, naar: A10, anker: "artikel 10", soort: "tekstueel",
    doel_soort: "artikel", doel_pad: "", betrouwbaarheid: "laag" }] };
  return leeg;
}

const berichten = [
  { rol: "user", tekst: "Wat regelt artikel 9 lid 2 van de Invorderingswet?", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" },
  { rol: "assistant", tekst: "Artikel 9 lid 2 wijkt af van het eerste lid en verwijst naar artikel 10.", denk: "",
    bronnen: [{ label: "Invorderingswet 1990, artikel 9 lid 2", uri: "jci1.3:c:BWBR0004770&artikel=9&lid=2" }],
    annotatie_slug: "", annotatie_titel: "" },
];

// Een antwoord dat twee artikelen noemt, met de bronnen in de canonieke vorm van graph-qa.
const berichtenTwee = [
  { rol: "user", tekst: "Hoe verhouden artikel 9 en 10 zich?", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" },
  { rol: "assistant", tekst: "Artikel 9 lid 2 verwijst naar artikel 10, dat uitstel regelt.", denk: "",
    bronnen: [
      { label: "Artikel 9, lid 2", uri: L2, bron_iri: L2, jci: "jci1.3:c:BWBR0004770&artikel=9&lid=2", bwb_id: "BWBR0004770", soort: "lid", regeling: "Invorderingswet 1990" },
      { label: "Artikel 10", uri: A10, bron_iri: A10, bwb_id: "BWBR0004770", soort: "artikel", regeling: "Invorderingswet 1990" },
      { label: "Invorderingswet 1990", uri: LAW, bron_iri: LAW, bwb_id: "BWBR0004770", soort: "regeling", regeling: "Invorderingswet 1990" }],
    annotatie_slug: "", annotatie_titel: "" },
];

// Een overzichtsantwoord: de duiding van Lex plus het overzicht uit de graaf (graph-qa
// `agent/overzicht.py`), zoals het in het bericht bewaard wordt.
const berichtenOverzicht = [
  { rol: "user", tekst: "Welke artikelen gaan over invordering?", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" },
  { rol: "assistant", tekst: "De invordering staat vooral in de Invorderingswet 1990.", denk: "",
    overzicht: {
      gevraagd: "invordering", onderwerp_opbouw: "invordering", onderwerp_tekst: "invordering", scope: [], volledig: true,
      definities: [], trefwoorden: [],
      regelingen: [{ bwb_id: "BWBR0004770", citeertitel: "Invorderingswet 1990", soort: "wet",
        delen: [{ iri: HII, soort: "Hoofdstuk", label: "Hoofdstuk II – Invordering in eerste aanleg", jci: "",
          bepalingen: [{ iri: ART, nummer: "9", label: "Artikel 9" }, { iri: A10, nummer: "10", label: "Artikel 10" }], subdelen: [] },
          { iri: HV, soort: "Hoofdstuk", label: "Hoofdstuk V – Invorderingsrente", jci: "",
            bepalingen: [{ iri: A28, nummer: "28", label: "Artikel 28" }], subdelen: [] }],
        ook_genoemd: [{ iri: `${LAW}:artikel:4`, nummer: "4", label: "Artikel 4", in_deel: { iri: `${LAW}:hoofdstuk:I`, label: "Hoofdstuk I – Algemene bepalingen" } }] }],
    },
    bronnen: [
      { label: "Hoofdstuk II – Invordering in eerste aanleg", uri: HII, bron_iri: HII, bwb_id: "BWBR0004770", soort: "hoofdstuk", regeling: "Invorderingswet 1990" },
      { label: "Artikel 4", uri: `${LAW}:artikel:4`, bron_iri: `${LAW}:artikel:4`, bwb_id: "BWBR0004770", soort: "artikel", regeling: "Invorderingswet 1990" }],
    annotatie_slug: "", annotatie_titel: "" },
];

// Een overzicht met de grens van 30 delen (`MAX_OVERZICHT_DOELEN`): de twee hoofdstukken van de Iw en 28
// hoofdstukken uit de proefregelingen van de kennisgraaf hieronder.
const PROEFDELEN = Array.from({ length: 28 }, (_, i) => `urn:bwb:BWBR90000${1 + Math.floor(i / 8)}0:hoofdstuk:${1 + (i % 8)}`);
const berichtenOverzicht30 = [
  { rol: "user", tekst: "Welke delen gaan over termijnen?", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "" },
  { rol: "assistant", tekst: "Termijnen staan op veel plaatsen.", denk: "",
    overzicht: { ...berichtenOverzicht[1].overzicht, gevraagd: "termijnen",
      regelingen: [berichtenOverzicht[1].overzicht.regelingen[0], { bwb_id: "BWBR9000010", citeertitel: "Proefregelingen", soort: "wet",
        delen: PROEFDELEN.map((iri) => ({ iri, soort: "Hoofdstuk", label: `Hoofdstuk ${iri.split(":").at(-1)}`, jci: "", bepalingen: [], subdelen: [] })),
        ook_genoemd: [] }] },
    bronnen: [], annotatie_slug: "", annotatie_titel: "" },
];

/** De hele kennisgraaf (`/graaf`) op echte schaal: de Invorderingswet van de fixtures (zodat de focus van
 *  een overzicht erin valt) plus gegenereerde regelingen tot ~6.500 knopen en ~2.000 verwijzingen.
 *  Deterministisch (vaste reeks), één keer opgebouwd. */
let kennisgraafCache;
function kennisgraaf() {
  if (kennisgraafCache) return kennisgraafCache;
  let t = 7;
  const r = () => (t = (Math.imul(t, 1103515245) + 12345) >>> 0) / 4294967296;
  const knopen = [], relaties = [], bepalingen = [];
  const voeg = (k) => knopen.push(k);
  for (const k of [...samenhang(ART).knopen, ...samenhang(HII).knopen, ...samenhang(HV).knopen, ...samenhang(A10).knopen]) {
    if (!knopen.some((x) => x.id === k.id) && k.soort !== "markering" && k.soort !== "klasse" && !k.rand) voeg({ ...k, tekst: "" });
  }
  for (const [a, b] of [[LAW, HII], [LAW, HV], [HII, ART], [HII, A10], [HV, A28], [ART, L1], [ART, L2], [A10, A10L1]]) relaties.push(rel(a, b, "bevat", "structuur"));
  voeg(knoop(`${LAW}:hoofdstuk:I`, "deel", { label: "Hoofdstuk I" })); relaties.push(rel(LAW, `${LAW}:hoofdstuk:I`, "bevat", "structuur"));
  voeg(knoop(`${LAW}:artikel:4`, "artikel", { label: "Artikel 4", artikel: "4" })); relaties.push(rel(`${LAW}:hoofdstuk:I`, `${LAW}:artikel:4`, "bevat", "structuur"));
  for (let g = 1; g <= 6; g++) {
    const bwb = `BWBR90000${g}0`, wortel = `urn:bwb:${bwb}`;
    voeg(knoop(wortel, "regeling", { label: `Proefregeling ${g}`, bwb_id: bwb }));
    for (let h = 1; h <= 8; h++) {
      const hid = `${wortel}:hoofdstuk:${h}`;
      voeg(knoop(hid, "deel", { label: `Hoofdstuk ${h}`, bwb_id: bwb })); relaties.push(rel(wortel, hid, "bevat", "structuur"));
      for (let a = 1; a <= 44; a++) {
        const nr = `${h}.${a}`, aid = `${wortel}:artikel:${nr}`;
        voeg(knoop(aid, "artikel", { label: `Artikel ${nr}`, artikel: nr, bwb_id: bwb })); relaties.push(rel(hid, aid, "bevat", "structuur"));
        bepalingen.push(aid);
        for (let l = 1; l <= 2; l++) {
          const lid = `${aid}:lid:${l}`;
          voeg(knoop(lid, "lid", { label: `Lid ${l}`, artikel: nr, lid: String(l), bwb_id: bwb })); relaties.push(rel(aid, lid, "bevat", "structuur"));
        }
      }
    }
  }
  for (let i = 0; i < 2000; i++) {
    const a = bepalingen[Math.floor(r() * bepalingen.length)], b = bepalingen[Math.floor(r() * bepalingen.length)];
    if (a !== b) relaties.push(rel(a, b, "verwijst_naar", "verwijzingen", "artikel"));
  }
  kennisgraafCache = { schema_versie: 1, versie: "proef", regelingen: [], knopen, relaties };
  return kennisgraafCache;
}

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });

async function nieuwePagina({ width = 1440, height = 1000, webgl = true } = {}) {
  const page = await browser.newPage({ viewport: { width, height } });
  const log = { errors: [], console: [], samenhang: [], samenhangMeer: [], mutaties: [], graaf: [] };
  page.on("pageerror", (e) => log.errors.push(e.message));
  // React meldt in dev dat de CSP geen eval toestaat; in productie gebruikt React geen eval.
  page.on("console", (m) => { if (m.type() === "error" && !/React will never use eval\(\) in production/.test(m.text())) log.console.push(m.text()); });
  await page.context().addCookies(await sessieCookies(base));
  await page.addInitScript((webgl) => {
    localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true }));
    if (!webgl) {
      const orig = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (type, ...rest) { return /webgl/.test(type) ? null : orig.call(this, type, ...rest); };
    }
  }, webgl);
  await page.route("**/api/**", async (route) => {
    const req = route.request(), url = new URL(req.url());
    if (url.pathname.startsWith("/api/auth/")) return route.continue();
    if (req.method() !== "GET") { log.mutaties.push(`${req.method()} ${url.pathname}`); bijgewerkt = true; }
    if (url.pathname.endsWith("/v2/capabilities")) return route.fulfill({ json: { schema_versie: 2, bronnodes_actief: true, samenhang: true } });
    if (url.pathname.endsWith("/v2/samenhang")) { log.samenhang.push(url.searchParams.get("bron_iri")); return route.fulfill({ json: samenhangNu(url.searchParams.get("bron_iri")) }); }
    if (url.pathname.endsWith("/v2/samenhang/meer")) {
      const iris = url.searchParams.getAll("bron_iri");
      log.samenhangMeer.push(iris);
      // Zoals de api (`MAX_SAMENHANG_MEER`): meer dan 30 doelen weigert het hele verzoek.
      if (iris.length > 30) return route.fulfill({ status: 422, json: { detail: "Hoogstens 30 doelen per verzoek." } });
      return route.fulfill({ json: { resultaten: iris.map(samenhangNu), fouten: [] } });
    }
    if (url.pathname.endsWith("/v2/graaf")) { log.graaf.push(url.search); return route.fulfill({ json: kennisgraaf() }); }
    if (url.pathname.endsWith("/v2/knoop")) return route.fulfill({ json: knoopInfo(url.searchParams.get("bron_iri")) });
    if (url.pathname.endsWith("/v2/weergave")) return route.fulfill({ json: weergave(url.searchParams.get("bron_iri")) });
    if (url.pathname.endsWith("/v2/elementen/e1")) return route.fulfill({ json: { element: weergave(ART).elementen[0] } });
    if (url.pathname.endsWith("/v2/elementen/e1/graaf")) return route.fulfill({ json: { element_id: "e1", laag_id: "laag1",
      turtle: "<urn:jas:element:e1> a <urn:jas-ns:Markering> .",
      graafcontrole: { laag_id: "laag1", revisie: 1, status: "achterstand", afwijkingen: [], shacl: null } } });
    if (url.pathname === "/api/gesprekken/g1") return route.fulfill({ json: { id: "g1", user_id: "browser-test", titel: "Samenhang", berichten } });
    if (url.pathname === "/api/gesprekken/g2") return route.fulfill({ json: { id: "g2", user_id: "browser-test", titel: "Twee artikelen", berichten: berichtenTwee } });
    if (url.pathname === "/api/gesprekken/g3") return route.fulfill({ json: { id: "g3", user_id: "browser-test", titel: "Overzicht", berichten: berichtenOverzicht } });
    if (url.pathname === "/api/gesprekken/g4") return route.fulfill({ json: { id: "g4", user_id: "browser-test", titel: "Dertig delen", berichten: berichtenOverzicht30 } });
    if (url.pathname === "/api/gesprekken") return route.fulfill({ json: [{ id: "g1", titel: "Samenhang", aantal_berichten: 2 }] });
    if (url.pathname.includes("/actief")) return route.fulfill({ status: 404, json: {} });
    if (url.pathname.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
    if (url.pathname.includes("/verklaringen")) return route.fulfill({ json: {
      besluit: { regel: { naam: "vaste regel", uitleg: "" } }, regels: { "jas.subject.actor": { naam: "Handelende partij", uitleg: "" } } } });
    return route.fulfill({ status: 200, json: [] });
  });
  return { page, log };
}

const detail = (page) => page.getByTestId("graaf-detail");
const graaf = (page) => page.getByTestId("samenhang-graaf");
const zoekveld = (page) => page.getByRole("combobox", { name: "Zoek in de graaf" });
const gekozen = (page) => graaf(page).getAttribute("data-selectie");
/** Kies een knoop via het zoekveld (ook als een laag hem verbergt). */
async function zoekEnKies(page, vraag, id) {
  await zoekveld(page).fill(vraag);
  const optie = page.locator(`[role="option"][data-knoop-id="${id}"]`);
  for (let i = 0; i < 3; i++) {
    try { await optie.click({ timeout: 5000 }); return; } catch { await zoekveld(page).click(); }
  }
  await optie.click();
}
/** Wat de zoeklijst over een knoop zegt: bestaat hij, en verbergt een laag hem? */
async function zoekStand(page, vraag, id) {
  await zoekveld(page).fill(vraag);
  const optie = page.locator(`[role="option"][data-knoop-id="${id}"]`);
  const er = await optie.count() > 0 || await optie.waitFor({ timeout: 1500 }).then(() => true, () => false);
  const tekst = er ? await optie.innerText() : "";
  await zoekveld(page).fill("");
  return { er, verborgen: /laag staat uit/.test(tekst) };
}
async function detailsOpen(page) {
  const knop = page.getByRole("button", { name: "Details tonen" });
  if (await knop.count()) await knop.click();
}
/** Een klik zoals een trackpad of een snelle muis hem geeft: een paar pixels trilling tussen indrukken
 *  en loslaten. Sigma telt bewegingen in plaats van afstand en zag zo'n klik als slepen. */
async function trilKlik(page, x, y) {
  await page.mouse.move(x, y);
  await page.mouse.down();
  for (const [dx, dy] of [[1, 0], [1, 1], [0, 1], [-1, 1], [0, 0]]) await page.mouse.move(x + dx, y + dy);
  await page.mouse.up();
}
async function wachtGereed(page) {
  await page.locator('[data-testid="samenhang-graaf"][data-gereed="true"]').waitFor({ timeout: 30000 });
  await page.getByTestId("graaf-tekenaar").waitFor();
}

// 1. Breed scherm: chatknop opent het paneel op de graaf; sigma tekent, de hint staat er.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina();
  await page.goto(`${base}/workbench?gesprek=g1`);
  // Citatie-chip: "Artikel 9 lid 2" hoort bij de bron van de beurt en opent een bronkaart;
  // "artikel 10" heeft geen bron en blijft gewone tekst.
  await page.getByRole("button", { name: "Artikel 9 lid 2", exact: true }).click();
  await page.getByTestId("bronkaart").getByText("Artikel 9, lid 2", { exact: true }).waitFor();
  await page.getByTestId("bronkaart").getByRole("button", { name: "Bekijk in de graaf" }).waitFor();
  await page.screenshot({ path: `${shots}/0-bronkaart.png` });
  assert.equal(await page.getByRole("button", { name: "artikel 10", exact: true }).count(), 0);
  await page.keyboard.press("Escape");
  await page.getByTestId("bronkaart").waitFor({ state: "detached" });
  await page.getByRole("button", { name: /^Bekijk samenhang van .* in de graaf$/ }).first().click();
  await graaf(page).waitFor();
  assert.deepEqual([...new Set(log.samenhang)], [L2], "de graaf vraagt de samenhang van de geciteerde bepaling");
  assert.equal(await page.getByRole("button", { name: "Graaf", exact: true }).getAttribute("aria-pressed"), "true");
  await wachtGereed(page);
  assert.equal(await page.getByTestId("graaf-tekenaar").getAttribute("data-knopen"), "8");
  assert.match(await page.getByTestId("graaf-telling").innerText(), /1 regeling · 3 bepalingen · 1 markering · 3 verwijzingen/);
  // Geen beginkeuze: het begin is de focus – lid 2 met wat erop ligt en waarnaar het verwijst.
  assert.equal(await gekozen(page), "", "het begin is de focus, geen keuze");
  assert.match(await page.getByTestId("graaf-focus").innerText(), /Nadruk op wat het antwoord noemt \(1 deel of bepaling/);
  assert.match(await detail(page).innerText(), /Dit antwoord[\s\S]*Artikel 9 · lid 2/i);
  await page.getByTestId("graaf-hint").waitFor();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${shots}/1-graaf.png` });

  // 2. Zoeken kiest een knoop; de inspector toont meteen de wettekst en de relaties per soort; de hint
  // verdwijnt.
  await zoekEnKies(page, "lid 2", L2);
  await page.getByTestId("graaf-hint").waitFor({ state: "detached" });
  assert.match(await detail(page).innerText(), /Artikel 9 · lid 2[\s\S]*In afwijking van het eerste lid[\s\S]*Verwijst naar/);
  // De lijn naar artikel 10 is alleen uit de tekst herkend: dat staat bij de regel, met een badge.
  await detail(page).getByTestId("graaf-verwijzing").first().waitFor();
  assert.match(await detail(page).getByTestId("graaf-verwijzing").first().innerText(), /uit de tekst herkend · artikel[\s\S]*lage betrouwbaarheid/);

  // 3. Een randbepaling kies je vanuit de inspector; de hoofdactie laadt haar erbij (één keer).
  await detail(page).getByRole("button", { name: /^Artikel 10\b/ }).click();
  await page.getByRole("button", { name: "In de graaf laden" }).click();
  for (let i = 0; i < 40 && !(await zoekStand(page, "lid 1", A10L1)).er; i++) await page.waitForTimeout(150);
  assert.ok((await zoekStand(page, "lid 1", A10L1)).er, "het bijgeladen artikel staat in de graaf");
  assert.deepEqual([...new Set(log.samenhang)], [L2, A10], "laden haalt het doelartikel op");
  assert.equal(log.samenhang.filter((i) => i === A10).length, 1, "één keer bijladen per klik");

  // 4. Een niet-geïmporteerde bepaling: vindbaar, zonder hoofdactie.
  await zoekEnKies(page, "awb", STUB);
  assert.match(await detail(page).innerText(), /niet in de kennisgraaf/);
  assert.equal(await page.getByRole("button", { name: "In de graaf laden" }).count(), 0, "extern is niet te laden");

  // 5. Klikken in de graaf: een knoop kiezen, de achtergrond heft de keuze op.
  await zoekEnKies(page, "lid 1", L1);
  await page.getByRole("button", { name: "Centreren" }).click();
  await page.waitForTimeout(700);
  await page.getByRole("button", { name: "Selectie opheffen" }).click();
  assert.equal(await gekozen(page), "");
  const doek = await page.getByTestId("graaf-tekenaar").boundingBox();
  // De hover noemt de volledige naam, niet het kaartlabel "Lid 1".
  await page.mouse.move(doek.x + doek.width / 2, doek.y + doek.height / 2);
  for (let i = 0; i < 20 && !(await page.getByTestId("graaf-tekenaar").getAttribute("data-hover-naam")); i++) await page.waitForTimeout(100);
  assert.equal(await page.getByTestId("graaf-tekenaar").getAttribute("data-hover-naam"), "Artikel 9 · lid 1");
  await trilKlik(page, doek.x + doek.width / 2, doek.y + doek.height / 2);
  for (let i = 0; i < 20 && (await gekozen(page)) !== L1; i++) await page.waitForTimeout(100);
  assert.equal(await gekozen(page), L1, `een klik met wat trilling op de knoop kiest hem (${await gekozen(page)})`);
  await page.screenshot({ path: `${shots}/1b-keuze.png` });
  // Twee klikken binnen sigma's dubbelklikvenster tellen als dubbelklik (zoomen), niet als twee klikken.
  await page.waitForTimeout(500);
  // Slepen is geen klik: de keuze blijft staan.
  await page.mouse.move(doek.x + 8, doek.y + doek.height / 2);
  await page.mouse.down();
  for (let i = 1; i <= 8; i++) await page.mouse.move(doek.x + 8 + i * 5, doek.y + doek.height / 2);
  await page.mouse.up();
  await page.waitForTimeout(400);
  assert.equal(await gekozen(page), L1, "slepen kiest niets en heft niets op");
  await page.waitForTimeout(400);
  await trilKlik(page, doek.x + 8, doek.y + doek.height / 2);
  for (let i = 0; i < 20 && (await gekozen(page)) !== ""; i++) await page.waitForTimeout(100);
  assert.equal(await gekozen(page), "", "een klik met wat trilling op de achtergrond heft de keuze op");
  assert.match(await detail(page).innerText(), /Dit antwoord/i, "en brengt het begin terug");
  // "Terug naar het antwoord" staat er zolang er een keuze is, en brengt het begin terug.
  assert.equal(await page.getByTestId("graaf-terug").count(), 0);
  await zoekEnKies(page, "lid 1", L1);
  await page.getByTestId("graaf-terug").click();
  assert.equal(await gekozen(page), "", "terug naar het antwoord heft de keuze op");
  assert.equal(await page.getByTestId("graaf-terug").count(), 0);

  // 6. Markering: alles staat meteen in de inspector – de span in zijn lid, de toelichting en het
  // waarom – zonder naar de tekst te gaan; "Beoordeel in de tekst" wisselt met dezelfde keuze.
  await zoekEnKies(page, "ontvanger", "element:e1");
  assert.match(await detail(page).innerText(), /Rechtssubject/);
  await detail(page).getByText("Voert de invordering uit", { exact: false }).waitFor();
  assert.equal(await detail(page).locator('mark[data-element="e1"]').innerText(), "ontvanger", "de span staat op zijn anker");
  assert.match(await detail(page).getByTestId("graaf-knooptekst").innerText(), /De ontvanger vordert de belastingaanslag in\./);
  await detail(page).getByText("Handelende partij", { exact: true }).waitFor();
  await detail(page).getByText("vaste regel", { exact: true }).waitFor();
  await page.screenshot({ path: `${shots}/1c-markering.png` });
  await detail(page).getByText("Technisch detail", { exact: true }).click();
  await detail(page).getByText("Nog niet in de graaf bijgewerkt", { exact: false }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Tekst", exact: true }).getAttribute("aria-pressed"), "false", "je blijft in de graaf");
  // Het paneel toont lid 2; e1 staat op lid 1. Naar de tekst springen zou niets tonen: dan opent het
  // paneel op lid 1 in plaats daarvan.
  assert.equal(await page.getByRole("button", { name: "Beoordeel in de tekst" }).count(), 0, "e1 staat niet in de tekst van het paneel");
  await page.getByRole("button", { name: "Open in het paneel" }).waitFor();
  await page.getByRole("button", { name: "Tekst", exact: true }).click();
  await page.locator("[data-artefact]").waitFor();
  await page.getByRole("button", { name: "Graaf", exact: true }).click();
  assert.match(await detail(page).innerText(), /ontvanger/, "keuze blijft na terugkeren");

  // 6b. Een JAS-klasse kiezen vanuit de inspector.
  await detailsOpen(page);
  await detail(page).getByRole("button", { name: "Rechtssubject", exact: true }).click();
  assert.match(await detail(page).innerText(), /JAS-klasse[\s\S]*Rechtssubject[\s\S]*Markeringen[\s\S]*ontvanger/i);

  // 7. ✕ heft de keuze op: de inspector zegt wat er geladen is en hoe kiezen werkt.
  await page.getByRole("button", { name: "Selectie opheffen" }).click();
  assert.match(await detail(page).innerText(), /bepalingen[\s\S]*Klik een knoop/);

  // 7a. Artikel 9: de inspector toont de tekst van álle leden, niet alleen het lid van het paneel.
  await zoekEnKies(page, "artikel 9", ART);
  await detail(page).getByTestId("graaf-knooptekst").waitFor();
  assert.match(await detail(page).getByTestId("graaf-knooptekst").innerText(), /De ontvanger vordert[\s\S]*In afwijking van het eerste lid/);
  // Uit de kennisgraaf: geldigheid in gewone woorden, "genoemd in" kiest wat op de kaart staat en linkt
  // de rest, en het ruwe vangnet telt alle triples.
  const feiten = detail(page).getByTestId("graaf-feiten");
  await feiten.waitFor();
  assert.match(await feiten.innerText(), /Geldigheid[\s\S]*In werking[\s\S]*1 juli 2026[\s\S]*Genoemd in/);
  // Een lange waarde zonder spaties (een JCI) breekt af in plaats van uit de inspector te lopen.
  const breedte = await feiten.evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }));
  assert.ok(breedte.scroll <= breedte.client + 1, `niets loopt uit beeld (${breedte.scroll} > ${breedte.client})`);
  assert.equal(await feiten.getByRole("link", { name: "Algemene wet inzake rijksbelastingen" }).getAttribute("href"), "https://wetten.overheid.nl/BWBR0002320");
  assert.match(await feiten.getByTestId("graaf-ruw").textContent(), /Alle eigenschappen uit de graaf \(3\)/);
  await page.screenshot({ path: `${shots}/7a-kennisgraaf-feiten.png` });
  await feiten.getByRole("button", { name: "Artikel 10" }).click();
  assert.equal(await gekozen(page), A10, "een knoop uit 'genoemd in' die op de kaart staat, kies je in de graaf");
  await page.getByRole("button", { name: "Selectie opheffen" }).click();

  // 7b. Een markering in de wettekst van de inspector aanklikken kiest haar in de graaf.
  await zoekEnKies(page, "lid 1", L1);
  await detail(page).locator('mark[data-element="e1"]').click();
  assert.equal(await gekozen(page), "element:e1", "de span kiest de markering");
  await page.getByRole("button", { name: "Selectie opheffen" }).click();

  // 8. Vergroten; Escape van binnen naar buiten: keuze op, dan verkleinen.
  await zoekEnKies(page, "lid 1", L1);
  await page.getByRole("button", { name: "Vergroten" }).click();
  assert.equal(await graaf(page).getAttribute("data-vergroot"), "true");
  await wachtGereed(page);
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${shots}/2-vergroot.png` });
  await page.keyboard.press("Escape");
  assert.match(await detail(page).innerText(), /Klik een knoop/, "eerste Escape heft de keuze op");
  assert.equal(await graaf(page).getAttribute("data-vergroot"), "true");
  await page.keyboard.press("Escape");
  assert.equal(await graaf(page).getAttribute("data-vergroot"), "false");

  // 8a. In de smalle zijkolom van de vergrote graaf loopt geen label over zijn waarde.
  await page.getByRole("button", { name: "Vergroten" }).click();
  await wachtGereed(page);
  await zoekEnKies(page, "artikel 9", ART);
  await detail(page).getByTestId("graaf-feiten").waitFor();
  const overloop = await detail(page).getByTestId("graaf-feiten").evaluate((el) =>
    [...el.querySelectorAll("dt:not(.sr-only), dd")].filter((x) => x.scrollWidth > x.clientWidth + 1).map((x) => x.textContent));
  assert.deepEqual(overloop, [], `geen label of waarde loopt uit zijn vak: ${JSON.stringify(overloop)}`);
  await page.screenshot({ path: `${shots}/8a-feiten-vergroot.png` });
  // Het muiswiel boven de inspector scrolt hem (er is één scrollvak; een tweede eromheen slikte het wiel).
  await page.setViewportSize({ width: 1440, height: 560 });
  await page.waitForTimeout(400);
  const vak = await detail(page).boundingBox();
  await page.mouse.move(vak.x + vak.width / 2, vak.y + Math.min(vak.height / 2, 200));
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(500);
  const gescrold = await detail(page).evaluate((el) => Math.max(...[el, ...el.querySelectorAll("*")].map((k) => k.scrollTop)));
  assert.ok(gescrold > 0, "het muiswiel scrolt de inspector");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.waitForTimeout(300);

  // De zijbalk is breder dan vroeger (320 px), en in te klappen tot een strook; de stand blijft.
  const zijbalk = page.getByTestId("graaf-zijbalk"), doekVak = page.getByTestId("graaf-tekenaar");
  const breed = (await zijbalk.boundingBox()).width, doekBreed = (await doekVak.boundingBox()).width;
  assert.ok(breed >= 352, `zijbalk breed genoeg (${breed}px)`);
  await page.getByRole("button", { name: "Zijbalk inklappen" }).click();
  assert.equal(await graaf(page).getAttribute("data-zijbalk"), "in");
  await page.waitForTimeout(400);
  assert.ok((await zijbalk.boundingBox()).width <= 48, "ingeklapt is het een strook");
  assert.ok((await doekVak.boundingBox()).width > doekBreed + 250, "het canvas krijgt de ruimte");
  await page.getByTestId("graaf-zijbalk-keuze").waitFor();
  await page.screenshot({ path: `${shots}/8a-zijbalk-ingeklapt.png` });
  // Onthouden: verkleinen en weer vergroten (de graaf remount) houdt hem ingeklapt.
  await page.getByRole("button", { name: "Verkleinen" }).click();
  await page.getByRole("button", { name: "Vergroten" }).click();
  await wachtGereed(page);
  assert.equal(await graaf(page).getAttribute("data-zijbalk"), "in", "de ingeklapte stand blijft");
  await page.getByRole("button", { name: "Zijbalk uitklappen" }).click();
  await page.waitForTimeout(400);
  assert.equal(Math.round((await zijbalk.boundingBox()).width), Math.round(breed), "uitgeklapt weer op breedte");
  await page.getByRole("button", { name: "Verkleinen" }).click();

  // 8b. Laag Dekking: het lid met een zinsdeel zonder detectortreffer toont dat in de inspector.
  await zoekEnKies(page, "lid 2", L2);
  await detailsOpen(page);
  await detail(page).getByTestId("graaf-dekking").getByText("“geldt artikel 10”").waitFor();
  await page.getByRole("button", { name: "Lagen" }).click();
  const lagen = page.getByRole("group", { name: "Lagen en legenda" });
  await lagen.getByTestId("graaf-legenda").getByText("Gedimd: niet verbonden met je keuze").waitFor();
  await page.screenshot({ path: `${shots}/8b-lagen.png` });
  const dekkingLaag = lagen.getByRole("checkbox", { name: /Dekking/ });
  assert.ok(await dekkingLaag.isChecked(), "de laag Dekking staat standaard aan");
  await dekkingLaag.uncheck();
  assert.equal(await detail(page).getByTestId("graaf-dekking").count(), 0, "laag uit haalt de dekking uit de inspector");
  await dekkingLaag.check();

  // 9. Lagen bepalen wat zichtbaar is; zoeken zegt het, en een keuze daaruit zet de laag weer aan.
  await lagen.getByRole("checkbox", { name: /Annotaties/ }).uncheck();
  assert.ok((await zoekStand(page, "ontvanger", "element:e1")).verborgen, "annotaties uit verbergt markeringen");
  await zoekEnKies(page, "ontvanger", "element:e1");
  if (!(await lagen.count())) await page.getByRole("button", { name: "Lagen" }).click();
  assert.ok(await lagen.getByRole("checkbox", { name: /Annotaties/ }).isChecked(), "kiezen zet de nodige laag aan");
  await lagen.getByLabel("Markeringen", { exact: true }).selectOption("aandacht");
  assert.ok((await zoekStand(page, "ontvanger", "element:e1")).verborgen, "het markeringsfilter verbergt e1");
  assert.ok(!(await zoekStand(page, "lid 1", L1)).verborgen, "structuur blijft staan");
  await lagen.getByLabel("Markeringen", { exact: true }).selectOption("alle");
  assert.ok(!(await zoekStand(page, "ontvanger", "element:e1")).verborgen, "alle brengt e1 terug");
  await page.getByRole("button", { name: "Lagen" }).focus();
  await page.keyboard.press("Escape");
  assert.equal(await lagen.count(), 0, "Escape sluit het lagenpaneel");

  // 10. Beeldknoppen.
  for (const naam of ["Inzoomen", "Uitzoomen", "Alles in beeld"]) await page.getByRole("button", { name: naam }).click();

  // 11. Vraag Lex over een bron zet de vraag klaar, zonder iets te versturen.
  await zoekEnKies(page, "lid 1", A10L1);
  await page.getByRole("button", { name: "Vraag Lex" }).click();
  assert.match(await page.locator("textarea").inputValue(), /Hoe hangt Artikel 10 · lid 1 \(BWBR0004770, artikel 10, lid 1\)/);
  assert.deepEqual(log.mutaties, [], "de graaf muteert niets");

  // 12. Een annotatiewijziging werkt de graaf bij zonder herladen, en de kaart verschuift niet. Zolang
  // de Tekst-tab openstaat, haalt de graaf niets op; terug op de graaf precies één ronde.
  const voor = log.samenhangMeer.length;
  await page.getByRole("button", { name: "Tekst", exact: true }).click();
  await page.getByRole("button", { name: /afronden/i }).first().click();
  await page.waitForTimeout(800);
  assert.equal(log.samenhangMeer.length, voor, "met de graaf onzichtbaar wordt er niets opgehaald");
  await page.getByRole("button", { name: "Graaf", exact: true }).click();
  for (let i = 0; i < 40 && !(await zoekStand(page, "Rechtsobject", "element:e2")).er; i++) await page.waitForTimeout(250);
  assert.ok((await zoekStand(page, "Rechtsobject", "element:e2")).er, "de nieuwe markering staat in de graaf");
  assert.equal(log.samenhangMeer.length, voor + 1, "terug op de graaf: één verversing");
  assert.deepEqual([...log.samenhangMeer.at(-1)].sort(), [A10, L2].sort(), "alle geladen delen in één verzoek");
  assert.ok((await zoekStand(page, "lid 1", A10L1)).er, "het bijgeladen artikel blijft");
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 13. Een antwoord dat twee artikelen noemt: de knop zegt het, de graaf laadt beide, en een knoop uit
// het tweede artikel opent dát in het paneel.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina();
  await page.goto(`${base}/workbench?gesprek=g2`);
  await page.getByRole("button", { name: /^Bronnen \(3\)/ }).click();
  assert.match(await page.locator('[data-tour="bronnen"]').innerText(), /Invorderingswet 1990 – Artikel 9, lid 2, Artikel 10/);
  await page.getByRole("button", { name: "Bekijk samenhang van de 2 genoemde artikelen in de graaf" }).click();
  await graaf(page).waitFor();
  await page.getByText("Samenhang van 2 artikelen").waitFor();
  assert.deepEqual(log.samenhangMeer.at(-1), [L2, A10], "beide genoemde artikelen in één verzoek");
  await wachtGereed(page);
  await zoekEnKies(page, "Artikel 10", A10);
  await page.getByRole("button", { name: "Open in het paneel" }).waitFor();
  await page.screenshot({ path: `${shots}/2b-twee-artikelen.png` });
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 14. Een overzichtsantwoord: het blok toont het overzicht uit het bericht; "Dit antwoord" laadt de delen
// uit dát overzicht – niet uit de tekst – in één verzoek.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina();
  await page.goto(`${base}/workbench?gesprek=g3`);
  const blok = page.getByTestId("overzicht");
  await blok.waitFor();
  // `.thread-rij` heeft content-visibility: auto – eerst in beeld, dan lezen.
  await blok.scrollIntoViewIfNeeded();
  await blok.getByText("Hoofdstuk II – Invordering in eerste aanleg").waitFor();
  assert.match(await blok.innerText(), /Hoofdstuk II – Invordering in eerste aanleg\s+art\. 9, art\. 10/);
  await blok.getByRole("button", { name: /Noemt het onderwerp ook \(1\)/ }).click();
  assert.match(await blok.innerText(), /art\. 4 · in Hoofdstuk I – Algemene bepalingen/);
  assert.equal(await page.getByRole("button", { name: /^Bronnen \(/ }).count(), 0, "geen bronnenlijst bij een overzicht");
  await page.getByRole("button", { name: "Bekijk de 2 delen in de kennisgraaf" }).click();
  await graaf(page).waitFor();
  await page.getByRole("button", { name: "Dit antwoord" }).click();
  await page.getByRole("heading", { name: /^Samenhang van 2 delen/ }).waitFor();
  assert.deepEqual(log.samenhang, [], "geen los verzoek per deel");
  assert.deepEqual(log.samenhangMeer.at(-1), [HII, HV], "één verzoek met de delen in overzichtsvolgorde");
  await wachtGereed(page);
  await zoekEnKies(page, "Artikel 10", A10);
  await page.getByRole("button", { name: "Bekijk in de tekst" }).waitFor();
  await page.screenshot({ path: `${shots}/2c-overzicht.png` });
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 14b. Een overzicht opent de hele kennisgraaf (~6.500 knopen) met de nadruk op alles uit het overzicht;
// koppen en nummers in het blok wijzen hun knoop aan en kiezen hem; de tweede keer komt de layout uit de
// cache.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina();
  await page.goto(`${base}/workbench?gesprek=g3`);
  const blok = page.getByTestId("overzicht");
  await blok.waitFor();
  await blok.scrollIntoViewIfNeeded();
  const begin = Date.now();
  await page.getByRole("button", { name: "Bekijk de 2 delen in de kennisgraaf" }).click();
  await page.getByRole("heading", { name: /^De hele kennisgraaf/ }).waitFor();
  await page.getByTestId("graaf-laadbalk").waitFor();
  await page.locator('[data-testid="samenhang-graaf"][data-gereed="true"]').waitFor({ timeout: 60000 });
  const eerste = Date.now() - begin;
  assert.equal(log.graaf.length, 1, "de kennisgraaf één keer opgehaald");
  assert.ok(Number(await page.getByTestId("graaf-tekenaar").getAttribute("data-knopen")) > 6000, "de hele kennisgraaf staat erin");
  assert.equal(await page.getByRole("button", { name: "Hele kennisgraaf" }).getAttribute("aria-pressed"), "true");
  assert.match(await page.getByTestId("graaf-focus").innerText(), /Nadruk op wat het antwoord noemt \(6 delen en bepalingen/);
  assert.equal(await gekozen(page), "", "geen keuze bij het openen: de focus is het begin");
  assert.match(await detail(page).innerText(), /7 regelingen · 6\.343 bepalingen/);
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${shots}/5-kennisgraaf.png` });
  // Labels: nooit over elkaar (`kiesLabels`), en meer naarmate je inzoomt.
  const labels = async () => (await page.getByTestId("graaf-tekenaar").getAttribute("data-label-soorten")).split(",");
  await page.getByRole("button", { name: "Alles in beeld" }).click();
  await page.waitForTimeout(900);
  const uitgezoomd = await labels();
  await page.screenshot({ path: `${shots}/5a-kennisgraaf-uitgezoomd.png` });
  for (let i = 0; i < 4; i++) { await page.getByRole("button", { name: "Inzoomen" }).click(); await page.waitForTimeout(350); }
  await page.waitForTimeout(600);
  const ingezoomd = await labels();
  await page.screenshot({ path: `${shots}/5a-kennisgraaf-ingezoomd.png` });
  assert.ok(uitgezoomd.includes("regeling") && !uitgezoomd.includes("artikel"), `uitgezoomd alleen de opbouw (${uitgezoomd})`);
  assert.ok(ingezoomd.includes("artikel"), `ingezoomd ook artikelen (${ingezoomd})`);
  await page.getByRole("button", { name: "Naar het antwoord" }).click();
  await page.waitForTimeout(900);

  // Het blok is de inhoudsopgave van de kaart: aanwijzen licht uit, klikken kiest – geen nieuw tabblad.
  await blok.getByRole("link", { name: "art. 28" }).hover();
  assert.equal(await graaf(page).getAttribute("data-aangewezen"), A28);
  await blok.getByRole("link", { name: "art. 28" }).click();
  for (let i = 0; i < 20 && (await gekozen(page)) !== A28; i++) await page.waitForTimeout(100);
  assert.equal(await gekozen(page), A28, "een klik in het blok kiest de knoop in de graaf");
  assert.equal(page.context().pages().length, 1, "geen link geopend");
  await page.mouse.move(5, 5);
  assert.equal(await graaf(page).getAttribute("data-aangewezen"), "");
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${shots}/5b-kennisgraaf-keuze.png` });

  // Wisselen naar "Dit antwoord" en terug: de keuze blijft, de kennisgraaf wordt niet opnieuw opgehaald.
  await page.getByRole("button", { name: "Dit antwoord" }).click();
  await page.locator('[data-testid="samenhang-graaf"][data-bereik="antwoord"][data-gereed="true"]').waitFor({ timeout: 20000 });
  await page.getByRole("heading", { name: /^Samenhang van 2 delen/ }).waitFor();
  assert.equal(await gekozen(page), A28, "de keuze blijft bij een wissel");
  await page.getByRole("button", { name: "Hele kennisgraaf" }).click();
  await page.locator('[data-testid="samenhang-graaf"][data-bereik="kennisgraaf"][data-gereed="true"]').waitFor({ timeout: 20000 });
  assert.equal(log.graaf.length, 1, "terugwisselen haalt niets opnieuw op");

  // De layout staat in IndexedDB; een tweede keer openen rekent niet opnieuw.
  const opgeslagen = await page.evaluate(() => new Promise((klaar) => {
    const v = indexedDB.open("wetsanalyse-graaf");
    v.onsuccess = () => { const t = v.result.transaction("layouts").objectStore("layouts").count(); t.onsuccess = () => klaar(t.result); };
    v.onerror = () => klaar(-1);
  }));
  assert.ok(opgeslagen >= 2, `layouts bewaard (${opgeslagen})`);
  await page.getByRole("button", { name: "Sluiten" }).last().click();
  await page.getByTestId("samenhang-graaf").waitFor({ state: "detached" });
  const tweedeBegin = Date.now();
  let layoutGezien = false;
  await page.getByRole("button", { name: "Bekijk de 2 delen in de kennisgraaf" }).click();
  for (let i = 0; i < 600; i++) {
    if (await page.locator('[data-testid="samenhang-graaf"][data-gereed="true"]').count()) break;
    if (/Layout berekenen/.test(await page.getByTestId("graaf-laadbalk").innerText().catch(() => ""))) layoutGezien = true;
    await page.waitForTimeout(50);
  }
  const tweede = Date.now() - tweedeBegin;
  assert.ok(!layoutGezien, "de tweede keer wordt er niets gerekend");
  console.log(`kennisgraaf: eerste keer ${eerste} ms, uit de cache ${tweede} ms`);
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 14c. Een overzicht op de grens van 30 delen, in de hele kennisgraaf: een knoop die alleen daarin staat
// opent in het paneel. Daarna zijn het 31 doelen – die gaan in partijen naar de api, het bereik blijft de
// hele kennisgraaf, en de kennisgraaf wordt niet opnieuw opgehaald.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina();
  await page.goto(`${base}/workbench?gesprek=g4`);
  await page.getByTestId("overzicht").scrollIntoViewIfNeeded();
  await page.getByRole("button", { name: "Bekijk de 30 delen in de kennisgraaf" }).click();
  await page.locator('[data-testid="samenhang-graaf"][data-bereik="kennisgraaf"][data-gereed="true"]').waitFor({ timeout: 60000 });
  assert.equal(log.graaf.length, 1);
  const ver = "urn:bwb:BWBR9000060:artikel:8.44";
  await zoekEnKies(page, "Artikel 8.44", ver);
  await page.getByRole("button", { name: "Open in het paneel" }).click();
  await page.getByRole("button", { name: "Graaf", exact: true }).click();
  await page.locator('[data-testid="samenhang-graaf"][data-gereed="true"]').waitFor({ timeout: 60000 });
  assert.equal(await graaf(page).getAttribute("data-bereik"), "kennisgraaf", "het bereik gaat mee naar het nieuwe paneel");
  assert.equal(log.graaf.length, 1, "de kennisgraaf gaat mee en wordt niet opnieuw opgehaald");
  assert.ok(log.samenhangMeer.every((iris) => iris.length <= 30), "geen verzoek boven de grens van de api");
  assert.equal(new Set(log.samenhangMeer.slice(-2).flat()).size, 31, "alle 31 doelen gevraagd, in twee partijen");
  assert.equal(await page.getByTestId("graaf-fout").count(), 0, "geen fout");
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 14d. Een kennisgraaf die niet laadt: de melding staat op het canvas met "Opnieuw proberen", en terug
// in "Dit antwoord" is hij weg – hij gold alleen voor de kennisgraaf.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina();
  let graafFaalt = true;
  await page.route("**/api/annotatie/v2/graaf*", (route) => graafFaalt
    ? route.fulfill({ status: 503, json: { detail: "De brongraaf is tijdelijk niet beschikbaar." } })
    : route.fallback());
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByRole("button", { name: /^Bekijk samenhang van .* in de graaf$/ }).first().click();
  await wachtGereed(page);
  await page.getByRole("button", { name: "Hele kennisgraaf" }).click();
  await page.getByTestId("graaf-fout").waitFor();
  assert.match(await page.getByTestId("graaf-fout").innerText(), /tijdelijk niet beschikbaar/);
  await page.getByRole("button", { name: "Dit antwoord" }).click();
  await page.getByTestId("graaf-fout").waitFor({ state: "detached" });
  await page.getByRole("button", { name: "Hele kennisgraaf" }).click();
  graafFaalt = false;
  await page.getByRole("button", { name: "Opnieuw proberen" }).click();
  await page.locator('[data-testid="samenhang-graaf"][data-bereik="kennisgraaf"][data-gereed="true"]').waitFor({ timeout: 60000 });
  assert.equal(await page.getByTestId("graaf-fout").count(), 0, "na herstel geen melding meer");
  assert.equal(log.graaf.length, 1, "één geslaagde lading");
  assert.deepEqual(log.errors, []);
  await page.close();
}

// 15. Mobiel: inspector onder de graaf, in te klappen; zoeken werkt met het toetsenbord.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina({ width: 390, height: 844 });
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByRole("button", { name: /^Bekijk samenhang van/ }).click();
  await wachtGereed(page);
  await zoekveld(page).fill("lid 1");
  await page.keyboard.press("Enter");
  // De details staan meteen open; inklappen kan.
  assert.match(await detail(page).innerText(), /Artikel 9 · lid 1[\s\S]*Onderdeel van/);
  await page.getByRole("button", { name: "Details inklappen" }).click();
  const hoogte = (await page.getByTestId("graaf-tekenaar").boundingBox()).height;
  assert.ok(hoogte >= 200, `het canvas houdt hoogte (${hoogte}px)`);
  await page.screenshot({ path: `${shots}/3-mobiel.png` });
  // Mobiel: artikel 9 met "Uit de kennisgraaf" – niets loopt horizontaal uit beeld, en de inspector
  // scrolt; ook vergroot (dan staat hij onder de graaf).
  await zoekEnKies(page, "artikel 9", ART);
  await detail(page).getByTestId("graaf-feiten").waitFor();
  const mobielBreed = async () => detail(page).evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth,
    pagina: document.documentElement.scrollWidth, venster: window.innerWidth }));
  let maat = await mobielBreed();
  assert.ok(maat.scroll <= maat.client + 1 && maat.pagina <= maat.venster, `mobiel geen horizontale overloop (${JSON.stringify(maat)})`);
  await page.screenshot({ path: `${shots}/3b-mobiel-artikel.png` });
  const mobielScroll = async () => {
    const vak = await detail(page).boundingBox();
    await page.mouse.move(vak.x + vak.width / 2, vak.y + Math.min(vak.height - 10, 120));
    await page.mouse.wheel(0, 300);
    await page.waitForTimeout(400);
    return detail(page).evaluate((el) => Math.max(...[el, ...el.querySelectorAll("*")].map((k) => k.scrollTop)));
  };
  assert.ok(await mobielScroll() > 0, "mobiel scrolt de inspector");
  await page.getByRole("button", { name: "Vergroten" }).click();
  await wachtGereed(page);
  await detail(page).getByTestId("graaf-feiten").waitFor();
  maat = await mobielBreed();
  assert.ok(maat.scroll <= maat.client + 1 && maat.pagina <= maat.venster, `mobiel vergroot geen overloop (${JSON.stringify(maat)})`);
  assert.equal(await page.getByRole("button", { name: "Zijbalk inklappen" }).isVisible(), false, "mobiel geen zijbalkgreep");
  assert.ok(await mobielScroll() > 0, "mobiel vergroot scrolt de inspector");
  const doekHoogte = (await page.getByTestId("graaf-tekenaar").boundingBox()).height;
  assert.ok(doekHoogte >= 250, `mobiel vergroot houdt het canvas hoogte (${doekHoogte}px)`);
  await page.screenshot({ path: `${shots}/3c-mobiel-vergroot.png` });
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

// 16. Zonder WebGL blijven zoeken, lagen en de inspector bruikbaar.
{
  bijgewerkt = false;
  const { page, log } = await nieuwePagina({ webgl: false });
  await page.goto(`${base}/workbench?gesprek=g1`);
  await page.getByRole("button", { name: /^Bekijk samenhang van/ }).click();
  await page.getByText("Deze browser kan de graaf niet tekenen.", { exact: false }).waitFor();
  await zoekEnKies(page, "lid 1", L1);
  assert.match(await detail(page).innerText(), /Artikel 9 · lid 1/);
  await page.getByRole("button", { name: "Lagen" }).click();
  await page.getByRole("group", { name: "Lagen en legenda" }).waitFor();
  await page.screenshot({ path: `${shots}/4-zonder-webgl.png` });
  assert.deepEqual(log.errors, []);
  assert.deepEqual(log.console, [], "geen consolefouten");
  await page.close();
}

await browser.close();
console.log(`samenhang: alle controles geslaagd; screenshots in ${shots}`);
