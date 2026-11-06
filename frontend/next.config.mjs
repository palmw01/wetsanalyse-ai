/** @type {import('next').NextConfig} */

// Conservatieve security-headers op alle routes. HSTS staat hier omdat TLS op de Azure-ingress eindigt
// en die de header zelf niet zet; browsers negeren hem over http, dus lokaal doet hij niets.
//
// De Content-Security-Policy staat hier NIET meer. Die zet `proxy.ts` per request, met een nonce
// (`lib/csp.ts`), zodat `script-src` geen `'unsafe-inline'` meer nodig heeft voor de inline
// hydration-scripts van Next. Stond hij hier óók, dan golden beide headers tegelijk – en liet de
// statische versie inline scripts gewoon weer toe. Statische bestanden (buiten de matcher van de
// proxy) krijgen dus geen CSP; die renderen ook niets.
const securityHeaders = [
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
