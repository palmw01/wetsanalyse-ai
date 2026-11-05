import assert from "node:assert/strict";
import { test } from "node:test";
import { AcceptatieClient, controleerPad, controleerUrl, leesFrames } from "./client.js";

test("een productie-URL wordt geweigerd", () => {
  assert.throws(() => controleerUrl("https://wetsanalyse-prd-frontend.example.org"));
  assert.throws(() => controleerUrl("https://app.prd.example.org"));
  assert.equal(controleerUrl("https://wetsanalyse-frontend.example.org/iets"), "https://wetsanalyse-frontend.example.org");
});

test("paden: alleen de BFF, en niet wat een accounttoken niet mag", () => {
  controleerPad("/api/werkgebieden");
  for (const pad of ["/v1/admin/users", "/api/../v1", "/api/auth/csrf", "/api/admin/api-tokens", "/api/account/2fa/begin"]) {
    assert.throws(() => controleerPad(pad), Error, pad);
  }
});

test("frames: \\r\\n, heartbeats en een half frame", () => {
  const { events, rest } = leesFrames('data: {"type":"a","seq":1}\r\n\r\n: ping\r\n\r\ndata: {"type":"b"}\r\n\r\ndata: {"ty');
  assert.deepEqual(events, [{ type: "a", seq: 1 }, { type: "b" }]);
  assert.equal(rest, 'data: {"ty');
});

const antwoord = (body: string, init: ResponseInit = {}) => new Response(body, init);

test("logt in, herhaalt na een 401, en verwart een weigering niet met succes", async () => {
  let sessies = 0;
  const nep = (async (url: string | URL, init?: RequestInit) => {
    const pad = new URL(url).pathname;
    if (pad === "/api/auth/csrf") {
      return antwoord('{"csrfToken":"c"}', { headers: { "Set-Cookie": "authjs.csrf-token=x; Path=/" } });
    }
    if (pad === "/api/auth/callback/api-token") {
      sessies += 1;
      assert.match(String(init?.body), /token=wa_pat_x/);
      assert.match((init?.headers as Record<string, string>).Cookie, /authjs.csrf-token=x/);
      return antwoord("", { status: 302, headers: { "Set-Cookie": `authjs.session-token=s${sessies}; Path=/` } });
    }
    const cookie = (init?.headers as Record<string, string>).Cookie;
    return cookie.includes("session-token=s1") ? antwoord("", { status: 401 }) : antwoord('{"ok":true}');
  }) as typeof fetch;
  const a = await new AcceptatieClient("http://x", "wa_pat_x", nep).bff("GET", "/api/account/me");
  assert.equal(a.status, 200);
  assert.deepEqual(a.data, { ok: true });
  assert.equal(sessies, 2);
  assert.match(a.trace_id, /^[0-9a-f]{32}$/);

  const geweigerd = (async (url: string | URL) =>
    new URL(url).pathname === "/api/auth/csrf"
      ? antwoord('{"csrfToken":"c"}')
      : antwoord("", { status: 302 })) as typeof fetch;
  await assert.rejects(new AcceptatieClient("http://x", "wa_pat_x", geweigerd).bff("GET", "/api/account/me"), /geweigerd/);
});

test("runEvents voegt tekst samen, laat status en reason weg en onthoudt seq", async () => {
  const stroom = 'data: {"type":"status","seq":1}\r\n\r\ndata: {"type":"token","content":"Hal","seq":2}\r\n\r\n' +
    'data: {"type":"token","content":"lo","seq":3}\r\n\r\ndata: {"type":"vraagkaart","seq":4}\r\n\r\n';
  const nep = (async (url: string | URL) => {
    const pad = new URL(url).pathname;
    if (pad === "/api/auth/csrf") return antwoord('{"csrfToken":"c"}');
    if (pad.endsWith("api-token")) return antwoord("", { status: 302, headers: { "Set-Cookie": "authjs.session-token=s" } });
    return antwoord(stroom);
  }) as typeof fetch;
  const uit = await new AcceptatieClient("http://x", "t", nep).runEvents("r1", 0, 5);
  assert.equal(uit.klaar, true);
  assert.equal(uit.tekst, "Hallo");
  assert.equal(uit.vanaf, 4);
  assert.deepEqual(uit.events, [{ type: "vraagkaart", seq: 4 }]);
});
