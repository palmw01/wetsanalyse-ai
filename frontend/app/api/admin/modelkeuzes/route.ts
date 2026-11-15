// De modelkeuzes van Lex voor het beheer (api `GET /v1/admin/modelkeuzes`): per sleutel het gekozen profiel, of het
// bruikbaar is, wie koos, en per profiel waar het gekozen is. Achter `admin: true`.
import { proxy } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxy(`/v1/admin/modelkeuzes`, { admin: true });
}
