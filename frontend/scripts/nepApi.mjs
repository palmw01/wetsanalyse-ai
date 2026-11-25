/** Gedeelde bouwstenen voor de nep-api van de browserscripts (Lex Bench §20.5 stap 2, testplan werkplek voorstel 2 en 4).
 *
 * **De SSE-stroom zoals graph-qa hem stuurt.** sse-starlette scheidt frames met `\r\n`, elk event draagt `seq`, en tussen
 * de events kan een commentaarregel (`: ping`) staan. Een eigen `sse()` per script met `\n\n` toetste de parser van de
 * werkplek dus nooit op de echte vorm (die viel daar eerder stil op, `frontend/lib/api.ts`). `sse(events)` maakt de
 * echte vorm; met `vanaf` begint hij bij dat volgnummer, zoals `/events?vanaf=` van graph-qa. Een stroom die halverwege
 * afbreekt, is een stroom zonder `done`: de werkplek haakt dan opnieuw aan met `vanaf` (`stroomInDelen`).
 *
 * **Een onbekend pad is een fout, geen stille 200.** Een nep-api die alles wat hij niet kent met `200 []` beantwoordt,
 * laat een gewijzigde of vergeten aanroep van de werkplek ongemerkt door. `onbekend(route)` antwoordt met 501, onthoudt
 * de aanroep, en `controleerOnbekend()` aan het eind van het script faalt als er zo'n aanroep was. Wie een pad bewust
 * niet nabootst, zegt dat per pad: `onbekend(route, { stil: [/^GET \/api\/berichten/] })`. Met `NEPAPI_LOG=1` meldt hij elk
 * onbekend pad meteen, ook als het script eerder op een assert faalt.
 */

const ONBEKEND = [];

/** De events als SSE-body in de vorm van graph-qa: `data: {...}\r\n\r\n`, met `seq` (het eigen `seq` van een event gaat
 *  voor), vanaf volgnummer `vanaf`. `ping` zet een commentaarregel vóór elk event, zoals de keep-alive van sse-starlette. */
export function sse(events, { vanaf = 0, ping = false } = {}) {
  return events
    .map((e, i) => ({ seq: i, ...e }))
    .filter((e) => e.seq >= vanaf)
    .map((e) => `${ping ? ": ping\r\n\r\n" : ""}data: ${JSON.stringify(e)}\r\n\r\n`)
    .join("");
}

/** Een stroom die na `breek` events afbreekt (zonder `done`) en bij het opnieuw aanhaken met `?vanaf=` verder gaat.
 *  Geeft een handler voor de route van `/events` en een lijst van de `vanaf`-waarden waarmee de werkplek aanhaakte. */
export function stroomInDelen(events, { breek, ping = false }) {
  const aangehaakt = [];
  const handler = (route) => {
    const vanaf = Number(new URL(route.request().url()).searchParams.get("vanaf") ?? "0");
    aangehaakt.push(vanaf);
    const eerste = aangehaakt.length === 1;
    const deel = eerste ? events.slice(0, breek) : events;
    return route.fulfill({ contentType: "text/event-stream", body: sse(deel, { vanaf: eerste ? 0 : vanaf, ping }) });
  };
  return { handler, aangehaakt };
}

/** De aanroepen van de schil om elke pagina heen (account, verbruik, berichten, de bronnen boven het invoerveld), en de
 *  afleidingsregels die elke werkgebiedpagina en begripskaart leest (de artefactkaart, *Afgeleid door*; ADR-018). Een
 *  script dat die niet toetst, zegt dat met `stil: SCHIL`; ze krijgen dan een leeg antwoord, zoals vroeger. */
export const SCHIL = [
  /^GET \/api\/account\/me$/, /^GET \/api\/account\/verbruik$/, /^GET \/api\/berichten\/ongelezen-aantal$/,
  /^GET \/api\/connectors$/, /^GET \/api\/gesprekken$/, /^GET \/api\/annotatie\/run$/, /^POST \/api\/ui-spoor$/,
  /^GET \/api\/werkgebieden\/[^/]+\/regels$/, /^GET \/api\/plugins$/,
];

/** Beantwoord een pad dat de nep-api niet kent met 501 en onthoud het, tenzij het onder `stil` valt (een lijst van
 *  RegExp op `"<METHODE> <pad>"`); dat krijgt `leeg` als antwoord, met `stilStatus` (standaard 200). */
export function onbekend(route, { stil = [], leeg = [], stilStatus = 200 } = {}) {
  const req = route.request();
  const sleutel = `${req.method()} ${new URL(req.url()).pathname}`;
  if (stil.some((r) => r.test(sleutel))) return route.fulfill({ status: stilStatus, json: leeg });
  ONBEKEND.push(sleutel);
  if (process.env.NEPAPI_LOG) console.error(`nep-api: niet nagebootst: ${sleutel}`);
  return route.fulfill({ status: 501, json: { detail: `Niet nagebootst in deze test: ${sleutel}` } });
}

/** Faal als de werkplek een pad aanriep dat de nep-api niet kent. Roep dit aan het eind van het script aan. */
export function controleerOnbekend() {
  const uniek = [...new Set(ONBEKEND)];
  if (uniek.length) {
    throw new Error(`De werkplek riep paden aan die de nep-api niet kent (zet ze erbij, of zeg per pad dat ze stil mogen):\n  ${uniek.join("\n  ")}`);
  }
}
