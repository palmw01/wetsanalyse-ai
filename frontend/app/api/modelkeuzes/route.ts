// Welk model Lex per agentprofiel en per stap gebruikt, om te lezen (api `GET /v1/modelkeuzes`): profielnaam,
// modelnaam en de catalogus van sleutels, nooit endpoint of sleutel. Voor elke ingelogde gebruiker; kiezen staat onder
// `/api/admin/modelkeuzes`.
import { proxy } from "@/app/api/_lib/proxy";
import { geenSessie, sessionUserId } from "@/app/api/_lib/session";

export const dynamic = "force-dynamic";

export async function GET() {
  if (!(await sessionUserId())) return geenSessie();
  return proxy(`/v1/modelkeuzes`);
}
