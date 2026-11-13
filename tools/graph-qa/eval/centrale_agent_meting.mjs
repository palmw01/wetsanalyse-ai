// De agentset draaien op acceptatie (ADR-016 §A6): één beurt tegelijk, langs dezelfde weg als de werkplek.
//
// Dit script gebruikt de clientbibliotheek van de acceptatie-MCP (tools/wetsanalyse-acceptatie-mcp/dist): een sessie uit
// een accounttoken, de BFF, en per beurt eerst de vraag in het gesprek en dan de run. De omgeving en het token komen
// alleen uit de omgevingsvariabelen WETSANALYSE_ACC_URL en WETSANALYSE_ACC_TOKEN; ze staan nergens in de uitvoer.
//
//   node eval/centrale_agent_meting.mjs werkgebied
//       maakt het meetwerkgebied uit de eerste regel van de set en print zijn id;
//   node eval/centrale_agent_meting.mjs run <nr> --werkgebied <id> --commit <sha> --uit <map> [id ...]
//       draait de set (of de genoemde opdrachten) en schrijft per opdracht één regel in <map>/ruw-run<nr>.jsonl.
//       Met `--set golden_centrale_agent_breed.jsonl` draait een aanvulling naast de 30 (uitvoer ruw-breed-…).
//       Met `--vorm <naam> --extra '<json>'` gaan de velden uit <json> mee op elke beurt van de run, en heet het
//       bestand ruw-<naam>-run<nr>.jsonl. Zo zijn twee vormen op dezelfde versie te meten: de vorm zonder het veld en de
//       vorm met het veld waarmee een run de centrale agent kiest (ADR-016 §A7). De naam staat op elke regel (`vorm`).
//
//   node eval/centrale_agent_meting.mjs vragen <kwaliteit|duiding|partijen|klassen|gesprek> <nr> --commit <sha> --uit <map> --vormen '<json>' [id ...]
//       stelt de vragen van de kwaliteitsset (`golden.jsonl`, K01, K02, …), de duidingset (`golden_duiding.jsonl`, op id), de partijenset
//       (`golden_duiding_partijen.jsonl`, op id), de klassenset (`golden_klasse_twijfel.jsonl`, op id, G2)
//       of de gesprekken van `golden_gesprek.jsonl`
//       in elke vorm uit <json> (`{"supervisor": {...}, "centraal": {...}}`: per vorm de velden op de beurt), per vraag
//       om en om, zodat tijd en cachestand geen vorm bevoordelen. Eén bestand per vorm:
//       ruw-<set>-<vorm>-run<nr>.jsonl. `python -m eval.centrale_agent_sets` scoort ze met de scorers van de sets.
//
// `--commit` is de commit van master waarop acceptatie draait; het script kan die niet zelf zien. Een run is hervatbaar:
// een opdracht die al in het bestand staat, wordt overgeslagen. Breekt een beurt af (een nieuwe revisie van graph-qa
// midden in een run), dan begint de opdracht opnieuw in een nieuw gesprek, hoogstens twee keer; de regel noemt het
// (`herhaald`, `afgebroken`). Het stoppunt per opdracht staat in de set: het script neemt geen bron op en bevestigt
// alleen de bronnenronde van een regie, nooit een ronde die annoteert.
// `python3 eval/centrale_agent_vat.py` vat het ruwe bestand samen.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AcceptatieClient } from "../../wetsanalyse-acceptatie-mcp/dist/client.js";
import { lexStart } from "../../wetsanalyse-acceptatie-mcp/dist/beurt.js";

const HIER = path.dirname(fileURLToPath(import.meta.url));
// `--set <bestand>` (alleen bij `run`): een aanvulling naast de 30, zoals golden_centrale_agent_breed.jsonl. Het bestand
// komt in de naam van de uitvoer, zodat het de runs van de set niet raakt.
const setOptie = process.argv.indexOf("--set");
const SETNAAM = setOptie < 0 ? "golden_centrale_agent.jsonl" : path.basename(process.argv.splice(setOptie, 2)[1]);
if (!/^golden_centrale_agent[a-z_]*\.jsonl$/.test(SETNAAM)) { console.error("--set: een bestand golden_centrale_agent….jsonl in eval/"); process.exit(2); }
const SET = path.join(HIER, SETNAAM);
const SETDEEL = SETNAAM === "golden_centrale_agent.jsonl" ? "" : SETNAAM.replace(/^golden_centrale_agent_|\.jsonl$/g, "") + "-";
const MAX_HERHALEN = 2;
const NAMEN = { BWBR0004770: "Invorderingswet 1990", BWBR0024096: "Leidraad Invordering 2008" };

