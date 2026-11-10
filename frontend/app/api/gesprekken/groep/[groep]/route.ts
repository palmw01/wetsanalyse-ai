import { wisAgentGeheugenBulk } from "@/app/api/_lib/agentGeheugen";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { logger } from "@/lib/logger";
import { bulk, idsInGroep, isGroep, onbekendeGroep } from "./_groep";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ groep: string }> };

/** Verwijder alle eigen gesprekken in een groep (`recent` of `archief`) in één keer.
 *
 *  Dezelfde volgorde als bij één gesprek (`../../[id]/route.ts`), maar per stap één verzoek voor de hele groep:
 *  1. de ids bij de api (dat zijn per definitie de eigen gesprekken);
 *  2. de lopende beurten stoppen en het geheugen van Lex wissen, in één verzoek aan graph-qa (best-effort);
 *  3. de api wist precies die ids, in één transactie. Een gesprek dat tussen 1 en 3 ontstond, gaat dus niet mee: van
 *     dat gesprek is het geheugen niet gewist. */
export async function DELETE(_req: Request, { params }: Params) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { groep } = await params;
  if (!isGroep(groep)) return onbekendeGroep();
  const start = performance.now();
  const lijst = await idsInGroep(groep, userid);
  if ("fout" in lijst) return lijst.fout;
  await wisAgentGeheugenBulk(lijst.ids, userid);
  const res = await bulk("verwijderen", groep, lijst.ids, userid);
  logger.info("Gesprekken verwijderen", {
    http_status: res.status,
    groep,
    aantal: lijst.ids.length,
    duur_ms: Math.round(performance.now() - start),
  });
  return res;
}
