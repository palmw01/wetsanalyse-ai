/**
 * Het gedeelde logboek van een run: `docs/acceptatie/lokaal/<run>/logboek.md`.
 *
 * De agents hebben geen schrijftools en ook geen shell, en dat blijft zo. Deze twee functies zijn hun
 * enige schrijfweg, en die kan alleen aanvullen: het pad ligt vast, het bestand opent in append-modus,
 * en een run-naam kan niet buiten de map wijzen. Eén kleine schrijfactie per regel zorgt dat twee agents
 * tegelijk elkaars regels niet door elkaar halen. De map is gitignored; dossierinhoud mag hier dus wel.
 */
import { appendFile, mkdir, readFile } from "node:fs/promises";
import { join } from "node:path";
/** De rollen van het E2E-team, en die van Lex Bench (analist en reviewer, plan-lex-bench §4.2 en §5). */
export const ROLLEN = ["jurist", "gegevensspecialist", "regelspecialist", "coördinator", "analist", "reviewer"];
/** Wie in een onenigheid een argument kan geven: de drie leden van het E2E-team. */
export const TEAM = ["jurist", "gegevensspecialist", "regelspecialist"];
export const SOORTEN = ["beslissing", "onenigheid", "overleg", "id", "bevinding", "omweg", "stand"];
const GEHEIM = /wa_pat_|wa_admin_|Bearer\s+\S|admin:[0-9a-f]{16}/;
/** Het logboek hoort bij de checkout met het dossier, ook als de sessie in een worktree draait. */
export function standaardMap(root) {
    return join(root.replace(/[/\\]\.claude[/\\]worktrees[/\\][^/\\]+[/\\]?$/, ""), "docs", "acceptatie", "lokaal");
}
function pad(map, run) {
    if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(run))
        throw new Error("Een run heet bijvoorbeeld rekeningafspraak-2026-11-06.");
    return join(map, run, "logboek.md");
}
export function alsTekst(r, nu) {
    const kop = [nu.toISOString().slice(0, 19) + "Z", `[${r.rol}]`, r.soort, ...(r.stap === undefined ? [] : [`stap ${r.stap}`])];
    const delen = [`### ${kop.join(" · ")}`, r.tekst.trim()];
    const argumenten = gevuld(r.argumenten);
    if (argumenten.length)
        delen.push(argumenten.map(([rol, a]) => `- ${rol}: ${a}`).join("\n"));
    if (r.ids?.length)
        delen.push(`ids: ${r.ids.join(", ")}`);
    return delen.join("\n\n") + "\n\n";
}
/** De argumenten die er echt staan, in de vaste volgorde van het team. */
function gevuld(argumenten) {
    return TEAM.flatMap((rol) => {
        const a = argumenten?.[rol]?.trim();
        return a ? [[rol, a]] : [];
    });
}
export async function aanvullen(map, r, nu = new Date()) {
    const bestand = pad(map, r.run);
    if (r.soort === "onenigheid" && gevuld(r.argumenten).length < 2) {
        throw new Error("Een onenigheid legt beide argumenten vast: van elke kant één, minstens twee.");
    }
    const tekst = alsTekst(r, nu);
    if (GEHEIM.test(tekst))
        throw new Error("Dit lijkt een token of wachtwoord: dat hoort niet in het logboek.");
    await mkdir(join(map, r.run), { recursive: true });
    await appendFile(bestand, tekst, { flag: "a" });
    return { pad: bestand };
}
/** Lees vanaf een eerdere stand, zodat een agent alleen het nieuwe leest en niet elke keer alles. */
export async function lezen(map, run, vanaf = 0) {
    let inhoud;
    try {
        inhoud = await readFile(pad(map, run));
    }
    catch (e) {
        if (e.code === "ENOENT")
            return { tekst: "", vanaf: 0 };
        throw e;
    }
    return { tekst: inhoud.subarray(vanaf).toString("utf8"), vanaf: inhoud.length };
}
