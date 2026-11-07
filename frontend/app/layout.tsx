import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { auth } from "@/auth";
import { BrowserFouten } from "@/components/BrowserFouten";
import { InstellingenVenster } from "@/components/instellingen/InstellingenVenster";
import { Providers } from "@/components/Providers";
import { sans, mono } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lex · Wetsanalyse",
  description:
    "Gestructureerd, brongetrouw en traceerbaar duiden van Nederlandse wet- en regelgeving (JAS).",
  // Favicon, apple-icon en manifest komen uit de bestandsconventies van Next (`app/favicon.ico`,
  // `app/icon.svg`, `app/apple-icon.png`, `app/manifest.ts`), gemaakt met `npm run iconen`.
  applicationName: "Lex – Wetsanalyse",
  appleWebApp: { capable: true, title: "Lex", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  themeColor: "#154273",
  // Laat het schermtoetsenbord de layout-viewport verkleinen in plaats van eroverheen te schuiven.
  // De werkplek is een niet-scrollende schil van 100dvh met de invoerbalk onderaan gepind; zonder
  // dit kan het toetsenbord die balk afdekken. Chrome/Android honoreert dit; iOS Safari (nog) niet —
  // dáár is het niet met een regel CSS op te lossen en moet iemand met een toestel kijken.
  interactiveWidget: "resizes-content",
};

/** De layout is bewust kaal: er is geen globale chrome meer. Elk scherm draagt zijn eigen kader —
 *  ingelogd is dat de app-schil (`/workbench`), uitgelogd de gecentreerde kaart van
 *  `AuthFrame`. De oude logobalk + navigatiebalk + footer zijn weg: die navigatie wees naar plekken
 *  die inmiddels ín de schil zitten, en de kop verborg zichzelf toch al op de app-paden.
 *
 *  `modal` is het parallelle slot dat de intercepting routes vullen (app/@modal/**); dat staat
 *  buiten `{children}`, want een dialog hoort over de hele app heen te liggen. */
export default async function RootLayout({
  children,
  modal,
}: {
  children: React.ReactNode;
  modal: React.ReactNode;
}) {
  const session = await auth();
  return (
    <html lang="nl" className={`${sans.variable} ${mono.variable}`}>
      {/* `min-h-[100dvh]` en niet alleen `min-h-screen`: `100vh` is op mobiel de viewport ZONDER
          adresbalk, dus zolang die balk in beeld staat is de body hoger dan wat je ziet en kan het
          document zelf scrollen. Dan schuiven de testomgeving-strook en de topbar mee weg terwijl de
          app-schil eronder juist niet-scrollend bedoeld is. `100dvh` volgt de zichtbare hoogte, dus
          er blijft niets over om te scrollen. `min-h-screen` blijft ervóór staan als terugval voor
          browsers zonder dvh. */}
      <body className="min-h-screen min-h-[100dvh]">
        <Providers session={session}>
          <BrowserFouten />
          {children}
          {modal}
          {/* Het instellingenvenster hangt aan `?instellingen=` en ligt over elke pagina (useSearchParams vraagt een
              Suspense-grens). */}
          <Suspense fallback={null}>
            <InstellingenVenster />
          </Suspense>
        </Providers>
      </body>
    </html>
  );
}
