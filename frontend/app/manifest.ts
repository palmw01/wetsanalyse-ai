import type { MetadataRoute } from "next";

/** Het manifest van de geïnstalleerde web-app. Next serveert het op `/manifest.webmanifest` en zet zelf de
 *  `<link rel="manifest">`; `proxy.ts` laat dat pad zonder sessie door. De iconen komen uit
 *  `npm run iconen` (bron: `merk/lex-merk.svg`). `theme_color` is het token `--lint`, gelijk aan
 *  `viewport.themeColor` in `app/layout.tsx` (`app/iconen.test.ts` bewaakt het). */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Lex – Wetsanalyse",
    short_name: "Lex",
    description:
      "Gestructureerd, brongetrouw en traceerbaar duiden van Nederlandse wet- en regelgeving volgens het Juridisch Analyseschema (JAS).",
    start_url: "/workbench",
    scope: "/",
    display: "standalone",
    lang: "nl",
    background_color: "#ffffff",
    theme_color: "#154273",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
