// Route-bescherming: bewaakt élke pagina + BFF-route (behalve login/setup/auth en assets) via de
// edge-veilige authConfig. De `authorized`-callback (auth.config.ts) bepaalt toegang en de rol-gate
// op /beheer en /api/admin.
//
// Next 16 hernoemde de "middleware"-conventie naar "proxy" (zelfde edge-hook, andere bestandsnaam +
// default-export). We exporteren de NextAuth-`auth`-functie expliciet als default zodat de
// Turbopack-build 'm als proxy-functie herkent (de gedestructureerde named export werd niet gezien).

//
// Daarnaast zet deze proxy de Content-Security-Policy, met een nonce per request (`lib/csp.ts`). Dat
// moet hier: Next leest het nonce tijdens de server-render uit de `Content-Security-Policy`-header
// van de REQUEST en zet het op zijn eigen scripts. De `authorized`-callback draait eerst; geeft die
// een eigen antwoord (redirect, 401/403/400), dan komt het verzoek hier niet – dat antwoord rendert
// geen pagina en heeft geen nonce nodig.

import NextAuth from "next-auth";
import { NextResponse } from "next/server";
import { authConfig } from "./auth.config";
import { bouwCsp, maakNonce } from "./lib/csp";

const { auth } = NextAuth(authConfig);

export default auth((request) => {
  // De BFF geeft JSON en streams terug, geen HTML: daar valt niets met een nonce te beveiligen.
  if (request.nextUrl.pathname.startsWith("/api/")) return NextResponse.next();
  const nonce = maakNonce();
  const csp = bouwCsp(nonce, process.env.NODE_ENV === "development");
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
});

export const config = {
  // Sluit Auth.js' eigen routes, Next-interne paden en statische bestanden uit.
  //
  // Twee dingen in dit patroon zijn er met opzet, want de kopieerbare variant die overal rondgaat
  // laat een gat vallen. De bestandsextensies staan **verankerd op het einde** (`$`): zonder dat
  // matcht `.*\.png` élk pad waar ".png" ergens in voorkomt, dus ook `/api/gesprekken/abc.png`, en
  // dan loopt dat verzoek buiten de sessie-, rol- en Origin-controle om. En `/api/` is expliciet
  // uitgezonderd van die bestandstak: onder de BFF staan geen statische bestanden, en een
  // dynamische route-parameter mág eruitzien als een bestandsnaam. De routehandlers doen ieder hun
  // eigen controle, maar deze laag hoort juist het vangnet te zijn voor de keer dat iemand dat
  // vergeet.
  matcher: [
    "/((?!api/auth|_next/static|_next/image|favicon.ico|manifest.webmanifest|(?!api/).*\\.(?:svg|png|jpg|jpeg|gif|ico|webmanifest)$).*)",
  ],
};
