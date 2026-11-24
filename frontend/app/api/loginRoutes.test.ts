import { afterEach, describe, expect, it, vi } from "vitest";

// De twee publieke login-stappen (vóór er een sessie is). Wat hier niet mag breken: het ticket en het
// trusted-device-token blijven in httpOnly cookies en komen nooit in de body naar de browser; en de status van de
// api gaat ongewijzigd mee, zodat een storing niet als "verkeerd wachtwoord" leest.

const nep = vi.hoisted(() => ({
  verify: vi.fn(),
  cookies: {
    loginTicket: undefined as string | undefined,
    trusted: undefined as string | undefined,
    gezet: [] as [string, string][],
  },
}));
vi.mock("@/lib/server", () => ({ postAuthVerify: nep.verify }));
vi.mock("@/lib/authCookies", () => ({
  getLoginTicketCookie: async () => nep.cookies.loginTicket,
  getTrustedDeviceCookie: async () => nep.cookies.trusted,
  setLoginTicketCookie: async (v: string) => { nep.cookies.gezet.push(["ticket", v]); },
  setTrustedDeviceCookie: async (v: string) => { nep.cookies.gezet.push(["trusted", v]); },
}));

const { POST: verifieer } = await import("./login-verify/route");
const { POST: tweeStap } = await import("./login-2fa/route");

afterEach(() => {
  nep.verify.mockReset();
  nep.cookies.loginTicket = undefined;
  nep.cookies.trusted = undefined;
  nep.cookies.gezet = [];
});

const post = (body: unknown) => new Request("http://x", { method: "POST", body: JSON.stringify(body) });
const antwoord = (body: Record<string, unknown>, status = 200) => ({
  status,
  body: { ok: false, code: "", userid: "", email: "", role: "", ...body },
});

describe("POST /api/login-verify (stap A)", () => {
  it("2FA nodig: het ticket gaat in de cookie, niet in de body", async () => {
    nep.verify.mockResolvedValue(antwoord({ code: "totp_required", ticket: "geheim-ticket" }));
    const res = await verifieer(post({ userid: "ann", password: "pw" }));
    const body = await res.json();
    expect(body).toEqual({ ok: false, code: "totp_required", userid: "ann", email: "", role: "" });
    expect(JSON.stringify(body)).not.toContain("geheim-ticket");
    expect(nep.cookies.gezet).toEqual([["ticket", "geheim-ticket"]]);
  });

  it("stuurt een vertrouwd apparaat mee, en zet geen ticket zonder totp_required", async () => {
    nep.cookies.trusted = "apparaat-token";
    nep.verify.mockResolvedValue(antwoord({ ok: true, code: "", ticket: "twee-fa", trusted_token: "nieuw" }));
    const res = await verifieer(post({ userid: "ann", password: "pw" }));
    expect(nep.verify).toHaveBeenCalledWith({ userid: "ann", password: "pw", trusted_token: "apparaat-token" });
    expect(nep.cookies.gezet).toEqual([]);
    expect(JSON.stringify(await res.json())).not.toMatch(/twee-fa|nieuw/);
  });

  it("een storing bij de api blijft een storing (de status gaat mee)", async () => {
    nep.verify.mockResolvedValue(antwoord({ code: "onbereikbaar" }, 502));
    const res = await verifieer(post({ userid: "ann", password: "pw" }));
    expect(res.status).toBe(502);
    expect((await res.json()).code).toBe("onbereikbaar");
  });

  it("een onleesbare body is een lege poging, geen 500", async () => {
    nep.verify.mockResolvedValue(antwoord({ code: "invalid" }));
    const res = await verifieer(new Request("http://x", { method: "POST", body: "{kapot" }));
    expect(res.status).toBe(200);
    expect(nep.verify).toHaveBeenCalledWith({ userid: "", password: "", trusted_token: null });
  });
});

describe("POST /api/login-2fa (stap B)", () => {
  it("zonder ticket: 401 invalid, en de api wordt niet gevraagd", async () => {
    const res = await tweeStap(post({ userid: "ann", totp: "123456" }));
    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ ok: false, code: "invalid" });
    expect(nep.verify).not.toHaveBeenCalled();
  });

  it("een goede code: het 2FA-ticket vervangt het login-ticket, onthouden zet de apparaatcookie", async () => {
    nep.cookies.loginTicket = "login-ticket";
    nep.verify.mockResolvedValue(antwoord({ ok: true, ticket: "twee-fa-ticket", trusted_token: "apparaat" }));
    const res = await tweeStap(post({ userid: "ann", totp: "123456", remember: true }));
    expect(nep.verify).toHaveBeenCalledWith({ userid: "ann", ticket: "login-ticket", totp: "123456", remember: true });
    expect(nep.cookies.gezet).toEqual([["trusted", "apparaat"], ["ticket", "twee-fa-ticket"]]);
    const body = await res.json();
    expect(body).toEqual({ ok: true, code: "", userid: "ann" });
  });

  it("een afgewezen code zet niets en geeft de status van de api door", async () => {
    nep.cookies.loginTicket = "login-ticket";
    nep.verify.mockResolvedValue(antwoord({ code: "invalid", ticket: "mag-niet", trusted_token: "ook-niet" }));
    const res = await tweeStap(post({ userid: "ann", totp: "000000", remember: "ja" }));
    expect(nep.cookies.gezet).toEqual([]);
    // `remember` is alleen echt `true`; een andere waarde onthoudt niets.
    expect(nep.verify.mock.calls[0][0].remember).toBe(false);
    expect(res.status).toBe(200);
  });
});
