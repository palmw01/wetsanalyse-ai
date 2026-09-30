/** De sessie- en disclaimercookies voor de browserscripts, voor dev én productie tegelijk.
 *
 * In productie (`next build` + `next start`) heten beide cookies anders: `__Secure-authjs.session-token`
 * en `__Secure-wa-disclaimer` (zie `auth.config.ts` en `lib/authCookies.ts`), en het JWT is met díe
 * naam als salt versleuteld. Zetten de scripts alleen de dev-namen, dan komt een productiebuild niet
 * voorbij het inlogscherm, en redirect de proxy naar `NEXTAUTH_URL` uit `.env.local`. De test faalt
 * dan op een time-out die niets met de wijziging te maken heeft. Daarom zetten we beide varianten;
 * de server leest alleen de zijne. Chromium accepteert `Secure`-cookies op `http://localhost`.
 */
import { encode } from "../node_modules/next-auth/jwt.js";

const GEHEIM = process.env.AUTH_SECRET || "annotatie-browser-test-only-secret";

/** Cookies voor een ingelogde gebruiker die de disclaimer al zag. `gebruiker` gaat als JWT-inhoud mee. */
export async function sessieCookies(base, gebruiker = {}) {
  const inhoud = {
    userid: "browser-test", role: "analist", email: "test@example.test",
    verifiedAt: Date.now(), loginAt: Date.now(), ...gebruiker,
  };
  const host = new URL(base).hostname;
  const dev = await encode({ secret: GEHEIM, salt: "authjs.session-token", token: inhoud });
  const prod = await encode({ secret: GEHEIM, salt: "__Secure-authjs.session-token", token: inhoud });
  return [
    { name: "authjs.session-token", value: dev, url: base },
    { name: "wa-disclaimer", value: "1", url: base },
    { name: "__Secure-authjs.session-token", value: prod, domain: host, path: "/", secure: true },
    { name: "__Secure-wa-disclaimer", value: "1", domain: host, path: "/", secure: true },
  ];
}