const { WETSANALYSE_ACC_URL: url, WETSANALYSE_ACC_TOKEN: token } = process.env;
if (!url || !token) { console.error("Zet WETSANALYSE_ACC_URL en WETSANALYSE_ACC_TOKEN."); process.exit(2); }
const c = new AcceptatieClient(url.replace(/\/$/, ""), token);
const rijen = fs.readFileSync(SET, "utf8").split("\n").filter(r => r.trim() && !r.startsWith("#")).map(r => JSON.parse(r));
const fixture = rijen.find(r => r.id === "_werkgebied");      // alleen in de set van 30
const set = rijen.filter(r => r.id !== "_werkgebied");
const perId = Object.fromEntries(set.map(r => [r.id, r]));

class BudgetOp extends Error {}
class Afgebroken extends Error {}

async function verbruik() { return (await c.bff("GET", "/api/account/verbruik")).data?.gebruikt ?? null; }

async function gesprek(titel, werkgebied_id) {
  const r = await c.bff("POST", "/api/gesprekken", { titel, ...(werkgebied_id ? { werkgebied_id } : {}) });
  if (r.status >= 300) throw new Afgebroken(`gesprek niet gemaakt (HTTP ${r.status})`);
  return r.data.id;
}

/** Eén beurt: de vraag bewaren, de run starten en volgen tot hij klaar is. Zonder `token` en `reason`. */
async function beurt(args) {
  const t0 = Date.now();
  const s = await lexStart(c, args);
  if (s.status === 429) throw new BudgetOp();
  if (s.status >= 300) throw new Afgebroken(`run niet gestart (HTTP ${s.status})`);
  const run_id = s.data.run_id;
  let vanaf = 0, tekst = "", events = [], klaar = false;
  for (let n = 0; !klaar && n < 12; n++) {
    const r = await c.runEvents(run_id, vanaf, 110);
    tekst += r.tekst; events.push(...r.events); vanaf = r.vanaf + 1; klaar = r.klaar;
  }
  const done = events.find(e => e.type === "done");
  // Een run die niet zelf kon eindigen (replica weg) of nooit `done` gaf: de opdracht gaat opnieuw.
  if (!klaar || !done) throw new Afgebroken("de run eindigde niet");
  if (done.uitkomst === "mislukt" && events.some(e => e.type === "error" && /afgebroken|verweesd|herstart|niet meer/i.test(JSON.stringify(e)))) {
    throw new Afgebroken("de run is afgebroken");
  }
  return { run_id, tekst, events, wand_ms: Date.now() - t0 };
}

async function meet(rec, label, args) {
  const v0 = await verbruik();
  const b = await beurt(args);
  const v1 = await verbruik();
  rec.beurten.push({ label, vraag: args.vraag, gesprek: args.conversation_id, run_id: b.run_id, wand_ms: b.wand_ms,
                     delta_account: v0 === null || v1 === null ? null : v1 - v0, tekst: b.tekst, events: b.events });
  return b;
}

/** De beurt, en bij een regievoorstel voor de bronnenronde ook de bevestiging (het stoppunt `bundel_bronnen`). */
async function metStoppunt(rec, label, args, stoppunt) {
  const b = await meet(rec, label, args);
  const bev = b.events.map(e => e.bevestiging).find(x => x && x.soort === "regie");
  if (stoppunt !== "bundel_bronnen" || !bev || bev.opdracht !== "bronnen") return [b, null];
  return [b, await meet(rec, `${label}:bevestigd`, { ...args, vraag: "Start", actie: "regie_bronnen", extra: { ...args.extra, plan_id: bev.plan_id } })];
}

async function opdracht(o, runnr, werkgebied, commit, vorm, velden) {
  const ctx = o.context || {};
  const wg = ctx.werkgebied ? werkgebied : undefined;
  if (ctx.werkgebied && !wg) throw new Error(`${o.id} vraagt --werkgebied`);
  // De velden van de vorm gaan vóór de bronstand: een vorm kiest de agent, niet de bronnen van de opdracht.
  const extra = { ...velden, bronnen: ctx.bronnen || [], bronnen_herkomst: "gesprek" };
  const rec = { id: o.id, run: runnr, commit, vorm, begin: new Date().toISOString(), beurten: [] };
  const hoofd = await gesprek(`Agentset ${vorm ? vorm + " " : ""}run ${runnr} – ${o.id}`, wg);
  let kind = null;
  for (const [i, stap] of (o.opzet || []).entries()) {
    const label = `opzet${i + 1}`;
    if (stap.opdracht) {
      const [, bev] = await metStoppunt(rec, `${label}:${stap.opdracht}`,
        { vraag: perId[stap.opdracht].opdracht, conversation_id: hoofd, werkgebied_id: wg, extra }, o.stoppunt);
      kind = (bev?.events || []).find(e => e.type === "regie_taak" && e.gesprek_id)?.gesprek_id ?? kind;
    } else if (stap.gesprek) {
      if (!kind) { rec.beurten.push({ label: `${label}:deelgesprek`, overgeslagen: "de opzet leverde geen deelgesprek op" }); continue; }
      await meet(rec, `${label}:deelgesprek`, { vraag: stap.vraag, conversation_id: kind, werkgebied_id: wg, extra });
    } else {
      await meet(rec, label, { vraag: stap.vraag, conversation_id: hoofd, werkgebied_id: wg, extra });
    }
  }
  await metStoppunt(rec, "gemeten", { vraag: o.opdracht, conversation_id: hoofd, werkgebied_id: wg, extra }, o.stoppunt);
  rec.eind = new Date().toISOString();
  return rec;
}

