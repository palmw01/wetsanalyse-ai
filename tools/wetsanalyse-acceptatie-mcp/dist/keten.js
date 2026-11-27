/**
 * Het ketenscenario op acceptatie (Lex Bench §20.5 stap 5, keten 3): inloggen met het accounttoken, via de BFF een
 * werkgebied en een gesprek maken, ze teruglezen, de vangrail toetsen op het echte account, en precies die twee weer
 * opruimen. Zonder model: er gaan geen tokens op.
 *
 * Het account is dat van de gebruiker, met eigen gesprekken en metingen. Het scenario maakt daarom alleen objecten met
 * het voorvoegsel `lex-bench-keten · <run>`, ruimt alleen die op, verwijdert nooit in bulk, en telt vooraf en achteraf
 * wat er verder staat: dat moet gelijk blijven.
 */
import { inRunruimte, leesRuimte, opruimplan, toetsVerwijderen, VOORVOEGSELS, voerUit } from "./runruimte.js";
import { opCodepunt } from "./tekst.js";
export const KETEN = VOORVOEGSELS[0];
class KetenFout extends Error {
}
function eis(stappen, stap, ok, detail = "") {
    stappen.push({ stap, ok, ...(detail ? { detail } : {}) });
    if (!ok)
        throw new KetenFout(`${stap}${detail ? `: ${detail}` : ""}`);
}
const id = (data) => String(data?.id ?? "");
/** De ids van alles wat er stond. De gebruiker kan intussen werken, dus erbij komen mag; verdwijnen niet. */
function ids(ruimte) {
    return new Set([...ruimte.werkgebieden.map((x) => `w:${x.id}`), ...ruimte.gesprekken.map((x) => `g:${x.id}`)]);
}
export async function ketenScenario(c, run) {
    const voorvoegsel = `${KETEN}${run}`;
    const stappen = [];
    let ik = "";
    try {
        const voor = await leesRuimte(c);
        ik = voor.ik;
        eis(stappen, "inloggen met het accounttoken", Boolean(ik));
        eis(stappen, "geen restanten van deze run", opruimplan(voorvoegsel, ik, voor.werkgebieden, voor.gesprekken)
            .werkgebieden.length === 0);
        const w = await c.bff("POST", "/api/werkgebieden", {
            naam: `${voorvoegsel} werkgebied`,
            analysevraag: "Ketentest: maakt alleen eigen objecten en ruimt alleen die op.",
        });
        const wid = id(w.data);
        eis(stappen, "werkgebied maken", w.status === 201 && Boolean(wid), `status ${w.status}`);
        const g = await c.bff("POST", "/api/gesprekken", { titel: `${voorvoegsel} gesprek`, werkgebied_id: wid });
        const gid = id(g.data);
        eis(stappen, "gesprek in het werkgebied maken", g.status === 201 && Boolean(gid), `status ${g.status}`);
        const wl = await c.bff("GET", `/api/werkgebieden/${encodeURIComponent(wid)}`);
        const wd = (wl.data ?? {});
        eis(stappen, "werkgebied teruglezen", wl.status === 200 && wd.naam === `${voorvoegsel} werkgebied`
            && wd.aangemaakt_door === ik);
        const gl = await c.bff("GET", `/api/gesprekken/${encodeURIComponent(gid)}`);
        eis(stappen, "gesprek teruglezen", gl.status === 200
            && gl.data?.werkgebied_id === wid);
        // De vangrail op het echte account: alleen een oordeel, er gaat geen DELETE uit.
        const midden = await leesRuimte(c);
        const vreemd = midden.gesprekken.find((x) => !inRunruimte(x.titel) && !x.werkgebied_id && !x.ouder_id);
        if (vreemd) {
            const o = await toetsVerwijderen(c, "DELETE", `/api/gesprekken/${encodeURIComponent(vreemd.id)}`, ik);
            eis(stappen, "vangrail weigert een gesprek dat de run niet maakte", !o.mag, o.mag ? "toegestaan" : "");
        }
        else {
            stappen.push({ stap: "vangrail op een ander gesprek", ok: true, detail: "het account heeft geen ander gesprek" });
        }
        const bulk = await toetsVerwijderen(c, "POST", "/api/gesprekken/verwijderen", ik);
        eis(stappen, "vangrail weigert bulkverwijderen", !bulk.mag);
        const plan = opruimplan(voorvoegsel, ik, midden.werkgebieden, midden.gesprekken);
        const gevonden = [...plan.werkgebieden.map((x) => x.id), ...plan.gesprekken.map((x) => x.id)].sort(opCodepunt);
        eis(stappen, "opruimplan bevat precies wat de run maakte", JSON.stringify(gevonden) === JSON.stringify([wid, gid].sort(opCodepunt)), gevonden.join(", "));
        const uit = await voerUit(c, plan, ik);
        eis(stappen, "opruimen", uit.verwijderd.length === 2 && uit.geweigerd.length === 0, uit.geweigerd.join("; "));
        const na = await leesRuimte(c);
        eis(stappen, "werkgebied en gesprek zijn weg", !na.werkgebieden.some((x) => x.id === wid)
            && !na.gesprekken.some((x) => x.id === gid));
        const nu = ids(na);
        const weg = [...ids(voor)].filter((x) => !nu.has(x));
        eis(stappen, "niets anders van het account is verdwenen", weg.length === 0, weg.join(", "));
        return { ok: true, stappen };
    }
    catch (e) {
        if (!(e instanceof KetenFout))
            stappen.push({ stap: "onverwachte fout", ok: false, detail: e.message });
        // Best effort: wat deze run maakte, gaat weg; langs dezelfde vangrail, nooit iets anders.
        if (ik) {
            try {
                const r = await leesRuimte(c);
                await voerUit(c, opruimplan(voorvoegsel, ik, r.werkgebieden, r.gesprekken), ik);
            }
            catch {
                stappen.push({ stap: "opruimen na de fout", ok: false });
            }
        }
        return { ok: false, stappen };
    }
}
