// BFF-route: Lex begrippen laten voorstellen voor een werkgebied (spoor D, levering 3a). De vorm deelt
// hij met `app/api/bronnen-run` (`_lib/werkgebiedRun.ts`).
//
// Een statische route en geen `app/api/werkgebieden/[id]/…`: naast de catch-all `[...pad]` op dat
// niveau weigert Next een tweede dynamische naam (`app/routes.test.ts`).

import { lopendeWerkgebiedRun, startWerkgebiedRun, type RunSoort } from "@/app/api/_lib/werkgebiedRun";

export const dynamic = "force-dynamic";

const SOORT: RunSoort = { pad: "begrippen-runs", sleutel: (w) => `werkgebied:${w}`, naam: "Begrippenrun" };

export async function POST(req: Request) {
  return startWerkgebiedRun(req, SOORT);
}

export async function GET(req: Request) {
  return lopendeWerkgebiedRun(req, SOORT);
}
