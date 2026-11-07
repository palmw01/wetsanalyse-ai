import { describe, expect, it } from "vitest";

import { clientIpUitHeaders } from "./clientIp";

const h = (xff?: string) => new Headers(xff === undefined ? {} : { "x-forwarded-for": xff });

describe("clientIpUitHeaders", () => {
  it("neemt het laatste element: dat zette de ingress, de rest kan de browser verzinnen", () => {
    expect(clientIpUitHeaders(h("198.51.100.7, 203.0.113.9"))).toBe("203.0.113.9");
    expect(clientIpUitHeaders(h("203.0.113.9"))).toBe("203.0.113.9");
  });

  it("haalt een poort eraf, ook bij IPv6 tussen haken", () => {
    expect(clientIpUitHeaders(h("203.0.113.9:51234"))).toBe("203.0.113.9");
    expect(clientIpUitHeaders(h("[2001:db8::1]:443"))).toBe("2001:db8::1");
    expect(clientIpUitHeaders(h("2001:db8::1"))).toBe("2001:db8::1");
  });

  it("geeft null zonder header of bij iets wat geen adres is", () => {
    expect(clientIpUitHeaders(h())).toBeNull();
    expect(clientIpUitHeaders(h(""))).toBeNull();
    expect(clientIpUitHeaders(h("203.0.113.9, unknown"))).toBeNull();
    expect(clientIpUitHeaders(h("203.0.113.9, fe80::1%eth0"))).toBeNull();
  });
});
