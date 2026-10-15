// BFF-route: Lex bepalingen laten zoeken voor een werkgebied (spoor D, fase A). Zelfde vorm als
// `app/api/begrippen-run` (`_lib/werkgebiedRun.ts`); de runstore-sleutel bij graph-qa is
// `werkgebied:<id>:bronnen`, zodat zoeken en begrippen voorstellen naast elkaar kunnen lopen.

import { lopendeWerkgebiedRun, startWerkgebiedRun, type RunSoort } from "@/app/api/_lib/werkgebiedRun";

export const dynamic = "force-dynamic";

const SOORT: RunSoort = { pad: "bronnen-runs", sleutel: (w) => `werkgebied:${w}:bronnen`, naam: "Bronnenrun" };

export async function POST(req: Request) {
  return startWerkgebiedRun(req, SOORT);
}

export async function GET(req: Request) {
  return lopendeWerkgebiedRun(req, SOORT);
}
