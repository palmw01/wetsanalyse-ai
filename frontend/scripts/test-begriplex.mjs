/** Browserregressie voor "Lex naast de kaart" (spoor D, fase E) op de echte Next-UI met een gemockte BFF.
 * Start Next met
 * AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109
 * en draai `node scripts/test-begriplex.mjs`.
 *
 * De mock gedraagt zich als api + graph-qa: `POST /api/kaart-run` start een run, de events leggen de
 * voorstellen vast (`api/app/begrip_voorstel_store.py`), en overnemen toetst de basis van een
 * definitievoorstel – een veranderde definitie geeft 409 `voorstel_verouderd`, tenzij `nu_gezien` klopt.
 *
 * Bewaakt (de acceptatie van fase E: niets wordt stil overschreven; herkomst gaat mee):
 *  - de vier knoppen met hun voorwaarden (voorbeelden pas met een definitie) en de schatting;
 *  - een brondefinitie overnemen: de definitie op de kaart, "Van Lex overgenomen", een revisie;
 *  - overnemen kan niet met onbewaarde wijzigingen; na een eigen wijziging toont het voorstel toen, nu en
 *    voorstel, en "Toch overnemen" stuurt de definitie mee die de analist zag;
 *  - voorbeelden: aanpassen en overnemen, afwijzen met een reden (Enter slaat het begrip niet op);
 *  - betekenisverschil met het voorgevulde begrip: de uitleg komt erbij;
 *  - na herladen staan de besluiten onder "Eerdere voorstellen van Lex", en er staat niets open;
 *  - de knoppen werken met het toetsenbord.
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { sessieCookies } from "./sessie.mjs";

const base = process.env.TEST_URL || "http://localhost:3109";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [], requests = [];
page.on("pageerror", (e) => errors.push(e.message));
await context.addCookies(await sessieCookies(base));
await page.addInitScript(() => localStorage.setItem("wa_rondleiding", JSON.stringify({ versie: 999, gezien: true })));

const nu = "2026-10-16T10:00:00+00:00";
const IW = "urn:bwb:BWBR0004770";
const wg = { id: "wg1", naam: "Termijnen", analysevraag: "", afbakening: "", peildatum: null, status: "actief", revisie: 2,
  aangemaakt_door: "t", aangemaakt: nu, gewijzigd: nu, gearchiveerd: null, bronnen: [] };
const LEEG = { naam: "", alternatieve_termen: [], context: "", jas_klasse: "", jas_subtype: "", geldigheid: "", definitie: "",
  definitie_herkomst: null, definitie_door: "", uitleg: "", onderbouwing: "", voorbeelden: [], eigenschappen: {}, open_vragen: [] };
const koppeling = (eid) => ({ id: `k-${eid}`, begrip_id: "b1", element_id: eid, rol: "duiding", motivatie: "",
  bewijs: { tekst: "de belastingaanslag", klasse: "Rechtsobject", ankers: [], eigenaar_iri: `${IW}:artikel:9:lid:1`, laag_id: "l",
    snapshot_id: "s", lifecycle: "human_approved", vindplaats: "Artikel 9 · Lid 1 – IW 1990", element_hash: "h" },
  beoordeling: "akkoord", beoordeeld_door: "t", beoordeeld_op: nu, toegevoegd_door: "t", toegevoegd: nu,
  actualiteit: "actueel", lifecycle_nu: "human_approved", annotatie_beoordeeld: true });
const begrippen = {
  b1: { id: "b1", status: "concept", revisie: 1, inhoud: { ...LEEG, naam: "belastingaanslag" }, koppelingen: [koppeling("e1")], revisies: [] },
  b2: { id: "b2", status: "concept", revisie: 1, inhoud: { ...LEEG, naam: "aanslag" }, koppelingen: [], revisies: [] },
};
const uit = (b) => ({ ...b, iri: `urn:wa:begrip:${b.id}`, werkgebied_id: "wg1", kader_iri: "urn:wa:kader:wg1", aangemaakt_door: "t",
  aangemaakt: nu, gewijzigd: nu, geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
  accorderen: { mag: false, redenen: ["De context ontbreekt."] }, aandachtspunten: [] });

// --- de voorstellen, zoals de api ze bewaart -----------------------------------------------------
const voorstellen = [], runs = {};
let teller = 0;
const fr = { id: "F0123456789", bron_iri: `${IW}:artikel:9:lid:1`, start: 0, eind: 18, tekst: "de belastingaanslag" };
const UITKOMST = {
  brondefinitie: [{ veld: "definitie", aandacht: "groen", aandachtspunten: [], motivatie: "De wet definieert “belastingaanslag” in Artikel 2.",
    waarde: { definitie: "de voorlopige aanslag, de aanslag en de navorderingsaanslag", herkomst: "letterlijk", fragmenten: [],
      definitie_bron_iri: `${IW}:artikel:2:lid:1:o:m`, definitie_vindplaats: "Artikel 2, lid 1, onderdeel m – Invorderingswet 1990",
      vindplaats_soort: "regeling" } }],
  scherper: [{ veld: "definitie", aandacht: "geel", aandachtspunten: ["DOOR_LEX_GEFORMULEERD"], motivatie: "Noemt de beschikking.",
    waarde: { definitie: "een beschikking die het verschuldigde bedrag vaststelt", herkomst: "geformuleerd", fragmenten: [fr],
      definitie_bron_iri: "", definitie_vindplaats: "", vindplaats_soort: "" } }],
  voorbeelden: [
    { veld: "voorbeelden", aandacht: "geel", aandachtspunten: ["DOOR_LEX_VOORBEELD"], motivatie: "",
      waarde: { tekst: "Een navorderingsaanslag IB 2024", fragmenten: [], oordeel: "wel", toelichting: "staat in de opsomming" } },
    { veld: "voorbeelden", aandacht: "geel", aandachtspunten: ["DOOR_LEX_VOORBEELD", "GEEN_TEGENVOORBEELD"], motivatie: "",
      waarde: { tekst: "Een beschikking invorderingsrente", fragmenten: [], oordeel: "wel", toelichting: "" } }],
  betekenisverschil: [{ veld: "uitleg", aandacht: "geel", aandachtspunten: ["DOOR_LEX_VERGELEKEN"], motivatie: "",
    waarde: { tekst: "Ten opzichte van “aanslag”: een belastingaanslag omvat ook de navorderingsaanslag.", fragmenten: [fr],
      vergelijking: "verwant" } }],
};
const basis = (b) => ({ revisie: b.revisie, definitie: b.inhoud.definitie, definitie_herkomst: b.inhoud.definitie_herkomst });
const stand = (b) => ({
  voorstellen: voorstellen.filter((v) => v.begrip_id === b.id).map((v) => v.veld === "definitie" && v.status === "open"
    ? { ...v, verouderd: v.basis.definitie !== b.inhoud.definitie, nu: { definitie: b.inhoud.definitie, definitie_herkomst: b.inhoud.definitie_herkomst } }
    : v),
  runs, schatting: { scherper: { tokens: 1800, basis: 2 } }, budget: { resterend: 40000, budget: 100000, actief: true, geblokkeerd: false } });
const sse = (events) => events.map((e, i) => `data: ${JSON.stringify({ seq: i, ...e })}\n\n`).join("");
const wachtend = {};

function overnemen(b, v, body) {
  if (v.status !== "open") return { status: 409, detail: { fout: "al_besloten", melding: "Over dit voorstel is al besloten." } };
  if (body.verwachte_revisie !== b.revisie) return { status: 412, detail: { fout: "revisie_conflict", revisie: b.revisie, melding: "Iemand anders…" } };
  const w = v.waarde, i = b.inhoud;
  let aangepast = false;
  if (v.veld === "definitie") {
    if (v.basis.definitie !== i.definitie && body.nu_gezien !== i.definitie)
      return { status: 409, detail: { fout: "voorstel_verouderd", toen: { definitie: v.basis.definitie }, nu: { definitie: i.definitie },
        voorstel: { definitie: w.definitie }, melding: "De definitie veranderde nadat Lex dit voorstelde." } };
    aangepast = !!body.aanpassing && body.aanpassing !== w.definitie;
    Object.assign(i, aangepast ? { definitie: body.aanpassing, definitie_herkomst: "geformuleerd", definitie_door: "analist" }
      : { definitie: w.definitie, definitie_herkomst: w.herkomst, definitie_door: "lex" });
  } else if (v.veld === "uitleg") {
    i.uitleg = i.uitleg ? `${i.uitleg}\n\n${w.tekst}` : w.tekst;
  } else if (v.veld === "voorbeelden") {
    const tekst = body.aanpassing || w.tekst;
    aangepast = tekst !== w.tekst || (body.oordeel && body.oordeel !== w.oordeel);
    i.voorbeelden = [...i.voorbeelden, { tekst, oordeel: body.oordeel ?? w.oordeel, toelichting: w.toelichting ?? "" }];
  }
  Object.assign(v, { status: aangepast ? "aangepast" : "overgenomen", besloten_door: "browser-test", besloten_op: nu, begrip_revisie: b.revisie + 1 });
  b.revisie += 1;
  b.revisies.unshift({ revisie: b.revisie, actie: "voorstel-overgenomen", detail: { veld: v.veld, aangepast }, actor: "browser-test" });
  return null;
}

await page.route("**/api/**", async (route) => {
  const req = route.request(), url = new URL(req.url()), p = url.pathname, m = req.method();
  if (p.startsWith("/api/auth/")) return route.continue();
  const body = m === "GET" || m === "DELETE" ? null : req.postDataJSON();
  requests.push({ p, m, body });
  if (p === "/api/werkgebieden/wg1") return route.fulfill({ json: wg });
  if (p === "/api/werkgebieden/wg1/begrippen" && m === "GET")
    return route.fulfill({ json: { kader_iri: "urn:wa:kader:wg1", primair: {},
      begrippen: Object.values(begrippen).map((b) => { const { koppelingen, ...r } = uit(b);
        return { ...r, aantal_koppelingen: koppelingen.length, element_ids: koppelingen.map((k) => k.element_id) }; }) } });
  const bm = p.match(/^\/api\/werkgebieden\/wg1\/begrippen\/(b\d)(?:\/(.+))?$/);
  if (bm) {
    const b = begrippen[bm[1]], rest = bm[2] ?? "";
    if (!rest && m === "GET") return route.fulfill({ json: uit(b) });
    if (!rest && m === "PATCH") {
      if (body.verwachte_revisie !== b.revisie) return route.fulfill({ status: 412, json: { detail: { fout: "revisie_conflict", revisie: b.revisie } } });
      const oud = b.inhoud;
      b.inhoud = { ...LEEG, ...body.inhoud, definitie_door: body.inhoud.definitie === oud.definitie ? oud.definitie_door : (body.inhoud.definitie ? "analist" : "") };
      b.revisie += 1;
      b.revisies.unshift({ revisie: b.revisie, actie: "begrip-gewijzigd", detail: { velden: ["definitie"] }, actor: "browser-test" });
      return route.fulfill({ json: uit(b) });
    }
    if (rest === "revisies") return route.fulfill({ json: { revisies: b.revisies.map((r) => ({ ...r, status: b.status, inhoud: b.inhoud, tijdstip: nu })) } });
    if (rest === "voorstellen") return route.fulfill({ json: stand(b) });
    const vm = rest.match(/^voorstellen\/(v\d+)\/(overnemen|afwijzen)$/);
    if (vm) {
      const v = voorstellen.find((x) => x.id === vm[1]);
      if (vm[2] === "afwijzen") {
        Object.assign(v, { status: "afgewezen", reden: body.reden, besloten_door: "browser-test", besloten_op: nu });
        return route.fulfill({ json: stand(b) });
      }
      const fout = overnemen(b, v, body);
      return fout ? route.fulfill({ status: fout.status, json: { detail: fout.detail } }) : route.fulfill({ json: uit(b) });
    }
  }
  if (p === "/api/kaart-run" && m === "POST") {
    const b = begrippen[body.begrip_id], rid = `kr${++teller}`;
    runs[body.actie] = { id: rid, begrip_id: b.id, actie: body.actie, status: "loopt", melding: "", reden: "", basis_revisie: b.revisie,
      ander_begrip_id: body.ander_begrip_id ?? null, gestart_door: "t", gestart: nu, gewijzigd: nu };
    wachtend[rid] = () => {
      // Nieuwste run eerst, binnen een run in de volgorde van Lex – zoals de api.
      voorstellen.unshift(...UITKOMST[body.actie].map((x, i) => ({ id: `v${++teller}`, begrip_id: b.id, run_id: rid, actie: body.actie, veld: x.veld, volgorde: i, basis: basis(b),
          waarde: x.waarde, motivatie: x.motivatie, aandacht: x.aandacht, aandachtspunten: x.aandachtspunten,
          door: { bron: body.actie === "brondefinitie" ? "graaf" : "model", model: "m", promptversie: "p" }, status: "open", reden: "",
          besloten_door: null, besloten_op: null, begrip_revisie: null, gemaakt: nu })));
      runs[body.actie] = { ...runs[body.actie], status: "klaar" };
    };
    return route.fulfill({ status: 201, json: { run: runs[body.actie], agent_run_id: rid } });
  }
  if (p === "/api/kaart-run") return route.fulfill({ json: null });
  const ev = p.match(/^\/api\/annotatie\/run\/(kr\d+)\/events$/);
  if (ev) {
    wachtend[ev[1]]?.();
    return route.fulfill({ contentType: "text/event-stream", body: sse([
      { type: "status", message: "Lex · Werk aan “belastingaanslag”" },
      { type: "opgeslagen", kaart_run: ev[1], voorstellen: 1, melding: "" }, { type: "done" }]) });
  }
  // De strook "Voorstellen van Lex" op dezelfde tab: hier leeg.
  if (p === "/api/werkgebieden/wg1/groepen") return route.fulfill({ json: { run: null, groepen: [], passages: {} } });
  if (p === "/api/werkgebieden/wg1/begrippen-runs/laatste") return route.fulfill({ json: { run: null } });
  if (p === "/api/werkgebieden/wg1/verdieping")
    return route.fulfill({ json: { run: null, aantal: 0, vragen: [], kaarten: [], batches: [], verdiept: false, schatting: null, budget: null } });
  if (p === "/api/begrippen-run") return route.fulfill({ json: null });
  if (p === "/api/gesprekken") return route.fulfill({ json: [] });
  if (p.includes("/verbruik")) return route.fulfill({ json: { actief: false, geblokkeerd: false } });
  return route.fulfill({ status: 404, json: { detail: "Niet in deze test." } });
});

const zie = (tekst) => page.getByText(tekst, { exact: false }).first().waitFor();
const strook = () => page.locator("[data-begrip-lex]");
const kaart = () => page.getByRole("article", { name: /^Begrip / });
const knop = (naam) => strook().getByRole("button", { name: naam });
const definitie = () => kaart().getByLabel(/^Definitie/);
const voorstel = () => kaart().locator("[data-voorstel]");
try {
  await page.goto(`${base}/werkgebieden/wg1?tab=begrippen&begrip=b1`);
  await strook().getByRole("heading", { name: "Lex naast de kaart" }).waitFor();

  // 1. De voorwaarden: voorbeelden pas met een definitie; de schatting staat bij scherper.
  assert.equal(await knop("Bedenk voorbeelden").isDisabled(), true);
  await strook().getByText("Voorbeelden toetsen een definitie").waitFor();
  await strook().getByText("Kost ~1.800 tokens.").waitFor();
  assert.equal(await strook().getByLabel("Vergelijk met").inputValue(), "b2");

  // 2. De brondefinitie, met het toetsenbord gestart en overgenomen: herkomst en revisie gaan mee.
  await knop("Zoek de brondefinitie").focus();
  await page.keyboard.press("Enter");
  await voorstel().getByText("Letterlijk uit Artikel 2, lid 1, onderdeel m – Invorderingswet 1990 (in een regeling van het werkgebied)").waitFor();
  await voorstel().getByRole("button", { name: "Overnemen" }).focus();
  await page.keyboard.press("Enter");
  await zie("Overgenomen van Lex; dat is een nieuwe revisie.");
  assert.equal(await definitie().inputValue(), "de voorlopige aanslag, de aanslag en de navorderingsaanslag");
  await kaart().getByText("Van Lex overgenomen", { exact: true }).waitFor();
  assert.equal(await voorstel().count(), 0);
  assert.equal(await knop("Bedenk voorbeelden").isDisabled(), false);

  // 3. Scherper: niet overnemen met onbewaarde wijzigingen; na een eigen wijziging toen/nu/voorstel.
  await knop("Stel een scherpere definitie voor").click();
  await voorstel().getByText("Geformuleerd door Lex").waitFor();
  await voorstel().getByText("De definitie is door Lex geformuleerd; toets haar aan de passages.").waitFor();
  await definitie().fill("mijn eigen definitie");
  await voorstel().getByText("Sla eerst je wijzigingen op").waitFor();
  assert.equal(await voorstel().getByRole("button", { name: "Overnemen" }).isDisabled(), true);
  assert.equal(await knop("Zoek de brondefinitie").isDisabled(), true);
  await kaart().getByRole("button", { name: "Opslaan" }).click();
  await zie("Opgeslagen.");
  const vergelijking = voorstel().getByLabel("Vergelijking");
  await vergelijking.getByText("mijn eigen definitie").waitFor();
  await vergelijking.getByText("de voorlopige aanslag, de aanslag en de navorderingsaanslag").waitFor();
  await kaart().getByText("Door de analist", { exact: true }).waitFor();
  const voor = requests.length;
  await voorstel().getByRole("button", { name: "Toch overnemen" }).click();
  await zie("Overgenomen van Lex; dat is een nieuwe revisie.");
  const verzoek = requests.slice(voor).find((r) => r.p.endsWith("/overnemen"));
  assert.equal(verzoek.body.nu_gezien, "mijn eigen definitie");
  assert.equal(await definitie().inputValue(), "een beschikking die het verschuldigde bedrag vaststelt");

  // 4. Voorbeelden: het eerste aangepast overgenomen, het tweede afgewezen met Enter in het redenveld.
  await knop("Bedenk voorbeelden").click();
  await voorstel().first().waitFor();
  assert.equal(await voorstel().count(), 2);
  await voorstel().nth(1).getByText("Er is geen tegenvoorbeeld").waitFor();
  await voorstel().first().getByRole("button", { name: "Aanpassen" }).click();
  await voorstel().first().getByLabel("Aangepaste tekst").fill("Een navorderingsaanslag IB 2023");
  await voorstel().first().getByRole("button", { name: "Aangepast overnemen" }).click();
  await zie("Overgenomen van Lex");
  assert.equal(await kaart().getByLabel("Voorbeeld 1", { exact: true }).inputValue(), "Een navorderingsaanslag IB 2023");
  const patchVoor = requests.filter((r) => r.m === "PATCH").length;
  await voorstel().first().getByRole("button", { name: "Afwijzen" }).click();
  await voorstel().first().getByLabel("Reden van afwijzen").fill("geen belastingaanslag");
  await page.keyboard.press("Enter");
  await voorstel().first().waitFor({ state: "detached" });
  assert.equal(requests.filter((r) => r.m === "PATCH").length, patchVoor, "Enter in het redenveld sloeg het begrip op");
  assert.equal(await voorstel().count(), 0);

  // 5. Betekenisverschil met het voorgevulde begrip: de uitleg komt erbij.
  await knop("Verklaar het betekenisverschil").click();
  await voorstel().getByText("Uitkomst: Verwant, maar een ander begrip").waitFor();
  await voorstel().getByRole("button", { name: "Overnemen" }).click();
  await zie("Overgenomen van Lex");
  assert.match(await kaart().getByLabel(/^Uitleg/).inputValue(), /omvat ook de navorderingsaanslag/);
  const start = requests.find((r) => r.p === "/api/kaart-run" && r.body?.actie === "betekenisverschil");
  assert.equal(start.body.ander_begrip_id, "b2");

  // 6. Na herladen: niets open, de besluiten in de historie van Lex en van het begrip.
  await page.reload();
  await strook().getByRole("heading", { name: "Lex naast de kaart" }).waitFor();
  await strook().getByText("Eerdere voorstellen van Lex").click();
  const eerder = strook().getByRole("list", { name: "Eerdere voorstellen van Lex" }).getByRole("listitem");
  assert.equal(await eerder.count(), 5);
  await eerder.filter({ hasText: "Afgewezen" }).getByText("geen belastingaanslag").waitFor();
  assert.equal(await voorstel().count(), 0);
  await kaart().getByText("Historie").click();
  await kaart().getByText("Aangepast overgenomen van Lex: voorbeelden").waitFor();

  assert.deepEqual(errors, []);
  console.log("OK test-begriplex");
} catch (e) {
  if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/begriplex-fout.png`, fullPage: true });
  console.error(e);
  process.exitCode = 1;
} finally {
  await browser.close();
}
