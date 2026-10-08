import { describe, expect, it } from "vitest";

import { bouwCsp, maakNonce } from "./csp";

const scriptSrc = (csp: string) => csp.split("; ").find((d) => d.startsWith("script-src")) ?? "";

describe("bouwCsp", () => {
  it("staat scripts alleen toe met het nonce van dit request", () => {
    const csp = bouwCsp("abc123", false);
    expect(scriptSrc(csp)).toBe("script-src 'self' 'nonce-abc123' 'strict-dynamic'");
  });

  it("laat geen inline scripts toe – dat was het gat dat het nonce dicht", () => {
    expect(scriptSrc(bouwCsp("x", false))).not.toContain("'unsafe-inline'");
    expect(scriptSrc(bouwCsp("x", true))).not.toContain("'unsafe-inline'");
  });

  it("staat eval alleen in development toe", () => {
    expect(scriptSrc(bouwCsp("x", true))).toContain("'unsafe-eval'");
    expect(scriptSrc(bouwCsp("x", false))).not.toContain("'unsafe-eval'");
  });

  it("staat een worker van de eigen origin toe – 'strict-dynamic' maakt 'self' in script-src ongeldig", () => {
    // De layout van de graaf rekent in een Web Worker; zonder `worker-src` valt de browser terug op
    // `script-src` en weigert hij hem.
    expect(bouwCsp("x", false)).toContain("worker-src 'self'");
  });

  it("houdt de overige directives van de statische policy", () => {
    const csp = bouwCsp("x", false);
    for (const d of ["default-src 'self'", "img-src 'self' data:", "connect-src 'self'", "frame-ancestors 'none'", "base-uri 'self'", "form-action 'self'"]) {
      expect(csp).toContain(d);
    }
  });
});

describe("maakNonce", () => {
  it("geeft per aanroep een ander nonce", () => {
    expect(maakNonce()).not.toBe(maakNonce());
  });
});
