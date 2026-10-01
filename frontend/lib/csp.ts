// De Content-Security-Policy van de app, per request opgebouwd met een nonce.
//
// Waarom per request: Next injecteert inline hydration-scripts, en zonder nonce vraagt dat om
// `script-src 'unsafe-inline'` – waarmee de CSP juist datgene toelaat waartegen hij bij XSS hoort te
// beschermen. Met een nonce hoeft dat niet: de proxy maakt er per request één, zet hem in de policy én in de
// request-header, en Next voorziet zijn eigen scripts tijdens de server-render van dat nonce (zie
// `node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md`). Dat vraagt dynamisch
// renderen; dat is hier al zo, want `app/layout.tsx` roept `auth()` aan.
//
// Een pure functie zodat de policy zelf zonder browser en zonder proxy te testen is.

/** Een onvoorspelbaar nonce voor één request. `btoa` en `crypto` bestaan in zowel de Node- als de
 *  edge-runtime. */
export function maakNonce(): string {
  return btoa(crypto.randomUUID());
}

/** De policy voor één request.
 *
 *  - `script-src`: alleen scripts met dit nonce, en wat die zelf laden (`'strict-dynamic'`: de lui
 *    geladen chunks van `next/dynamic`, zoals three.js voor de 3D-graaf). In development komt er
 *    `'unsafe-eval'` bij, omdat React daar `eval` gebruikt voor zijn foutmeldingen; in productie niet.
 *  - `style-src` houdt bewust `'unsafe-inline'`: de server-render geeft `style="…"`-attributen mee
 *    (Popover, de 3D-graaf), en een nonce geldt alleen voor `<style>`-elementen, niet voor
 *    attributen. De XSS-winst zit in `script-src`; een stijl voert geen code uit.
 *  - De overige directives zijn vast. */
export function bouwCsp(nonce: string, dev: boolean): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}
