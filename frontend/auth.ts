// Volledige Auth.js-setup (Node-runtime): de Credentials-provider verifieert e-mail + wachtwoord
// (+ optionele TOTP) server→server tegen de API. De API is de identiteitsbron; Auth.js houdt
// alleen de browsersessie (httpOnly cookie, JWT-strategie). Het API-token blijft server-side
// (via lib/server.ts) en komt nooit in de browser.

import NextAuth from "next-auth";
import { encode } from "next-auth/jwt";
import Credentials from "next-auth/providers/credentials";
import { authConfig, SESSIE_KORT, SESSIE_LANG, type Role } from "./auth.config";
import { getAccountStatus, verifyCredentials, type AccountStatus } from "@/lib/server";
import { sessieGerevoceerd } from "@/lib/sessie";
import { clearLoginTicketCookie, getLoginTicketCookie, getTrustedDeviceCookie } from "@/lib/authCookies";

// Hoe lang een JWT op de laatste verificatie mag teren voordat we de accountstatus opnieuw
// bij de API checken. Samen met session.maxAge (auth.config.ts) begrenst dit hoe lang een
// gedeactiveerde/gedegradeerde gebruiker nog toegang houdt.
const HERVERIFICATIE_MS = 5 * 60 * 1000;

// De laatst gemeten accountstatus per userid, met dezelfde houdbaarheid als de herverificatie.
//
// Waarom dit nodig is: `auth()` in een route handler geeft de bijgewerkte JWT (met een verse
// `verifiedAt`) niet terug aan de browser – Auth.js gooit de Set-Cookie van die interne
// sessie-aanroep weg. Het token in de cookie bleef dus op zijn oude `verifiedAt` staan, en vanaf
// vijf minuten na het inloggen deed élke BFF-call eerst `/v1/auth/me`. Met deze cache is dat
// weer hooguit één keer per vijf minuten per gebruiker (per replica), en blijft de revocatiegrens
// dezelfde. "Onbekend" (API-hapering) wordt niet onthouden: dan volgende keer opnieuw proberen.
const statusCache = new Map<string, { status: AccountStatus; tot: number }>();

async function accountStatus(userid: string): Promise<AccountStatus> {
  const nu = Date.now();
  const bekend = statusCache.get(userid);
  if (bekend && bekend.tot > nu) return bekend.status;
  const status = await getAccountStatus(userid);
  if (status.status !== "onbekend") {
    // Verlopen regels opruimen zodra de map groeit; anders blijft elke ooit ingelogde gebruiker staan.
    if (statusCache.size > 500) for (const [k, v] of statusCache) if (v.tot <= nu) statusCache.delete(k);
    statusCache.set(userid, { status, tot: nu + HERVERIFICATIE_MS });
  }
  return status;
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  // De effectieve sessieduur per login: 30 dagen als "Ingelogd blijven op dit apparaat" is gekozen
  // (token.rememberMe), anders 12 uur. Het cookie zelf leeft session.maxAge (30 d); een niet-onthouden
  // JWT verloopt na 12 u → daarna netjes uitgelogd.
  jwt: {
    maxAge: SESSIE_LANG,
    encode: (params) =>
      encode({ ...params, maxAge: params.token?.rememberMe === true ? SESSIE_LANG : SESSIE_KORT }),
  },
  callbacks: {
    ...authConfig.callbacks,
    // Node-runtime-variant van de jwt-callback: als auth.config.ts, plus periodieke
    // herverificatie tegen de API (revocatie + rolwijziging). De edge-middleware gebruikt de
    // lichte variant zonder herverificatie (lib/server.ts is node-only); elke auth()-aanroep
    // in Server Components en route handlers loopt wél langs deze versie.
    async jwt({ token, user }) {
      if (user) {
        token.userid = (user as { userid?: string }).userid;
        token.role = (user as { role?: Role }).role;
        token.email = user.email;
        token.rememberMe = (user as { rememberMe?: boolean }).rememberMe === true;
        token.verifiedAt = Date.now();
        token.loginAt = Date.now(); // inlogmoment: voor sessie-revocatie bij wachtwoordwijziging
        return token;
      }
      const verifiedAt = typeof token.verifiedAt === "number" ? token.verifiedAt : 0;
      if (!token.userid || Date.now() - verifiedAt < HERVERIFICATIE_MS) return token;
      const status = await accountStatus(String(token.userid));
      if (status.status === "ingetrokken") return null; // sessie invalideren
      if (status.status === "actief") {
        // Credential-wijziging (wachtwoord) ná het inloggen → dit token is gerevoceerd.
        if (sessieGerevoceerd(token.loginAt, status.sessionsValidFrom)) return null;
        token.role = status.role; // rolwijziging (bv. degradatie) meteen doorvoeren
        token.email = status.email;
        token.verifiedAt = Date.now();
      }
      return token; // "onbekend" (API-hapering): laten staan; maxAge begrenst het venster
    },
  },
  providers: [
    Credentials({
      credentials: {
        userid: { label: "Gebruikersnaam", type: "text" },
        password: { label: "Wachtwoord", type: "password" },
        totp: { label: "2FA-code", type: "text" },
        remember: { label: "Ingelogd blijven", type: "text" },
      },
      async authorize(credentials) {
        const userid = String(credentials?.userid ?? "");
        const password = String(credentials?.password ?? "");
        const totp = credentials?.totp ? String(credentials.totp) : undefined;
        const remember = credentials?.remember === "1"; // "Ingelogd blijven op dit apparaat"
        if (!userid) return null;
        // Bewijzen uit de httpOnly cookies (server-side): het login-ticket vervangt het wachtwoord op
        // het aparte 2FA-scherm; de trusted-device-cookie slaat bij een 2FA-account de TOTP over.
        const ticket = (await getLoginTicketCookie()) ?? null;
        const trusted_token = (await getTrustedDeviceCookie()) ?? null;
        // Wachtwoord óf een geldig login-ticket is vereist.
        if (!password && !ticket) return null;
        const res = await verifyCredentials(userid, password, totp, { ticket, trusted_token });
        if (!res.ok) {
          // Bij rate-limiting (code "rate") of foutieve gegevens retourneert null zodat Auth.js
          // de sessie weigert. De loginVerify-precheck in LoginClient toont de specifieke
          // rate-limit-melding; dit pad is de veiligheidsnet-verificatie.
          return null;
        }
        // Het ticket heeft zijn werk gedaan. Laten staan maakte het tot zijn TTL bruikbaar als
        // wachtwoordbewijs voor een tweede login op dit apparaat. Best-effort: lukt het niet, dan
        // vervalt het na vijf minuten alsnog.
        if (ticket) await clearLoginTicketCookie().catch(() => {});
        // Userid + rol (+ de remember-keuze) reizen mee naar het JWT (zie jwt-callback). Bij ok is role nooit "".
        return { id: res.userid, userid: res.userid, name: res.userid, email: res.email, role: res.role as Role, rememberMe: remember };
      },
    }),
  ],
});
