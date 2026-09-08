// Ontvangt de UI-sporen uit `lib/uiSpoor.ts` en schrijft ze als gewone logregel weg.
//
// Waarom deze route bestaat: een klik die niets deed laat nergens een spoor achter. De BFF logt
// alleen wat er langs `proxy()` komt, dus juist de twee gevallen die onderzocht worden — de klik die
// nooit een request werd, en de call die nog liep toen de gebruiker het opgaf — zijn onzichtbaar.
//
// De route neemt niets van de client over dan wat `leesSpoor` erkent: een actienaam uit een gesloten
// lijst, een uitkomst, een duur en een http-status. Geen vrije tekst, dus ook geen gebruikersinhoud
// die hier ongemerkt in een logregel belandt. De identiteit komt uit de sessie en gaat NIET mee de
// log in: waar het om gaat is dát een handeling bleef hangen, niet bij wie.

import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { Venstertel } from "@/app/api/_lib/venstertel";
import { logger } from "@/lib/logger";
import { leesSpoor } from "@/lib/uiSpoor";

export const dynamic = "force-dynamic";

/** Hoogstens zoveel meldingen per gebruiker per minuut. Een waarneming mag geen logstroom worden
 *  als er in de browser iets in een lus raakt. Een handeling levert twee regels (`gestart` + de
 *  uitkomst), dus zestig is ruim boven wat een mens in een minuut aanklikt. */
const rem = new Venstertel(60, 60_000);

export async function POST(req: Request) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();

  let ruw: unknown;
  try {
    ruw = await req.json();
  } catch {
    return new Response(null, { status: 400 });
  }
  const spoor = leesSpoor(ruw);
  if (!spoor) return new Response(null, { status: 400 });
  // Stil weigeren: de client kan er niets mee, en een fout terugsturen naar een `sendBeacon` is
  // sowieso een gesprek met niemand.
  if (!rem.mag(userid)) return new Response(null, { status: 204 });

  // Platte velden, en `http_status`/`duur_ms` met dezelfde namen als in `proxy.ts`: dan staan de
  // klik en de bijbehorende upstream-call in dezelfde query naast elkaar.
  logger.info("UI-actie", {
    ui_actie: spoor.actie,
    ui_uitkomst: spoor.uitkomst,
    duur_ms: spoor.duur_ms,
    http_status: spoor.status,
  });
  return new Response(null, { status: 204 });
}
