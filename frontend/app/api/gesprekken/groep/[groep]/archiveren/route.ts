import { geenSessie, sessionUserId } from "@/app/api/_lib/session";
import { bulk, idsInGroep, isGroep, onbekendeGroep } from "../_groep";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ groep: string }> };

/** Archiveer alle eigen gesprekken in een groep in één keer. Het geheugen van Lex blijft: archiveren is terug te
 *  halen. De api accepteert alleen `recent`. */
export async function POST(_req: Request, { params }: Params) {
  const userid = await sessionUserId();
  if (!userid) return geenSessie();
  const { groep } = await params;
  if (!isGroep(groep)) return onbekendeGroep();
  const lijst = await idsInGroep(groep, userid);
  if ("fout" in lijst) return lijst.fout;
  return bulk("archiveren", groep, lijst.ids, userid);
}
