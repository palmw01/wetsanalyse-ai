// Publieke stap B van de login (het aparte /login/2fa-scherm): verifieert de TOTP-code met het
// login-ticket uit stap A (httpOnly cookie) – het wachtwoord is hier dus niet nodig. Bij "30 dagen
// onthouden" zet de route een httpOnly trusted-device-cookie. Zet géén sessie; dat doet de
// daaropvolgende signIn, die het 2FA-ticket uit deze stap server-side in authorize meestuurt.
import { postAuthVerify } from "@/lib/server";
import {
  getLoginTicketCookie,
  setLoginTicketCookie,
  setTrustedDeviceCookie,
} from "@/lib/authCookies";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const { userid, totp, remember } = (await req.json().catch(() => ({}))) as {
    userid?: string;
    totp?: string;
    remember?: boolean;
  };
  const ticket = (await getLoginTicketCookie()) ?? null;
  if (!ticket) {
    // Geen (geldig) ticket meer → stap A opnieuw doen.
    return Response.json({ ok: false, code: "invalid" }, { status: 401 });
  }

  const { status, body } = await postAuthVerify({
    userid: userid ?? "",
    ticket,
    totp: totp ?? null,
    remember: remember === true,
  });

  if (body.ok && body.trusted_token) {
    // "Dit apparaat 30 dagen onthouden": sla de 2FA-prompt voortaan over op deze browser.
    await setTrustedDeviceCookie(body.trusted_token);
  }
  // Een TOTP-code geldt maar één keer. De aansluitende signIn verifieert nog een keer (authorize in
  // `auth.ts`) en kan de code dan niet opnieuw gebruiken; in plaats daarvan geeft de api na een
  // geslaagde code een 2FA-ticket mee. Dat vervangt het login-ticket in dezelfde httpOnly cookie,
  // zodat authorize het zonder verdere wijziging meestuurt. `authorize` wist de cookie na de login.
  if (body.ok && body.ticket) {
    await setLoginTicketCookie(body.ticket);
  }

  // De status gaat ongewijzigd mee (BFF-regel): een afgewezen code is bij de API een 200 met
  // `ok: false`, dus een 5xx hier is een storing – en die mag de client niet als "verkeerde code"
  // tonen. De 401 hierboven (ticket verlopen) blijft wat hij is.
  return Response.json({ ok: body.ok, code: body.code, userid: userid ?? "" }, { status });
}
