// BFF-route voor het starten en opzoeken van een agent-run (graph-qa /v1/runs).
//
// Waarom een run en geen open verbinding: die koppelde de beurt aan één tabblad — wegklikken of
// herladen doodde het antwoord. Een run is een object van de server; starten,
// meekijken (`[id]/events`) en stoppen (`[id]/cancel`) zijn losse handelingen.

import { proxy, sluit } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { isPuntSegment, pathSegment } from "@/lib/url";

export const dynamic = "force-dynamic";

// Starten is een korte call: de agent zet een achtergrondtaak weg en antwoordt meteen. Het lange
// wachten gebeurt op de events-route, niet hier. Behalve bij een koude start: graph-qa staat op
// `minReplicas: 0`, en dan houdt Azure de request vast tot de replica de readiness-probe haalt.
// Gemeten op acceptatie (6 okt 2026): ~15 s van request tot routering – precies op de oude grens
// van 15 s, met "Agent onbereikbaar" als gevolg terwijl de agent net opkwam.
const START_TIMEOUT_MS = 45_000;

export async function POST(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();

  // De identiteit gaat als HEADER mee, niet in de body – één mechanisme voor alle run-routes en
  // hetzelfde als de api hanteert. Staat ze ook in de body, dan lopen de twee bronnen bij de eerste
  // eigenaarscontrole meteen uit elkaar.
  const body = await req.text();
  let gesprekId = "";
  try {
    const ontleed = JSON.parse(body) as Record<string, unknown>;
    gesprekId = typeof ontleed.conversation_id === "string" ? ontleed.conversation_id : "";
  } catch {
    // Geen geldige JSON: laat de agent er zelf een 422 van maken in plaats van hier te raden.
  }

  // Is dit gesprek wel van jou? `conversation_id` is óók de thread_id van het agent-geheugen, dus
  // zonder deze controle kan iemand met een vreemd gespreks-id een vraag in andermans geheugen
  // injecteren en de context daarvan teruglezen. De api is de eigenaarsadministratie; die vragen we.
  if (gesprekId) {
    const eigen = await proxy(`/v1/gesprekken/${pathSegment(gesprekId)}`, {
      headers: { "X-User-Id": userid },
    });
    if (eigen.status === 404) {
      await sluit(eigen);
      return Response.json({ detail: "Onbekend gesprek." }, { status: 404 });
    }
    // Elke andere fout is een storing bij de api, geen oordeel over het gesprek: die status gaat
    // ongewijzigd door, zodat de werkplek "probeer het zo opnieuw" kan zeggen in plaats van
    // "onbekend gesprek".
    if (!eigen.ok) return eigen;
    await sluit(eigen);
  }

  // Bewust ZONDER `req.signal`: de browser die deze POST afbreekt mag de run niet meenemen — dat was
  // precies de oude fout. `proxy()` geeft hem ook niet door; alleen een eigen timeout op het starten.
  // 409 (er loopt al een run) gaat ongewijzigd door: de client hoort daarop aan te haken bij het
  // meegegeven run_id, niet te falen.
  return proxy("/v1/runs", {
    agent: true,
    method: "POST",
    headers: { "X-User-Id": userid, "Content-Type": "application/json" },
    body,
    timeoutMs: START_TIMEOUT_MS,
  });
}

/** `?gesprek=<id>` → de run waar je op kunt aanhaken, of `null`. Dit is wat de werkplek bij
 *  binnenkomst vraagt om een lopende beurt weer in beeld te krijgen.
 *
 *  `?actief=1` → je runs over alle gesprekken heen: de lopende plus wat de laatste tien minuten
 *  eindigde (`[{run_id, conversation_id, status, afgerond_op?}]`). Daaruit toont de sidebar welk
 *  gesprek bezig is of een nieuw antwoord heeft (`lib/runStanden.ts`). `proxy()` zet de
 *  `traceparent` er zelf op (`metTrace()`). */
export async function GET(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();

  const params = new URL(req.url).searchParams;
  if (params.get("actief") === "1") {
    // Ook hier is de header de eigenaarscontrole: zonder zou de lijst van iedereen zijn.
    return proxy("/v1/runs?actief=true", {
      agent: true,
      headers: { "X-User-Id": userid },
      timeoutMs: 10_000,
    });
  }

  const gesprek = params.get("gesprek") ?? "";
  // `pathSegment` weigert `..` met een fout, en die zou hieronder een 502 worden.
  if (!gesprek || isPuntSegment(gesprek)) return Response.json(null);
  // Een fout is géén `null`: `null` betekent "er loopt niets", en dat is een uitspraak die we bij een
  // storing juist niet kunnen doen. Gaven we hem toch, dan las de werkplek een timeout als een beurt
  // die verdwenen was – mét de bijbehorende waarschuwing – terwijl de run gewoon doorliep. `proxy()`
  // geeft dan 502/504, en de client maakt het onderscheid (`haalActieveRun` → `"onbekend"`).
  return proxy(`/v1/conversations/${pathSegment(gesprek)}/run`, {
    agent: true,
    // Zonder deze header zou een gespreks-id – dat gewoon in de URL van de werkplek staat — genoeg
    // zijn om andermans lopende vraag en antwoord te lezen.
    headers: { "X-User-Id": userid },
    timeoutMs: 10_000,
  });
}
