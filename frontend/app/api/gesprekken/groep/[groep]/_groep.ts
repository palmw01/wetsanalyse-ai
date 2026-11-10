import { proxy } from "@/app/api/_lib/proxy";

/** De groepen die je in één keer opruimt; de api kent dezelfde (`GesprekGroep`). */
export const GROEPEN = ["recent", "archief"] as const;
export type Groep = (typeof GROEPEN)[number];

export function isGroep(waarde: string): waarde is Groep {
  return (GROEPEN as readonly string[]).includes(waarde);
}

export const onbekendeGroep = () => Response.json({ detail: "Onbekende groep." }, { status: 404 });

/** De ids in de groep zoals de api ze nu ziet; lukt dat niet, dan het foutantwoord (en gebeurt er niets). */
export async function idsInGroep(groep: Groep, userid: string): Promise<{ ids: string[] } | { fout: Response }> {
  const res = await proxy(`/v1/gesprekken/groep/${groep}`, { headers: { "X-User-Id": userid } });
  if (!res.ok) return { fout: res };
  return { ids: ((await res.json()) as { ids: string[] }).ids };
}

/** De bulkhandeling bij de api, met de ids die de route net ophaalde. */
export function bulk(handeling: "verwijderen" | "archiveren", groep: Groep, ids: string[], userid: string) {
  const init = {
    method: "POST",
    body: JSON.stringify({ groep, ids }),
    headers: { "X-User-Id": userid, "Content-Type": "application/json" },
  };
  // Twee letterlijke paden in plaats van één sjabloon: het routecontract (`tests/poort/`) leest ze zo.
  return handeling === "verwijderen"
    ? proxy(`/v1/gesprekken/verwijderen`, { ...init, method: "POST" })
    : proxy(`/v1/gesprekken/archiveren`, { ...init, method: "POST" });
}