/** Draai één opdracht; breekt een beurt af (een revisiewissel), dan opnieuw in een nieuw gesprek, hoogstens twee keer. */
async function metHerhalen(id, kop, draai) {
  const afgebroken = [];
  let rec = null;
  for (let poging = 0; poging <= MAX_HERHALEN && !rec; poging++) {
    try { rec = await draai(); }
    catch (e) {
      if (e instanceof BudgetOp) { console.log("429: het budget is op bij", id); process.exit(3); }
      if (!(e instanceof Afgebroken) && !/fetch failed|ECONN|socket|terminated|aborted/i.test(String(e))) throw e;
      afgebroken.push({ om: new Date().toISOString(), reden: String(e.message || e).slice(0, 200) });
      await new Promise(r => setTimeout(r, 60_000));        // een revisiewissel duurt ongeveer een minuut
    }
  }
  rec ??= { ...kop, beurten: [], mislukt: "na herhalen niet afgerond" };
  if (afgebroken.length) Object.assign(rec, { herhaald: afgebroken.length, afgebroken });
  return rec;
}

/** Eén case van een andere set: de beurten na elkaar in één nieuw gesprek, in één vorm. */
async function vraagcase(c, kop, werkgebied, velden) {
  const inWerkgebied = c.beurten.some(b => b.werkgebied_id);
  if (inWerkgebied && !werkgebied) throw new Error(`${c.id} vraagt --werkgebied`);
  const rec = { ...kop, begin: new Date().toISOString(), beurten: [] };
  const hoofd = await gesprek(`Agentset ${kop.set} ${kop.vorm} run ${kop.run} – ${c.id}`, inWerkgebied ? werkgebied : undefined);
  for (const [i, b] of c.beurten.entries()) {
    await meet(rec, `beurt${i + 1}`, { vraag: b.vraag, conversation_id: hoofd, werkgebied_id: b.werkgebied_id ? werkgebied : undefined,
                                       extra: { ...velden, bronnen: [], bronnen_herkomst: "gesprek" } });
  }
  rec.eind = new Date().toISOString();
  return rec;
}

const leesSet = naam => fs.readFileSync(path.join(HIER, naam), "utf8").split("\n").filter(r => r.trim() && !r.startsWith("#")).map(r => JSON.parse(r));

function optie(naam, args) { const i = args.indexOf(naam); return i < 0 ? undefined : args.splice(i, 2)[1]; }

