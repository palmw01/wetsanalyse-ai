// Publieke BFF-route voor zelfregistratie (vóór er een sessie bestaat).
// POST → leg een aanvraag vast die een beheerder nog moet goedkeuren. Dit maakt géén account.
// De API weigert een dubbel e-mailadres met 409 en heeft een eigen, krappe rate limit (429).
import { proxy, readBody } from "@/app/api/_lib/proxy";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await readBody(req);
  return proxy(`/v1/auth/registratie`, {
    method: "POST",
    body,
    headers: { "Content-Type": "application/json" },
  });
}
