/**
 * Een beurt starten zoals de werkplek dat doet.
 *
 * De werkplek doet twee aanroepen op de BFF: eerst bewaart hij de vraag als user-bericht
 * (`POST /api/gesprekken/<id>/berichten`), daarna start hij de run (`POST /api/annotatie/run`). graph-qa legt alleen
 * het antwoord vast. Wie alleen de run start, krijgt dus een gesprek met antwoorden zonder vragen. Deze module neemt
 * dezelfde twee stappen in dezelfde volgorde (`frontend/components/werkplek/WerkplekClient.tsx`, `verstuur`).
 *
 * Wat er op het user-bericht staat volgt `userVelden` in `frontend/lib/beurtVerzoek.ts` en `antwoordOp` in
 * `frontend/lib/vraagkaart.ts`. Alleen het label van een onderwerp-chip (`Bij <label>: …`) ontbreekt: dat kent alleen de
 * browser. `tests/poort/test_gedeelde_lijsten.py` let erop dat de velden niet uit elkaar lopen.
 */
const tekstVeld = (v) => typeof v === "string" && v !== "";
/** Het user-bericht bij een run-body: de vraag, en bij een klik wat de knop beantwoordt. */
export function vraagBericht(body) {
    const bericht = { rol: "user", tekst: String(body.question ?? "") };
    // Een klik op een vraagkaartje: zo staat het antwoord na herladen weer in de Vragen-kaart (`antwoordOp`).
    const k = body.intake_actie;
    if (k && typeof k === "object" && !Array.isArray(k)) {
        const a = k;
        if (tekstVeld(a.intake_id) && tekstVeld(a.stap) && tekstVeld(a.actie)) {
            bericht.intake_antwoord = {
                intake_id: a.intake_id, stap: a.stap, ...(typeof a.deel === "number" ? { deel: a.deel } : {}), actie: a.actie,
                ...(tekstVeld(a.deelvraag_id) ? { deelvraag_id: a.deelvraag_id } : {}),
            };
        }
    }
    // Een knop bij een voorstel van Lex (`bevestigt`): daarna staat er geen knop meer.
    if (body.bevestigd !== undefined || tekstVeld(body.plan_id))
        bericht.bevestiging_antwoord = { keuze: "gestart" };
    return bericht;
}
/** Start een beurt: eerst de vraag in het gesprek, dan de run. Zoals in de werkplek blokkeert een mislukt bewaren de
 *  beurt niet; wat er misging staat in `vraag`. */
export async function lexStart(c, a) {
    const body = {
        question: a.vraag,
        conversation_id: a.conversation_id,
        ...a.extra,
        ...(a.werkgebied_id ? { werkgebied_id: a.werkgebied_id } : {}),
        ...(a.intake_actie ? { intake_actie: a.intake_actie } : {}),
        ...(a.actie ? { actie: a.actie } : {}),
    };
    let vraag;
    if (a.vraag_bewaren !== false) {
        // Bewust vóór de run: de thread is geordend op volgorde van binnenkomst, en een snelle beurt zou anders vóór zijn
        // eigen vraag landen.
        try {
            const r = await c.bff("POST", `/api/gesprekken/${encodeURIComponent(a.conversation_id)}/berichten`, vraagBericht(body));
            vraag = r.status < 300 ? { status: r.status } : { status: r.status, fout: r.data };
        }
        catch (e) {
            vraag = { status: 0, fout: e.message };
        }
    }
    const run = await c.bff("POST", "/api/annotatie/run", body);
    return vraag ? { ...run, vraag } : run;
}