const [commando, ...rest] = process.argv.slice(2);
if (commando === "werkgebied") {
  const r = await c.bff("POST", "/api/werkgebieden", {
    naam: fixture.naam, analysevraag: fixture.analysevraag, gebeurtenis: fixture.gebeurtenis,
    context: "Meetwerkgebied van de agentset (ADR-016 §A6). Niet wijzigen of verwijderen buiten de metingen.",
    regelingen: fixture.zoekbereik.map(b => ({ bwb_id: b, label: NAMEN[b] ?? b })),
    deelvragen: fixture.deelvragen.map(vraag => ({ vraag, herkomst: "analist" })),
  });
  console.log(r.status, r.data?.id ?? "");
} else if (commando === "run") {
  const werkgebied = optie("--werkgebied", rest), commit = optie("--commit", rest), map = optie("--uit", rest) ?? ".";
  const vorm = optie("--vorm", rest) ?? "", extraJson = optie("--extra", rest);
  const [nr, ...ids] = rest;
  if (!nr || !commit) { console.error("run <nr> --commit <sha> [--werkgebied <id>] [--uit <map>] [--vorm <naam> --extra <json>] [id ...]"); process.exit(2); }
  if (!/^[a-z0-9-]*$/.test(vorm)) { console.error("--vorm: alleen kleine letters, cijfers en streepjes"); process.exit(2); }
  let velden = {};
  if (extraJson) {
    try { velden = JSON.parse(extraJson); } catch { console.error("--extra is geen JSON"); process.exit(2); }
    if (!velden || typeof velden !== "object" || Array.isArray(velden)) { console.error("--extra is een JSON-object"); process.exit(2); }
    if (!vorm) { console.error("--extra vraagt --vorm: zo zijn de bestanden van twee vormen uit elkaar te houden"); process.exit(2); }
  }
  const uit = path.join(map, `ruw-${SETDEEL}${vorm ? vorm + "-" : ""}run${nr}.jsonl`);
  const gedaan = new Set(fs.existsSync(uit) ? fs.readFileSync(uit, "utf8").split("\n").filter(Boolean).map(r => JSON.parse(r).id) : []);
  console.log("account vóór", await verbruik());
  for (const o of set) {
    if ((ids.length && !ids.includes(o.id)) || gedaan.has(o.id)) continue;
    const rec = await metHerhalen(o.id, { id: o.id, run: Number(nr), commit, vorm }, () => opdracht(o, Number(nr), werkgebied, commit, vorm, velden));
    const afgebroken = rec.afgebroken ?? [];
    fs.appendFileSync(uit, JSON.stringify(rec) + "\n");
    console.log(o.id, rec.mislukt ?? "", `beurten ${rec.beurten.length}`, afgebroken.length ? `herhaald ${afgebroken.length}` : "");
  }
  console.log("account na", await verbruik());
} else if (commando === "vragen") {
  const werkgebied = optie("--werkgebied", rest), commit = optie("--commit", rest), map = optie("--uit", rest) ?? ".";
  const vormenJson = optie("--vormen", rest);
  const [setnaam, nr, ...ids] = rest;
  if (!["kwaliteit", "duiding", "partijen", "klassen", "gesprek"].includes(setnaam) || !nr || !commit || !vormenJson) {
    console.error("vragen <kwaliteit|duiding|partijen|klassen|gesprek> <nr> --commit <sha> --vormen <json> [--werkgebied <id>] [--uit <map>] [id ...]"); process.exit(2);
  }
  let vormen;
  try { vormen = Object.entries(JSON.parse(vormenJson)); } catch { console.error("--vormen is geen JSON"); process.exit(2); }
  if (!vormen.length || vormen.some(([naam, v]) => !/^[a-z0-9-]+$/.test(naam) || !v || typeof v !== "object" || Array.isArray(v))) {
    console.error("--vormen: een object van vormnaam (kleine letters, cijfers, streepjes) naar de velden op de beurt"); process.exit(2);
  }
  const cases = (setnaam === "kwaliteit"
    ? leesSet("golden.jsonl").map((c, i) => ({ id: `K${String(i + 1).padStart(2, "0")}`, beurten: [{ vraag: c.question }] }))
    : setnaam === "duiding"
      ? leesSet("golden_duiding.jsonl").map(c => ({ id: c.id, beurten: [{ vraag: c.question }] }))
      : setnaam === "partijen"
        ? leesSet("golden_duiding_partijen.jsonl").map(c => ({ id: c.id, beurten: [{ vraag: c.question }] }))
      : setnaam === "klassen"
        ? leesSet("golden_klasse_twijfel.jsonl").map(c => ({ id: c.id, beurten: [{ vraag: c.question }] }))
      : leesSet("golden_gesprek.jsonl").map(c => ({ id: c.id, beurten: c.beurten })))
    .filter(c => !ids.length || ids.includes(c.id));
  const onbekend = ids.filter(i => !cases.some(c => c.id === i));
  if (onbekend.length) { console.error("onbekend:", onbekend.join(", ")); process.exit(2); }
  const bestand = vorm => path.join(map, `ruw-${setnaam}-${vorm}-run${nr}.jsonl`);
  const gedaan = Object.fromEntries(vormen.map(([vorm]) => [vorm, new Set(fs.existsSync(bestand(vorm))
    ? fs.readFileSync(bestand(vorm), "utf8").split("\n").filter(Boolean).map(r => JSON.parse(r).id) : [])]));
  console.log("account vóór", await verbruik());
  for (const [i, c] of cases.entries()) {
    // Om en om: de ene case begint met de eerste vorm, de volgende met de laatste.
    for (const [vorm, velden] of i % 2 ? [...vormen].reverse() : vormen) {
      if (gedaan[vorm].has(c.id)) continue;
      const kop = { id: c.id, set: setnaam, run: Number(nr), commit, vorm };
      const rec = await metHerhalen(c.id, kop, () => vraagcase(c, kop, werkgebied, velden));
      fs.appendFileSync(bestand(vorm), JSON.stringify(rec) + "\n");
      console.log(c.id, vorm, rec.mislukt ?? "", `beurten ${rec.beurten.length}`, rec.herhaald ? `herhaald ${rec.herhaald}` : "");
    }
  }
  console.log("account na", await verbruik());
} else {
  console.error("gebruik: werkgebied | run <nr> … | vragen <kwaliteit|duiding|partijen|klassen|gesprek> <nr> … (zie de kop van dit bestand)");
  process.exit(2);
}
